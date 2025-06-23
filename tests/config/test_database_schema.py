"""Real Database Schema Setup for Healthcare Testing.

This creates the ACTUAL production database schema for testing
NO SIMPLIFIED SCHEMAS - Lives depend on accurate testing
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates

Base = declarative_base()  # type: Any


class AccessLevel(enum.Enum):
    """Medical record access levels."""

    PUBLIC = "public"
    HEALTHCARE_PROVIDER = "healthcare_provider"
    EMERGENCY_ONLY = "emergency_only"
    PATIENT_ONLY = "patient_only"
    RESTRICTED = "restricted"


class AuditAction(enum.Enum):
    """HIPAA-compliant audit actions."""

    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EMERGENCY_ACCESS = "EMERGENCY_ACCESS"
    EXPORT = "EXPORT"
    PRINT = "PRINT"
    SHARE = "SHARE"


class Patient(Base):
    """Patient model with full HIPAA compliance."""

    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Encrypted PHI fields
    first_name_encrypted = Column(LargeBinary, nullable=False)
    last_name_encrypted = Column(LargeBinary, nullable=False)
    date_of_birth_encrypted = Column(LargeBinary, nullable=False)
    ssn_encrypted = Column(LargeBinary, nullable=True)

    # Non-PHI identifiers
    medical_record_number = Column(String(50), unique=True, index=True)
    refugee_id = Column(String(100), unique=True, index=True)
    unhcr_number = Column(String(50), unique=True, nullable=True)

    # Contact info (encrypted)
    phone_encrypted = Column(LargeBinary, nullable=True)
    email_encrypted = Column(LargeBinary, nullable=True)
    address_encrypted = Column(LargeBinary, nullable=True)

    # Demographics
    gender = Column(String(20))
    nationality = Column(String(100))
    preferred_language = Column(String(10), default="en")

    # Medical metadata
    blood_type = Column(String(10))
    allergies_encrypted = Column(LargeBinary, nullable=True)
    emergency_contact_encrypted = Column(LargeBinary, nullable=True)

    # Blockchain verification
    blockchain_hash = Column(String(66), unique=True, nullable=True)
    blockchain_tx_hash = Column(String(66), nullable=True)
    blockchain_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed_at = Column(TIMESTAMP)

    # Compliance fields
    consent_given = Column(Boolean, default=False)
    consent_date = Column(TIMESTAMP)
    data_retention_date = Column(TIMESTAMP)
    deletion_requested = Column(Boolean, default=False)
    deletion_date = Column(TIMESTAMP)

    # Relationships
    health_records = relationship(
        "HealthRecord", back_populates="patient", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="patient")
    access_logs = relationship("AccessLog", back_populates="patient")

    # Indexes for performance
    __table_args__ = (
        Index("idx_patient_mrn", "medical_record_number"),
        Index("idx_patient_refugee_id", "refugee_id"),
        Index("idx_patient_created", "created_at"),
        Index("idx_patient_blockchain", "blockchain_hash"),
        CheckConstraint(
            "gender IN ('male', 'female', 'other', 'unknown')", name="check_gender"
        ),
    )

    @validates("medical_record_number")
    def validate_mrn(self, _key, value):
        """Validate medical record number format."""
        if not value or len(value) < 5:
            raise ValueError("Invalid medical record number")
        return value


class HealthRecord(Base):
    """Health record with encryption and access control."""

    __tablename__ = "health_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    # Record metadata
    record_type = Column(
        String(50), nullable=False
    )  # diagnosis, medication, procedure, lab_result, etc
    record_date = Column(TIMESTAMP, nullable=False)

    # Encrypted medical data
    data_encrypted = Column(LargeBinary, nullable=False)  # Full FHIR resource encrypted

    # FHIR compliance
    fhir_resource_type = Column(String(50))
    fhir_resource_id = Column(String(100))
    fhir_version = Column(String(10), default="R4")

    # Access control
    access_level: Any = Column(
        Enum(AccessLevel), default=AccessLevel.HEALTHCARE_PROVIDER
    )

    # Provider information
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"))
    provider_name_encrypted = Column(LargeBinary)
    facility_name = Column(String(200))
    facility_country = Column(String(100))

    # Verification
    verified = Column(Boolean, default=False)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("providers.id"))
    verified_at = Column(TIMESTAMP)
    verification_notes = Column(Text)

    # Blockchain
    blockchain_hash = Column(String(66), unique=True)
    blockchain_tx_hash = Column(String(66))

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="health_records")
    provider = relationship("Provider", foreign_keys=[provider_id])
    verifier = relationship("Provider", foreign_keys=[verified_by])

    __table_args__ = (
        Index("idx_record_patient", "patient_id"),
        Index("idx_record_type_date", "record_type", "record_date"),
        Index("idx_record_provider", "provider_id"),
        Index("idx_record_blockchain", "blockchain_hash"),
        CheckConstraint(
            "record_type IN ('diagnosis', 'medication', 'procedure', 'lab_result', "
            "'imaging', 'immunization', 'allergy', 'vital_signs', 'clinical_note')",
            name="check_record_type",
        ),
    )


class Provider(Base):
    """Healthcare provider with verification."""

    __tablename__ = "providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Provider info (encrypted where sensitive)
    license_number_encrypted = Column(LargeBinary, nullable=False)
    first_name_encrypted = Column(LargeBinary, nullable=False)
    last_name_encrypted = Column(LargeBinary, nullable=False)

    # Professional info
    specialization = Column(String(100))
    facility_name = Column(String(200))
    facility_country = Column(String(100))

    # Verification
    verified = Column(Boolean, default=False)
    verification_date = Column(TIMESTAMP)
    verification_authority = Column(String(200))

    # Access
    active = Column(Boolean, default=True)
    role = Column(String(50), default="physician")

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_login_at = Column(TIMESTAMP)

    __table_args__ = (
        Index("idx_provider_facility", "facility_name", "facility_country"),
        CheckConstraint(
            "role IN ('physician', 'nurse', 'pharmacist', 'technician', 'admin')",
            name="check_provider_role",
        ),
    )


class AuditLog(Base):
    """HIPAA-compliant audit logging."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who
    user_id = Column(UUID(as_uuid=True), nullable=False)
    user_type = Column(String(50))  # patient, provider, admin

    # What
    action: Any = Column(Enum(AuditAction), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=False)

    # When
    timestamp = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    # Where
    ip_address = Column(String(45))
    user_agent = Column(Text)
    location = Column(String(100))

    # Why
    reason = Column(Text)
    emergency_override = Column(Boolean, default=False)

    # Additional context
    details = Column(JSONB)
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Patient reference
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"))
    patient = relationship("Patient", back_populates="audit_logs")

    # Retention (7 years for HIPAA)
    retention_date = Column(TIMESTAMP)

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_patient", "patient_id"),
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )


