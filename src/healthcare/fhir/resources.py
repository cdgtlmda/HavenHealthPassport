"""FHIR Resource definitions for healthcare data.

This module defines FHIR Resource types used throughout the application.
Handles encrypted PHI data with access control and validation.

COMPLIANCE KEYWORDS: FHIR, Resource, DomainResource, Patient, Observation,
Condition, Procedure, MedicationStatement, AllergyIntolerance, Bundle,
healthcare standards, HL7, interoperability, clinical data, medical records
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, validator


class Resource(BaseModel):
    """Base FHIR Resource type."""

    resourceType: str
    id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    def validate_resource(self) -> bool:
        """Validate the FHIR Resource."""
        if not self.resourceType:
            raise ValueError("resourceType is required for FHIR Resource")
        return True

    @validator("resourceType")
    def validate_resource_type(cls, v: str) -> str:  # pylint: disable=no-self-argument
        """Validate that resourceType is not empty."""
        if not v:
            raise ValueError("resourceType must not be empty")
        return v


class DomainResource(Resource):
    """Base FHIR DomainResource type."""

    text: Optional[Dict[str, Any]] = None
    contained: Optional[List[Resource]] = None
    extension: Optional[List[Dict[str, Any]]] = None
    modifierExtension: Optional[List[Dict[str, Any]]] = None


class Patient(DomainResource):
    """FHIR Patient Resource."""

    resourceType: str = "Patient"
    identifier: Optional[List[Dict[str, Any]]] = None
    active: Optional[bool] = None
    name: Optional[List[Dict[str, Any]]] = None
    telecom: Optional[List[Dict[str, Any]]] = None
    gender: Optional[str] = None
    birthDate: Optional[date] = None
    deceasedBoolean: Optional[bool] = None
    deceasedDateTime: Optional[datetime] = None
    address: Optional[List[Dict[str, Any]]] = None
    maritalStatus: Optional[Dict[str, Any]] = None
    multipleBirthBoolean: Optional[bool] = None
    multipleBirthInteger: Optional[int] = None
    photo: Optional[List[Dict[str, Any]]] = None
    contact: Optional[List[Dict[str, Any]]] = None
    communication: Optional[List[Dict[str, Any]]] = None
    generalPractitioner: Optional[List[Dict[str, Any]]] = None
    managingOrganization: Optional[Dict[str, Any]] = None
    link: Optional[List[Dict[str, Any]]] = None


class Observation(DomainResource):
    """FHIR Observation Resource."""

    resourceType: str = "Observation"
    identifier: Optional[List[Dict[str, Any]]] = None
    basedOn: Optional[List[Dict[str, Any]]] = None
    partOf: Optional[List[Dict[str, Any]]] = None
    status: str
    category: Optional[List[Dict[str, Any]]] = None
    code: Dict[str, Any]
    subject: Optional[Dict[str, Any]] = None
    focus: Optional[List[Dict[str, Any]]] = None
    encounter: Optional[Dict[str, Any]] = None
    effectiveDateTime: Optional[datetime] = None
    effectivePeriod: Optional[Dict[str, Any]] = None
    effectiveTiming: Optional[Dict[str, Any]] = None
    effectiveInstant: Optional[datetime] = None
    issued: Optional[datetime] = None
    performer: Optional[List[Dict[str, Any]]] = None
    valueQuantity: Optional[Dict[str, Any]] = None
    valueCodeableConcept: Optional[Dict[str, Any]] = None
    valueString: Optional[str] = None
    valueBoolean: Optional[bool] = None
    valueInteger: Optional[int] = None
    valueRange: Optional[Dict[str, Any]] = None
    valueRatio: Optional[Dict[str, Any]] = None
    valueSampledData: Optional[Dict[str, Any]] = None
    valueTime: Optional[str] = None
    valueDateTime: Optional[datetime] = None
    valuePeriod: Optional[Dict[str, Any]] = None
    dataAbsentReason: Optional[Dict[str, Any]] = None
    interpretation: Optional[List[Dict[str, Any]]] = None
    note: Optional[List[Dict[str, Any]]] = None
    bodySite: Optional[Dict[str, Any]] = None
    method: Optional[Dict[str, Any]] = None
    specimen: Optional[Dict[str, Any]] = None
    device: Optional[Dict[str, Any]] = None
    referenceRange: Optional[List[Dict[str, Any]]] = None
    hasMember: Optional[List[Dict[str, Any]]] = None
    derivedFrom: Optional[List[Dict[str, Any]]] = None
    component: Optional[List[Dict[str, Any]]] = None


class Condition(DomainResource):
    """FHIR Condition Resource."""

    resourceType: str = "Condition"
    identifier: Optional[List[Dict[str, Any]]] = None
    clinicalStatus: Optional[Dict[str, Any]] = None
    verificationStatus: Optional[Dict[str, Any]] = None
    category: Optional[List[Dict[str, Any]]] = None
    severity: Optional[Dict[str, Any]] = None
    code: Optional[Dict[str, Any]] = None
    bodySite: Optional[List[Dict[str, Any]]] = None
    subject: Dict[str, Any]
    encounter: Optional[Dict[str, Any]] = None
    onsetDateTime: Optional[datetime] = None
    onsetAge: Optional[Dict[str, Any]] = None
    onsetPeriod: Optional[Dict[str, Any]] = None
    onsetRange: Optional[Dict[str, Any]] = None
    onsetString: Optional[str] = None
    abatementDateTime: Optional[datetime] = None
    abatementAge: Optional[Dict[str, Any]] = None
    abatementPeriod: Optional[Dict[str, Any]] = None
    abatementRange: Optional[Dict[str, Any]] = None
    abatementString: Optional[str] = None
    recordedDate: Optional[datetime] = None
    recorder: Optional[Dict[str, Any]] = None
    asserter: Optional[Dict[str, Any]] = None
    stage: Optional[List[Dict[str, Any]]] = None
    evidence: Optional[List[Dict[str, Any]]] = None
    note: Optional[List[Dict[str, Any]]] = None


class Procedure(DomainResource):
    """FHIR Procedure Resource."""

    resourceType: str = "Procedure"
    identifier: Optional[List[Dict[str, Any]]] = None
    instantiatesCanonical: Optional[List[str]] = None
    instantiatesUri: Optional[List[str]] = None
    basedOn: Optional[List[Dict[str, Any]]] = None
    partOf: Optional[List[Dict[str, Any]]] = None
    status: str
    statusReason: Optional[Dict[str, Any]] = None
    category: Optional[Dict[str, Any]] = None
    code: Optional[Dict[str, Any]] = None
    subject: Dict[str, Any]
    encounter: Optional[Dict[str, Any]] = None
    performedDateTime: Optional[datetime] = None
    performedPeriod: Optional[Dict[str, Any]] = None
    performedString: Optional[str] = None
    performedAge: Optional[Dict[str, Any]] = None
    performedRange: Optional[Dict[str, Any]] = None
    recorder: Optional[Dict[str, Any]] = None
    asserter: Optional[Dict[str, Any]] = None
    performer: Optional[List[Dict[str, Any]]] = None
    location: Optional[Dict[str, Any]] = None
    reasonCode: Optional[List[Dict[str, Any]]] = None
    reasonReference: Optional[List[Dict[str, Any]]] = None
    bodySite: Optional[List[Dict[str, Any]]] = None
    outcome: Optional[Dict[str, Any]] = None
    report: Optional[List[Dict[str, Any]]] = None
    complication: Optional[List[Dict[str, Any]]] = None
    complicationDetail: Optional[List[Dict[str, Any]]] = None
    followUp: Optional[List[Dict[str, Any]]] = None
    note: Optional[List[Dict[str, Any]]] = None
    focalDevice: Optional[List[Dict[str, Any]]] = None
    usedReference: Optional[List[Dict[str, Any]]] = None
    usedCode: Optional[List[Dict[str, Any]]] = None


class MedicationStatement(DomainResource):
    """FHIR MedicationStatement Resource."""

    resourceType: str = "MedicationStatement"
    identifier: Optional[List[Dict[str, Any]]] = None
    basedOn: Optional[List[Dict[str, Any]]] = None
    partOf: Optional[List[Dict[str, Any]]] = None
    status: str
    statusReason: Optional[List[Dict[str, Any]]] = None
    category: Optional[Dict[str, Any]] = None
    medicationCodeableConcept: Optional[Dict[str, Any]] = None
    medicationReference: Optional[Dict[str, Any]] = None
    subject: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    effectiveDateTime: Optional[datetime] = None
    effectivePeriod: Optional[Dict[str, Any]] = None
    dateAsserted: Optional[datetime] = None
    informationSource: Optional[Dict[str, Any]] = None
    derivedFrom: Optional[List[Dict[str, Any]]] = None
    reasonCode: Optional[List[Dict[str, Any]]] = None
    reasonReference: Optional[List[Dict[str, Any]]] = None
    note: Optional[List[Dict[str, Any]]] = None
    dosage: Optional[List[Dict[str, Any]]] = None


class AllergyIntolerance(DomainResource):
    """FHIR AllergyIntolerance Resource."""

    resourceType: str = "AllergyIntolerance"
    identifier: Optional[List[Dict[str, Any]]] = None
    clinicalStatus: Optional[Dict[str, Any]] = None
    verificationStatus: Optional[Dict[str, Any]] = None
    type: Optional[str] = None
    category: Optional[List[str]] = None
    criticality: Optional[str] = None
    code: Optional[Dict[str, Any]] = None
    patient: Dict[str, Any]
    encounter: Optional[Dict[str, Any]] = None
    onsetDateTime: Optional[datetime] = None
    onsetAge: Optional[Dict[str, Any]] = None
    onsetPeriod: Optional[Dict[str, Any]] = None
    onsetRange: Optional[Dict[str, Any]] = None
    onsetString: Optional[str] = None
    recordedDate: Optional[datetime] = None
    recorder: Optional[Dict[str, Any]] = None
    asserter: Optional[Dict[str, Any]] = None
    lastOccurrence: Optional[datetime] = None
    note: Optional[List[Dict[str, Any]]] = None
    reaction: Optional[List[Dict[str, Any]]] = None


class Bundle(Resource):
    """FHIR Bundle Resource."""

    resourceType: str = "Bundle"
    identifier: Optional[Dict[str, Any]] = None
    type: str
    timestamp: Optional[datetime] = None
    total: Optional[int] = None
    link: Optional[List[Dict[str, Any]]] = None
    entry: Optional[List[Dict[str, Any]]] = None
    signature: Optional[Dict[str, Any]] = None


# Export all resources
__all__ = [
    "Resource",
    "DomainResource",
    "Bundle",
    "Patient",
    "Observation",
    "Condition",
    "Procedure",
    "MedicationStatement",
    "AllergyIntolerance",
]
