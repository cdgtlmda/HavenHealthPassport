"""Verification database model.

Note: This module handles PHI-related verification data.
- Access Control: Implement role-based access control (RBAC) for verification operations
"""

import enum
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID as UUIDType

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from src.models.db_types import JSONB, UUID

from .base import BaseModel

logger = logging.getLogger(__name__)


class VerificationMethod(enum.Enum):
    """Methods used for verification."""

    BIOMETRIC = "biometric"
    DOCUMENT = "document"
    WITNESS = "witness"
    BLOCKCHAIN = "blockchain"
    GOVERNMENT_ID = "government_id"
    UNHCR_REGISTRATION = "unhcr_registration"
    MEDICAL_PROFESSIONAL = "medical_professional"
    COMMUNITY_LEADER = "community_leader"
    NGO_STAFF = "ngo_staff"
    MULTI_FACTOR = "multi_factor"


class VerificationLevel(enum.Enum):
    """Level of verification confidence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class VerificationStatus(enum.Enum):
    """Current status of verification."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Verification(BaseModel):
    """Verification model for identity and document verification."""

    __tablename__ = "verifications"
    __fhir_resource__ = "VerificationResult"  # FHIR Resource type

    # Subject of Verification
    patient_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Verification Details
    verification_type = Column(
        String(50), nullable=False
    )  # identity, document, medical_record
    verification_method: Mapped[VerificationMethod] = mapped_column(
        Enum(VerificationMethod), nullable=False
    )
    verification_level: Mapped[VerificationLevel] = mapped_column(
        Enum(VerificationLevel), nullable=False
    )
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), nullable=False, default=VerificationStatus.PENDING
    )

    # Verifier Information
    verifier_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), nullable=False)
    verifier_name = Column(String(200), nullable=False)
    verifier_organization = Column(String(200))
    verifier_role = Column(String(100))
    verifier_credentials = Column(JSONB, default=dict)  # Professional credentials

    # Verification Process
    requested_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    # Evidence and Documentation
    evidence_provided = Column(JSONB, default=list)  # List of evidence items
    documents_verified = Column(JSONB, default=list)  # List of document references
    biometric_data_hash = Column(String(255))  # Hash of biometric data

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with validator."""
        super().__init__(**kwargs)
        self._validator: Optional[Any] = None  # Lazy load to avoid circular import

    @property
    def validator(self) -> Any:
        """Get FHIR validator instance (lazy loaded)."""
        if not self._validator:
            from src.healthcare.fhir_validator import (  # pylint: disable=import-outside-toplevel
                FHIRValidator,
            )

            self._validator = FHIRValidator()
        return self._validator

    def validate_verification(self) -> bool:
        """Validate verification data.

        Returns:
            True if valid
        """
        try:
            # Basic validation
            if not self.patient_id or not self.verifier_id:
                return False

            # Validate verification type
            valid_types = ["identity", "document", "medical_record"]
            if self.verification_type not in valid_types:
                return False

            return True
        except (AttributeError, TypeError, ValueError) as e:
            logger.warning("Validation error in verification: %s", str(e))
            return False

    verification_notes = Column(Text)

    # Multi-Factor Verification
    factors_required = Column(Integer, default=1)
    factors_completed = Column(JSONB, default=list)  # List of completed factors

    # Blockchain Integration
    blockchain_hash = Column(
        String(255), unique=True
    )  # Verification hash on blockchain
    blockchain_tx_id = Column(String(255))  # Blockchain transaction ID
    blockchain_network = Column(String(50))  # Which blockchain network
    smart_contract_address = Column(String(255))

    # Witness/Reference Information
    witnesses = Column(JSONB, default=list)  # List of witness details
    reference_verifications = Column(JSONB, default=list)  # Related verification IDs

    # Scoring and Confidence
    confidence_score = Column(Integer)  # 0-100 confidence score
    risk_indicators = Column(JSONB, default=list)  # Any risk flags
    verification_strength = Column(String(20))  # weak, moderate, strong

    # Revocation
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True))
    revoked_by: Mapped[Optional[UUIDType]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revocation_reason = Column(Text)

    # Cross-Border Recognition
    recognized_countries = Column(
        JSONB, default=list
    )  # Countries that recognize this verification
    international_standard = Column(String(100))  # Which standard it complies with

    # Audit Trail
    verification_log = Column(JSONB, default=list)  # Detailed log of verification steps
    ip_address = Column(String(45))  # IP address of verifier
    device_fingerprint = Column(String(255))  # Device used for verification

    # Relationships
    patient = relationship("Patient", back_populates="verifications")

    # Indexes
    __table_args__ = (
        Index("idx_verification_patient_type", "patient_id", "verification_type"),
        Index("idx_verification_status", "status"),
        Index("idx_verification_expires", "expires_at"),
        Index("idx_verification_blockchain", "blockchain_hash"),
    )

    @property
    def is_valid(self) -> bool:
        """Check if verification is currently valid."""
        if self.status != VerificationStatus.COMPLETED:
            return False

        if self.revoked:
            return False

        if self.expires_at and self.expires_at < datetime.utcnow():
            return False

        return True

    @property
    def is_multi_factor(self) -> bool:
        """Check if this is a multi-factor verification."""
        return bool(self.factors_required > 1)

    def add_evidence(self, evidence_type: str, evidence_data: Dict[str, Any]) -> None:
        """Add evidence to the verification."""
        if not self.evidence_provided:
            current_evidence = []  # type: List[Dict[str, Any]]
        else:
            current_evidence = list(self.evidence_provided)

        evidence = {
            "type": evidence_type,
            "data": evidence_data,
            "added_at": datetime.utcnow().isoformat(),
            "hash": self._hash_evidence(evidence_data),
        }
        current_evidence.append(evidence)
        self.evidence_provided = current_evidence  # type: ignore[assignment]

    def add_witness(
        self, witness_id: str, witness_name: str, witness_role: str, statement: str
    ) -> None:
        """Add a witness to the verification."""
        if not self.witnesses:
            current_witnesses = []  # type: List[Dict[str, Any]]
        else:
            current_witnesses = list(self.witnesses)

        witness = {
            "id": witness_id,
            "name": witness_name,
            "role": witness_role,
            "statement": statement,
            "timestamp": datetime.utcnow().isoformat(),
        }
        current_witnesses.append(witness)
        self.witnesses = current_witnesses  # type: ignore[assignment]

    def complete_factor(self, factor_type: str, factor_data: Dict[str, Any]) -> None:
        """Complete a factor in multi-factor verification."""
        if not self.factors_completed:
            current_factors = []  # type: List[Dict[str, Any]]
        else:
            current_factors = list(self.factors_completed)

        factor = {
            "type": factor_type,
            "completed_at": datetime.utcnow().isoformat(),
            "data": factor_data,
        }
        current_factors.append(factor)
        self.factors_completed = current_factors  # type: ignore[assignment]

        # Check if all factors are complete
        if len(current_factors) >= self.factors_required:
            self.status = VerificationStatus.COMPLETED
            self.completed_at = datetime.utcnow()  # type: ignore[assignment]

    def calculate_confidence_score(self) -> int:
        """Calculate confidence score based on verification factors."""
        score = 0

        # Base score by verification method
        method_scores = {
            VerificationMethod.BIOMETRIC: 30,
            VerificationMethod.GOVERNMENT_ID: 25,
            VerificationMethod.UNHCR_REGISTRATION: 25,
            VerificationMethod.DOCUMENT: 20,
            VerificationMethod.MEDICAL_PROFESSIONAL: 20,
            VerificationMethod.WITNESS: 15,
            VerificationMethod.COMMUNITY_LEADER: 15,
            VerificationMethod.NGO_STAFF: 15,
            VerificationMethod.BLOCKCHAIN: 10,
            VerificationMethod.MULTI_FACTOR: 35,
        }
        verification_method_value = self.verification_method
        score += method_scores.get(verification_method_value, 10)

        # Additional points for evidence
        if self.evidence_provided:
            score += min(len(self.evidence_provided) * 5, 20)

        # Additional points for witnesses
        if self.witnesses:
            score += min(len(self.witnesses) * 10, 20)

        # Additional points for blockchain verification
        if self.blockchain_hash:
            score += 10

        # Additional points for multi-factor
        if self.is_multi_factor:
            score += 10

        # Cap at 100
        final_score = min(score, 100)
        self.confidence_score = final_score  # type: ignore[assignment]

        # Set verification strength
        if final_score >= 80:
            self.verification_strength = "strong"  # type: ignore[assignment]
        elif final_score >= 60:
            self.verification_strength = "moderate"  # type: ignore[assignment]
        else:
            self.verification_strength = "weak"  # type: ignore[assignment]

        return final_score

    def generate_blockchain_hash(self) -> str:
        """Generate hash for blockchain storage."""
        data = {
            "patient_id": str(self.patient_id),
            "verification_type": self.verification_type,
            "verification_method": self.verification_method.value,
            "verifier_id": str(self.verifier_id),
            "verifier_organization": self.verifier_organization,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "evidence_hashes": (
                [e.get("hash") for e in getattr(self, "evidence_provided", [])]
                if getattr(self, "evidence_provided", None)
                else []
            ),
        }

        # Create deterministic hash
        data_str = json.dumps(data, sort_keys=True)
        hash_value = hashlib.sha256(data_str.encode()).hexdigest()
        self.blockchain_hash = hash_value  # type: ignore[assignment]
        return hash_value

    def _hash_evidence(self, evidence_data: Dict[str, Any]) -> str:
        """Create hash of evidence data."""
        data_str = json.dumps(evidence_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def revoke(self, revoked_by: UUIDType, reason: str) -> None:
        """Revoke this verification."""
        self.revoked = True  # type: ignore[assignment]
        self.revoked_at = datetime.utcnow()  # type: ignore[assignment]
        self.revoked_by = revoked_by
        self.revocation_reason = reason  # type: ignore[assignment]
        self.status = VerificationStatus.REVOKED

    def add_recognition(self, country_code: str) -> None:
        """Add a country that recognizes this verification."""
        if not self.recognized_countries:
            current_countries = []  # type: List[str]
        else:
            current_countries = list(self.recognized_countries)

        if country_code not in current_countries:
            current_countries.append(country_code)
            self.recognized_countries = current_countries  # type: ignore[assignment]

    def log_step(self, action: str, details: Dict[str, Any]) -> None:
        """Log a step in the verification process."""
        if not self.verification_log:
            current_log = []  # type: List[Dict[str, Any]]
        else:
            current_log = list(self.verification_log)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details,
        }
        current_log.append(log_entry)
        self.verification_log = current_log  # type: ignore[assignment]

    @classmethod
    def create_verification_request(
        cls,
        session: Session,
        patient_id: UUIDType,
        verification_type: str,
        verification_method: VerificationMethod,
        verifier_id: UUIDType,
        verifier_name: str,
        verifier_organization: Optional[str] = None,
        expires_in_days: int = 365,
    ) -> "Verification":
        """Create a new verification request."""
        verification = cls(
            patient_id=patient_id,
            verification_type=verification_type,
            verification_method=verification_method,
            verification_level=VerificationLevel.LOW,  # Will be updated based on evidence
            verifier_id=verifier_id,
            verifier_name=verifier_name,
            verifier_organization=verifier_organization,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
        )

        # Log the creation
        verification.log_step(
            "created", {"verifier": verifier_name, "method": verification_method.value}
        )

        session.add(verification)
        return verification

    @classmethod
    def get_active_verifications(
        cls,
        session: Session,
        patient_id: UUIDType,
        verification_type: Optional[str] = None,
    ) -> List["Verification"]:
        """Get all active verifications for a patient."""
        query = (
            session.query(cls)
            .filter(cls.patient_id == patient_id)
            .filter(cls.status == VerificationStatus.COMPLETED)
            .filter(cls.revoked.is_(False))
        )

        if verification_type:
            query = query.filter(cls.verification_type == verification_type)

        # Filter out expired verifications
        query = query.filter(
            (cls.expires_at.is_(None)) | (cls.expires_at > datetime.utcnow())
        )

        return query.all()

    def to_summary(self) -> Dict[str, Any]:
        """Get a summary of the verification for display."""
        return {
            "id": str(self.id),
            "type": self.verification_type,
            "method": self.verification_method.value,
            "level": self.verification_level.value,
            "status": self.status.value,
            "verifier": {
                "name": self.verifier_name,
                "organization": self.verifier_organization,
            },
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_valid": self.is_valid,
            "confidence_score": self.confidence_score,
            "blockchain_verified": bool(self.blockchain_hash),
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Verification(id={self.id}, type='{self.verification_type}', status='{self.status.value}')>"
