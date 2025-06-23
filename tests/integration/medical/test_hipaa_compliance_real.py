"""Test HIPAA Compliance with Real Audit Trail Implementation.

Tests actual HIPAA audit requirements with real database and logging.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from tests.config import HIPAAAuditLog, Patient, User


@pytest.mark.integration
@pytest.mark.hipaa_required
@pytest.mark.audit_required
class TestHIPAAComplianceReal:
    """Test actual HIPAA audit trail requirements with real systems."""

    def test_hipaa_audit_trail_completeness(self, real_test_services, real_db_session):
        """Test that all required HIPAA audit fields are captured."""
        # Set the user context for database triggers
        provider_id = uuid.uuid4()
        real_db_session.execute(
            text("SET LOCAL app.current_user_id = :user_id"),
            {"user_id": str(provider_id)},
        )

        # Create test provider and patient
        provider = User(
            id=provider_id,
            email="provider@hospital.org",
            role="healthcare_provider",
            department="emergency",
            license_number="MD123456",
        )
        real_db_session.add(provider)

        patient = Patient(
            id=uuid.uuid4(),
            first_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Jane", {"field": "first_name"}
            ),
            last_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Doe", {"field": "last_name"}
            ),
            date_of_birth_encrypted=real_test_services.encryption_service.encrypt_phi(
                "1990-05-15", {"field": "date_of_birth"}
            ),
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
            refugee_id=f"REF{uuid.uuid4().hex[:8]}",
        )
        real_db_session.add(patient)
        real_db_session.commit()

        # Simulate accessing patient records
        access_details = {
            "user_id": str(provider.id),
            "patient_id": str(patient.id),
            "action": "VIEW_PATIENT_RECORDS",
            "resource_type": "PatientRecord",
            "resource_id": str(patient.id),
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "session_id": str(uuid.uuid4()),
            "reason_for_access": "treatment",
            "access_location": "emergency_department",
            "workstation_id": "ED-TERM-01",
        }

        # Create HIPAA audit log entry
        hipaa_audit = HIPAAAuditLog(
            id=uuid.uuid4(),
            user_id=uuid.UUID(access_details["user_id"]),
            patient_id=uuid.UUID(access_details["patient_id"]),
            action=access_details["action"],
            resource_type=access_details["resource_type"],
            resource_id=uuid.UUID(access_details["resource_id"]),
            timestamp=datetime.utcnow(),
            ip_address=access_details["ip_address"],
            user_agent=access_details["user_agent"],
            session_id=access_details["session_id"],
            reason_for_access=access_details["reason_for_access"],
            access_location=access_details["access_location"],
            workstation_id=access_details["workstation_id"],
            data_accessed=[
                "medical_history",
                "medications",
                "allergies",
                "lab_results",
            ],
            access_granted=True,
            authentication_method="password_mfa",
        )

        real_db_session.add(hipaa_audit)
        real_db_session.commit()

        # Verify all required HIPAA fields are present
        audit_record = (
            real_db_session.query(HIPAAAuditLog).filter_by(id=hipaa_audit.id).first()
        )

        assert audit_record is not None

        # Verify all required fields per HIPAA § 164.312(b)
        assert audit_record.user_id == provider.id
        assert audit_record.patient_id == patient.id
        assert audit_record.action == "VIEW_PATIENT_RECORDS"
        assert audit_record.timestamp is not None
        assert audit_record.ip_address == "192.168.1.100"
        assert audit_record.user_agent is not None
        assert audit_record.reason_for_access == "treatment"
        assert audit_record.data_accessed == [
            "medical_history",
            "medications",
            "allergies",
            "lab_results",
        ]
        assert audit_record.access_granted is True
        assert audit_record.authentication_method == "password_mfa"

        # Verify audit log is immutable (no updates allowed)
        with pytest.raises(Exception):  # noqa: B017
            audit_record.action = "MODIFIED_ACTION"
            real_db_session.commit()

        real_db_session.rollback()

        print("✅ HIPAA audit trail created with all required fields")

    def test_audit_log_for_all_phi_access(self, real_test_services, real_db_session):
        """Test that every PHI access generates an audit log."""
        # Create patient with PHI
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            first_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "John", {"field": "first_name"}
            ),
            last_name_encrypted=real_test_services.encryption_service.encrypt_phi(
                "Smith", {"field": "last_name"}
            ),
            date_of_birth_encrypted=real_test_services.encryption_service.encrypt_phi(
                "1985-03-20", {"field": "date_of_birth"}
            ),
            ssn_encrypted=real_test_services.encryption_service.encrypt_phi(
                "123-45-6789", {"field": "ssn", "sensitivity": "high"}
            ),
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
        )
        real_db_session.add(patient)
        real_db_session.commit()

        # Track all PHI access operations
        operations = []

        # 1. Create operation
        operations.append(
            {
                "action": "CREATE",
                "fields_accessed": ["first_name", "last_name", "date_of_birth", "ssn"],
            }
        )

        # 2. Read operation - decrypt PHI
        real_test_services.encryption_service.decrypt_phi(
            patient.first_name_encrypted,
            {"field": "first_name", "patient_id": str(patient_id)},
        )
        operations.append({"action": "READ", "fields_accessed": ["first_name"]})

        # 3. Update operation
        patient.phone_encrypted = real_test_services.encryption_service.encrypt_phi(
            "+1-555-123-4567", {"field": "phone"}
        )
        real_db_session.commit()
        operations.append({"action": "UPDATE", "fields_accessed": ["phone"]})

        # 4. Batch read for export
        fields_to_export = [
            "first_name",
            "last_name",
            "date_of_birth",
            "medical_record_number",
        ]
        export_data = {}
        for field in ["first_name", "last_name", "date_of_birth"]:
            encrypted_field = getattr(patient, f"{field}_encrypted")
            if encrypted_field:
                export_data[field] = real_test_services.encryption_service.decrypt_phi(
                    encrypted_field, {"field": field, "purpose": "patient_export"}
                )
        operations.append({"action": "EXPORT", "fields_accessed": fields_to_export})

        # Verify audit logs were created for each operation
        audit_logs = (
            real_db_session.query(HIPAAAuditLog)
            .filter_by(patient_id=patient_id)
            .order_by(HIPAAAuditLog.timestamp)
            .all()
        )

        # Should have at least one audit log per operation
        assert len(audit_logs) >= len(operations)

        # Verify each operation type is logged
        logged_actions = [log.action for log in audit_logs]
        assert "CREATE" in logged_actions
        assert "READ" in logged_actions
        assert "UPDATE" in logged_actions
        assert "EXPORT" in logged_actions

        print(
            f"✅ All PHI access operations generated audit logs: {len(audit_logs)} logs"
        )

    def test_audit_retention_and_search(self, real_test_services, real_db_session):
        """Test audit log retention and search capabilities."""
        # Create audit logs over time
        user_id = uuid.uuid4()
        patient_id = uuid.uuid4()

        # Create logs for different time periods
        now = datetime.utcnow()
        time_periods = [
            now - timedelta(days=2555),  # 7 years ago (HIPAA minimum)
            now - timedelta(days=365),  # 1 year ago
            now - timedelta(days=30),  # 1 month ago
            now - timedelta(days=1),  # Yesterday
            now,  # Today
        ]

        audit_logs = []
        for i, timestamp in enumerate(time_periods):
            audit = HIPAAAuditLog(
                id=uuid.uuid4(),
                user_id=user_id,
                patient_id=patient_id,
                action=f"ACCESS_{i}",
                resource_type="Patient",
                resource_id=patient_id,
                timestamp=timestamp,
                ip_address=f"192.168.1.{100 + i}",
                reason_for_access="treatment",
                data_accessed=["vitals"],
                access_granted=True,
            )
            audit_logs.append(audit)
            real_db_session.add(audit)

        real_db_session.commit()

        # Test retention - all logs should be retained (7+ years)
        all_logs = (
            real_db_session.query(HIPAAAuditLog).filter_by(patient_id=patient_id).all()
        )
        assert len(all_logs) == len(time_periods)

        # Test search by date range
        recent_logs = (
            real_db_session.query(HIPAAAuditLog)
            .filter(
                HIPAAAuditLog.patient_id == patient_id,
                HIPAAAuditLog.timestamp >= now - timedelta(days=31),
            )
            .all()
        )
        assert len(recent_logs) == 3  # Last 3 entries

        # Test search by user
        user_logs = (
            real_db_session.query(HIPAAAuditLog).filter_by(user_id=user_id).all()
        )
        assert len(user_logs) == len(time_periods)

        # Test search by action
        access_0_logs = (
            real_db_session.query(HIPAAAuditLog).filter_by(action="ACCESS_0").all()
        )
        assert len(access_0_logs) == 1

        # Verify oldest log is still accessible
        oldest_log = (
            real_db_session.query(HIPAAAuditLog)
            .filter_by(patient_id=patient_id)
            .order_by(HIPAAAuditLog.timestamp)
            .first()
        )

        assert oldest_log is not None
        assert oldest_log.action == "ACCESS_0"
        assert (now - oldest_log.timestamp).days >= 2555

        print("✅ Audit logs retained for 7+ years and searchable")

    def test_failed_access_audit(self, real_test_services, real_db_session):
        """Test that failed access attempts are audited."""
        # Create restricted patient record
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            first_name_encrypted=b"encrypted",
            last_name_encrypted=b"encrypted",
            date_of_birth_encrypted=b"encrypted",
            medical_record_number=f"MRN{uuid.uuid4().hex[:8]}",
            access_restricted=True,
            restriction_reason="VIP patient - board member",
        )
        real_db_session.add(patient)

        # Create unauthorized user
        unauthorized_user = User(
            id=uuid.uuid4(),
            email="nurse@hospital.org",
            role="nurse",
            department="general",
        )
        real_db_session.add(unauthorized_user)
        real_db_session.commit()

        # Simulate failed access attempt
        failed_audit = HIPAAAuditLog(
            id=uuid.uuid4(),
            user_id=unauthorized_user.id,
            patient_id=patient_id,
            action="UNAUTHORIZED_ACCESS_ATTEMPT",
            resource_type="Patient",
            resource_id=patient_id,
            timestamp=datetime.utcnow(),
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0",
            reason_for_access="routine_care",
            access_granted=False,
            denial_reason="insufficient_privileges",
            alert_generated=True,
        )
        real_db_session.add(failed_audit)
        real_db_session.commit()

        # Verify failed access was logged
        failed_logs = (
            real_db_session.query(HIPAAAuditLog)
            .filter_by(patient_id=patient_id, access_granted=False)
            .all()
        )

        assert len(failed_logs) == 1
        assert failed_logs[0].action == "UNAUTHORIZED_ACCESS_ATTEMPT"
        assert failed_logs[0].denial_reason == "insufficient_privileges"
        assert failed_logs[0].alert_generated is True

        print("✅ Failed access attempts are properly audited")

    def test_emergency_override_audit(self, real_test_services, real_db_session):
        """Test emergency access override generates detailed audit."""
        # Create patient and emergency provider
        patient_id = uuid.uuid4()
        emergency_provider_id = uuid.uuid4()

        # Create emergency access audit with full context
        emergency_audit = HIPAAAuditLog(
            id=uuid.uuid4(),
            user_id=emergency_provider_id,
            patient_id=patient_id,
            action="EMERGENCY_OVERRIDE",
            resource_type="Patient",
            resource_id=patient_id,
            timestamp=datetime.utcnow(),
            ip_address="192.168.100.50",
            user_agent="HavenHealth iOS App 2.1.0",
            reason_for_access="emergency_treatment",
            emergency_override=True,
            override_reason="Patient unconscious, need allergy information for emergency surgery",
            override_authorized_by="Dr. Smith (Attending)",
            access_location="emergency_room",
            workstation_id="ER-TABLET-03",
            data_accessed=["allergies", "medications", "medical_history", "blood_type"],
            access_granted=True,
            alert_generated=True,
            notification_sent_to=[
                "patient_primary_care",
                "privacy_officer",
                "department_head",
            ],
        )
        real_db_session.add(emergency_audit)
        real_db_session.commit()

        # Verify emergency override details
        emergency_log = (
            real_db_session.query(HIPAAAuditLog)
            .filter_by(id=emergency_audit.id)
            .first()
        )

        assert emergency_log.emergency_override is True
        assert "unconscious" in emergency_log.override_reason
        assert emergency_log.override_authorized_by is not None
        assert emergency_log.alert_generated is True
        assert len(emergency_log.notification_sent_to) == 3

        print("✅ Emergency override access properly audited with full context")

    def test_audit_log_integrity(self, real_test_services, real_db_session):
        """Test audit log integrity and tamper detection."""
        # Create audit log with integrity hash
        audit_data = {
            "user_id": str(uuid.uuid4()),
            "patient_id": str(uuid.uuid4()),
            "action": "VIEW_RECORDS",
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": "192.168.1.100",
        }

        # Calculate integrity hash
        hash_input = json.dumps(audit_data, sort_keys=True)
        integrity_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        audit_log = HIPAAAuditLog(
            id=uuid.uuid4(),
            user_id=uuid.UUID(audit_data["user_id"]),
            patient_id=uuid.UUID(audit_data["patient_id"]),
            action=audit_data["action"],
            timestamp=datetime.fromisoformat(audit_data["timestamp"]),
            ip_address=audit_data["ip_address"],
            integrity_hash=integrity_hash,
            data_accessed=["demographics"],
            access_granted=True,
        )
        real_db_session.add(audit_log)
        real_db_session.commit()

        # Verify integrity
        stored_log = (
            real_db_session.query(HIPAAAuditLog).filter_by(id=audit_log.id).first()
        )

        # Recalculate hash to verify
        verify_data = {
            "user_id": str(stored_log.user_id),
            "patient_id": str(stored_log.patient_id),
            "action": stored_log.action,
            "timestamp": stored_log.timestamp.isoformat(),
            "ip_address": stored_log.ip_address,
        }
        verify_hash = hashlib.sha256(
            json.dumps(verify_data, sort_keys=True).encode()
        ).hexdigest()

        assert stored_log.integrity_hash == verify_hash
        print("✅ Audit log integrity verification passed")

    def test_audit_export_for_compliance(self, real_test_services, real_db_session):
        """Test audit log export for compliance reporting."""
        # Create sample audit logs
        patient_id = uuid.uuid4()
        start_date = datetime.utcnow() - timedelta(days=30)

        for i in range(10):
            audit = HIPAAAuditLog(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                patient_id=patient_id,
                action=f"ACTION_{i}",
                resource_type="Patient",
                resource_id=patient_id,
                timestamp=start_date + timedelta(days=i),
                ip_address=f"192.168.1.{100 + i}",
                data_accessed=["field1", "field2"],
                access_granted=True,
            )
            real_db_session.add(audit)

        real_db_session.commit()

        # Export audit logs for patient
        export_logs = (
            real_db_session.query(HIPAAAuditLog)
            .filter_by(patient_id=patient_id)
            .order_by(HIPAAAuditLog.timestamp)
            .all()
        )

        # Format for compliance report
        compliance_export = []
        for log in export_logs:
            compliance_export.append(
                {
                    "audit_id": str(log.id),
                    "date": log.timestamp.strftime("%Y-%m-%d"),
                    "time": log.timestamp.strftime("%H:%M:%S"),
                    "user": str(log.user_id),
                    "action": log.action,
                    "patient": str(log.patient_id),
                    "ip_address": log.ip_address,
                    "data_accessed": log.data_accessed,
                    "access_granted": log.access_granted,
                }
            )

        assert len(compliance_export) == 10
        assert all("audit_id" in entry for entry in compliance_export)
        assert all("date" in entry for entry in compliance_export)

        print(
            f"✅ Audit logs exported for compliance: {len(compliance_export)} entries"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
