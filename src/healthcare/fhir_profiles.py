"""FHIR profile definitions for Haven Health Passport.

COMPLIANCE NOTE: This module handles PHI data including patient identifiers,
demographics, and medical records. All PHI data must be encrypted at rest
and in transit using AES-256 encryption or equivalent. Access to this module
requires proper authentication and authorization through the HIPAA access
control system.
"""

from typing import Any, Dict

from src.healthcare.hipaa_access_control import (
    AccessLevel,
    audit_phi_access,
    require_phi_access,
)

# FHIR resource type for this module
__fhir_resource__ = "StructureDefinition"

# Base URL for Haven Health Passport FHIR profiles
HAVEN_FHIR_BASE_URL = "https://havenhealthpassport.org/fhir"

# Refugee-specific FHIR profiles
REFUGEE_PATIENT_PROFILE = f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-patient"

# Extension URLs
REFUGEE_STATUS_EXTENSION = f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-status"
DISPLACEMENT_DATE_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/displacement-date"
)
CAMP_SETTLEMENT_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/camp-settlement-identifier"
)
UNHCR_REGISTRATION_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/unhcr-registration"
)
MULTI_LANGUAGE_NAME_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/multi-language-name"
)
VERIFICATION_STATUS_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/verification-status"
)
CROSS_BORDER_ACCESS_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/cross-border-access"
)
CULTURAL_CONTEXT_EXTENSION = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/cultural-context"
)

# Observation profile for refugee health
REFUGEE_OBSERVATION_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-observation"
)

# Medication profile for refugee health
REFUGEE_MEDICATION_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-medication"
)

# MedicationRequest profile for refugee health
REFUGEE_MEDICATION_REQUEST_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-medication-request"
)

# Condition profile for refugee health
REFUGEE_CONDITION_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-condition"
)

# Procedure profile for refugee health
REFUGEE_PROCEDURE_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-procedure"
)

# DiagnosticReport profile for refugee health
REFUGEE_DIAGNOSTIC_REPORT_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-diagnostic-report"
)

# Documentation profile for refugee health
REFUGEE_DOCUMENTATION_PROFILE = (
    f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/refugee-documentation"
)

# Full profile definitions
REFUGEE_PATIENT_PROFILE_DEF = {
    "resourceType": "StructureDefinition",
    "id": "refugee-patient",
    "url": REFUGEE_PATIENT_PROFILE,
    "name": "RefugeePatient",
    "status": "active",
    "kind": "resource",
    "abstract": False,
    "type": "Patient",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Patient",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Patient.identifier",
                "path": "Patient.identifier",
                "slicing": {
                    "discriminator": [{"type": "value", "path": "system"}],
                    "rules": "open",
                },
                "min": 1,
            },
            {
                "id": "Patient.identifier:unhcrId",
                "path": "Patient.identifier",
                "sliceName": "unhcrId",
                "min": 0,
                "max": "1",
                "type": [{"code": "Identifier"}],
            },
            {
                "id": "Patient.identifier:unhcrId.system",
                "path": "Patient.identifier.system",
                "min": 1,
                "fixedUri": "https://www.unhcr.org/identifiers",
            },
            {
                "id": "Patient.extension",
                "path": "Patient.extension",
                "slicing": {
                    "discriminator": [{"type": "value", "path": "url"}],
                    "rules": "open",
                },
            },
            {
                "id": "Patient.extension:refugeeStatus",
                "path": "Patient.extension",
                "sliceName": "refugeeStatus",
                "min": 0,
                "max": "1",
                "type": [
                    {
                        "code": "Extension",
                        "profile": [REFUGEE_STATUS_EXTENSION],
                    }
                ],
            },
            {
                "id": "Patient.extension:displacementDate",
                "path": "Patient.extension",
                "sliceName": "displacementDate",
                "min": 0,
                "max": "1",
                "type": [
                    {
                        "code": "Extension",
                        "profile": [DISPLACEMENT_DATE_EXTENSION],
                    }
                ],
            },
            {
                "id": "Patient.extension:campSettlement",
                "path": "Patient.extension",
                "sliceName": "campSettlement",
                "min": 0,
                "max": "1",
                "type": [
                    {
                        "code": "Extension",
                        "profile": [CAMP_SETTLEMENT_EXTENSION],
                    }
                ],
            },
            {
                "id": "Patient.extension:culturalContext",
                "path": "Patient.extension",
                "sliceName": "culturalContext",
                "min": 0,
                "max": "1",
                "type": [
                    {
                        "code": "Extension",
                        "profile": [CULTURAL_CONTEXT_EXTENSION],
                    }
                ],
            },
        ]
    },
}

