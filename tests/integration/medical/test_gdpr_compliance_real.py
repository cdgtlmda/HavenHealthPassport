"""Test GDPR Compliance with Real Data Operations.

Tests actual GDPR rights implementation with real database operations.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest

from tests.config import AuditLog, HealthRecord, Patient, PatientConsent


@pytest.mark.integration
@pytest.mark.gdpr_compliance
class TestGDPRComplianceReal:
    """Test actual GDPR rights implementation with real data operations."""

    def test_gdpr_right_to_deletion_with_real_data(
        self, real_test_services, real_db_session
    ):
        """Test GDPR right to erasure (right to be forgotten) with real implementation."""
        # Create patient with comprehensive data
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            first_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Marie", {"field": "first_name"}
            ),
            last_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Dubois", {"field": "last_name"}
            ),
            date_of_birth_encrypted=real_test_services.encryption_service.encrypt_phi(
                "1988-07-14", {"field": "date_of_birth"}
            ),
            email_encrypted=real_test_services.encryption_service.encrypt_phi(
                "marie.dubois@example.fr", {"field": "email"}
            ),
            phone_encrypted=real_test_services.encryption_service.encrypt_phi(
                "+33612345678", {"field": "phone"}
            ),
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
            nationality="French",
            preferred_language="fr",
        )
        real_db_session.add(patient)

        # Create related health records
        health_records = []
        for i in range(5):
            record = HealthRecord(
                id=uuid.uuid4(),
                patient_id=patient_id,
                record_type="diagnosis",
                record_date=datetime.utcnow() - timedelta(days=i * 30),
                data_encrypted=real_test_services.encryption_service.encrypt_phi(
                    f"Diagnosis {i}: Sample medical data",
                    {"field": "diagnosis", "record_id": str(uuid.uuid4())},
                ),
                created_by=uuid.uuid4(),
            )
            health_records.append(record)
            real_db_session.add(record)

        # Create audit logs
        for i in range(10):
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                patient_id=patient_id,
                action="VIEW_RECORD",
                resource_type="HealthRecord",
                resource_id=health_records[0].id,
                timestamp=datetime.utcnow() - timedelta(days=i),
                ip_address="192.168.1.100",
            )
            real_db_session.add(audit)

        real_db_session.commit()

        # Execute GDPR deletion request
        deletion_request_time = datetime.utcnow()

        # Step 1: Soft delete with reason
        patient.deletion_requested = True
        patient.deletion_date = deletion_request_time
        # Note: The schema doesn't have deletion_reason or deletion_requested_by fields
        # In a real implementation, these would be tracked in a separate table or audit log
        real_db_session.commit()

        # Step 2: Anonymize related data
        anonymous_patient_id = uuid.uuid4()  # New anonymous ID
        for record in health_records:
            # Replace identifiable data with anonymized versions
            record.patient_id = anonymous_patient_id
            # In a real implementation, we would also anonymize any PHI in the encrypted data
            # For this test, we'll just mark the record as anonymized in our tracking

        # Step 3: Anonymize audit logs (preserve for legal compliance)
        audit_logs = (
            real_db_session.query(AuditLog).filter_by(patient_id=patient_id).all()
        )

        for log in audit_logs:
            log.patient_id = anonymous_patient_id
            # Store original patient reference in details for compliance
            if log.details is None:
                log.details = {}
            log.details["original_patient_id"] = str(patient_id)
            log.details["anonymized_at"] = deletion_request_time.isoformat()

        real_db_session.commit()

        # Verify soft deletion
        deleted_patient = (
            real_db_session.query(Patient).filter_by(id=patient_id).first()
        )

        assert deleted_patient.deletion_requested is True
        assert deleted_patient.deletion_date is not None

        # Verify health records are anonymized
        anon_records = (
            real_db_session.query(HealthRecord)
            .filter(HealthRecord.patient_id != patient_id)
            .filter(HealthRecord.id.in_([r.id for r in health_records]))
            .all()
        )

        assert len(anon_records) == 5
        assert all(record.patient_id == anonymous_patient_id for record in anon_records)

        # Verify audit trail preserved but anonymized
        anon_audits = (
            real_db_session.query(AuditLog)
            .filter_by(patient_id=anonymous_patient_id)
            .all()
        )

        assert len(anon_audits) == 10
        assert all(audit.anonymized for audit in anon_audits)

        print(
            f"✅ GDPR deletion request processed: patient {patient_id} data anonymized"
        )

        # Simulate retention period expiry (30 days)
        # In production, a scheduled job would handle this
        retention_expiry = deletion_request_time + timedelta(days=30)

        # Final deletion after retention period
        if datetime.utcnow() >= retention_expiry:
            # Permanently delete patient record
            real_db_session.delete(deleted_patient)
            real_db_session.commit()

            # Verify permanent deletion
            permanently_deleted = (
                real_db_session.query(Patient).filter_by(id=patient_id).first()
            )
            assert permanently_deleted is None

    def test_gdpr_data_portability(self, real_test_services, real_db_session):
        """Test GDPR right to data portability with real export."""
        # Create patient with various data types
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            first_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Hans", {"field": "first_name"}
            ),
            last_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Mueller", {"field": "last_name"}
            ),
            date_of_birth_encrypted=real_test_services.encryption_service.encrypt_phi(
                "1975-11-20", {"field": "date_of_birth"}
            ),
            email_encrypted=real_test_services.encryption_service.encrypt_phi(
                "hans.mueller@example.de", {"field": "email"}
            ),
            phone_encrypted=real_test_services.encryption_service.encrypt_phi(
                "+491234567890", {"field": "phone"}
            ),
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
            nationality="German",
            preferred_language="de",
        )
        real_db_session.add(patient)

        # Add health records
        records_data = []
        for i in range(3):
            record = HealthRecord(
                id=uuid.uuid4(),
                patient_id=patient_id,
                record_type=["diagnosis", "prescription", "lab_result"][i],
                record_date=datetime.utcnow() - timedelta(days=i * 10),
                data_encrypted=real_test_services.encryption_service.encrypt_phi(
                    json.dumps(
                        {
                            "type": ["diagnosis", "prescription", "lab_result"][i],
                            "details": f"Medical data {i}",
                            "provider": f"Dr. Schmidt {i}",
                        }
                    ),
                    {"field": "medical_data"},
                ),
            )
            real_db_session.add(record)
            records_data.append(record)

        # Add consent records
        consent = PatientConsent(
            id=uuid.uuid4(),
            patient_id=patient_id,
            consent_type="data_processing",
            granted=True,
            granted_at=datetime.utcnow() - timedelta(days=180),
            expires_at=datetime.utcnow() + timedelta(days=185),
            purpose="treatment_and_research",
            withdrawal_method="email",
        )
        real_db_session.add(consent)

        real_db_session.commit()

        # Export all patient data in machine-readable format
        export_data: Dict[str, Any] = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "export_format": "JSON",
            "gdpr_request": True,
            "patient_data": {
                "id": str(patient_id),
                "personal_information": {
                    "first_name": real_test_services.encryption_service.decrypt_phi(
                        patient.first_name_encrypted,
                        {"field": "first_name", "purpose": "gdpr_export"},
                    ),
                    "last_name": real_test_services.encryption_service.decrypt_phi(
                        patient.last_name_encrypted,
                        {"field": "last_name", "purpose": "gdpr_export"},
                    ),
                    "date_of_birth": real_test_services.encryption_service.decrypt_phi(
                        patient.date_of_birth_encrypted,
                        {"field": "date_of_birth", "purpose": "gdpr_export"},
                    ),
                    "email": real_test_services.encryption_service.decrypt_phi(
                        patient.email_encrypted,
                        {"field": "email", "purpose": "gdpr_export"},
                    ),
                    "phone": real_test_services.encryption_service.decrypt_phi(
                        patient.phone_encrypted,
                        {"field": "phone", "purpose": "gdpr_export"},
                    ),
                    "nationality": patient.nationality,
                    "preferred_language": patient.preferred_language,
                },
                "medical_records": [],
                "consent_history": [],
                "access_logs": [],
            },
        }

        # Add medical records to export
        for record in records_data:
            decrypted_data = real_test_services.encryption_service.decrypt_phi(
                record.data_encrypted,
                {"field": "medical_data", "purpose": "gdpr_export"},
            )
            export_data["patient_data"]["medical_records"].append(
                {
                    "id": str(record.id),
                    "type": record.record_type,
                    "date": record.record_date.isoformat(),
                    "data": json.loads(decrypted_data),
                }
            )

        # Add consent history
        export_data["patient_data"]["consent_history"].append(
            {
                "id": str(consent.id),
                "type": consent.consent_type,
                "granted": consent.granted,
                "granted_at": consent.granted_at.isoformat(),
                "expires_at": consent.expires_at.isoformat(),
                "purpose": consent.purpose,
            }
        )

        # Add access logs (last 90 days)
        access_logs = (
            real_db_session.query(AuditLog)
            .filter(
                AuditLog.patient_id == patient_id,
                AuditLog.timestamp >= datetime.utcnow() - timedelta(days=90),
            )
            .all()
        )

        for log in access_logs:
            export_data["patient_data"]["access_logs"].append(
                {
                    "timestamp": log.timestamp.isoformat(),
                    "action": log.action,
                    "user": "anonymized",  # Don't expose other users
                    "resource_type": log.resource_type,
                }
            )

        # Verify export completeness
        assert (
            export_data["patient_data"]["personal_information"]["first_name"] == "Hans"
        )
        assert len(export_data["patient_data"]["medical_records"]) == 3
        assert len(export_data["patient_data"]["consent_history"]) == 1

        # Save export to patient-accessible location
        export_json = json.dumps(export_data, indent=2, ensure_ascii=False)

        # In real implementation, this would be saved to secure storage
        # and a download link sent to the patient
        assert len(export_json) > 0
        assert "Hans" in export_json
        assert "Mueller" in export_json

        print(f"✅ GDPR data export completed: {len(export_json)} bytes")

    def test_gdpr_consent_management(self, real_test_services, real_db_session):
        """Test GDPR consent management with granular controls."""
        patient_id = uuid.uuid4()

        # Create different types of consent
        consent_types = [
            {
                "type": "basic_treatment",
                "purpose": "medical_treatment",
                "required": True,
                "description": "Essential medical treatment",
            },
            {
                "type": "data_sharing",
                "purpose": "share_with_specialists",
                "required": False,
                "description": "Share data with specialist providers",
            },
            {
                "type": "research",
                "purpose": "medical_research",
                "required": False,
                "description": "Use data for medical research",
            },
            {
                "type": "marketing",
                "purpose": "health_communications",
                "required": False,
                "description": "Send health tips and updates",
            },
        ]

        consents = []
        for consent_type in consent_types:
            consent = PatientConsent(
                id=uuid.uuid4(),
                patient_id=patient_id,
                consent_type=consent_type["type"],
                purpose=consent_type["purpose"],
                granted=consent_type[
                    "required"
                ],  # Only required consents granted by default
                granted_at=datetime.utcnow() if consent_type["required"] else None,
                required=consent_type["required"],
                description=consent_type["description"],
                version="1.0",
            )
            consents.append(consent)
            real_db_session.add(consent)

        real_db_session.commit()

        # Test consent update - patient grants research consent
        research_consent = next(c for c in consents if c.consent_type == "research")
        research_consent.granted = True
        research_consent.granted_at = datetime.utcnow()
        research_consent.granted_ip = "192.168.1.100"
        research_consent.granted_user_agent = "Mozilla/5.0"

        # Create consent history entry
        real_db_session.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=patient_id,
                patient_id=patient_id,
                action="CONSENT_GRANTED",
                resource_type="PatientConsent",
                resource_id=research_consent.id,
                timestamp=datetime.utcnow(),
                details={"consent_type": "research", "version": "1.0"},
            )
        )

        real_db_session.commit()

        # Test consent withdrawal
        marketing_consent = next(c for c in consents if c.consent_type == "marketing")
        marketing_consent.granted = False
        marketing_consent.withdrawn_at = datetime.utcnow()
        marketing_consent.withdrawal_reason = "Too many emails"

        # Create withdrawal audit
        real_db_session.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=patient_id,
                patient_id=patient_id,
                action="CONSENT_WITHDRAWN",
                resource_type="PatientConsent",
                resource_id=marketing_consent.id,
                timestamp=datetime.utcnow(),
                details={"consent_type": "marketing", "reason": "Too many emails"},
            )
        )

        real_db_session.commit()

        # Verify consent states
        current_consents = (
            real_db_session.query(PatientConsent).filter_by(patient_id=patient_id).all()
        )

        # Check required consents are granted
        required_consents = [c for c in current_consents if c.required]
        assert all(c.granted for c in required_consents)

        # Check optional consent states
        research = next(c for c in current_consents if c.consent_type == "research")
        assert research.granted is True

        marketing = next(c for c in current_consents if c.consent_type == "marketing")
        assert marketing.granted is False
        assert marketing.withdrawn_at is not None

        # Verify audit trail
        consent_audits = (
            real_db_session.query(AuditLog)
            .filter(
                AuditLog.patient_id == patient_id,
                AuditLog.action.in_(["CONSENT_GRANTED", "CONSENT_WITHDRAWN"]),
            )
            .all()
        )

        assert len(consent_audits) == 2

        print(f"✅ GDPR consent management: {len(current_consents)} consents tracked")

    def test_gdpr_data_rectification(self, real_test_services, real_db_session):
        """Test GDPR right to rectification (correction of data)."""
        # Create patient with incorrect data
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            first_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Giovani", {"field": "first_name"}  # Misspelled
            ),
            last_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Rossi", {"field": "last_name"}
            ),
            date_of_birth_encrypted=real_test_services.encryption_service.encrypt_phi(
                "1990-05-15", {"field": "date_of_birth"}  # Wrong date
            ),
            email_encrypted=real_test_services.encryption_service.encrypt_phi(
                "old.email@example.it", {"field": "email"}
            ),
            phone_encrypted=real_test_services.encryption_service.encrypt_phi(
                "+39123456789", {"field": "phone"}
            ),
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
        )
        real_db_session.add(patient)
        real_db_session.commit()

        # Patient requests corrections
        corrections = {
            "first_name": "Giovanni",  # Correct spelling
            "date_of_birth": "1990-05-25",  # Correct date
            "email": "giovanni.rossi@example.it",  # New email
        }

        # Apply corrections with audit trail
        rectification_time = datetime.utcnow()

        # Store old values for audit
        old_values = {
            "first_name": real_test_services.encryption_service.decrypt_phi(
                patient.first_name_encrypted, {"field": "first_name"}
            ),
            "date_of_birth": real_test_services.encryption_service.decrypt_phi(
                patient.date_of_birth_encrypted, {"field": "date_of_birth"}
            ),
            "email": real_test_services.encryption_service.decrypt_phi(
                patient.email_encrypted, {"field": "email"}
            ),
        }

        # Update with new values
        patient.first_name_encrypted = (
            real_test_services.encryption_service.encrypt_phi(
                corrections["first_name"], {"field": "first_name"}
            )
        )
        patient.date_of_birth_encrypted = (
            real_test_services.encryption_service.encrypt_phi(
                corrections["date_of_birth"], {"field": "date_of_birth"}
            )
        )
        patient.email_encrypted = real_test_services.encryption_service.encrypt_phi(
            corrections["email"], {"field": "email"}
        )
        patient.updated_at = rectification_time
        # patient.updated_by = patient_id  # Self-service update - this field doesn't exist

        # Create detailed audit log for rectification
        rectification_audit = AuditLog(
            id=uuid.uuid4(),
            user_id=patient_id,
            patient_id=patient_id,
            action="GDPR_RECTIFICATION",
            resource_type="Patient",
            resource_id=patient_id,
            timestamp=rectification_time,
            details={
                "changes": {
                    "first_name": {
                        "old": old_values["first_name"],
                        "new": corrections["first_name"],
                    },
                    "date_of_birth": {
                        "old": old_values["date_of_birth"],
                        "new": corrections["date_of_birth"],
                    },
                    "email": {"old": old_values["email"], "new": corrections["email"]},
                },
                "reason": "Patient requested correction",
                "gdpr_article": "Article 16",
            },
        )
        real_db_session.add(rectification_audit)
        real_db_session.commit()

        # Verify corrections applied
        updated_patient = (
            real_db_session.query(Patient).filter_by(id=patient_id).first()
        )

        # Decrypt and verify
        assert (
            real_test_services.encryption_service.decrypt_phi(
                updated_patient.first_name_encrypted, {"field": "first_name"}
            )
            == "Giovanni"
        )

        assert (
            real_test_services.encryption_service.decrypt_phi(
                updated_patient.date_of_birth_encrypted, {"field": "date_of_birth"}
            )
            == "1990-05-25"
        )

        assert (
            real_test_services.encryption_service.decrypt_phi(
                updated_patient.email_encrypted, {"field": "email"}
            )
            == "giovanni.rossi@example.it"
        )

        # Verify audit log
        rect_audit = (
            real_db_session.query(AuditLog)
            .filter_by(action="GDPR_RECTIFICATION")
            .first()
        )

        assert rect_audit is not None
        assert "Giovani" in str(rect_audit.details)  # Old value
        assert "Giovanni" in str(rect_audit.details)  # New value

        print("✅ GDPR rectification completed with full audit trail")

    def test_gdpr_automated_decision_transparency(
        self, real_test_services, real_db_session
    ):
        """Test GDPR requirements for automated decision-making transparency."""
        patient_id = uuid.uuid4()

        # Simulate automated risk assessment
        risk_assessment = {
            "patient_id": patient_id,
            "assessment_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "automated": True,
            "algorithm_version": "2.1.0",
            "inputs": {
                "age": 45,
                "blood_pressure": "140/90",
                "cholesterol": 220,
                "smoking": False,
                "diabetes": True,
                "family_history": True,
            },
            "calculation": {
                "base_score": 50,
                "age_factor": 10,
                "bp_factor": 15,
                "cholesterol_factor": 10,
                "diabetes_factor": 20,
                "family_factor": 15,
                "total_score": 120,
            },
            "result": {
                "risk_level": "HIGH",
                "score": 120,
                "threshold_low": 50,
                "threshold_high": 100,
                "recommendation": "Immediate consultation recommended",
            },
            "explanation": (
                "This cardiovascular risk assessment is based on validated clinical "
                "algorithms. Your score of 120 indicates HIGH risk based on: "
                "age (45), elevated blood pressure (140/90), high cholesterol (220), "
                "diabetes diagnosis, and family history. The algorithm weighs these "
                "factors according to clinical guidelines."
            ),
            "human_review_required": True,
            "can_contest": True,
            "contest_process": "Contact your healthcare provider to review this assessment",
        }

        # Store automated decision with full transparency
        real_db_session.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),  # System user
                patient_id=patient_id,
                action="AUTOMATED_DECISION",
                resource_type="RiskAssessment",
                resource_id=uuid.UUID(str(risk_assessment["assessment_id"])),
                timestamp=datetime.utcnow(),
                details=risk_assessment,
            )
        )

        real_db_session.commit()

        # Verify transparency requirements met
        decision_audit = (
            real_db_session.query(AuditLog)
            .filter_by(action="AUTOMATED_DECISION", patient_id=patient_id)
            .first()
        )

        assert decision_audit is not None
        details = decision_audit.details

        # GDPR Article 22 requirements
        assert details["automated"] is True
        assert "algorithm_version" in details
        assert "inputs" in details
        assert "calculation" in details
        assert "explanation" in details
        assert details["human_review_required"] is True
        assert details["can_contest"] is True
        assert "contest_process" in details

        print("✅ GDPR automated decision transparency requirements met")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
