"""Core compliance matrix data structures."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evidence.evidence_package import CertificationStandard, EvidenceType


class ComplianceStatus(Enum):
    """Compliance status for requirements."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    CERTIFIED = "certified"
    NOT_APPLICABLE = "not_applicable"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"


class ImplementationType(Enum):
    """Types of implementations for compliance."""

    TECHNICAL_CONTROL = "technical_control"
    ADMINISTRATIVE_CONTROL = "administrative_control"
    PHYSICAL_CONTROL = "physical_control"
    POLICY = "policy"
    PROCEDURE = "procedure"
    CONFIGURATION = "configuration"
    CODE_IMPLEMENTATION = "code_implementation"
    DOCUMENTATION = "documentation"


class RiskLevel(Enum):
    """Risk levels for non-compliance."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


@dataclass
class ComplianceMatrixEntry:
    """Individual entry in the compliance matrix."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Standard and requirement information
    standard: CertificationStandard = CertificationStandard.HIPAA
    requirement_id: str = ""
    requirement_title: str = ""
    requirement_description: str = ""
    requirement_category: str = ""

    # Compliance status
    status: ComplianceStatus = ComplianceStatus.NOT_STARTED
    compliance_percentage: float = 0.0

    # Implementation details
    implementation_type: ImplementationType = ImplementationType.TECHNICAL_CONTROL
    implementation_description: str = ""
    implementation_location: str = ""  # File path, module, or system component

    # Evidence and validation
    evidence_ids: List[str] = field(default_factory=list)
    evidence_types_required: List[EvidenceType] = field(default_factory=list)
    validation_method: str = ""
    test_procedures: List[str] = field(default_factory=list)

    # Risk and priority
    mandatory: bool = True
    risk_level: RiskLevel = RiskLevel.MEDIUM
    priority: int = 1  # 1 = highest priority

    # Cross-references
    related_standards: List[CertificationStandard] = field(default_factory=list)
    related_requirements: List[str] = field(
        default_factory=list
    )  # IDs of related requirements
    dependencies: List[str] = field(
        default_factory=list
    )  # IDs of dependent requirements

    # Tracking
    responsible_party: str = ""
    implementation_date: Optional[datetime] = None
    validation_date: Optional[datetime] = None
    last_review_date: Optional[datetime] = None
    next_review_date: Optional[datetime] = None

    # Notes and documentation
    notes: str = ""
    remediation_plan: str = ""
    exceptions: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)

    def calculate_compliance_percentage(self) -> float:
        """Calculate compliance percentage based on evidence and status."""
        if self.status == ComplianceStatus.CERTIFIED:
            return 100.0
        elif self.status == ComplianceStatus.VALIDATED:
            return 95.0
        elif self.status == ComplianceStatus.IMPLEMENTED:
            return 80.0
        elif self.status == ComplianceStatus.IN_PROGRESS:
            # Calculate based on evidence collection
            if self.evidence_types_required:
                collected_types = len(self.evidence_ids)
                required_types = len(self.evidence_types_required)
                return min((collected_types / required_types) * 70, 70)
            return 50.0
        elif self.status == ComplianceStatus.NOT_APPLICABLE:
            return 100.0  # N/A items don't affect compliance
        elif self.status == ComplianceStatus.PARTIALLY_COMPLIANT:
            return 60.0
        elif self.status == ComplianceStatus.NON_COMPLIANT:
            return 0.0
        else:  # NOT_STARTED
            return 0.0

    def is_blocking(self) -> bool:
        """Check if this requirement blocks certification."""
        return self.mandatory and self.status not in [
            ComplianceStatus.IMPLEMENTED,
            ComplianceStatus.VALIDATED,
            ComplianceStatus.CERTIFIED,
            ComplianceStatus.NOT_APPLICABLE,
        ]

    def get_remediation_priority(self) -> int:
        """Calculate remediation priority score (lower = higher priority)."""
        # Base priority on status
        status_priority = {
            ComplianceStatus.NON_COMPLIANT: 0,
            ComplianceStatus.NOT_STARTED: 1,
            ComplianceStatus.PARTIALLY_COMPLIANT: 2,
            ComplianceStatus.IN_PROGRESS: 3,
            ComplianceStatus.IMPLEMENTED: 4,
            ComplianceStatus.VALIDATED: 5,
            ComplianceStatus.CERTIFIED: 6,
            ComplianceStatus.NOT_APPLICABLE: 7,
        }

        # Factor in risk level
        risk_multiplier = {
            RiskLevel.CRITICAL: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 4,
            RiskLevel.MINIMAL: 5,
        }

        base_score = status_priority.get(self.status, 10)
        risk_factor = risk_multiplier.get(self.risk_level, 3)
        mandatory_factor = 1 if self.mandatory else 2

        return base_score * risk_factor * mandatory_factor * self.priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "id": self.id,
            "standard": self.standard.value,
            "requirement_id": self.requirement_id,
            "requirement_title": self.requirement_title,
            "requirement_description": self.requirement_description,
            "requirement_category": self.requirement_category,
            "status": self.status.value,
            "compliance_percentage": self.compliance_percentage,
            "implementation_type": self.implementation_type.value,
            "implementation_description": self.implementation_description,
            "implementation_location": self.implementation_location,
            "evidence_ids": self.evidence_ids,
            "evidence_types_required": [
                et.value for et in self.evidence_types_required
            ],
            "validation_method": self.validation_method,
            "test_procedures": self.test_procedures,
            "mandatory": self.mandatory,
            "risk_level": self.risk_level.value,
            "priority": self.priority,
            "related_standards": [rs.value for rs in self.related_standards],
            "related_requirements": self.related_requirements,
            "dependencies": self.dependencies,
            "responsible_party": self.responsible_party,
            "implementation_date": (
                self.implementation_date.isoformat()
                if self.implementation_date
                else None
            ),
            "validation_date": (
                self.validation_date.isoformat() if self.validation_date else None
            ),
            "last_review_date": (
                self.last_review_date.isoformat() if self.last_review_date else None
            ),
            "next_review_date": (
                self.next_review_date.isoformat() if self.next_review_date else None
            ),
            "notes": self.notes,
            "remediation_plan": self.remediation_plan,
            "exceptions": self.exceptions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
        }


