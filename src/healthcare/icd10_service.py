"""
Production ICD-10 Mapping Service for Haven Health Passport.

CRITICAL: This service provides ICD-10 diagnosis code mapping which is essential
for insurance claims, epidemiological reporting, and cross-border health records.
Incorrect mapping can lead to claim denials, incorrect statistics, and
misrepresentation of patient conditions.

This service provides:
- ICD-10-CM code validation
- SNOMED to ICD-10 mapping
- ICD-9 to ICD-10 conversion
- Code description lookup
- Hierarchy navigation
"""

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple, cast

from src.healthcare.hipaa_access_control import (  # Added for HIPAA access control
    AccessLevel,
    require_phi_access,
)
from src.security.secrets_service import get_secrets_service
from src.services.cache_service import CacheService
from src.translation.medical.snomed_service import get_snomed_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ICD10Code:
    """Represents an ICD-10 diagnosis code."""

    code: str
    description: str  # PHI when linked to patient - encrypt in storage
    category: str
    is_billable: bool
    parent_code: Optional[str] = None
    children: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    excludes1: List[str] = field(default_factory=list)  # Never coded together
    excludes2: List[str] = field(default_factory=list)  # Not included here
    code_first: List[str] = field(default_factory=list)
    use_additional: List[str] = field(default_factory=list)