# Refugee Status Extension
REFUGEE_STATUS_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "refugee-status",
    "url": REFUGEE_STATUS_EXTENSION,
    "name": "RefugeeStatus",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "Patient"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Refugee status information",
                "definition": "Information about the refugee status of the patient",
            },
            {
                "id": "Extension.extension:status",
                "path": "Extension.extension",
                "sliceName": "status",
                "min": 1,
                "max": "1",
            },
            {
                "id": "Extension.extension:status.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
                "binding": {
                    "strength": "required",
                    "valueSet": f"{HAVEN_FHIR_BASE_URL}/ValueSet/refugee-status-codes",
                },
            },
            {
                "id": "Extension.extension:countryOfOrigin",
                "path": "Extension.extension",
                "sliceName": "countryOfOrigin",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:countryOfOrigin.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
                "binding": {
                    "strength": "required",
                    "valueSet": "http://hl7.org/fhir/ValueSet/iso3166-1-3",
                },
            },
            {
                "id": "Extension.extension:dateOfArrival",
                "path": "Extension.extension",
                "sliceName": "dateOfArrival",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:dateOfArrival.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "date"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": REFUGEE_STATUS_EXTENSION,
            },
        ]
    },
}

# Displacement Date Extension
DISPLACEMENT_DATE_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "displacement-date",
    "url": DISPLACEMENT_DATE_EXTENSION,
    "name": "DisplacementDate",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "Patient"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Date of displacement",
                "definition": "The date when the person was displaced from their home",
            },
            {
                "id": "Extension.value[x]",
                "path": "Extension.value[x]",
                "type": [{"code": "date"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": DISPLACEMENT_DATE_EXTENSION,
            },
        ]
    },
}

# Camp/Settlement Identifier Extension
CAMP_SETTLEMENT_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "camp-settlement-identifier",
    "url": CAMP_SETTLEMENT_EXTENSION,
    "name": "CampSettlementIdentifier",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "Patient"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Camp or settlement identifier",
                "definition": "Identifier for the refugee camp or settlement",
            },
            {
                "id": "Extension.extension:campName",
                "path": "Extension.extension",
                "sliceName": "campName",
                "min": 1,
                "max": "1",
            },
            {
                "id": "Extension.extension:campName.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.extension:campCode",
                "path": "Extension.extension",
                "sliceName": "campCode",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:campCode.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.extension:sector",
                "path": "Extension.extension",
                "sliceName": "sector",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:sector.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": CAMP_SETTLEMENT_EXTENSION,
            },
        ]
    },
}

# UNHCR Registration Extension
UNHCR_REGISTRATION_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "unhcr-registration",
    "url": UNHCR_REGISTRATION_EXTENSION,
    "name": "UNHCRRegistration",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "Patient"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "UNHCR registration details",
                "definition": "Registration information from UNHCR",
            },
            {
                "id": "Extension.extension:registrationNumber",
                "path": "Extension.extension",
                "sliceName": "registrationNumber",
                "min": 1,
                "max": "1",
            },
            {
                "id": "Extension.extension:registrationNumber.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.extension:registrationDate",
                "path": "Extension.extension",
                "sliceName": "registrationDate",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:registrationDate.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "date"}],
            },
            {
                "id": "Extension.extension:registrationOffice",
                "path": "Extension.extension",
                "sliceName": "registrationOffice",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:registrationOffice.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": UNHCR_REGISTRATION_EXTENSION,
            },
        ]
    },
}

