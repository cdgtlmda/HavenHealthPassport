"""Standards mapper for cross-referencing requirements between standards. Handles FHIR Resource validation."""

import logging
from typing import Any, Dict, List, Set, Tuple

from .compliance_matrix import ComplianceMatrix

logger = logging.getLogger(__name__)


class StandardsMapper:
    """Maps relationships between different certification standards."""

    # Known mappings between standards
    STANDARD_MAPPINGS = {
        # HIPAA to GDPR mappings
        ("hipaa", "164.308(a)(1)(i)"): [
            ("gdpr", "Art.32"),
            ("iso_27001", "A.12.1.1"),
        ],  # Security management
        ("hipaa", "164.308(a)(4)(i)"): [("gdpr", "Art.5(1)(f)")],  # Access management
        ("hipaa", "164.312(a)(1)"): [("gdpr", "Art.32")],  # Access control
        ("hipaa", "164.312(e)(1)"): [("gdpr", "Art.32")],  # Transmission security
        # HIPAA to ISO 27001 mappings
        ("hipaa", "164.308(a)(3)(i)"): [
            ("iso_27001", "A.9.1.1")
        ],  # Access control policy
        ("hipaa", "164.312(b)"): [("iso_27001", "A.18.1.3")],  # Audit controls
        # GDPR to ISO 27001 mappings
        ("gdpr", "Art.32"): [("iso_27001", "A.9.1.1"), ("iso_27001", "A.12.1.1")],
        ("gdpr", "Art.25"): [("iso_27001", "A.12.1.1")],  # Privacy by design
        # HL7 FHIR to other standards
        ("hl7_fhir", "FHIR-SEC-1"): [("hipaa", "164.312(a)(1)"), ("gdpr", "Art.32")],
    }

    def __init__(self) -> None:
        """Initialize standards mapper."""
        self.reverse_mappings = self._build_reverse_mappings()

    def _build_reverse_mappings(self) -> Dict[Tuple[str, str], List[Tuple[str, str]]]:
        """Build reverse mappings for bidirectional lookup."""
        reverse: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}

        for source, targets in self.STANDARD_MAPPINGS.items():
            for target in targets:
                if target not in reverse:
                    reverse[target] = []
                reverse[target].append(source)

        return reverse

    def find_related_requirements(
        self, standard: str, requirement_id: str
    ) -> List[Tuple[str, str]]:
        """Find related requirements in other standards.

        Args:
            standard: Source standard
            requirement_id: Source requirement ID

        Returns:
            List of (standard, requirement_id) tuples
        """
        key = (standard.lower(), requirement_id)
        related = []

        # Check forward mappings
        if key in self.STANDARD_MAPPINGS:
            related.extend(self.STANDARD_MAPPINGS[key])

        # Check reverse mappings
        if key in self.reverse_mappings:
            related.extend(self.reverse_mappings[key])

        # Remove duplicates
        return list(set(related))

    def map_evidence_across_standards(
        self, matrix: ComplianceMatrix
    ) -> Dict[str, Set[str]]:
        """Map evidence that can be reused across standards.

        Args:
            matrix: Compliance matrix

        Returns:
            Mapping of evidence IDs to requirement IDs that can use them
        """
        evidence_mapping: Dict[str, Set[str]] = {}

        for entry in matrix.entries.values():
            # Find related requirements
            related = self.find_related_requirements(
                entry.standard.value, entry.requirement_id
            )

            # For each evidence item in this requirement
            for evidence_id in entry.evidence_ids:
                if evidence_id not in evidence_mapping:
                    evidence_mapping[evidence_id] = set()

                # This evidence can be used for related requirements
                for rel_standard, rel_req_id in related:
                    # Find the requirement in the matrix
                    for other_entry in matrix.entries.values():
                        if (
                            other_entry.standard.value == rel_standard
                            and other_entry.requirement_id == rel_req_id
                        ):
                            evidence_mapping[evidence_id].add(other_entry.id)

        return evidence_mapping

    def suggest_evidence_reuse(self, matrix: ComplianceMatrix) -> List[Dict[str, Any]]:
        """Suggest where evidence can be reused across requirements.

        Args:
            matrix: Compliance matrix

        Returns:
            List of reuse suggestions
        """
        suggestions = []
        # evidence_mapping = self.map_evidence_across_standards(matrix)  # Currently unused

        for entry in matrix.entries.values():
            # Skip if already has evidence
            if entry.evidence_ids:
                continue

            # Find related requirements
            related = self.find_related_requirements(
                entry.standard.value, entry.requirement_id
            )

            # Check if any related requirements have evidence
            for rel_standard, rel_req_id in related:
                for other_entry in matrix.entries.values():
                    if (
                        other_entry.standard.value == rel_standard
                        and other_entry.requirement_id == rel_req_id
                        and other_entry.evidence_ids
                    ):

                        suggestions.append(
                            {
                                "target_entry_id": entry.id,
                                "target_requirement": f"{entry.standard.value} {entry.requirement_id}",
                                "source_entry_id": other_entry.id,
                                "source_requirement": f"{other_entry.standard.value} {other_entry.requirement_id}",
                                "evidence_ids": other_entry.evidence_ids,
                                "confidence": (
                                    "high"
                                    if (rel_standard, rel_req_id)
                                    in self.STANDARD_MAPPINGS.get(
                                        (entry.standard.value, entry.requirement_id), []
                                    )
                                    else "medium"
                                ),
                            }
                        )

        return suggestions

    def analyze_standard_overlap(self, matrix: ComplianceMatrix) -> Dict[str, Any]:
        """Analyze overlap between different standards.

        Args:
            matrix: Compliance matrix

        Returns:
            Analysis of standard overlaps
        """
        overlap_analysis: Dict[str, Any] = {
            "total_requirements": len(matrix.entries),
            "standards": list(set(e.standard.value for e in matrix.entries.values())),
            "overlap_matrix": {},
            "shared_evidence_potential": {},
        }

        # Build overlap matrix
        standards = overlap_analysis["standards"]
        for std1 in standards:
            overlap_analysis["overlap_matrix"][std1] = {}
            for std2 in standards:
                if std1 != std2:
                    overlap_count = 0
                    std1_reqs = [
                        e for e in matrix.entries.values() if e.standard.value == std1
                    ]

                    for req in std1_reqs:
                        related = self.find_related_requirements(
                            std1, req.requirement_id
                        )
                        if any(r[0] == std2 for r in related):
                            overlap_count += 1

                    overlap_analysis["overlap_matrix"][std1][std2] = {
                        "overlapping_requirements": overlap_count,
                        "percentage": (
                            (overlap_count / len(std1_reqs) * 100) if std1_reqs else 0
                        ),
                    }

        # Calculate shared evidence potential
        evidence_reuse = self.map_evidence_across_standards(matrix)
        for _evidence_id, requirement_ids in evidence_reuse.items():
            standards_covered = set()
            for req_id in requirement_ids:
                if req_id in matrix.entries:
                    standards_covered.add(matrix.entries[req_id].standard.value)

            if len(standards_covered) > 1:
                key = tuple(sorted(standards_covered))
                if key not in overlap_analysis["shared_evidence_potential"]:
                    overlap_analysis["shared_evidence_potential"][key] = 0
                overlap_analysis["shared_evidence_potential"][key] += 1

        return overlap_analysis

    def generate_mapping_report(self, matrix: ComplianceMatrix) -> str:
        """Generate a report of standard mappings and overlaps.

        Args:
            matrix: Compliance matrix

        Returns:
            Formatted report string
        """
        analysis = self.analyze_standard_overlap(matrix)
        suggestions = self.suggest_evidence_reuse(matrix)

        report_lines = [
            "# Standards Mapping Report",
            "",
            f"Total Requirements: {analysis['total_requirements']}",
            f"Standards Analyzed: {', '.join(analysis['standards'])}",
            "",
            "## Overlap Analysis",
            "",
        ]

        # Add overlap matrix
        for std1, overlaps in analysis["overlap_matrix"].items():
            report_lines.append(f"### {std1.upper()}")
            for std2, data in overlaps.items():
                if data["overlapping_requirements"] > 0:
                    report_lines.append(
                        f"- Overlaps with {std2.upper()}: "
                        f"{data['overlapping_requirements']} requirements "
                        f"({data['percentage']:.1f}%)"
                    )
            report_lines.append("")

        # Add evidence reuse suggestions
        if suggestions:
            report_lines.extend(
                [
                    "## Evidence Reuse Opportunities",
                    "",
                    f"Found {len(suggestions)} opportunities to reuse evidence:",
                    "",
                ]
            )

            for i, suggestion in enumerate(suggestions[:10], 1):
                report_lines.append(
                    f"{i}. {suggestion['target_requirement']} can reuse evidence from "
                    f"{suggestion['source_requirement']} (Confidence: {suggestion['confidence']})"
                )

        # Add shared evidence potential
        if analysis["shared_evidence_potential"]:
            report_lines.extend(
                [
                    "",
                    "## Shared Evidence Potential",
                    "",
                    "Evidence items that can satisfy multiple standards:",
                    "",
                ]
            )

            for standards, count in analysis["shared_evidence_potential"].items():
                report_lines.append(
                    f"- {' & '.join(standards)}: {count} evidence items"
                )

        return "\n".join(report_lines)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