class ICD10Service:
    """
    Production ICD-10 mapping and validation service.

    Provides comprehensive ICD-10 code management including
    validation, mapping, and clinical decision support.
    """

    def __init__(self) -> None:
        """Initialize ICD-10 service with cache and common codes."""
        self.cache_service = CacheService()
        self.cache_ttl = timedelta(days=7)  # ICD-10 codes are stable

        # Initialize with common codes for refugee health
        self._initialize_common_codes()

        # In production, would connect to ICD-10 API
        secrets = get_secrets_service()
        self.icd10_api_key = secrets.get_secret("ICD10_API_KEY", required=False)

        logger.info("Initialized ICD-10 Service")

    def _initialize_common_codes(self) -> None:
        """Initialize commonly used ICD-10 codes for refugee populations."""
        self.common_codes = {
            # Infectious diseases
            "A00": ICD10Code(
                code="A00",
                description="Cholera",
                category="Intestinal infectious diseases",
                is_billable=False,
                children=["A00.0", "A00.1", "A00.9"],
            ),
            "A00.0": ICD10Code(
                code="A00.0",
                description="Cholera due to Vibrio cholerae 01, biovar cholerae",
                category="Intestinal infectious diseases",
                is_billable=True,
                parent_code="A00",
            ),
            "A00.1": ICD10Code(
                code="A00.1",
                description="Cholera due to Vibrio cholerae 01, biovar eltor",
                category="Intestinal infectious diseases",
                is_billable=True,
                parent_code="A00",
            ),
            "A00.9": ICD10Code(
                code="A00.9",
                description="Cholera, unspecified",
                category="Intestinal infectious diseases",
                is_billable=True,
                parent_code="A00",
            ),
            # Tuberculosis
            "A15": ICD10Code(
                code="A15",
                description="Respiratory tuberculosis",
                category="Tuberculosis",
                is_billable=False,
                children=[
                    "A15.0",
                    "A15.4",
                    "A15.5",
                    "A15.6",
                    "A15.7",
                    "A15.8",
                    "A15.9",
                ],
            ),
            "A15.0": ICD10Code(
                code="A15.0",
                description="Tuberculosis of lung",
                category="Tuberculosis",
                is_billable=True,
                parent_code="A15",
            ),
            # Malaria
            "B50": ICD10Code(
                code="B50",
                description="Plasmodium falciparum malaria",
                category="Malaria",
                is_billable=False,
                children=["B50.0", "B50.8", "B50.9"],
            ),
            "B50.9": ICD10Code(
                code="B50.9",
                description="Plasmodium falciparum malaria, unspecified",
                category="Malaria",
                is_billable=True,
                parent_code="B50",
            ),
            # Mental health
            "F43.1": ICD10Code(
                code="F43.1",
                description="Post-traumatic stress disorder (PTSD)",
                category="Trauma and stress-related disorders",
                is_billable=True,
                includes=["Traumatic neurosis"],
            ),
            "F43.10": ICD10Code(
                code="F43.10",
                description="Post-traumatic stress disorder, unspecified",
                category="Trauma and stress-related disorders",
                is_billable=True,
                parent_code="F43.1",
            ),
            # Malnutrition
            "E44": ICD10Code(
                code="E44",
                description="Protein-calorie malnutrition of moderate and mild degree",
                category="Malnutrition",
                is_billable=False,
                children=["E44.0", "E44.1"],
            ),
            "E44.0": ICD10Code(
                code="E44.0",
                description="Moderate protein-calorie malnutrition",
                category="Malnutrition",
                is_billable=True,
                parent_code="E44",
            ),
            # Pregnancy
            "Z33.1": ICD10Code(
                code="Z33.1",
                description="Pregnant state, incidental",
                category="Pregnancy",
                is_billable=True,
                use_additional=["codes from category Z3A for weeks of gestation"],
            ),
            # Diabetes
            "E11": ICD10Code(
                code="E11",
                description="Type 2 diabetes mellitus",
                category="Diabetes mellitus",
                is_billable=False,
                children=[
                    "E11.0",
                    "E11.1",
                    "E11.2",
                    "E11.3",
                    "E11.4",
                    "E11.5",
                    "E11.6",
                    "E11.7",
                    "E11.8",
                    "E11.9",
                ],
                use_additional=["code to identify control using insulin (Z79.4)"],
            ),
            "E11.9": ICD10Code(
                code="E11.9",
                description="Type 2 diabetes mellitus without complications",
                category="Diabetes mellitus",
                is_billable=True,
                parent_code="E11",
            ),
            # Hypertension
            "I10": ICD10Code(
                code="I10",
                description="Essential (primary) hypertension",
                category="Hypertensive diseases",
                is_billable=True,
                includes=[
                    "High blood pressure",
                    "Hypertension (arterial)(benign)(essential)(malignant)(primary)(systemic)",
                ],
                excludes1=[
                    "hypertensive disease complicating pregnancy (O10-O11, O13-O16)"
                ],
            ),
        }

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def validate_code(
        self, code: str
    ) -> Tuple[bool, Optional[ICD10Code], List[str]]:
        """
        Validate an ICD-10 code.

        Args:
            code: ICD-10 code to validate

        Returns:
            Tuple of (is_valid, code_object, issues)
        """
        issues = []

        # Basic format validation
        if not self._validate_format(code):
            issues.append(f"Invalid ICD-10 format: {code}")
            return False, None, issues

        # Normalize code
        normalized_code = code.upper().strip()

        # Check cache
        cache_key = f"icd10:code:{normalized_code}"
        cached = await self.cache_service.get(cache_key)
        if cached:
            code_obj = ICD10Code(**json.loads(cached))
            return True, code_obj, []

        # Check common codes
        if normalized_code in self.common_codes:
            code_obj = self.common_codes[normalized_code]
            # Cache for future use
            await self.cache_service.set(
                cache_key, json.dumps(code_obj.__dict__), ttl=self.cache_ttl
            )
            return True, code_obj, []

        # In production, query ICD-10 API
        if self.icd10_api_key:
            api_result = await self._query_icd10_api(normalized_code)
            if api_result:
                return True, api_result, []

        # Check if it's a valid parent code
        parent_code = normalized_code.split(".")[0]
        if parent_code in self.common_codes:
            issues.append(f"Code {code} not found, but parent {parent_code} exists")
            return False, None, issues

        issues.append(f"ICD-10 code {code} not found")
        return False, None, issues

    def _validate_format(self, code: str) -> bool:
        """Validate ICD-10 code format."""
        # ICD-10 format: Letter + 2 digits, optionally followed by . and up to 4 more characters
        pattern = r"^[A-Z]\d{2}(\.\w{1,4})?$"
        return bool(re.match(pattern, code.upper().strip()))

    async def _query_icd10_api(self, code: str) -> Optional[ICD10Code]:
        """Query external ICD-10 API (placeholder for production)."""
        # In production, this would query CMS or other ICD-10 API
        # For now, return None
        logger.info(f"Would query ICD-10 API for code: {code}")
        return None

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def get_code_description(self, code: str) -> Optional[str]:
        """
        Get description for an ICD-10 code.

        Args:
            code: ICD-10 code

        Returns:
            Description or None if not found
        """
        is_valid, code_obj, _ = await self.validate_code(code)
        if is_valid and code_obj:
            return cast(Optional[str], code_obj.description)
        return None

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def map_from_snomed(self, snomed_code: str) -> List[str]:
        """
        Map SNOMED CT code to ICD-10 codes.

        Args:
            snomed_code: SNOMED CT concept ID

        Returns:
            List of mapped ICD-10 codes
        """
        # Check cache
        cache_key = f"snomed_to_icd10:{snomed_code}"
        cached = await self.cache_service.get(cache_key)
        if cached:
            return cast(List[str], json.loads(cached))

        # Basic mapping for common conditions
        snomed_to_icd10_map = {
            # Infectious diseases
            "63650001": ["A00.9"],  # Cholera
            "56717001": ["A15.0"],  # Tuberculosis of lung
            "76272004": ["B50.9"],  # Malaria
            "37109004": ["B20"],  # HIV disease
            "128241005": ["B15-B19"],  # Viral hepatitis (range)
            # Chronic conditions
            "38341003": ["I10"],  # Hypertension
            "73211009": ["E11.9"],  # Type 2 diabetes without complications
            "195967001": ["J45.909"],  # Asthma, unspecified
            "84114007": ["I50.9"],  # Heart failure, unspecified
            # Mental health
            "47505003": ["F43.10"],  # PTSD
            "35489007": ["F32.9"],  # Major depressive disorder
            "48694002": ["F41.9"],  # Anxiety disorder
            # Maternal health
            "77386006": ["Z33.1"],  # Pregnancy
            "169826009": ["Z34.90"],  # Normal pregnancy supervision
            # Pediatric
            "38907003": ["E44.0"],  # Moderate malnutrition
            "396345004": ["B05.9"],  # Measles without complication
        }

        icd10_codes = snomed_to_icd10_map.get(snomed_code, [])

        # In production, would use SNOMED service for mapping
        if not icd10_codes:
            try:
                snomed_service = get_snomed_service()
                icd10_codes = await snomed_service.map_to_icd10(snomed_code)
            except (RuntimeError, TypeError, ValueError) as e:
                logger.error(f"Failed to map SNOMED {snomed_code} to ICD-10: {e}")

        # Cache the result
        if icd10_codes:
            await self.cache_service.set(
                cache_key, json.dumps(icd10_codes), ttl=self.cache_ttl
            )

        return icd10_codes

    @require_phi_access(AccessLevel.READ)  # Added access control for PHI
    async def get_billable_code(self, code: str) -> Optional[str]:
        """
        Get billable ICD-10 code for a given code.

        Args:
            code: ICD-10 code (may be category)

        Returns:
            Billable code or None
        """
        is_valid, code_obj, _ = await self.validate_code(code)

        if is_valid and code_obj:
            if code_obj.is_billable:
                return code

            # If not billable, try to find billable child
            if code_obj.children:
                for child_code in code_obj.children:
                    child_valid, child_obj, _ = await self.validate_code(child_code)
                    if child_valid and child_obj and child_obj.is_billable:
                        return cast(Optional[str], child_code)

        return None

    async def get_code_hierarchy(self, code: str) -> Dict[str, Any]:
        """
        Get hierarchy information for an ICD-10 code.

        Args:
            code: ICD-10 code

        Returns:
            Hierarchy information including parent and children
        """
        is_valid, code_obj, _ = await self.validate_code(code)

        if not is_valid or not code_obj:
            return {}

        hierarchy = {
            "code": code,
            "description": code_obj.description,
            "is_billable": code_obj.is_billable,
            "parent": None,
            "children": [],
            "siblings": [],
        }

        # Get parent information
        if code_obj.parent_code:
            parent_valid, parent_obj, _ = await self.validate_code(code_obj.parent_code)
            if parent_valid and parent_obj:
                hierarchy["parent"] = {
                    "code": parent_obj.code,
                    "description": parent_obj.description,
                }

                # Get siblings (other children of parent)
                for sibling_code in parent_obj.children:
                    if sibling_code != code:
                        sibling_valid, sibling_obj, _ = await self.validate_code(
                            sibling_code
                        )
                        if sibling_valid and sibling_obj:
                            hierarchy["siblings"].append(
                                {
                                    "code": sibling_obj.code,
                                    "description": sibling_obj.description,
                                    "is_billable": sibling_obj.is_billable,
                                }
                            )

        # Get children
        for child_code in code_obj.children:
            child_valid, child_obj, _ = await self.validate_code(child_code)
            if child_valid and child_obj:
                hierarchy["children"].append(
                    {
                        "code": child_obj.code,
                        "description": child_obj.description,
                        "is_billable": child_obj.is_billable,
                    }
                )

        return hierarchy

    async def check_excludes(
        self, primary_code: str, additional_codes: List[str]
    ) -> List[Dict[str, str]]:
        """
        Check for ICD-10 exclude rules violations.

        Args:
            primary_code: Primary diagnosis code
            additional_codes: List of additional codes

        Returns:
            List of exclude violations
        """
        violations: List[Dict[str, str]] = []

        is_valid, code_obj, _ = await self.validate_code(primary_code)
        if not is_valid or not code_obj:
            return violations

        # Check Excludes1 (never coded together)
        for exclude_code in code_obj.excludes1:
            for additional_code in additional_codes:
                if additional_code.startswith(exclude_code):
                    violations.append(
                        {
                            "type": "excludes1",
                            "primary_code": primary_code,
                            "excluded_code": additional_code,
                            "message": f"{primary_code} excludes {additional_code} - never code together",
                        }
                    )

        # Check Excludes2 (not included here)
        for exclude_code in code_obj.excludes2:
            for additional_code in additional_codes:
                if additional_code.startswith(exclude_code):
                    violations.append(
                        {
                            "type": "excludes2",
                            "primary_code": primary_code,
                            "excluded_code": additional_code,
                            "message": f"{primary_code} excludes {additional_code} - not included in this code",
                        }
                    )

        return violations

    async def get_coding_guidelines(self, code: str) -> Dict[str, Any]:
        """
        Get coding guidelines for an ICD-10 code.

        Args:
            code: ICD-10 code

        Returns:
            Coding guidelines including sequencing rules
        """
        is_valid, code_obj, _ = await self.validate_code(code)

        if not is_valid or not code_obj:
            return {}

        guidelines = {
            "code": code,
            "description": code_obj.description,
            "guidelines": [],
        }

        # Add includes
        if code_obj.includes:
            guidelines["guidelines"].append(
                {
                    "type": "includes",
                    "items": code_obj.includes,
                    "instruction": "This code includes the following conditions",
                }
            )

        # Add excludes
        if code_obj.excludes1:
            guidelines["guidelines"].append(
                {
                    "type": "excludes1",
                    "items": code_obj.excludes1,
                    "instruction": "Never code these conditions together with this code",
                }
            )

        if code_obj.excludes2:
            guidelines["guidelines"].append(
                {
                    "type": "excludes2",
                    "items": code_obj.excludes2,
                    "instruction": "These conditions are not included in this code",
                }
            )

        # Add sequencing
        if code_obj.code_first:
            guidelines["guidelines"].append(
                {
                    "type": "code_first",
                    "items": code_obj.code_first,
                    "instruction": "Code these conditions first when present",
                }
            )

        if code_obj.use_additional:
            guidelines["guidelines"].append(
                {
                    "type": "use_additional",
                    "items": code_obj.use_additional,
                    "instruction": "Use additional codes to identify these conditions",
                }
            )

        return guidelines

    async def convert_from_icd9(self, icd9_code: str) -> List[str]:
        """
        Convert ICD-9 code to ICD-10 (General Equivalence Mappings).

        Args:
            icd9_code: ICD-9 diagnosis code

        Returns:
            List of equivalent ICD-10 codes
        """
        # Basic GEM mapping for common codes
        icd9_to_icd10_map = {
            # Infectious diseases
            "001.0": ["A00.0"],  # Cholera due to Vibrio cholerae
            "011.9": ["A15.0"],  # Pulmonary tuberculosis
            "084.6": ["B50.9"],  # Malaria
            "042": ["B20"],  # HIV disease
            # Chronic conditions
            "401.9": ["I10"],  # Essential hypertension
            "250.00": ["E11.9"],  # Diabetes mellitus without complication
            "493.90": ["J45.909"],  # Asthma
            # Mental health
            "309.81": ["F43.10"],  # PTSD
            "296.20": ["F32.9"],  # Major depressive disorder
            "300.00": ["F41.9"],  # Anxiety state
            # Pregnancy
            "V22.2": ["Z33.1"],  # Pregnant state
        }

        return icd9_to_icd10_map.get(icd9_code, [])


# Thread-safe singleton pattern without global statement


class _ICD10ServiceSingleton:
    """Thread-safe singleton holder for ICD10Service."""

    _instance: Optional[ICD10Service] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ICD10Service:
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ICD10Service()
        return cls._instance


def get_icd10_service() -> ICD10Service:
    """Get or create global ICD-10 service instance."""
    return _ICD10ServiceSingleton.get_instance()
