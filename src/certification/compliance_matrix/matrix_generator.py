"""Compliance matrix generator for creating comprehensive compliance tracking."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evidence.evidence_package import CertificationStandard, EvidenceType
from .compliance_matrix import (
    ComplianceMatrix,
    ComplianceMatrixEntry,
    ComplianceStatus,
    ImplementationType,
    RiskLevel,
)

logger = logging.getLogger(__name__)


class ComplianceMatrixGenerator:
    """Generates compliance matrix from standards requirements."""

    def __init__(self, requirements_dir: Optional[Path] = None):
        """Initialize matrix generator.

        Args:
            requirements_dir: Directory containing requirements definitions
        """
        self.requirements_dir = (
            requirements_dir or Path(__file__).parent / "requirements"
        )
        self.requirements_data = self._load_requirements_data()

    def _load_requirements_data(self) -> Dict[str, Any]:
        """Load requirements data from files or use built-in definitions."""
        requirements = {}

        # Try to load from files
        if self.requirements_dir.exists():
            for req_file in self.requirements_dir.glob("*.json"):
                try:
                    with open(req_file, "r") as f:
                        data = json.load(f)
                        standard = data.get("standard")
                        if standard:
                            requirements[standard] = data
                except Exception as e:
                    logger.error(f"Error loading requirements from {req_file}: {e}")

        # Use built-in definitions if no files found
        if not requirements:
            requirements = self._get_builtin_requirements()

        return requirements

    def generate_matrix(
        self, standards: List[CertificationStandard], include_all: bool = False
    ) -> ComplianceMatrix:
        """Generate compliance matrix for specified standards.

        Args:
            standards: List of certification standards to include
            include_all: Include all requirements regardless of applicability

        Returns:
            Generated compliance matrix
        """
        matrix = ComplianceMatrix(
            name="Haven Health Passport Compliance Matrix",
            description="Comprehensive compliance tracking for healthcare certification",
            standards=standards,
        )

        # Generate entries for each standard
        for standard in standards:
            entries = self._generate_standard_entries(standard, include_all)
            for entry in entries:
                matrix.add_entry(entry)

        # Set audit dates
        matrix.last_audit_date = datetime.utcnow()
        matrix.next_audit_date = datetime.utcnow() + timedelta(days=90)

        logger.info(f"Generated compliance matrix with {len(matrix.entries)} entries")

        return matrix

    def _generate_standard_entries(
        self, standard: CertificationStandard, include_all: bool
    ) -> List[ComplianceMatrixEntry]:
        """Generate matrix entries for a specific standard."""
        entries = []

        # Get requirements for standard
        req_data = self.requirements_data.get(standard.value, {})
        requirements = req_data.get("requirements", [])

        for req in requirements:
            # Skip non-applicable requirements unless include_all
            if not include_all and not req.get("applicable", True):
                continue

            entry = ComplianceMatrixEntry(
                standard=standard,
                requirement_id=req.get("id", ""),
                requirement_title=req.get("title", ""),
                requirement_description=req.get("description", ""),
                requirement_category=req.get("category", "General"),
                status=ComplianceStatus.NOT_STARTED,
                implementation_type=ImplementationType(
                    req.get("implementation_type", "technical_control")
                ),
                implementation_description=req.get("implementation_description", ""),
                evidence_types_required=[
                    EvidenceType(et) for et in req.get("evidence_types", [])
                ],
                validation_method=req.get("validation_method", ""),
                test_procedures=req.get("test_procedures", []),
                mandatory=req.get("mandatory", True),
                risk_level=RiskLevel(req.get("risk_level", "medium")),
                priority=req.get("priority", 2),
                related_standards=[
                    CertificationStandard(rs) for rs in req.get("related_standards", [])
                ],
                dependencies=req.get("dependencies", []),
                responsible_party=req.get("responsible_party", "Compliance Team"),
                tags=req.get("tags", []),
            )

            entries.append(entry)

        return entries

    def _get_builtin_requirements(self) -> Dict[str, Any]:
        """Get built-in requirements definitions."""
        return {
            "hipaa": {
                "standard": "hipaa",
                "version": "2013",
                "requirements": [
                    {
                        "id": "164.308(a)(1)(i)",
                        "title": "Security Management Process",
                        "description": "Implement policies and procedures to prevent, detect, contain, and correct security violations",
                        "category": "Administrative Safeguards",
                        "implementation_type": "administrative_control",
                        "evidence_types": [
                            "policy_document",
                            "audit_log",
                            "security_assessment",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "164.308(a)(3)(i)",
                        "title": "Workforce Security",
                        "description": "Implement procedures for authorization and/or supervision of workforce members who work with ePHI",
                        "category": "Administrative Safeguards",
                        "implementation_type": "administrative_control",
                        "evidence_types": [
                            "policy_document",
                            "audit_log",
                            "training_material",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "164.308(a)(4)(i)",
                        "title": "Information Access Management",
                        "description": "Implement policies and procedures for authorizing access to ePHI",
                        "category": "Administrative Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "configuration_snapshot",
                            "audit_log",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "164.308(a)(5)(i)",
                        "title": "Security Awareness and Training",
                        "description": "Implement security awareness and training program for all workforce members",
                        "category": "Administrative Safeguards",
                        "implementation_type": "administrative_control",
                        "evidence_types": [
                            "training_material",
                            "audit_log",
                            "policy_document",
                        ],
                        "mandatory": True,
                        "risk_level": "medium",
                        "priority": 2,
                    },
                    {
                        "id": "164.312(a)(1)",
                        "title": "Access Control",
                        "description": "Implement technical policies and procedures that allow only authorized persons to access ePHI",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "configuration_snapshot",
                            "test_result",
                            "code_review",
                        ],
                        "mandatory": True,
                        "risk_level": "critical",
                        "priority": 1,
                    },
                    {
                        "id": "164.312(a)(2)(i)",
                        "title": "Unique User Identification",
                        "description": "Assign a unique name and/or number for identifying and tracking user identity",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": ["configuration_snapshot", "test_result"],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "164.312(a)(2)(iii)",
                        "title": "Automatic Logoff",
                        "description": "Implement electronic procedures that terminate an electronic session after predetermined time of inactivity",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": ["configuration_snapshot", "test_result"],
                        "mandatory": False,
                        "risk_level": "medium",
                        "priority": 2,
                    },
                    {
                        "id": "164.312(a)(2)(iv)",
                        "title": "Encryption and Decryption",
                        "description": "Implement mechanism to encrypt and decrypt ePHI",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "configuration_snapshot",
                            "test_result",
                            "security_assessment",
                        ],
                        "mandatory": False,
                        "risk_level": "critical",
                        "priority": 1,
                    },
                    {
                        "id": "164.312(b)",
                        "title": "Audit Controls",
                        "description": "Implement hardware, software, and/or procedural mechanisms to record and examine activity in information systems containing ePHI",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "audit_log",
                            "configuration_snapshot",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "164.312(c)(1)",
                        "title": "Integrity",
                        "description": "Implement policies and procedures to protect ePHI from improper alteration or destruction",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "test_result",
                            "configuration_snapshot",
                            "policy_document",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "164.312(e)(1)",
                        "title": "Transmission Security",
                        "description": "Implement technical security measures to guard against unauthorized access to ePHI transmitted over electronic networks",
                        "category": "Technical Safeguards",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "configuration_snapshot",
                            "test_result",
                            "penetration_test",
                        ],
                        "mandatory": True,
                        "risk_level": "critical",
                        "priority": 1,
                    },
                ],
            },
            "gdpr": {
                "standard": "gdpr",
                "version": "2018",
                "requirements": [
                    {
                        "id": "Art.5(1)(f)",
                        "title": "Integrity and Confidentiality",
                        "description": "Process personal data in a manner that ensures appropriate security, including protection against unauthorized processing",
                        "category": "Data Protection Principles",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "security_assessment",
                            "configuration_snapshot",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "Art.25",
                        "title": "Data Protection by Design and Default",
                        "description": "Implement appropriate technical and organizational measures designed to implement data-protection principles",
                        "category": "Controller Obligations",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "code_review",
                            "configuration_snapshot",
                            "compliance_report",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "Art.32",
                        "title": "Security of Processing",
                        "description": "Implement appropriate technical and organizational measures to ensure a level of security appropriate to the risk",
                        "category": "Security",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "security_assessment",
                            "penetration_test",
                            "risk_assessment",
                        ],
                        "mandatory": True,
                        "risk_level": "critical",
                        "priority": 1,
                    },
                    {
                        "id": "Art.33",
                        "title": "Notification of Personal Data Breach",
                        "description": "Notify supervisory authority of personal data breach within 72 hours",
                        "category": "Security",
                        "implementation_type": "procedure",
                        "evidence_types": [
                            "policy_document",
                            "incident_report",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "Art.35",
                        "title": "Data Protection Impact Assessment",
                        "description": "Carry out assessment of impact on protection of personal data where processing likely results in high risk",
                        "category": "Controller Obligations",
                        "implementation_type": "documentation",
                        "evidence_types": ["risk_assessment", "compliance_report"],
                        "mandatory": True,
                        "risk_level": "medium",
                        "priority": 2,
                    },
                ],
            },
            "hl7_fhir": {
                "standard": "hl7_fhir",
                "version": "R4",
                "requirements": [
                    {
                        "id": "FHIR-CONF-1",
                        "title": "Conformance Statement",
                        "description": "Server SHALL provide a conformance statement at the /metadata endpoint",
                        "category": "Core Requirements",
                        "implementation_type": "code_implementation",
                        "evidence_types": [
                            "interoperability_test",
                            "api_documentation",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "medium",
                        "priority": 1,
                    },
                    {
                        "id": "FHIR-SEC-1",
                        "title": "Security Labels",
                        "description": "Support security labels on resources for access control",
                        "category": "Security",
                        "implementation_type": "code_implementation",
                        "evidence_types": ["test_result", "configuration_snapshot"],
                        "mandatory": False,
                        "risk_level": "medium",
                        "priority": 2,
                    },
                    {
                        "id": "FHIR-REST-1",
                        "title": "RESTful API",
                        "description": "Implement RESTful API supporting standard FHIR operations",
                        "category": "API Requirements",
                        "implementation_type": "code_implementation",
                        "evidence_types": [
                            "interoperability_test",
                            "api_documentation",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "FHIR-SEARCH-1",
                        "title": "Search Parameters",
                        "description": "Support standard search parameters for implemented resources",
                        "category": "API Requirements",
                        "implementation_type": "code_implementation",
                        "evidence_types": ["test_result", "api_documentation"],
                        "mandatory": True,
                        "risk_level": "medium",
                        "priority": 2,
                    },
                    {
                        "id": "FHIR-VAL-1",
                        "title": "Resource Validation",
                        "description": "Validate resources against FHIR specifications and profiles",
                        "category": "Data Quality",
                        "implementation_type": "code_implementation",
                        "evidence_types": ["test_result", "interoperability_test"],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                ],
            },
            "iso_27001": {
                "standard": "iso_27001",
                "version": "2013",
                "requirements": [
                    {
                        "id": "A.9.1.1",
                        "title": "Access Control Policy",
                        "description": "An access control policy shall be established, documented and reviewed",
                        "category": "Access Control",
                        "implementation_type": "policy",
                        "evidence_types": ["policy_document", "audit_log"],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                    {
                        "id": "A.12.1.1",
                        "title": "Documented Operating Procedures",
                        "description": "Operating procedures shall be documented and made available",
                        "category": "Operations Security",
                        "implementation_type": "documentation",
                        "evidence_types": ["policy_document", "user_manual"],
                        "mandatory": True,
                        "risk_level": "medium",
                        "priority": 2,
                    },
                    {
                        "id": "A.18.1.3",
                        "title": "Protection of Records",
                        "description": "Records shall be protected from loss, destruction, falsification and unauthorized access",
                        "category": "Compliance",
                        "implementation_type": "technical_control",
                        "evidence_types": [
                            "configuration_snapshot",
                            "audit_log",
                            "test_result",
                        ],
                        "mandatory": True,
                        "risk_level": "high",
                        "priority": 1,
                    },
                ],
            },
        }

    def update_matrix_from_scan(
        self, matrix: ComplianceMatrix, scan_results: Dict[str, Any]
    ) -> None:
        """Update matrix based on automated compliance scan results.

        Args:
            matrix: Compliance matrix to update
            scan_results: Results from automated compliance scanning
        """
        logger.info("Updating matrix from scan results")

        for entry_id, entry in matrix.entries.items():
            # Check if scan results contain information about this requirement
            req_scan = scan_results.get(entry.requirement_id, {})

            if req_scan:
                # Update status based on scan
                if req_scan.get("implemented", False):
                    if req_scan.get("validated", False):
                        entry.status = ComplianceStatus.VALIDATED
                    else:
                        entry.status = ComplianceStatus.IMPLEMENTED
                elif req_scan.get("in_progress", False):
                    entry.status = ComplianceStatus.IN_PROGRESS

                # Update implementation location if found
                if req_scan.get("implementation_location"):
                    entry.implementation_location = req_scan["implementation_location"]

                # Link evidence if found
                for evidence_id in req_scan.get("evidence_ids", []):
                    matrix.link_evidence(entry_id, evidence_id)

                # Update notes with scan findings
                if req_scan.get("findings"):
                    entry.notes = f"{entry.notes}\n[Scan {datetime.utcnow().isoformat()}] {req_scan['findings']}".strip()

        matrix.updated_at = datetime.utcnow()
        logger.info("Matrix updated from scan results")