@dataclass
class ComplianceMatrix:
    """Complete compliance matrix for all certification standards."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Healthcare Compliance Matrix"
    description: str = (
        "Comprehensive compliance tracking matrix for healthcare certification standards"
    )
    version: str = "1.0.0"

    # Matrix entries
    entries: Dict[str, ComplianceMatrixEntry] = field(default_factory=dict)

    # Organization
    standards: List[CertificationStandard] = field(default_factory=list)
    categories: Dict[str, List[str]] = field(
        default_factory=dict
    )  # Category -> Entry IDs

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_audit_date: Optional[datetime] = None
    next_audit_date: Optional[datetime] = None

    # Configuration
    auto_calculate_compliance: bool = True
    include_related_standards: bool = True
    track_dependencies: bool = True

    def add_entry(self, entry: ComplianceMatrixEntry) -> None:
        """Add an entry to the matrix."""
        self.entries[entry.id] = entry

        # Update categories
        if entry.requirement_category:
            if entry.requirement_category not in self.categories:
                self.categories[entry.requirement_category] = []
            if entry.id not in self.categories[entry.requirement_category]:
                self.categories[entry.requirement_category].append(entry.id)

        # Update standards list
        if entry.standard not in self.standards:
            self.standards.append(entry.standard)

        # Update timestamps
        self.updated_at = datetime.utcnow()

        # Auto-calculate compliance if enabled
        if self.auto_calculate_compliance:
            entry.compliance_percentage = entry.calculate_compliance_percentage()

    def get_entries_by_standard(
        self, standard: CertificationStandard
    ) -> List[ComplianceMatrixEntry]:
        """Get all entries for a specific standard."""
        return [entry for entry in self.entries.values() if entry.standard == standard]

    def get_entries_by_status(
        self, status: ComplianceStatus
    ) -> List[ComplianceMatrixEntry]:
        """Get all entries with a specific status."""
        return [entry for entry in self.entries.values() if entry.status == status]

    def get_entries_by_category(self, category: str) -> List[ComplianceMatrixEntry]:
        """Get all entries in a specific category."""
        entry_ids = self.categories.get(category, [])
        return [self.entries[eid] for eid in entry_ids if eid in self.entries]

    def get_blocking_requirements(self) -> List[ComplianceMatrixEntry]:
        """Get all requirements that block certification."""
        return [entry for entry in self.entries.values() if entry.is_blocking()]

    def get_high_priority_items(self, limit: int = 10) -> List[ComplianceMatrixEntry]:
        """Get highest priority items for remediation."""
        items = [
            entry
            for entry in self.entries.values()
            if entry.status
            not in [
                ComplianceStatus.VALIDATED,
                ComplianceStatus.CERTIFIED,
                ComplianceStatus.NOT_APPLICABLE,
            ]
        ]

        # Sort by remediation priority
        items.sort(key=lambda x: x.get_remediation_priority())

        return items[:limit]

    def calculate_overall_compliance(self) -> Dict[str, Any]:
        """Calculate overall compliance metrics."""
        total_entries = len(self.entries)
        if total_entries == 0:
            return {
                "overall_percentage": 0.0,
                "by_standard": {},
                "by_status": {},
                "blocking_count": 0,
            }

        # Overall compliance
        total_compliance = sum(
            entry.compliance_percentage for entry in self.entries.values()
        )
        overall_percentage = total_compliance / total_entries

        # By standard
        by_standard = {}
        for standard in self.standards:
            standard_entries = self.get_entries_by_standard(standard)
            if standard_entries:
                standard_compliance = sum(
                    entry.compliance_percentage for entry in standard_entries
                )
                by_standard[standard.value] = {
                    "percentage": standard_compliance / len(standard_entries),
                    "total_requirements": len(standard_entries),
                    "compliant": sum(
                        1
                        for entry in standard_entries
                        if entry.compliance_percentage >= 80
                    ),
                }

        # By status
        by_status = {}
        for status in ComplianceStatus:
            count = len(self.get_entries_by_status(status))
            if count > 0:
                by_status[status.value] = count

        # Blocking requirements
        blocking_count = len(self.get_blocking_requirements())

        return {
            "overall_percentage": overall_percentage,
            "by_standard": by_standard,
            "by_status": by_status,
            "blocking_count": blocking_count,
            "total_requirements": total_entries,
        }

    def update_entry_status(
        self, entry_id: str, new_status: ComplianceStatus, notes: Optional[str] = None
    ) -> bool:
        """Update the status of a matrix entry."""
        if entry_id not in self.entries:
            return False

        entry = self.entries[entry_id]
        entry.status = new_status
        entry.updated_at = datetime.utcnow()

        if notes:
            entry.notes = f"{entry.notes}\n[{datetime.utcnow().isoformat()}] Status changed to {new_status.value}: {notes}".strip()

        # Update compliance percentage
        if self.auto_calculate_compliance:
            entry.compliance_percentage = entry.calculate_compliance_percentage()

        # Update matrix timestamp
        self.updated_at = datetime.utcnow()

        return True

    def link_evidence(self, entry_id: str, evidence_id: str) -> bool:
        """Link evidence to a matrix entry."""
        if entry_id not in self.entries:
            return False

        entry = self.entries[entry_id]
        if evidence_id not in entry.evidence_ids:
            entry.evidence_ids.append(evidence_id)
            entry.updated_at = datetime.utcnow()

            # Recalculate compliance if in progress
            if (
                entry.status == ComplianceStatus.IN_PROGRESS
                and self.auto_calculate_compliance
            ):
                entry.compliance_percentage = entry.calculate_compliance_percentage()

            self.updated_at = datetime.utcnow()
            return True

        return False

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get dependency graph of requirements."""
        graph = {}

        for entry_id, entry in self.entries.items():
            if entry.dependencies:
                graph[entry_id] = entry.dependencies

        return graph

    def validate_dependencies(self) -> List[Dict[str, Any]]:
        """Validate that dependencies are properly satisfied."""
        issues = []

        for entry_id, entry in self.entries.items():
            for dep_id in entry.dependencies:
                if dep_id not in self.entries:
                    issues.append(
                        {
                            "entry_id": entry_id,
                            "issue": "missing_dependency",
                            "dependency_id": dep_id,
                            "message": f"Dependency {dep_id} not found in matrix",
                        }
                    )
                else:
                    dep_entry = self.entries[dep_id]
                    # Check if dependency is satisfied before dependent
                    if entry.status in [
                        ComplianceStatus.VALIDATED,
                        ComplianceStatus.CERTIFIED,
                    ] and dep_entry.status not in [
                        ComplianceStatus.VALIDATED,
                        ComplianceStatus.CERTIFIED,
                    ]:
                        issues.append(
                            {
                                "entry_id": entry_id,
                                "issue": "unsatisfied_dependency",
                                "dependency_id": dep_id,
                                "message": f"Dependency {dep_entry.requirement_title} must be satisfied first",
                            }
                        )

        return issues

    def to_dict(self) -> Dict[str, Any]:
        """Convert matrix to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "standards": [s.value for s in self.standards],
            "categories": self.categories,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_audit_date": (
                self.last_audit_date.isoformat() if self.last_audit_date else None
            ),
            "next_audit_date": (
                self.next_audit_date.isoformat() if self.next_audit_date else None
            ),
            "auto_calculate_compliance": self.auto_calculate_compliance,
            "include_related_standards": self.include_related_standards,
            "track_dependencies": self.track_dependencies,
            "compliance_metrics": self.calculate_overall_compliance(),
        }

    def save_to_file(self, file_path: Path) -> None:
        """Save matrix to JSON file."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: Path) -> "ComplianceMatrix":
        """Load matrix from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)

        # Create matrix
        matrix = cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            version=data["version"],
            standards=[CertificationStandard(s) for s in data["standards"]],
            categories=data["categories"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_audit_date=(
                datetime.fromisoformat(data["last_audit_date"])
                if data["last_audit_date"]
                else None
            ),
            next_audit_date=(
                datetime.fromisoformat(data["next_audit_date"])
                if data["next_audit_date"]
                else None
            ),
            auto_calculate_compliance=data.get("auto_calculate_compliance", True),
            include_related_standards=data.get("include_related_standards", True),
            track_dependencies=data.get("track_dependencies", True),
        )

        # Load entries
        for entry_id, entry_data in data["entries"].items():
            entry = ComplianceMatrixEntry(
                id=entry_data["id"],
                standard=CertificationStandard(entry_data["standard"]),
                requirement_id=entry_data["requirement_id"],
                requirement_title=entry_data["requirement_title"],
                requirement_description=entry_data["requirement_description"],
                requirement_category=entry_data["requirement_category"],
                status=ComplianceStatus(entry_data["status"]),
                compliance_percentage=entry_data["compliance_percentage"],
                implementation_type=ImplementationType(
                    entry_data["implementation_type"]
                ),
                implementation_description=entry_data["implementation_description"],
                implementation_location=entry_data["implementation_location"],
                evidence_ids=entry_data["evidence_ids"],
                evidence_types_required=[
                    EvidenceType(et) for et in entry_data["evidence_types_required"]
                ],
                validation_method=entry_data["validation_method"],
                test_procedures=entry_data["test_procedures"],
                mandatory=entry_data["mandatory"],
                risk_level=RiskLevel(entry_data["risk_level"]),
                priority=entry_data["priority"],
                related_standards=[
                    CertificationStandard(rs) for rs in entry_data["related_standards"]
                ],
                related_requirements=entry_data["related_requirements"],
                dependencies=entry_data["dependencies"],
                responsible_party=entry_data["responsible_party"],
                implementation_date=(
                    datetime.fromisoformat(entry_data["implementation_date"])
                    if entry_data["implementation_date"]
                    else None
                ),
                validation_date=(
                    datetime.fromisoformat(entry_data["validation_date"])
                    if entry_data["validation_date"]
                    else None
                ),
                last_review_date=(
                    datetime.fromisoformat(entry_data["last_review_date"])
                    if entry_data["last_review_date"]
                    else None
                ),
                next_review_date=(
                    datetime.fromisoformat(entry_data["next_review_date"])
                    if entry_data["next_review_date"]
                    else None
                ),
                notes=entry_data["notes"],
                remediation_plan=entry_data["remediation_plan"],
                exceptions=entry_data["exceptions"],
                created_at=datetime.fromisoformat(entry_data["created_at"]),
                updated_at=datetime.fromisoformat(entry_data["updated_at"]),
                tags=entry_data["tags"],
            )
            matrix.entries[entry_id] = entry

        return matrix