# Multi-Language Name Extension
MULTI_LANGUAGE_NAME_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "multi-language-name",
    "url": MULTI_LANGUAGE_NAME_EXTENSION,
    "name": "MultiLanguageName",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "HumanName"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Name in multiple languages/scripts",
                "definition": "Representation of name in different languages and scripts",
            },
            {
                "id": "Extension.extension:language",
                "path": "Extension.extension",
                "sliceName": "language",
                "min": 1,
                "max": "1",
            },
            {
                "id": "Extension.extension:language.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "code"}],
                "binding": {
                    "strength": "required",
                    "valueSet": "http://hl7.org/fhir/ValueSet/languages",
                },
            },
            {
                "id": "Extension.extension:script",
                "path": "Extension.extension",
                "sliceName": "script",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:script.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "code"}],
            },
            {
                "id": "Extension.extension:pronunciationGuide",
                "path": "Extension.extension",
                "sliceName": "pronunciationGuide",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:pronunciationGuide.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": MULTI_LANGUAGE_NAME_EXTENSION,
            },
        ]
    },
}

# Verification Status Extension
VERIFICATION_STATUS_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "verification-status",
    "url": VERIFICATION_STATUS_EXTENSION,
    "name": "VerificationStatus",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [
        {"type": "element", "expression": "Patient"},
        {"type": "element", "expression": "Practitioner"},
        {"type": "element", "expression": "Organization"},
    ],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Identity verification status",
                "definition": "Current verification status and details",
            },
            {
                "id": "Extension.extension:level",
                "path": "Extension.extension",
                "sliceName": "level",
                "min": 1,
                "max": "1",
            },
            {
                "id": "Extension.extension:level.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "code"}],
                "binding": {
                    "strength": "required",
                    "valueSet": f"{HAVEN_FHIR_BASE_URL}/ValueSet/verification-levels",
                },
            },
            {
                "id": "Extension.extension:timestamp",
                "path": "Extension.extension",
                "sliceName": "timestamp",
                "min": 1,
                "max": "1",
            },
            {
                "id": "Extension.extension:timestamp.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "dateTime"}],
            },
            {
                "id": "Extension.extension:verifier",
                "path": "Extension.extension",
                "sliceName": "verifier",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:verifier.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [
                    {
                        "code": "Reference",
                        "targetProfile": [
                            "http://hl7.org/fhir/StructureDefinition/Practitioner",
                            "http://hl7.org/fhir/StructureDefinition/Organization",
                        ],
                    }
                ],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": VERIFICATION_STATUS_EXTENSION,
            },
        ]
    },
}

# Cross-Border Access Extension
CROSS_BORDER_ACCESS_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "cross-border-access",
    "url": CROSS_BORDER_ACCESS_EXTENSION,
    "name": "CrossBorderAccess",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "Patient"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Cross-border data access permissions",
                "definition": "Countries and organizations permitted to access patient data",
            },
            {
                "id": "Extension.extension:countries",
                "path": "Extension.extension",
                "sliceName": "countries",
                "min": 0,
                "max": "*",
            },
            {
                "id": "Extension.extension:countries.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
                "binding": {
                    "strength": "required",
                    "valueSet": "http://hl7.org/fhir/ValueSet/iso3166-1-2",
                },
            },
            {
                "id": "Extension.extension:duration",
                "path": "Extension.extension",
                "sliceName": "duration",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:duration.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "Period"}],
            },
            {
                "id": "Extension.extension:emergencyAccess",
                "path": "Extension.extension",
                "sliceName": "emergencyAccess",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:emergencyAccess.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "boolean"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": CROSS_BORDER_ACCESS_EXTENSION,
            },
        ]
    },
}

# Cultural Context Extension
CULTURAL_CONTEXT_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "cultural-context",
    "url": CULTURAL_CONTEXT_EXTENSION,
    "name": "CulturalContext",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [{"type": "element", "expression": "Patient"}],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Cultural and religious context",
                "definition": "Cultural, religious, and dietary considerations for patient care",
            },
            {
                "id": "Extension.extension:dietaryRestrictions",
                "path": "Extension.extension",
                "sliceName": "dietaryRestrictions",
                "min": 0,
                "max": "*",
            },
            {
                "id": "Extension.extension:dietaryRestrictions.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
                "binding": {
                    "strength": "extensible",
                    "valueSet": f"{HAVEN_FHIR_BASE_URL}/ValueSet/dietary-restrictions",
                },
            },
            {
                "id": "Extension.extension:religiousAffiliation",
                "path": "Extension.extension",
                "sliceName": "religiousAffiliation",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:religiousAffiliation.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
                "binding": {
                    "strength": "extensible",
                    "valueSet": "http://terminology.hl7.org/ValueSet/v3-ReligiousAffiliation",
                },
            },
            {
                "id": "Extension.extension:genderSpecificRequirements",
                "path": "Extension.extension",
                "sliceName": "genderSpecificRequirements",
                "min": 0,
                "max": "*",
            },
            {
                "id": "Extension.extension:genderSpecificRequirements.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": CULTURAL_CONTEXT_EXTENSION,
            },
        ]
    },
}