class AccessLog(Base):
    """Track all data access for compliance."""

    __tablename__ = "access_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Access details
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    accessor_id = Column(UUID(as_uuid=True), nullable=False)
    accessor_type = Column(String(50))

    # What was accessed
    fields_accessed = Column(JSONB)  # List of fields viewed
    records_accessed = Column(JSONB)  # List of record IDs

    # Context
    access_reason = Column(String(200))
    access_timestamp = Column(TIMESTAMP, default=datetime.utcnow)
    access_duration_seconds = Column(Integer)

    # Relationships
    patient = relationship("Patient", back_populates="access_logs")

    __table_args__ = (
        Index("idx_access_patient_time", "patient_id", "access_timestamp"),
        Index("idx_access_accessor", "accessor_id"),
    )


class EmergencyAccess(Base):
    """Emergency access override tracking."""

    __tablename__ = "emergency_access"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Emergency details
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)

    # Justification
    reason = Column(Text, nullable=False)
    severity = Column(String(20))  # critical, urgent, moderate

    # Approval
    approved_by = Column(UUID(as_uuid=True))
    approval_timestamp = Column(TIMESTAMP)

    # Access window
    access_granted_at = Column(TIMESTAMP, default=datetime.utcnow)
    access_expires_at = Column(TIMESTAMP, nullable=False)
    access_revoked_at = Column(TIMESTAMP)

    # Audit
    actions_performed = Column(JSONB)  # List of actions taken

    __table_args__ = (
        Index("idx_emergency_patient", "patient_id"),
        Index("idx_emergency_provider", "provider_id"),
        Index("idx_emergency_time", "access_granted_at", "access_expires_at"),
        CheckConstraint(
            "severity IN ('critical', 'urgent', 'moderate')", name="check_severity"
        ),
    )


