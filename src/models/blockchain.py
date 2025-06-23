"""Blockchain reference models for local caching and performance optimization.

This module handles blockchain references for FHIR Resources.
All health records stored on blockchain must validate against FHIR standards.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel
from src.models.db_types import JSONB
from src.models.db_types import UUID as PostgresUUID


class BlockchainReference(BaseModel):
    """Local cache of blockchain transaction references for performance."""

    __tablename__ = "blockchain_references"

    # Record reference
    record_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID of the health record stored on blockchain",
    )

    # Blockchain transaction details
    transaction_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Blockchain transaction ID",
    )

    hash_value = Column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of the record data",
    )

    blockchain_network = Column(
        String(100),
        nullable=False,
        default="healthcare-channel",
        comment="Blockchain network/channel name",
    )

    # Metadata
    block_number = Column(
        String(50), nullable=True, comment="Block number where transaction was included"
    )

    contract_name = Column(
        String(100),
        nullable=True,
        default="health-records",
        comment="Smart contract name",
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the reference was created",
    )

    # Create composite index for efficient lookups
    __table_args__ = (
        Index("idx_blockchain_record_tx", "record_id", "transaction_id"),
        Index("idx_blockchain_hash", "hash_value"),
    )

    def __repr__(self) -> str:
        """Return a string representation of the blockchain reference."""
        return f"<BlockchainReference(record_id={self.record_id}, tx_id={self.transaction_id})>"


class CrossBorderVerification(BaseModel):
    """Track cross-border verification requests."""

    __tablename__ = "cross_border_verifications"

    # Verification details
    verification_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique verification identifier",
    )

    patient_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=False, index=True, comment="Patient ID"
    )

    origin_country = Column(
        String(3), nullable=False, comment="ISO 3166-1 alpha-3 country code of origin"
    )

    destination_country = Column(
        String(3),
        nullable=False,
        comment="ISO 3166-1 alpha-3 country code of destination",
    )

    # Blockchain reference
    blockchain_tx_id = Column(
        String(255),
        nullable=True,
        comment="Blockchain transaction ID for this verification",
    )

    # Status tracking
    status = Column(
        String(50),
        nullable=False,
        default="pending",
        comment="Verification status: pending, active, expired, revoked",
    )

    # Validity period
    valid_from = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Start of validity period",
    )

    valid_until = Column(DateTime, nullable=False, comment="End of validity period")

    # Package details
    package_hash = Column(
        String(64), nullable=True, comment="Hash of the encrypted verification package"
    )

    health_records_count = Column(
        Integer, nullable=False, default=0, comment="Number of health records included"
    )

    # Purpose and metadata
    purpose = Column(
        String(100),
        nullable=False,
        default="medical_treatment",
        comment="Purpose of cross-border access",
    )

    # Revocation info
    revoked_at = Column(
        DateTime, nullable=True, comment="When the verification was revoked"
    )

    revocation_reason = Column(Text, nullable=True, comment="Reason for revocation")

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the verification was created",
    )

    last_accessed = Column(
        DateTime, nullable=True, comment="Last time this verification was accessed"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_cbv_patient", "patient_id"),
        Index("idx_cbv_countries", "origin_country", "destination_country"),
        Index("idx_cbv_validity", "valid_from", "valid_until"),
        Index("idx_cbv_status", "status"),
    )

    def is_valid(self) -> bool:
        """Check if verification is currently valid."""
        now = datetime.utcnow()
        return bool(
            self.status == "active"
            and self.valid_from <= now <= self.valid_until
            and self.revoked_at is None
        )

    def __repr__(self) -> str:
        """Return string representation of CrossBorderVerification."""
        return f"<CrossBorderVerification(id={self.verification_id}, patient={self.patient_id}, {self.origin_country}->{self.destination_country})>"


class BlockchainAuditLog(BaseModel):
    """Audit log for all blockchain operations."""

    __tablename__ = "blockchain_audit_logs"

    # Operation details
    operation_type = Column(
        String(50), nullable=False, comment="Type of blockchain operation"
    )

    entity_type = Column(
        String(50),
        nullable=False,
        comment="Type of entity (health_record, verification, etc.)",
    )

    entity_id = Column(String(255), nullable=False, comment="ID of the entity")

    # Transaction details
    blockchain_tx_id = Column(
        String(255), nullable=True, comment="Resulting blockchain transaction ID"
    )

    # User/System info
    initiated_by: Mapped[Optional[UUID]] = mapped_column(
        PostgresUUID(as_uuid=True),
        nullable=True,
        comment="User who initiated the operation",
    )

    organization = Column(
        String(100), nullable=True, comment="Organization performing the operation"
    )

    # Result
    success = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the operation succeeded",
    )

    error_message = Column(
        Text, nullable=True, comment="Error message if operation failed"
    )

    # Metadata
    operation_metadata = Column(
        JSONB, nullable=True, comment="Additional operation metadata"
    )

    # Timestamp
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the operation was performed",
    )

    # Indexes
    __table_args__ = (
        Index("idx_blockchain_audit_entity", "entity_type", "entity_id"),
        Index("idx_blockchain_audit_tx", "blockchain_tx_id"),
        Index("idx_blockchain_audit_user", "initiated_by"),
        Index("idx_blockchain_audit_time", "created_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of BlockchainAuditLog."""
        return f"<BlockchainAuditLog(op={self.operation_type}, entity={self.entity_type}:{self.entity_id}, success={self.success})>"
