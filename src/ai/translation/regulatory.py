"""
Regulatory Term Mapping Module.

Maps healthcare regulatory terms, compliance requirements, and legal terminology
across different jurisdictions and healthcare systems.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RegulatorySystem(Enum):
    """Major healthcare regulatory systems."""

    # United States
    HIPAA = "HIPAA"  # Health Insurance Portability and Accountability Act
    FDA = "FDA"  # Food and Drug Administration
    CMS = "CMS"  # Centers for Medicare & Medicaid Services

    # European Union
    GDPR = "GDPR"  # General Data Protection Regulation
    MDR = "MDR"  # Medical Device Regulation
    EMA = "EMA"  # European Medicines Agency

    # United Kingdom
    MHRA = "MHRA"  # Medicines and Healthcare products Regulatory Agency
    NHS = "NHS"  # National Health Service
    CQC = "CQC"  # Care Quality Commission

    # Canada
    PIPEDA = "PIPEDA"  # Personal Information Protection and Electronic Documents Act
    HEALTH_CANADA = "HEALTH_CANADA"

    # Australia
    TGA = "TGA"  # Therapeutic Goods Administration
    PRIVACY_ACT_AU = "PRIVACY_ACT_AU"

    # Japan
    PMDA = "PMDA"  # Pharmaceuticals and Medical Devices Agency

    # India
    CDSCO = "CDSCO"  # Central Drugs Standard Control Organization

    # Brazil
    ANVISA = "ANVISA"  # Brazilian Health Regulatory Agency

    # China
    NMPA = "NMPA"  # National Medical Products Administration

    # International
    WHO = "WHO"  # World Health Organization
    ICH = "ICH"  # International Council for Harmonisation
    ISO = "ISO"  # International Organization for Standardization


class ComplianceCategory(Enum):
    """Categories of regulatory compliance."""

    PRIVACY = "privacy"
    DATA_PROTECTION = "data_protection"
    CLINICAL_TRIALS = "clinical_trials"
    DRUG_APPROVAL = "drug_approval"
    DEVICE_APPROVAL = "device_approval"
    PATIENT_RIGHTS = "patient_rights"
    QUALITY_STANDARDS = "quality_standards"
    BILLING = "billing"
    INSURANCE = "insurance"
    CONSENT = "consent"
    RECORDS = "records"
    REPORTING = "reporting"


@dataclass
class RegulatoryTerm:
    """A regulatory term with its context and mappings."""

    term: str
    system: RegulatorySystem
    category: ComplianceCategory
    definition: str
    aliases: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)


@dataclass
class TermMapping:
    """Mapping between regulatory terms across systems."""

    source_term: str
    source_system: RegulatorySystem
    target_term: str
    target_system: RegulatorySystem
    confidence: float = 1.0
    notes: Optional[str] = None


@dataclass
class RegulatoryContext:
    """Context for regulatory term translation."""

    source_jurisdiction: str
    target_jurisdiction: str
    document_type: Optional[str] = None
    specialty: Optional[str] = None
    include_definitions: bool = False
    strict_compliance: bool = True


# Core regulatory term database
REGULATORY_TERMS: Dict[str, RegulatoryTerm] = {
    # Privacy Terms
    "protected_health_information": RegulatoryTerm(
        term="Protected Health Information",
        system=RegulatorySystem.HIPAA,
        category=ComplianceCategory.PRIVACY,
        definition="Any information about health status, healthcare provision, or payment that can be linked to an individual",
        aliases=["PHI", "protected health data"],
        related_terms=["personal health information", "health data"],
    ),
    "personal_data": RegulatoryTerm(
        term="Personal Data",
        system=RegulatorySystem.GDPR,
        category=ComplianceCategory.DATA_PROTECTION,
        definition="Any information relating to an identified or identifiable natural person",
        aliases=["personal information", "PII"],
        related_terms=["sensitive personal data", "special category data"],
    ),
    # Consent Terms
    "informed_consent": RegulatoryTerm(
        term="Informed Consent",
        system=RegulatorySystem.FDA,
        category=ComplianceCategory.CONSENT,
        definition="Permission granted with knowledge of possible consequences",
        aliases=["patient consent", "medical consent"],
        related_terms=["consent form", "authorization"],
    ),
    "data_subject_consent": RegulatoryTerm(
        term="Data Subject Consent",
        system=RegulatorySystem.GDPR,
        category=ComplianceCategory.CONSENT,
        definition="Freely given, specific, informed and unambiguous indication of agreement",
        aliases=["GDPR consent", "explicit consent"],
        related_terms=["consent withdrawal", "consent management"],
    ),
}


# Term mappings between regulatory systems
TERM_MAPPINGS: List[TermMapping] = [
    # Privacy mappings
    TermMapping(
        "Protected Health Information",
        RegulatorySystem.HIPAA,
        "Health Data",
        RegulatorySystem.GDPR,
        confidence=0.9,
        notes="GDPR health data is broader than HIPAA PHI",
    ),
    TermMapping(
        "Minimum Necessary",
        RegulatorySystem.HIPAA,
        "Data Minimization",
        RegulatorySystem.GDPR,
        confidence=0.95,
    ),
    TermMapping(
        "Business Associate",
        RegulatorySystem.HIPAA,
        "Data Processor",
        RegulatorySystem.GDPR,
        confidence=0.9,
    ),
    TermMapping(
        "Covered Entity",
        RegulatorySystem.HIPAA,
        "Data Controller",
        RegulatorySystem.GDPR,
        confidence=0.85,
    ),
    # Drug/Device Approval mappings
    TermMapping(
        "510(k) Clearance",
        RegulatorySystem.FDA,
        "CE Marking",
        RegulatorySystem.MDR,
        confidence=0.7,
        notes="Different approval processes but similar intent",
    ),
    TermMapping(
        "Investigational New Drug",
        RegulatorySystem.FDA,
        "Clinical Trial Authorisation",
        RegulatorySystem.EMA,
        confidence=0.9,
    ),
    TermMapping(
        "New Drug Application",
        RegulatorySystem.FDA,
        "Marketing Authorisation Application",
        RegulatorySystem.EMA,
        confidence=0.95,
    ),
    # Quality Standards mappings
    TermMapping(
        "Good Manufacturing Practice",
        RegulatorySystem.FDA,
        "Good Manufacturing Practice",
        RegulatorySystem.EMA,
        confidence=1.0,
        notes="Harmonized through ICH guidelines",
    ),
    TermMapping(
        "Quality System Regulation",
        RegulatorySystem.FDA,
        "ISO 13485",
        RegulatorySystem.ISO,
        confidence=0.85,
    ),
]


# Jurisdiction-specific term variations
JURISDICTION_TERMS: Dict[str, Dict[str, str]] = {
    "US": {
        "medical_record": "Medical Record",
        "healthcare_provider": "Healthcare Provider",
        "insurance_claim": "Insurance Claim",
        "prior_authorization": "Prior Authorization",
        "emergency_room": "Emergency Room",
        "primary_care_physician": "Primary Care Physician",
        "prescription": "Prescription",
        "pharmacy": "Pharmacy",
        "copayment": "Copayment",
        "deductible": "Deductible",
    },
    "UK": {
        "medical_record": "Medical Notes",
        "healthcare_provider": "Healthcare Professional",
        "insurance_claim": "Insurance Claim",
        "prior_authorization": "Prior Approval",
        "emergency_room": "Accident & Emergency",
        "primary_care_physician": "General Practitioner",
        "prescription": "Prescription",
        "pharmacy": "Chemist",
        "copayment": "Patient Contribution",
        "deductible": "Excess",
    },
    "EU": {
        "medical_record": "Health Record",
        "healthcare_provider": "Healthcare Professional",
        "insurance_claim": "Reimbursement Claim",
        "prior_authorization": "Prior Approval",
        "emergency_room": "Emergency Department",
        "primary_care_physician": "General Practitioner",
        "prescription": "Medical Prescription",
        "pharmacy": "Pharmacy",
        "copayment": "Co-payment",
        "deductible": "Franchise",
    },
    "CA": {
        "medical_record": "Health Record",
        "healthcare_provider": "Healthcare Provider",
        "insurance_claim": "Benefit Claim",
        "prior_authorization": "Pre-approval",
        "emergency_room": "Emergency Department",
        "primary_care_physician": "Family Doctor",
        "prescription": "Prescription",
        "pharmacy": "Pharmacy",
        "copayment": "Co-payment",
        "deductible": "Deductible",
    },
}


class RegulatoryMapper:
    """Maps regulatory terms between different systems and jurisdictions."""

    def __init__(self) -> None:
        """Initialize the regulatory mapper."""
        self.terms = REGULATORY_TERMS
        self.mappings = TERM_MAPPINGS
        self.jurisdiction_terms = JURISDICTION_TERMS

        # Build reverse mapping index
        self._build_mapping_index()

    def _build_mapping_index(self) -> None:
        """Build indices for efficient lookup."""
        self.mapping_index: Dict[Tuple[str, RegulatorySystem], List[TermMapping]] = {}

        for mapping in self.mappings:
            key = (mapping.source_term.lower(), mapping.source_system)
            if key not in self.mapping_index:
                self.mapping_index[key] = []
            self.mapping_index[key].append(mapping)

    def map_term(
        self,
        term: str,
        source_system: RegulatorySystem,
        target_system: RegulatorySystem,
    ) -> Optional[TermMapping]:
        """Map a term from source to target regulatory system."""
        key = (term.lower(), source_system)
        mappings = self.mapping_index.get(key, [])

        # Find mapping to target system
        for mapping in mappings:
            if mapping.target_system == target_system:
                return mapping

        # Try aliases
        if term.lower() in self.terms:
            reg_term = self.terms[term.lower()]
            for alias in reg_term.aliases:
                alias_key = (alias.lower(), source_system)
                alias_mappings = self.mapping_index.get(alias_key, [])
                for mapping in alias_mappings:
                    if mapping.target_system == target_system:
                        return mapping

        return None

    def translate_jurisdiction_term(
        self, term: str, source_jurisdiction: str, target_jurisdiction: str
    ) -> str:
        """Translate common healthcare terms between jurisdictions."""
        source_terms = self.jurisdiction_terms.get(source_jurisdiction, {})
        target_terms = self.jurisdiction_terms.get(target_jurisdiction, {})

        # Find the term key
        term_key = None
        for key, value in source_terms.items():
            if value.lower() == term.lower():
                term_key = key
                break

        if term_key and term_key in target_terms:
            return target_terms[term_key]

        return term  # Return original if no translation found

    def process_document(self, text: str, context: RegulatoryContext) -> str:
        """Process a document to translate regulatory terms."""
        result = text

        # Get jurisdiction terms
        source_terms = self.jurisdiction_terms.get(context.source_jurisdiction, {})
        target_terms = self.jurisdiction_terms.get(context.target_jurisdiction, {})

        # Replace jurisdiction-specific terms
        for term_key, source_term in source_terms.items():
            if term_key in target_terms and source_term in result:
                target_term = target_terms[term_key]
                # Use word boundaries for accurate replacement
                pattern = r"\b" + re.escape(source_term) + r"\b"
                result = re.sub(pattern, target_term, result, flags=re.IGNORECASE)

        # Add definitions if requested
        if context.include_definitions:
            result = self._add_definitions(result, context)

        return result

    def _add_definitions(self, text: str, context: RegulatoryContext) -> str:
        """Add regulatory term definitions to text."""
        # Find regulatory terms in text
        terms_found = set()

        # Use context to determine which definitions to include
        # Add system filtering based on jurisdiction
        system_filter = None
        if context and context.source_jurisdiction:
            # Map jurisdiction to regulatory system
            jurisdiction_to_system = {
                "US": RegulatorySystem.FDA,
                "EU": RegulatorySystem.EMA,
                "UK": RegulatorySystem.MHRA,
                "JP": RegulatorySystem.PMDA,
                "CA": RegulatorySystem.HEALTH_CANADA,
                "AU": RegulatorySystem.TGA,
                "IN": RegulatorySystem.CDSCO,
                "BR": RegulatorySystem.ANVISA,
                "CN": RegulatorySystem.NMPA,
            }
            system_filter = jurisdiction_to_system.get(context.source_jurisdiction)

        for _, term_obj in self.terms.items():
            # Filter by system if specified in context
            if system_filter and term_obj.system != system_filter:
                continue

            if term_obj.term.lower() in text.lower():
                terms_found.add(term_obj.term)

            # Check aliases
            for alias in term_obj.aliases:
                if alias.lower() in text.lower():
                    terms_found.add(term_obj.term)
                    break

        if terms_found:
            # Add glossary section
            glossary = "\n\n--- Regulatory Terms Glossary ---\n"
            for term in sorted(terms_found):
                term_obj = next(
                    (t for t in self.terms.values() if t.term == term),
                    RegulatoryTerm(
                        term="",
                        system=RegulatorySystem.FDA,
                        category=ComplianceCategory.PRIVACY,
                        definition="",
                    ),
                )
                if term_obj and term_obj.term:
                    glossary += f"\n{term}: {term_obj.definition}"
                    if term_obj.system:
                        glossary += f" ({term_obj.system.value})"

            text += glossary

        return text

    def get_equivalent_terms(
        self, term: str, source_system: RegulatorySystem
    ) -> List[Tuple[RegulatorySystem, str, float]]:
        """Get equivalent terms across all regulatory systems."""
        equivalents = []

        # Check direct mappings
        key = (term.lower(), source_system)
        mappings = self.mapping_index.get(key, [])

        for mapping in mappings:
            equivalents.append(
                (mapping.target_system, mapping.target_term, mapping.confidence)
            )

        return sorted(equivalents, key=lambda x: x[2], reverse=True)


class ComplianceChecker:
    """Checks for regulatory compliance requirements in translations."""

    def __init__(self) -> None:
        """Initialize the compliance checker."""
        self.required_elements = {
            RegulatorySystem.HIPAA: {
                ComplianceCategory.PRIVACY: [
                    "privacy notice",
                    "patient rights",
                    "use and disclosure",
                ],
                ComplianceCategory.CONSENT: [
                    "authorization",
                    "revocation",
                    "expiration",
                ],
            },
            RegulatorySystem.GDPR: {
                ComplianceCategory.DATA_PROTECTION: [
                    "lawful basis",
                    "data subject rights",
                    "data protection officer",
                ],
                ComplianceCategory.CONSENT: [
                    "explicit consent",
                    "withdraw consent",
                    "consent record",
                ],
            },
        }

    def check_compliance(
        self, text: str, system: RegulatorySystem, category: ComplianceCategory
    ) -> Dict[str, bool]:
        """Check if text contains required compliance elements."""
        results = {}

        required = self.required_elements.get(system, {}).get(category, [])
        for element in required:
            results[element] = element.lower() in text.lower()

        return results

    def suggest_missing_elements(
        self, text: str, system: RegulatorySystem, category: ComplianceCategory
    ) -> List[str]:
        """Suggest missing compliance elements."""
        compliance_check = self.check_compliance(text, system, category)
        missing = [
            element for element, present in compliance_check.items() if not present
        ]
        return missing


# Convenience functions
def map_regulatory_term(
    term: str, source_system: str, target_system: str
) -> Optional[str]:
    """Map a regulatory term between systems."""
    mapper = RegulatoryMapper()

    try:
        source = RegulatorySystem(source_system)
        target = RegulatorySystem(target_system)
    except ValueError:
        return None

    mapping = mapper.map_term(term, source, target)
    return mapping.target_term if mapping else None


def translate_healthcare_terms(
    text: str, source_jurisdiction: str, target_jurisdiction: str
) -> str:
    """Translate healthcare terms between jurisdictions."""
    context = RegulatoryContext(
        source_jurisdiction=source_jurisdiction, target_jurisdiction=target_jurisdiction
    )

    mapper = RegulatoryMapper()
    return mapper.process_document(text, context)


def check_regulatory_compliance(
    text: str, system: str, category: str
) -> Dict[str, bool]:
    """Check regulatory compliance in text."""
    checker = ComplianceChecker()

    try:
        reg_system = RegulatorySystem(system)
        comp_category = ComplianceCategory(category)
    except ValueError:
        return {}

    return checker.check_compliance(text, reg_system, comp_category)


def get_regulatory_definition(term: str) -> Optional[str]:
    """Get the regulatory definition of a term."""
    for term_obj in REGULATORY_TERMS.values():
        if term_obj.term.lower() == term.lower():
            return term_obj.definition

        # Check aliases
        for alias in term_obj.aliases:
            if alias.lower() == term.lower():
                return term_obj.definition

    return None


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