# Value Sets
REFUGEE_STATUS_CODES = {
    "resourceType": "ValueSet",
    "id": "refugee-status-codes",
    "url": f"{HAVEN_FHIR_BASE_URL}/ValueSet/refugee-status-codes",
    "name": "RefugeeStatusCodes",
    "status": "active",
    "compose": {
        "include": [
            {
                "system": f"{HAVEN_FHIR_BASE_URL}/CodeSystem/refugee-status",
                "concept": [
                    {"code": "refugee", "display": "Refugee"},
                    {"code": "asylum-seeker", "display": "Asylum Seeker"},
                    {
                        "code": "internally-displaced",
                        "display": "Internally Displaced Person",
                    },
                    {"code": "stateless", "display": "Stateless Person"},
                    {"code": "returnee", "display": "Returnee"},
                ],
            }
        ]
    },
}

VERIFICATION_LEVELS = {
    "resourceType": "ValueSet",
    "id": "verification-levels",
    "url": f"{HAVEN_FHIR_BASE_URL}/ValueSet/verification-levels",
    "name": "VerificationLevels",
    "status": "active",
    "compose": {
        "include": [
            {
                "system": f"{HAVEN_FHIR_BASE_URL}/CodeSystem/verification-levels",
                "concept": [
                    {"code": "unverified", "display": "Unverified"},
                    {"code": "basic", "display": "Basic Verification"},
                    {"code": "standard", "display": "Standard Verification"},
                    {"code": "enhanced", "display": "Enhanced Verification"},
                    {"code": "full", "display": "Full Verification"},
                ],
            }
        ]
    },
}

DIETARY_RESTRICTIONS = {
    "resourceType": "ValueSet",
    "id": "dietary-restrictions",
    "url": f"{HAVEN_FHIR_BASE_URL}/ValueSet/dietary-restrictions",
    "name": "DietaryRestrictions",
    "status": "active",
    "compose": {
        "include": [
            {
                "system": f"{HAVEN_FHIR_BASE_URL}/CodeSystem/dietary-restrictions",
                "concept": [
                    {"code": "halal", "display": "Halal"},
                    {"code": "kosher", "display": "Kosher"},
                    {"code": "vegetarian", "display": "Vegetarian"},
                    {"code": "vegan", "display": "Vegan"},
                    {"code": "gluten-free", "display": "Gluten Free"},
                    {"code": "lactose-free", "display": "Lactose Free"},
                    {"code": "nut-allergy", "display": "Nut Allergy"},
                    {"code": "diabetic", "display": "Diabetic Diet"},
                ],
            }
        ]
    },
}

# Trauma-informed care extension
TRAUMA_ASSESSMENT_EXTENSION_DEF = {
    "resourceType": "StructureDefinition",
    "id": "trauma-assessment",
    "url": f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/trauma-assessment",
    "name": "TraumaAssessment",
    "status": "active",
    "kind": "complex-type",
    "abstract": False,
    "context": [
        {"type": "element", "expression": "Observation"},
        {"type": "element", "expression": "Condition"},
    ],
    "type": "Extension",
    "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Extension",
    "derivation": "constraint",
    "differential": {
        "element": [
            {
                "id": "Extension",
                "path": "Extension",
                "short": "Trauma-informed care assessment",
                "definition": "Assessment of trauma history and care requirements",
            },
            {
                "id": "Extension.extension:traumaType",
                "path": "Extension.extension",
                "sliceName": "traumaType",
                "min": 0,
                "max": "*",
            },
            {
                "id": "Extension.extension:traumaType.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
            },
            {
                "id": "Extension.extension:severity",
                "path": "Extension.extension",
                "sliceName": "severity",
                "min": 0,
                "max": "1",
            },
            {
                "id": "Extension.extension:severity.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "CodeableConcept"}],
            },
            {
                "id": "Extension.extension:triggers",
                "path": "Extension.extension",
                "sliceName": "triggers",
                "min": 0,
                "max": "*",
            },
            {
                "id": "Extension.extension:triggers.value[x]",
                "path": "Extension.extension.value[x]",
                "type": [{"code": "string"}],
            },
            {
                "id": "Extension.url",
                "path": "Extension.url",
                "fixedUri": f"{HAVEN_FHIR_BASE_URL}/StructureDefinition/trauma-assessment",
            },
        ]
    },
}


