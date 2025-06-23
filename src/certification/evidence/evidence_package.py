"""Evidence package data structure for certification compliance. Handles FHIR Resource validation."""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvidenceType(Enum):
    """Types of evidence that can be included in certification packages."""

    TEST_RESULT = "test_result"
    AUDIT_LOG = "audit_log"
    COMPLIANCE_REPORT = "compliance_report"
    SECURITY_ASSESSMENT = "security_assessment"
    PERFORMANCE_METRIC = "performance_metric"
    INTEROPERABILITY_TEST = "interoperability_test"
    CONFIGURATION_SNAPSHOT = "configuration_snapshot"
    API_DOCUMENTATION = "api_documentation"
    USER_MANUAL = "user_manual"
    TRAINING_MATERIAL = "training_material"
    POLICY_DOCUMENT = "policy_document"
    RISK_ASSESSMENT = "risk_assessment"
    INCIDENT_REPORT = "incident_report"
    PENETRATION_TEST = "penetration_test"
    CODE_REVIEW = "code_review"


class CertificationStandard(Enum):
    """Healthcare certification standards."""

    HIPAA = "hipaa"
    GDPR = "gdpr"
    ISO_27001 = "iso_27001"
    ISO_13485 = "iso_13485"
    SOC2 = "soc2"
    HITRUST = "hitrust"
    HL7_FHIR = "hl7_fhir"
    IHE = "ihe"
    CCHIT = "cchit"
    ONC_HIT = "onc_hit"
    NIST_800_53 = "nist_800_53"
    NIST_800_66 = "nist_800_66"


@dataclass
class EvidenceItem:
    """Individual piece of evidence for certification."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EvidenceType = EvidenceType.TEST_RESULT
    title: str = ""
    description: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[Path] = None
    file_hash: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of the evidence content."""
        content_str = json.dumps(self.content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence item to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "file_path": str(self.file_path) if self.file_path else None,
            "file_hash": self.file_hash or self.calculate_hash(),
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class EvidenceRequirement:
    """Requirement that evidence must satisfy for certification."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    standard: CertificationStandard = CertificationStandard.HIPAA
    requirement_id: str = ""
    title: str = ""
    description: str = ""
    evidence_types: List[EvidenceType] = field(default_factory=list)
    mandatory: bool = True
    satisfied: bool = False
    evidence_items: List[str] = field(default_factory=list)  # Evidence item IDs
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert requirement to dictionary."""
        return {
            "id": self.id,
            "standard": self.standard.value,
            "requirement_id": self.requirement_id,
            "title": self.title,
            "description": self.description,
            "evidence_types": [et.value for et in self.evidence_types],
            "mandatory": self.mandatory,
            "satisfied": self.satisfied,
            "evidence_items": self.evidence_items,
            "notes": self.notes,
        }


@dataclass
class EvidencePackage:
    """Complete evidence package for certification submission."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    certification_standards: List[CertificationStandard] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    status: str = "draft"  # draft, review, submitted, approved, rejected
    evidence_items: Dict[str, EvidenceItem] = field(default_factory=dict)
    requirements: Dict[str, EvidenceRequirement] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_evidence(self, evidence: EvidenceItem) -> None:
        """Add evidence item to the package."""
        self.evidence_items[evidence.id] = evidence
        self.updated_at = datetime.utcnow()

    def add_requirement(self, requirement: EvidenceRequirement) -> None:
        """Add certification requirement to the package."""
        self.requirements[requirement.id] = requirement
        self.updated_at = datetime.utcnow()

    def link_evidence_to_requirement(
        self, evidence_id: str, requirement_id: str
    ) -> None:
        """Link evidence item to a requirement."""
        if requirement_id in self.requirements and evidence_id in self.evidence_items:
            if evidence_id not in self.requirements[requirement_id].evidence_items:
                self.requirements[requirement_id].evidence_items.append(evidence_id)
                self.updated_at = datetime.utcnow()

    def get_evidence_by_type(self, evidence_type: EvidenceType) -> List[EvidenceItem]:
        """Get all evidence items of a specific type."""
        return [e for e in self.evidence_items.values() if e.type == evidence_type]

    def get_requirements_by_standard(
        self, standard: CertificationStandard
    ) -> List[EvidenceRequirement]:
        """Get all requirements for a specific certification standard."""
        return [r for r in self.requirements.values() if r.standard == standard]

    def get_unsatisfied_requirements(self) -> List[EvidenceRequirement]:
        """Get all unsatisfied mandatory requirements."""
        return [
            r for r in self.requirements.values() if r.mandatory and not r.satisfied
        ]

    def calculate_completeness(self) -> float:
        """Calculate package completeness percentage."""
        mandatory_reqs = [r for r in self.requirements.values() if r.mandatory]
        if not mandatory_reqs:
            return 100.0
        satisfied_count = sum(1 for r in mandatory_reqs if r.satisfied)
        return (satisfied_count / len(mandatory_reqs)) * 100

    def validate_requirements(self) -> None:
        """Validate and update requirement satisfaction status."""
        for requirement in self.requirements.values():
            # Check if requirement has sufficient evidence
            has_evidence = len(requirement.evidence_items) > 0
            has_correct_types = False

            if has_evidence and requirement.evidence_types:
                # Check if evidence types match requirement
                evidence_types = {
                    self.evidence_items[eid].type
                    for eid in requirement.evidence_items
                    if eid in self.evidence_items
                }
                has_correct_types = any(
                    et in evidence_types for et in requirement.evidence_types
                )

            requirement.satisfied = has_evidence and (
                not requirement.evidence_types or has_correct_types
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert package to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "certification_standards": [
                cs.value for cs in self.certification_standards
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "status": self.status,
            "completeness": self.calculate_completeness(),
            "evidence_items": {k: v.to_dict() for k, v in self.evidence_items.items()},
            "requirements": {k: v.to_dict() for k, v in self.requirements.items()},
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert package to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, file_path: Path) -> None:
        """Save package to JSON file."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def load_from_file(cls, file_path: Path) -> "EvidencePackage":
        """Load package from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)

        # Reconstruct the package
        package = cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            certification_standards=[
                CertificationStandard(cs) for cs in data["certification_standards"]
            ],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            version=data["version"],
            status=data["status"],
            metadata=data.get("metadata", {}),
        )

        # Reconstruct evidence items
        for eid, edata in data.get("evidence_items", {}).items():
            evidence = EvidenceItem(
                id=edata["id"],
                type=EvidenceType(edata["type"]),
                title=edata["title"],
                description=edata["description"],
                content=edata["content"],
                file_path=Path(edata["file_path"]) if edata["file_path"] else None,
                file_hash=edata["file_hash"],
                created_at=datetime.fromisoformat(edata["created_at"]),
                created_by=edata["created_by"],
                tags=edata["tags"],
                metadata=edata.get("metadata", {}),
            )
            package.evidence_items[eid] = evidence

        # Reconstruct requirements
        for rid, rdata in data.get("requirements", {}).items():
            requirement = EvidenceRequirement(
                id=rdata["id"],
                standard=CertificationStandard(rdata["standard"]),
                requirement_id=rdata["requirement_id"],
                title=rdata["title"],
                description=rdata["description"],
                evidence_types=[EvidenceType(et) for et in rdata["evidence_types"]],
                mandatory=rdata["mandatory"],
                satisfied=rdata["satisfied"],
                evidence_items=rdata["evidence_items"],
                notes=rdata.get("notes", ""),
            )
            package.requirements[rid] = requirement

        return package