class EncryptionKey(Base):
    """Key management for field-level encryption."""

    __tablename__ = "encryption_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Key info
    key_id = Column(String(100), unique=True, nullable=False)
    key_version = Column(Integer, default=1)
    algorithm = Column(String(50), default="AES-256-GCM")

    # Key data (encrypted with master key)
    encrypted_key = Column(LargeBinary, nullable=False)

    # Usage
    purpose = Column(String(50))  # patient_data, provider_data, audit_data
    active = Column(Boolean, default=True)

    # Rotation
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    rotated_at = Column(TIMESTAMP)
    expires_at = Column(TIMESTAMP)

    __table_args__ = (
        Index("idx_key_active", "active", "purpose"),
        UniqueConstraint("key_id", "key_version", name="uq_key_version"),
    )


class HIPAAAuditLog(Base):
    """Extended audit log with HIPAA-specific requirements."""

    __tablename__ = "hipaa_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core HIPAA fields
    user_id = Column(UUID(as_uuid=True), nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=False)
    timestamp = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    # Access context
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text)
    session_id = Column(String(100))
    authentication_method = Column(String(50))

    # HIPAA-specific fields
    reason_for_access = Column(String(100), nullable=False)
    data_accessed = Column(JSONB)  # List of fields/data accessed
    access_granted = Column(Boolean, default=True)
    denial_reason = Column(String(200))

    # Location and device
    access_location = Column(String(100))
    workstation_id = Column(String(100))

    # Emergency access
    emergency_override = Column(Boolean, default=False)
    override_reason = Column(Text)
    override_authorized_by = Column(String(200))

    # Notifications
    alert_generated = Column(Boolean, default=False)
    notification_sent_to = Column(JSONB)  # List of notified parties

    # Data integrity
    integrity_hash = Column(String(64))  # SHA-256 hash of critical fields

    # GDPR fields
    anonymized = Column(Boolean, default=False)
    original_patient_id = Column(UUID(as_uuid=True))  # Encrypted reference

    # Retention
    retention_date = Column(TIMESTAMP)  # 7 years from timestamp

    # Relationships
    patient = relationship("Patient", backref="hipaa_audit_logs")

    # Immutability - no updates allowed after creation
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_hipaa_audit_timestamp", "timestamp"),
        Index("idx_hipaa_audit_patient", "patient_id"),
        Index("idx_hipaa_audit_user", "user_id"),
        Index("idx_hipaa_audit_action", "action"),
        Index("idx_hipaa_audit_access_granted", "access_granted"),
        CheckConstraint(
            "reason_for_access IN ('treatment', 'payment', 'operations', "
            "'emergency', 'legal', 'patient_request', 'other')",
            name="check_access_reason",
        ),
    )


class PatientConsent(Base):
    """GDPR-compliant patient consent management."""

    __tablename__ = "patient_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    # Consent details
    consent_type = Column(String(50), nullable=False)
    purpose = Column(String(200), nullable=False)
    description = Column(Text)

    # Consent status
    granted = Column(Boolean, default=False)
    granted_at = Column(TIMESTAMP)
    granted_ip = Column(String(45))
    granted_user_agent = Column(Text)

    # Consent withdrawal
    withdrawn_at = Column(TIMESTAMP)
    withdrawal_reason = Column(Text)
    withdrawal_method = Column(String(50))  # email, portal, written

    # Consent metadata
    version = Column(String(20), default="1.0")
    required = Column(Boolean, default=False)
    expires_at = Column(TIMESTAMP)

    # Legal basis
    legal_basis = Column(String(100))  # consent, contract, legal_obligation, etc

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", backref="consents")

    __table_args__ = (
        Index("idx_consent_patient", "patient_id"),
        Index("idx_consent_type", "consent_type"),
        Index("idx_consent_granted", "granted"),
        UniqueConstraint(
            "patient_id", "consent_type", "version", name="uq_patient_consent_version"
        ),
        CheckConstraint(
            "consent_type IN ('basic_treatment', 'data_sharing', 'research', "
            "'marketing', 'third_party', 'emergency_contact')",
            name="check_consent_type",
        ),
    )