@require_phi_access(AccessLevel.READ)
@audit_phi_access("get_profile_definitions")
def get_profile_definitions() -> Dict[str, Any]:
    """Get all custom FHIR profile definitions."""
    return {
        "refugee_patient": REFUGEE_PATIENT_PROFILE_DEF,
        "refugee_status_extension": REFUGEE_STATUS_EXTENSION_DEF,
        "displacement_date_extension": DISPLACEMENT_DATE_EXTENSION_DEF,
        "camp_settlement_extension": CAMP_SETTLEMENT_EXTENSION_DEF,
        "unhcr_registration_extension": UNHCR_REGISTRATION_EXTENSION_DEF,
        "multi_language_name_extension": MULTI_LANGUAGE_NAME_EXTENSION_DEF,
        "verification_status_extension": VERIFICATION_STATUS_EXTENSION_DEF,
        "cross_border_access_extension": CROSS_BORDER_ACCESS_EXTENSION_DEF,
        "cultural_context_extension": CULTURAL_CONTEXT_EXTENSION_DEF,
        "trauma_assessment_extension": TRAUMA_ASSESSMENT_EXTENSION_DEF,
        "refugee_status_codes": REFUGEE_STATUS_CODES,
        "verification_levels": VERIFICATION_LEVELS,
        "dietary_restrictions": DIETARY_RESTRICTIONS,
    }


@require_phi_access(AccessLevel.READ)
@audit_phi_access("get_extension_url")
def get_extension_url(extension_name: str) -> str:
    """Get the URL for a named extension."""
    extension_urls = {
        "refugee_status": REFUGEE_STATUS_EXTENSION,
        "displacement_date": DISPLACEMENT_DATE_EXTENSION,
        "camp_settlement": CAMP_SETTLEMENT_EXTENSION,
        "unhcr_registration": UNHCR_REGISTRATION_EXTENSION,
        "multi_language_name": MULTI_LANGUAGE_NAME_EXTENSION,
        "verification_status": VERIFICATION_STATUS_EXTENSION,
        "cross_border_access": CROSS_BORDER_ACCESS_EXTENSION,
        "cultural_context": CULTURAL_CONTEXT_EXTENSION,
    }
    return extension_urls.get(extension_name, "")


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data against Haven Health Passport profiles.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check resource type
    resource_type = fhir_data.get("resourceType")
    if resource_type == "StructureDefinition":
        # Validate structure definition
        required_fields = ["url", "name", "status", "kind"]
        for field in required_fields:
            if field not in fhir_data:
                errors.append(f"Required field '{field}' is missing")

        # Check if it's one of our profiles
        if "url" in fhir_data:
            known_profiles = [
                REFUGEE_PATIENT_PROFILE,
                REFUGEE_OBSERVATION_PROFILE,
                REFUGEE_MEDICATION_PROFILE,
                REFUGEE_CONDITION_PROFILE,
                REFUGEE_PROCEDURE_PROFILE,
                REFUGEE_DOCUMENTATION_PROFILE,
            ]
            if fhir_data["url"] not in known_profiles:
                warnings.append("Unknown Haven Health Passport profile URL")

    elif resource_type == "Extension":
        # Check if it's one of our extensions
        if "url" in fhir_data:
            known_extensions = [
                REFUGEE_STATUS_EXTENSION,
                DISPLACEMENT_DATE_EXTENSION,
                CAMP_SETTLEMENT_EXTENSION,
                UNHCR_REGISTRATION_EXTENSION,
                MULTI_LANGUAGE_NAME_EXTENSION,
                VERIFICATION_STATUS_EXTENSION,
                CROSS_BORDER_ACCESS_EXTENSION,
                CULTURAL_CONTEXT_EXTENSION,
            ]
            if fhir_data["url"] not in known_extensions:
                warnings.append("Unknown Haven Health Passport extension URL")

    else:
        errors.append("Resource type must be StructureDefinition or Extension")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
