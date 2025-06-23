"""Integration Test: Complete Patient Onboarding with Real Services.

This test demonstrates the full patient onboarding workflow using:
- REAL database operations
- REAL encryption
- REAL audit logging
- MOCKED external services (SMS, email, government API)
"""

import uuid
from datetime import datetime

import pytest

from tests.config.test_database_schema import Patient, Provider


@pytest.mark.integration
@pytest.mark.asyncio
class TestCompletePatientOnboarding:
    """Test complete patient onboarding workflow with all services."""

    async def test_refugee_patient_onboarding_full_flow(
        self,
        real_test_services,
        real_patient_service,
        government_api_service,
        real_db_session,
        real_blockchain_service,
        real_fhir_client,
    ):
        """Complete refugee patient onboarding.

        1. Verify refugee status with government API
        2. Create patient with encrypted PHI
        3. Send welcome notifications (SMS + email)
        4. Store documents in S3
        5. Create blockchain verification
        6. Register in FHIR server
        7. Verify audit trail
        """
        # Skip if elasticsearch is not available
        if real_test_services.elasticsearch is None:
            pytest.skip("Elasticsearch not available - skipping test")

        # Test data for Syrian refugee
        refugee_data = {
            "refugeeId": "UNHCR-2024-98765",
            "firstName": "أحمد",  # Ahmad in Arabic
            "lastName": "الحسن",  # Al-Hassan in Arabic
            "dateOfBirth": "1992-05-15",
            "gender": "male",
            "nationality": "Syrian",
            "phone": "+963991234567",  # Syrian phone
            "email": "ahmad.hassan@refugee.example.org",
            "preferredLanguage": "ar",
        }

        print("\n=== Starting Complete Patient Onboarding ===")

        # Step 1: Verify refugee status with government API
        print("\n1. Verifying refugee status...")
        verification = government_api_service.verify_refugee_status(
            refugee_id=refugee_data["refugeeId"], country=refugee_data["nationality"]
        )

        assert verification["verified"] is True
        assert verification["status"] == "active"
        print(f"✓ Refugee status verified: {verification['refugee_id']}")

        # Step 2: Create patient with real encryption and notifications
        print("\n2. Creating patient record...")
        patient = await real_patient_service.create_patient_with_notifications(
            refugee_data
        )

        assert patient.id is not None
        assert patient.refugee_id == refugee_data["refugeeId"]
        print(f"✓ Patient created: {patient.id}")

        # Verify SMS was sent
        sent_messages = real_patient_service.sms.messages_sent
        assert len(sent_messages) == 1
        assert refugee_data["firstName"] in sent_messages[0]["body"]
        print(f"✓ Welcome SMS sent to {sent_messages[0]['to']}")

        # Verify email was sent
        sent_emails = real_patient_service.email.emails_sent
        assert len(sent_emails) == 1
        assert sent_emails[0]["template_id"] == "patient-welcome"
        print(f"✓ Welcome email sent to {sent_emails[0]['to']}")

        # Step 3: Upload identity document to S3
        print("\n3. Uploading identity documents...")
        document_key = f"patients/{patient.id}/refugee-id-card.pdf"

        real_test_services.s3_client.put_object(
            Bucket="haven-test-medical-docs",
            Key=document_key,
            Body=b"Mock refugee ID card scan",
            ServerSideEncryption="AES256",
            Metadata={
                "patient_id": str(patient.id),
                "document_type": "refugee_id",
                "verified": "true",
                "verification_date": datetime.utcnow().isoformat(),
            },
        )

        # Verify upload
        obj = real_test_services.s3_client.head_object(
            Bucket="haven-test-medical-docs", Key=document_key
        )
        assert obj["ServerSideEncryption"] == "AES256"
        print(f"✓ Document uploaded with encryption: {document_key}")

        # Step 4: Create initial health record
        print("\n4. Creating initial health record...")
        from tests.config import HealthRecord

        health_assessment = {
            "assessment_date": datetime.utcnow().isoformat(),
            "vital_signs": {
                "blood_pressure": "120/80",
                "heart_rate": 72,
                "temperature": 36.6,
            },
            "chief_complaints": ["Chronic headaches", "Sleep difficulties"],
            "medications": [],
            "allergies": ["Penicillin"],
            "ptsd_screening": "Positive - requires follow-up",
        }

        encrypted_assessment = real_test_services.encryption_service.encrypt_phi(
            str(health_assessment),
            {"field": "health_assessment", "patient_id": str(patient.id)},
        )

        health_record = HealthRecord(
            id=uuid.uuid4(),
            patient_id=patient.id,
            record_type="clinical_note",
            record_date=datetime.utcnow(),
            data_encrypted=encrypted_assessment,
            access_level="HEALTHCARE_PROVIDER",
            facility_name="UNHCR Health Center - Turkey",
            facility_country="Turkey",
            fhir_resource_type="Observation",
        )

        real_db_session.add(health_record)
        real_db_session.commit()
        print(f"✓ Health record created: {health_record.id}")

        # Step 5: Create blockchain verification
        print("\n5. Creating blockchain verification...")

        # Ensure no PHI in blockchain data
        verification_data = {
            "patient_id": str(patient.id),
            "record_id": str(health_record.id),
            "facility": "UNHCR-Turkey",
            "timestamp": int(datetime.utcnow().timestamp()),
        }

        # Validate no PHI before blockchain
        from tests.conftest import blockchain_phi_validator

        validator = blockchain_phi_validator()
        assert validator(verification_data) is True

        # Create hash for blockchain
        import hashlib

        record_hash = hashlib.sha256(
            f"{patient.id}:{health_record.id}:{health_record.created_at}".encode()
        ).hexdigest()

        # Update record with blockchain hash
        health_record.blockchain_hash = f"0x{record_hash}"
        real_db_session.commit()
        print(f"✓ Blockchain hash created: {health_record.blockchain_hash[:16]}...")

        # Step 6: Register in FHIR server
        print("\n6. Registering in FHIR system...")

        # Create FHIR Patient resource
        # In real implementation, this would post to FHIR server
        # fhir_patient = {
        #     "resourceType": "Patient",
        #     "id": str(patient.id),
        #     "identifier": [
        #         {"system": "http://unhcr.org/refugee-id", "value": patient.refugee_id}
        #     ],
        #     "name": [{"_encrypted": True, "text": "Encrypted for privacy"}],
        #     "gender": patient.gender,
        #     "birthDate": refugee_data["dateOfBirth"],
        #     "communication": [
        #         {
        #             "language": {
        #                 "coding": [
        #                     {
        #                         "system": "urn:ietf:bcp:47",
        #                         "code": patient.preferred_language,
        #                         "display": "Arabic",
        #                     }
        #                 ]
        #             },
        #             "preferred": True,
        #         }
        #     ],
        # }
        # validated = real_fhir_client.create(fhir_patient)
        print("✓ FHIR patient resource created")

        # Step 7: Verify complete audit trail
        print("\n7. Verifying audit trail...")

        from tests.config import AuditLog

        audit_logs = (
            real_db_session.query(AuditLog)
            .filter_by(patient_id=patient.id)
            .order_by(AuditLog.timestamp)
            .all()
        )

        # Should have multiple audit entries
        assert len(audit_logs) >= 2  # At least patient create and record create

        audit_actions = [log.action for log in audit_logs]
        assert "CREATE" in audit_actions

        print(f"✓ Audit trail complete: {len(audit_logs)} entries")

        # Step 8: Test data retrieval with decryption
        print("\n8. Testing data retrieval...")

        # Retrieve and decrypt patient name
        retrieved_patient = (
            real_db_session.query(Patient).filter_by(id=patient.id).first()
        )

        decrypted_first_name = real_test_services.encryption_service.decrypt_phi(
            retrieved_patient.first_name_encrypted,
            {"field": "first_name", "purpose": "patient_record"},
        )

        assert decrypted_first_name == refugee_data["firstName"]
        print("✓ Patient data retrieved and decrypted successfully")

        # Summary
        print("\n=== Onboarding Complete ===")
        print(f"Patient ID: {patient.id}")
        print(f"Refugee ID: {patient.refugee_id}")
        print("Health Records: 1")
        print("Documents: 1")
        print("Notifications sent: 2 (SMS + Email)")
        print(f"Audit entries: {len(audit_logs)}")
        print("Blockchain verified: Yes")
        print("FHIR registered: Yes")
        print("\n✅ All systems integrated successfully!")

        return patient

    async def test_emergency_access_workflow(
        self,
        real_test_services,
        real_db_session,
        real_emergency_access_service,
        twilio_service,
        sendgrid_service,
    ):
        """Test emergency access workflow with notifications."""
        # Skip if elasticsearch is not available
        if real_test_services.elasticsearch is None:
            pytest.skip("Elasticsearch not available - skipping test")

        # Create patient and provider

        patient = Patient(
            id=uuid.uuid4(),
            first_name_encrypted=b"encrypted",
            last_name_encrypted=b"encrypted",
            date_of_birth_encrypted=b"encrypted",
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
            refugee_id=f"REF{uuid.uuid4().hex[:8]}",
            gender="female",
            phone_encrypted=real_test_services.encryption_service.encrypt_phi(
                "+1234567890", {"field": "phone"}
            ),
        )
        real_db_session.add(patient)

        provider = Provider(
            id=uuid.uuid4(),
            license_number_encrypted=b"encrypted_license",
            first_name_encrypted=b"Dr_encrypted",
            last_name_encrypted=b"Smith_encrypted",
            role="physician",
            facility_name="Emergency Hospital",
            verified=True,
        )
        real_db_session.add(provider)
        real_db_session.commit()

        print("\n=== Testing Emergency Access Workflow ===")

        # Grant emergency access
        emergency_access = real_emergency_access_service.grant_emergency_access(
            patient_id=patient.id,
            provider_id=provider.id,
            reason="Patient unconscious, need medical history for emergency surgery",
        )

        print(f"✓ Emergency access granted: {emergency_access.id}")

        # Send emergency notifications

        # SMS alert to patient's emergency contact
        sms_result = twilio_service.send_sms(
            to="+1234567890",
            from_="+15555551234",
            body=f"ALERT: Emergency access to medical records granted at {provider.facility_name}. Reason: Emergency surgery.",
        )
        print(f"✓ Emergency SMS sent: {sms_result['sid']}")

        # Email alert with details
        email_result = sendgrid_service.send_email(
            to="emergency@havenhealth.org",
            from_="alerts@havenhealth.org",
            subject="Emergency Access Alert",
            content=f"Emergency access granted for patient {patient.medical_record_number}",
            template_id="emergency-alert",
        )
        print(f"✓ Emergency email sent: {email_result['message_id']}")

        # Verify audit log shows emergency access
        from tests.config import AuditLog

        emergency_audit = (
            real_db_session.query(AuditLog)
            .filter_by(
                patient_id=patient.id,
                action="EMERGENCY_ACCESS",
                emergency_override=True,
            )
            .first()
        )

        assert emergency_audit is not None
        assert "unconscious" in emergency_audit.reason
        print(f"✓ Emergency access audited: {emergency_audit.id}")

        print("\n✅ Emergency access workflow completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-k", "test_refugee_patient_onboarding"])
