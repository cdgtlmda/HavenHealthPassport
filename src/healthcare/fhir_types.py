"""FHIR Resource Type Definitions.

This module provides proper FHIR resource type definitions to ensure
compliance with FHIR standards across the Haven Health Passport system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional, Type, TypedDict, Union


class FHIRResourceBase(TypedDict, total=False):
    """Base FHIR Resource type definition."""

    resourceType: str
    id: Optional[str]
    meta: Optional[Dict[str, Any]]
    implicitRules: Optional[str]
    language: Optional[str]
    text: Optional[Dict[str, Any]]
    contained: Optional[List[Dict[str, Any]]]
    extension: Optional[List[Dict[str, Any]]]
    modifierExtension: Optional[List[Dict[str, Any]]]
    __fhir_type__: str


class FHIRElement(TypedDict, total=False):
    """Base FHIR Element type definition."""

    id: Optional[str]
    extension: Optional[List[Dict[str, Any]]]
    __fhir_type__: str


class FHIRTypedResource(ABC):
    """Abstract base class for FHIR typed resources."""

    @property
    @abstractmethod
    def __fhir_resource_type__(self) -> str:
        """Return the FHIR resource type."""

    @abstractmethod
    def validate_fhir(self) -> Dict[str, Any]:
        """Validate the FHIR resource."""


class FHIRIdentifier(FHIRElement):
    """FHIR Identifier type definition."""

    use: Optional[Literal["usual", "official", "temp", "secondary", "old"]]
    type: Optional[Dict[str, Any]]
    system: Optional[str]
    value: Optional[str]
    period: Optional[Dict[str, Any]]
    assigner: Optional[Dict[str, Any]]


class FHIRCodeableConcept(FHIRElement):
    """FHIR CodeableConcept type definition."""

    coding: Optional[List[Dict[str, Any]]]
    text: Optional[str]


class FHIRReference(FHIRElement):
    """FHIR Reference type definition."""

    reference: Optional[str]
    type: Optional[str]
    identifier: Optional[FHIRIdentifier]
    display: Optional[str]


class FHIRPeriod(FHIRElement):
    """FHIR Period type definition."""

    start: Optional[str]
    end: Optional[str]


class FHIRQuantity(FHIRElement):
    """FHIR Quantity type definition."""

    value: Optional[Union[int, float]]
    comparator: Optional[Literal["<", "<=", ">=", ">"]]
    unit: Optional[str]
    system: Optional[str]
    code: Optional[str]


class FHIRRange(FHIRElement):
    """FHIR Range type definition."""

    low: Optional[FHIRQuantity]
    high: Optional[FHIRQuantity]


class FHIRHumanName(FHIRElement):
    """FHIR HumanName type definition."""

    use: Optional[
        Literal["usual", "official", "temp", "nickname", "anonymous", "old", "maiden"]
    ]
    text: Optional[str]
    family: Optional[str]
    given: Optional[List[str]]
    prefix: Optional[List[str]]
    suffix: Optional[List[str]]
    period: Optional[FHIRPeriod]


class FHIRAddress(FHIRElement):
    """FHIR Address type definition."""

    use: Optional[Literal["home", "work", "temp", "old", "billing"]]
    type: Optional[Literal["postal", "physical", "both"]]
    text: Optional[str]
    line: Optional[List[str]]
    city: Optional[str]
    district: Optional[str]
    state: Optional[str]
    postalCode: Optional[str]
    country: Optional[str]
    period: Optional[FHIRPeriod]


class FHIRContactPoint(FHIRElement):
    """FHIR ContactPoint type definition."""

    system: Optional[Literal["phone", "fax", "email", "pager", "url", "sms", "other"]]
    value: Optional[str]
    use: Optional[Literal["home", "work", "temp", "old", "mobile"]]
    rank: Optional[int]
    period: Optional[FHIRPeriod]


# Resource Type Definitions


class FHIRPatient(FHIRResourceBase):
    """FHIR Patient resource type definition."""

    identifier: Optional[List[FHIRIdentifier]]
    active: Optional[bool]
    name: Optional[List[FHIRHumanName]]
    telecom: Optional[List[FHIRContactPoint]]
    gender: Optional[Literal["male", "female", "other", "unknown"]]
    birthDate: Optional[str]
    deceasedBoolean: Optional[bool]
    deceasedDateTime: Optional[str]
    address: Optional[List[FHIRAddress]]
    maritalStatus: Optional[FHIRCodeableConcept]
    multipleBirthBoolean: Optional[bool]
    multipleBirthInteger: Optional[int]
    photo: Optional[List[Dict[str, Any]]]
    contact: Optional[List[Dict[str, Any]]]
    communication: Optional[List[Dict[str, Any]]]
    generalPractitioner: Optional[List[FHIRReference]]
    managingOrganization: Optional[FHIRReference]
    link: Optional[List[Dict[str, Any]]]


class FHIRObservation(FHIRResourceBase):
    """FHIR Observation resource type definition."""

    identifier: Optional[List[FHIRIdentifier]]
    basedOn: Optional[List[FHIRReference]]
    partOf: Optional[List[FHIRReference]]
    status: Literal[
        "registered",
        "preliminary",
        "final",
        "amended",
        "corrected",
        "cancelled",
        "entered-in-error",
        "unknown",
    ]
    category: Optional[List[FHIRCodeableConcept]]
    code: FHIRCodeableConcept
    subject: Optional[FHIRReference]
    focus: Optional[List[FHIRReference]]
    encounter: Optional[FHIRReference]
    effectiveDateTime: Optional[str]
    effectivePeriod: Optional[FHIRPeriod]
    effectiveTiming: Optional[Dict[str, Any]]
    effectiveInstant: Optional[str]
    issued: Optional[str]
    performer: Optional[List[FHIRReference]]
    valueQuantity: Optional[FHIRQuantity]
    valueCodeableConcept: Optional[FHIRCodeableConcept]
    valueString: Optional[str]
    valueBoolean: Optional[bool]
    valueInteger: Optional[int]
    valueRange: Optional[FHIRRange]
    valueRatio: Optional[Dict[str, Any]]
    valueSampledData: Optional[Dict[str, Any]]
    valueTime: Optional[str]
    valueDateTime: Optional[str]
    valuePeriod: Optional[FHIRPeriod]
    dataAbsentReason: Optional[FHIRCodeableConcept]
    interpretation: Optional[List[FHIRCodeableConcept]]
    note: Optional[List[Dict[str, Any]]]
    bodySite: Optional[FHIRCodeableConcept]
    method: Optional[FHIRCodeableConcept]
    specimen: Optional[FHIRReference]
    device: Optional[FHIRReference]
    referenceRange: Optional[List[Dict[str, Any]]]
    hasMember: Optional[List[FHIRReference]]
    derivedFrom: Optional[List[FHIRReference]]
    component: Optional[List[Dict[str, Any]]]


class FHIRCommunication(FHIRResourceBase):
    """FHIR Communication resource type definition."""

    identifier: Optional[List[FHIRIdentifier]]
    instantiatesCanonical: Optional[List[str]]
    instantiatesUri: Optional[List[str]]
    basedOn: Optional[List[FHIRReference]]
    partOf: Optional[List[FHIRReference]]
    inResponseTo: Optional[List[FHIRReference]]
    status: Literal[
        "preparation",
        "in-progress",
        "not-done",
        "on-hold",
        "stopped",
        "completed",
        "entered-in-error",
        "unknown",
    ]
    statusReason: Optional[FHIRCodeableConcept]
    category: Optional[List[FHIRCodeableConcept]]
    priority: Optional[Literal["routine", "urgent", "asap", "stat"]]
    medium: Optional[List[FHIRCodeableConcept]]
    subject: Optional[FHIRReference]
    topic: Optional[FHIRCodeableConcept]
    about: Optional[List[FHIRReference]]
    encounter: Optional[FHIRReference]
    sent: Optional[str]
    received: Optional[str]
    recipient: Optional[List[FHIRReference]]
    sender: Optional[FHIRReference]
    reasonCode: Optional[List[FHIRCodeableConcept]]
    reasonReference: Optional[List[FHIRReference]]
    payload: Optional[List[Dict[str, Any]]]
    note: Optional[List[Dict[str, Any]]]


class FHIROrganization(FHIRResourceBase):
    """FHIR Organization resource type definition."""

    identifier: Optional[List[FHIRIdentifier]]
    active: Optional[bool]
    type: Optional[List[FHIRCodeableConcept]]
    name: Optional[str]
    alias: Optional[List[str]]
    telecom: Optional[List[FHIRContactPoint]]
    address: Optional[List[FHIRAddress]]
    partOf: Optional[FHIRReference]
    contact: Optional[List[Dict[str, Any]]]
    endpoint: Optional[List[FHIRReference]]


class FHIRBundle(FHIRResourceBase):
    """FHIR Bundle resource type definition."""

    identifier: Optional[FHIRIdentifier]
    type: Literal[
        "document",
        "message",
        "transaction",
        "transaction-response",
        "batch",
        "batch-response",
        "history",
        "searchset",
        "collection",
    ]
    timestamp: Optional[str]
    total: Optional[int]
    link: Optional[List[Dict[str, Any]]]
    entry: Optional[List[Dict[str, Any]]]
    signature: Optional[Dict[str, Any]]


class FHIRAuditEvent(FHIRResourceBase):
    """FHIR AuditEvent resource type definition."""

    type: Dict[str, Any]
    subtype: Optional[List[Dict[str, Any]]]
    action: Optional[
        Literal["C", "R", "U", "D", "E"]
    ]  # Create, Read, Update, Delete, Execute
    period: Optional[Dict[str, Any]]
    recorded: str
    outcome: Optional[
        Literal["0", "4", "8", "12"]
    ]  # Success, Minor failure, Serious failure, Major failure
    outcomeDesc: Optional[str]
    purposeOfEvent: Optional[List[Dict[str, Any]]]
    agent: List[Dict[str, Any]]
    source: Dict[str, Any]
    entity: Optional[List[Dict[str, Any]]]


# Type mapping
FHIR_RESOURCE_TYPES: Dict[str, Type[FHIRResourceBase]] = {
    "Patient": FHIRPatient,
    "Observation": FHIRObservation,
    "Communication": FHIRCommunication,
    "Organization": FHIROrganization,
    "Bundle": FHIRBundle,
    "AuditEvent": FHIRAuditEvent,
}


def validate_fhir_resource_type(resource_data: Dict[str, Any]) -> bool:
    """Validate that a resource has proper FHIR typing.

    Args:
        resource_data: The resource data to validate

    Returns:
        True if the resource has proper FHIR typing
    """
    # Get resource type
    resource_type = resource_data.get("resourceType")
    if not resource_type:
        return False

    # Check if it's a known FHIR resource type
    return resource_type in FHIR_RESOURCE_TYPES


def create_fhir_typed_resource(
    resource_type: str, data: Dict[str, Any]
) -> Optional[FHIRResourceBase]:
    """Create a properly typed FHIR resource.

    Args:
        resource_type: The FHIR resource type
        data: The resource data

    Returns:
        A typed FHIR resource or None if invalid
    """
    if resource_type not in FHIR_RESOURCE_TYPES:
        return None

    resource_class = FHIR_RESOURCE_TYPES[resource_type]

    # Ensure resourceType is set
    data["resourceType"] = resource_type
    data["__fhir_type__"] = resource_type

    # Create typed resource
    return resource_class(**data)


# Export main types
__all__ = [
    "FHIRResourceBase",
    "FHIRElement",
    "FHIRTypedResource",
    "FHIRIdentifier",
    "FHIRCodeableConcept",
    "FHIRReference",
    "FHIRPeriod",
    "FHIRQuantity",
    "FHIRRange",
    "FHIRHumanName",
    "FHIRAddress",
    "FHIRContactPoint",
    "FHIRPatient",
    "FHIRObservation",
    "FHIRCommunication",
    "FHIROrganization",
    "FHIRBundle",
    "FHIRAuditEvent",
    "FHIR_RESOURCE_TYPES",
    "validate_fhir_resource_type",
    "create_fhir_typed_resource",
]
