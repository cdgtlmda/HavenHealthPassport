"""
FHIR Terminology Service Integration.

This module integrates the terminology service with the FHIR server,
providing endpoints for terminology operations. Handles FHIR ValueSet and
CodeSystem Resource validation for terminology services.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.healthcare.fhir_terminology_service import (
    get_terminology_service,
)
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

# FHIR resource type for this module
__fhir_resource__ = "ValueSet"

logger = get_logger(__name__)

# Initialize validator
validator = FHIRValidator()

# Create router for terminology endpoints
router = APIRouter(prefix="/fhir", tags=["terminology"])

# Default Query parameters to avoid B008 errors
QUERY_SYSTEM = Query(..., description="Code system URI")
QUERY_CODE = Query(..., description="Code to validate")
QUERY_VERSION_OPTIONAL = Query(None, description="Code system version")
QUERY_DISPLAY_OPTIONAL = Query(None, description="Display to validate")
QUERY_URL = Query(..., description="Value set URL")
QUERY_FILTER_OPTIONAL = Query(None, description="Text filter", alias="filter")
QUERY_OFFSET = Query(0, description="Pagination offset")
QUERY_COUNT = Query(100, description="Number of codes to return")
QUERY_CODE_LOOKUP = Query(..., description="Code to lookup")
QUERY_CODE_A = Query(..., description="First code")
QUERY_CODE_B = Query(..., description="Second code")


class ValidateCodeRequest(BaseModel):
    """Request for code validation."""

    system: str
    code: str
    version: Optional[str] = None
    display: Optional[str] = None


class ExpandValueSetRequest(BaseModel):
    """Request for value set expansion."""

    url: str
    filter: Optional[str] = None
    offset: int = 0
    count: int = 100


class SubsumptionRequest(BaseModel):
    """Request for subsumption testing."""

    system: str
    codeA: str
    codeB: str
    version: Optional[str] = None


@router.get("/CodeSystem/$validate-code")
async def validate_code(
    system: str = QUERY_SYSTEM,
    code: str = QUERY_CODE,
    version: Optional[str] = QUERY_VERSION_OPTIONAL,
    display: Optional[str] = QUERY_DISPLAY_OPTIONAL,
) -> Dict[str, Any]:
    """Validate a code against a code system."""
    service = get_terminology_service()
    result = service.validate_code(system, code, version, display)

    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": result.valid},
            {"name": "message", "valueString": result.message or ""},
            {"name": "display", "valueString": result.display or ""},
        ],
    }


@router.get("/ValueSet/$expand")
async def expand_value_set(
    url: str = QUERY_URL,
    filter_text: Optional[str] = QUERY_FILTER_OPTIONAL,
    offset: int = QUERY_OFFSET,
    count: int = QUERY_COUNT,
) -> Dict[str, Any]:
    """Expand a value set."""
    service = get_terminology_service()
    result = service.expand_value_set(url, filter_text, offset, count)

    return {
        "resourceType": "ValueSet",
        "expansion": {
            "total": result.total,
            "offset": result.offset,
            "contains": result.contains,
        },
    }


@router.get("/CodeSystem/$lookup")
async def lookup_code(
    system: str = QUERY_SYSTEM,
    code: str = QUERY_CODE_LOOKUP,
    version: Optional[str] = QUERY_VERSION_OPTIONAL,
) -> Dict[str, Any]:
    """Lookup details for a code."""
    service = get_terminology_service()
    result = service.lookup_code(system, code, version)

    if not result:
        raise HTTPException(status_code=404, detail="Code not found")

    parameters: List[Dict[str, Any]] = [
        {"name": "name", "valueString": result.name},
        {"name": "display", "valueString": result.display},
    ]

    if result.definition:
        parameters.append({"name": "definition", "valueString": result.definition})

    for designation in result.designations:
        parameters.append(
            {
                "name": "designation",
                "part": [
                    {"name": "language", "valueCode": designation.language},
                    {"name": "value", "valueString": designation.value},
                ],
            }
        )

    return {"resourceType": "Parameters", "parameter": parameters}


@router.get("/CodeSystem/$subsumes")
async def test_subsumption(
    system: str = QUERY_SYSTEM,
    codeA: str = QUERY_CODE_A,
    codeB: str = QUERY_CODE_B,
    version: Optional[str] = QUERY_VERSION_OPTIONAL,
) -> Dict[str, Any]:
    """Test subsumption relationship between codes."""
    service = get_terminology_service()
    result = service.test_subsumption(system, codeA, codeB, version)

    return {
        "resourceType": "Parameters",
        "parameter": [{"name": "outcome", "valueCode": result.outcome}],
    }