# Duplicate definition removed to prevent SQLAlchemy conflict
# class EmergencyAccess(Base):
#     """Emergency access override tracking"""
#
#     __tablename__ = "emergency_access"
#
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
#     provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
#
#     # Access details
#     reason = Column(Text, nullable=False)
#     severity = Column(String(20), nullable=False)  # critical, urgent, emergent
#
#     # Time bounds
#     granted_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
#     access_expires_at = Column(TIMESTAMP, nullable=False)
#
#     # Authorization
#     authorized_by = Column(UUID(as_uuid=True), ForeignKey("providers.id"))
#     authorization_notes = Column(Text)
#
#     # Relationships
#     patient = relationship("Patient", backref="emergency_accesses")
#     provider = relationship("Provider", foreign_keys=[provider_id])
#     authorizer = relationship("Provider", foreign_keys=[authorized_by])
#
#     __table_args__ = (
#         Index("idx_emergency_patient", "patient_id"),
#         Index("idx_emergency_provider", "provider_id"),
#         Index("idx_emergency_expires", "access_expires_at"),
#     )


class User(Base):
    """System user (provider, admin, patient)."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255))

    # User details
    role = Column(String(50), nullable=False)
    department = Column(String(100))
    license_number = Column(String(50))

    # Security
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))

    # Status
    active = Column(Boolean, default=True)
    locked = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_login = Column(TIMESTAMP)

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_role", "role"),
    )


def create_test_schema(db_engine):
    """Create all tables with proper medical compliance."""
    # Drop all tables first for clean test environment
    Base.metadata.drop_all(db_engine)

    # Create all tables
    Base.metadata.create_all(db_engine)

    # Add database-level encryption
    with db_engine.connect() as conn:
        # Enable row-level security
        conn.execute(text("ALTER TABLE patients ENABLE ROW LEVEL SECURITY"))
        conn.execute(text("ALTER TABLE health_records ENABLE ROW LEVEL SECURITY"))

        # Create audit trigger function
        conn.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION audit_trigger_function()
            RETURNS TRIGGER AS $$
            DECLARE
                v_user_id UUID;
            BEGIN
                -- Try to get user_id from current setting, use NULL if not set
                BEGIN
                    v_user_id := current_setting('app.current_user_id', true)::UUID;
                EXCEPTION WHEN OTHERS THEN
                    v_user_id := NULL;
                END;

                -- Only insert audit log if we have a user_id or if it's a system operation
                IF v_user_id IS NOT NULL OR TG_OP = 'DELETE' THEN
                    INSERT INTO audit_logs (
                        id, user_id, action, resource_type, resource_id,
                        timestamp, details
                    ) VALUES (
                        gen_random_uuid(),
                        v_user_id,
                        CASE
                            WHEN TG_OP = 'INSERT' THEN 'CREATE'::auditaction
                            WHEN TG_OP = 'UPDATE' THEN 'UPDATE'::auditaction
                            WHEN TG_OP = 'DELETE' THEN 'DELETE'::auditaction
                        END,
                        TG_TABLE_NAME,
                        COALESCE(NEW.id, OLD.id),
                        NOW(),
                        jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW))
                    );
                END IF;

                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
        """
            )
        )

        # Apply audit triggers to sensitive tables
        for table in ["patients", "health_records", "providers"]:
            conn.execute(
                text(
                    f"""
                CREATE TRIGGER audit_{table}
                AFTER INSERT OR UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
            """
                )
            )

        # Make HIPAA audit logs immutable - prevent updates and deletes
        conn.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION prevent_audit_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'HIPAA audit logs are immutable and cannot be modified or deleted';
            END;
            $$ LANGUAGE plpgsql;
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TRIGGER protect_hipaa_audit_logs
            BEFORE UPDATE OR DELETE ON hipaa_audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
        """
            )
        )

        conn.commit()

    print("Medical-compliant test database schema created successfully")


if __name__ == "__main__":
    # Create test database schema
    from tests.config.real_test_config import RealTestConfig

    engine = RealTestConfig.create_real_database_engine()
    create_test_schema(engine)
