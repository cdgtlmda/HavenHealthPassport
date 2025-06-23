"""LOINC Implementation.

This module implements LOINC (Logical Observation Identifiers Names and Codes)
for standardizing laboratory and clinical observations, with focus on tests
commonly needed in refugee healthcare settings. Handles FHIR CodeSystem Resource
validation for LOINC codes.
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "CodeSystem"

# Initialize FHIR validator for LOINC validation
validator = FHIRValidator()

logger = logging.getLogger(__name__)


class LOINCComponent(Enum):
    """LOINC component types (what is measured)."""

    # Hematology
    HEMOGLOBIN = "Hemoglobin"
    HEMATOCRIT = "Hematocrit"
    WBC = "Leukocytes"
    PLATELET = "Platelets"

    # Chemistry
    GLUCOSE = "Glucose"
    CREATININE = "Creatinine"
    UREA_NITROGEN = "Urea nitrogen"

    # Infectious disease
    HIV_AB = "HIV 1+2 Ab"
    HEP_B_SURFACE_AG = "Hepatitis B virus surface Ag"
    HEP_C_AB = "Hepatitis C virus Ab"
    MALARIA_AG = "Plasmodium sp Ag"
    TB_AG = "Mycobacterium tuberculosis Ag"

    # Nutritional markers
    ALBUMIN = "Albumin"
    PREALBUMIN = "Prealbumin"
    VITAMIN_A = "Vitamin A"
    VITAMIN_D = "Vitamin D"
    IRON = "Iron"

    # Pregnancy
    HCG = "Choriogonadotropin"

    # Vital signs
    BODY_TEMP = "Body temperature"
    HEART_RATE = "Heart rate"
    RESP_RATE = "Respiratory rate"
    BP_SYSTOLIC = "Systolic blood pressure"
    BP_DIASTOLIC = "Diastolic blood pressure"
    OXYGEN_SAT = "Oxygen saturation"


class LOINCProperty(Enum):
    """LOINC property types (characteristics of what is measured)."""

    MASS_CONCENTRATION = "MCnc"  # Mass concentration (mg/dL)
    SUBSTANCE_CONCENTRATION = "SCnc"  # Substance concentration (mmol/L)
    CATALYTIC_CONCENTRATION = "CCnc"  # Catalytic concentration (U/L)
    NUMBER_CONCENTRATION = "NCnc"  # Number concentration (#/volume)
    VOLUME_FRACTION = "VFr"  # Volume fraction (%)
    MASS_FRACTION = "MFr"  # Mass fraction (%)
    ARBITRARY_CONCENTRATION = "ACnc"  # Arbitrary concentration
    PRESENCE_ABSENCE = "Ord"  # Ordinal presence/absence
    NARRATIVE = "Nar"  # Narrative/text
    TEMPERATURE = "Temp"  # Temperature
    RATE = "NRat"  # Number rate (per time)
    PRESSURE = "Pres"  # Pressure


class LOINCTiming(Enum):
    """LOINC timing aspects."""

    POINT = "PT"  # Point in time (spot)
    AVERAGE = "Avg"  # Average over time
    MAX = "Max"  # Maximum
    MIN = "Min"  # Minimum
    TWENTY_FOUR_HOUR = "24H"  # 24 hour collection


class LOINCSystem(Enum):
    """LOINC system/specimen types."""

    BLOOD = "Bld"  # Whole blood
    SERUM = "Ser"  # Serum
    PLASMA = "Plas"  # Plasma
    URINE = "Ur"  # Urine
    CSF = "CSF"  # Cerebrospinal fluid
    BODY_FLUID = "Body fld"  # Body fluid
    STOOL = "Stl"  # Stool

    # Microbiological specimens
    THROAT = "Thrt"  # Throat
    NASOPHARYNX = "Nph"  # Nasopharynx
    SPUTUM = "Spt"  # Sputum

    # Vital signs "specimens"
    PATIENT = "^Patient"  # Patient as specimen


class LOINCScale(Enum):
    """LOINC scale types."""

    QUANTITATIVE = "Qn"  # Quantitative
    ORDINAL = "Ord"  # Ordinal
    NOMINAL = "Nom"  # Nominal
    NARRATIVE = "Nar"  # Narrative
    DOCUMENT = "Doc"  # Document


class LOINCMethod(Enum):
    """Common LOINC methods."""

    # General methods
    MANUAL = "Manual"
    AUTOMATED = "Automated"
    ESTIMATED = "Estimated"
    MEASURED = "Measured"

    # Specific test methods
    IMMUNOASSAY = "IA"
    RAPID_TEST = "IA.rapid"
    PCR = "Probe.amp.tar"
    CULTURE = "Cult"
    MICROSCOPY = "Microscopy"
    BLOOD_SMEAR = "Smear.light"
    DIPSTICK = "Test strip"


class LOINCCode:
    """Represents a LOINC code with its components."""

    def __init__(
        self,
        loinc_num: str,
        component: str,
        property_measured: str,
        timing: str,
        system: str,
        scale: str,
        method: Optional[str] = None,
        long_name: Optional[str] = None,
        short_name: Optional[str] = None,
        units: Optional[str] = None,
        normal_range: Optional[Dict] = None,
    ):
        """Initialize LOINC code.

        Args:
            loinc_num: LOINC number
            component: What is measured
            property_measured: Property measured
            timing: Time aspect
            system: System/specimen
            scale: Scale of measurement
            method: Method (optional)
            long_name: Long display name
            short_name: Short display name
            units: Common units
            normal_range: Normal ranges by population
        """
        self.loinc_num = loinc_num
        self.component = component
        self.property = property_measured
        self.timing = timing
        self.system = system
        self.scale = scale
        self.method = method
        self.long_name = long_name or self._generate_long_name()
        self.short_name = short_name
        self.units = units
        self.normal_range = normal_range or {}
        self.order_obs: Optional[str] = None  # Order or observation
        self.class_type: Optional[str] = None  # LOINC class

    def _generate_long_name(self) -> str:
        """Generate long name from components."""
        parts = [self.component, self.property, self.timing, self.system, self.scale]
        if self.method:
            parts.append(self.method)
        return ":".join(parts)

    def is_quantitative(self) -> bool:
        """Check if this is a quantitative test."""
        return self.scale == LOINCScale.QUANTITATIVE.value

    def is_panel(self) -> bool:
        """Check if this is a panel/battery of tests."""
        return "panel" in self.component.lower()

    def get_ucum_units(self) -> Optional[str]:
        """Get UCUM (Unified Code for Units of Measure) units."""
        # Map common units to UCUM
        ucum_map = {
            "mg/dL": "mg/dL",
            "g/dL": "g/dL",
            "mmol/L": "mmol/L",
            "%": "%",
            "10*3/uL": "10*3/uL",
            "10*6/uL": "10*6/uL",
            "/min": "/min",
            "mm[Hg]": "mm[Hg]",
            "Cel": "Cel",
        }
        return ucum_map.get(self.units) if self.units else None


class LOINCRepository:
    """Repository for managing LOINC codes."""

    def __init__(self) -> None:
        """Initialize LOINC repository."""
        self.codes: Dict[str, LOINCCode] = {}
        self.component_index: Dict[str, Set[str]] = {}
        self.class_index: Dict[str, Set[str]] = {}
        self.system_index: Dict[str, Set[str]] = {}
        self._initialize_refugee_health_tests()

    def _initialize_refugee_health_tests(self) -> None:
        """Initialize common LOINC codes for refugee health."""
        # Basic metabolic panel components
        self.add_code(
            LOINCCode(
                "2345-7",
                "Glucose",
                "MCnc",
                "PT",
                "Ser/Plas",
                "Qn",
                units="mg/dL",
                short_name="Glucose SerPl-mCnc",
                normal_range={"adult": (70, 100), "pediatric": (60, 100)},
            )
        )

        # Hemoglobin for anemia screening
        self.add_code(
            LOINCCode(
                "718-7",
                "Hemoglobin",
                "MCnc",
                "PT",
                "Bld",
                "Qn",
                units="g/dL",
                short_name="Hgb Bld-mCnc",
                normal_range={
                    "adult_male": (13.5, 17.5),
                    "adult_female": (12.0, 15.5),
                    "child": (11.0, 14.0),
                },
            )
        )
        # HIV screening
        self.add_code(
            LOINCCode(
                "75622-1",
                "HIV 1+2 Ab",
                "Ord",
                "PT",
                "Ser/Plas",
                "Ord",
                method="IA.rapid",
                short_name="HIV 1+2 Ab SerPl Ql Rapid",
            )
        )

        # Hepatitis B screening
        self.add_code(
            LOINCCode(
                "5195-3",
                "Hepatitis B virus surface Ag",
                "ACnc",
                "PT",
                "Ser",
                "Ord",
                short_name="HBsAg Ser Ql",
            )
        )

        # Malaria rapid test
        self.add_code(
            LOINCCode(
                "51587-4",
                "Plasmodium sp Ag",
                "ACnc",
                "PT",
                "Bld",
                "Ord",
                method="IA.rapid",
                short_name="Malaria Ag Bld Ql Rapid",
            )
        )

        # Tuberculosis test
        self.add_code(
            LOINCCode(
                "71774-4",
                "Mycobacterium tuberculosis DNA",
                "ACnc",
                "PT",
                "Spt",
                "Ord",
                method="Probe.amp.tar",
                short_name="TB DNA Spt Ql PCR",
            )
        )

        # Vital signs
        self.add_code(
            LOINCCode(
                "8310-5",
                "Body temperature",
                "Temp",
                "PT",
                "^Patient",
                "Qn",
                units="Cel",
                short_name="Body temp",
                normal_range={"all": (36.5, 37.5)},
            )
        )

        self.add_code(
            LOINCCode(
                "8867-4",
                "Heart rate",
                "NRat",
                "PT",
                "^Patient",
                "Qn",
                units="/min",
                short_name="Heart rate",
                normal_range={
                    "adult": (60, 100),
                    "child": (70, 120),
                    "infant": (100, 160),
                },
            )
        )

        # Nutritional markers
        self.add_code(
            LOINCCode(
                "1751-7",
                "Albumin",
                "MCnc",
                "PT",
                "Ser/Plas",
                "Qn",
                units="g/dL",
                short_name="Albumin SerPl-mCnc",
                normal_range={"all": (3.5, 5.0)},
            )
        )

        # Pregnancy test
        self.add_code(
            LOINCCode(
                "2118-8",
                "Choriogonadotropin",
                "ACnc",
                "PT",
                "Ur",
                "Ord",
                method="IA.rapid",
                short_name="hCG Ur Ql",
            )
        )

    def add_code(self, code: LOINCCode) -> None:
        """Add a LOINC code to the repository.

        Args:
            code: LOINCCode to add
        """
        self.codes[code.loinc_num] = code

        # Update component index
        component_key = code.component.lower()
        if component_key not in self.component_index:
            self.component_index[component_key] = set()
        self.component_index[component_key].add(code.loinc_num)

        # Update system index
        if code.system not in self.system_index:
            self.system_index[code.system] = set()
        self.system_index[code.system].add(code.loinc_num)

    def get_code(self, loinc_num: str) -> Optional[LOINCCode]:
        """Get a LOINC code by number.

        Args:
            loinc_num: LOINC number

        Returns:
            LOINCCode or None
        """
        return self.codes.get(loinc_num)

    def search_by_component(
        self, component: str, system: Optional[str] = None
    ) -> List[LOINCCode]:
        """Search for LOINC codes by component.

        Args:
            component: Component to search for
            system: Optional system filter

        Returns:
            List of matching LOINC codes
        """
        component_lower = component.lower()
        matching_codes = []

        # Find codes with matching component
        for comp_key, code_nums in self.component_index.items():
            if component_lower in comp_key:
                for code_num in code_nums:
                    code = self.codes[code_num]

                    # Apply system filter if specified
                    if system and code.system != system:
                        continue

                    matching_codes.append(code)

        return matching_codes

    def get_panel_members(self, panel_loinc: str) -> List[LOINCCode]:
        """Get member tests of a panel.

        Args:
            panel_loinc: LOINC number of panel

        Returns:
            List of member test codes
        """
        # Define common panels
        panel_members = {
            "24323-8": [  # Comprehensive metabolic panel
                "2345-7",  # Glucose
                "3094-0",  # Urea nitrogen
                "2160-0",  # Creatinine
                "1751-7",  # Albumin
                "1975-2",  # Bilirubin total
                "1920-8",  # AST
                "1742-6",  # ALT
            ],
            "58410-2": [  # Complete blood count panel
                "718-7",  # Hemoglobin
                "4544-3",  # Hematocrit
                "6690-2",  # WBC count
                "777-3",  # Platelet count
            ],
            "24360-0": [  # Hemoglobin and Hematocrit panel
                "718-7",  # Hemoglobin
                "4544-3",  # Hematocrit
            ],
        }

        member_codes = []
        if panel_loinc in panel_members:
            for member_loinc in panel_members[panel_loinc]:
                code = self.get_code(member_loinc)
                if code:
                    member_codes.append(code)

        return member_codes

    def get_by_specimen_type(self, system: str) -> List[LOINCCode]:
        """Get all tests for a specimen type.

        Args:
            system: Specimen type

        Returns:
            List of LOINC codes for that specimen
        """
        code_nums = self.system_index.get(system, set())
        return [self.codes[num] for num in code_nums]


class LOINCValidator:
    """Validates LOINC codes and results."""

    @staticmethod
    def validate_loinc_format(loinc_num: str) -> Tuple[bool, Optional[str]]:
        """Validate LOINC number format.

        Args:
            loinc_num: LOINC number to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # LOINC format: 1-5 digits, hyphen, 1 digit (check digit)
        pattern = r"^\d{1,5}-\d$"

        if not re.match(pattern, loinc_num):
            return False, "Invalid LOINC format. Expected: #####-#"

        # Validate check digit using mod 10 algorithm
        parts = loinc_num.split("-")
        if not LOINCValidator._validate_check_digit(parts[0], parts[1]):
            return False, "Invalid check digit"

        return True, None

    @staticmethod
    def _validate_check_digit(main_part: str, check_digit: str) -> bool:
        """Validate LOINC check digit using mod 10 algorithm.

        Args:
            main_part: Main part of LOINC number
            check_digit: Check digit

        Returns:
            True if valid
        """
        # Calculate sum with alternating weights
        total = 0
        for i, digit in enumerate(main_part):
            weight = 2 if i % 2 == 0 else 1
            value = int(digit) * weight
            if value > 9:
                value = value // 10 + value % 10
            total += value

        # Check digit should make total divisible by 10
        calculated_check = (10 - (total % 10)) % 10
        return str(calculated_check) == check_digit

    @staticmethod
    def validate_result_units(
        loinc_code: LOINCCode, units: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate that units are appropriate for a LOINC code.

        Args:
            loinc_code: LOINC code
            units: Reported units

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not loinc_code.units:
            return True, None  # No expected units defined

        # Allow exact match
        if units == loinc_code.units:
            return True, None

        # Allow common unit variations
        unit_equivalents = {
            "mg/dL": ["mg/dl", "mg/dL"],
            "g/dL": ["g/dl", "g/dL", "gm/dL"],
            "mmol/L": ["mmol/l", "mmol/L"],
            "%": ["%", "percent"],
            "/min": ["/min", "per min", "bpm"],
            "mm[Hg]": ["mmHg", "mm Hg", "mm[Hg]"],
            "Cel": ["C", "°C", "Cel", "celsius"],
        }

        expected_variants = unit_equivalents.get(loinc_code.units, [loinc_code.units])
        if units in expected_variants:
            return True, None

        return False, f"Invalid units. Expected: {loinc_code.units}, got: {units}"


class RefugeeHealthLOINCPanels:
    """Pre-defined LOINC panels for refugee health screening."""

    INITIAL_SCREENING = {
        "name": "Refugee Initial Health Screening",
        "loinc": "CUSTOM-001",
        "members": [
            "718-7",  # Hemoglobin
            "51587-4",  # Malaria rapid test
            "75622-1",  # HIV rapid test
            "5195-3",  # Hepatitis B surface antigen
            "13955-0",  # Hepatitis C antibody
            "71774-4",  # TB PCR
            "2118-8",  # Pregnancy test (if applicable)
        ],
    }

    NUTRITIONAL_ASSESSMENT = {
        "name": "Nutritional Status Assessment",
        "loinc": "CUSTOM-002",
        "members": [
            "718-7",  # Hemoglobin
            "4544-3",  # Hematocrit
            "1751-7",  # Albumin
            "2885-2",  # Total protein
            "14338-8",  # Prealbumin
            "2284-8",  # Folate
            "2132-9",  # Vitamin B12
        ],
    }

    CHRONIC_DISEASE_SCREENING = {
        "name": "Chronic Disease Screening",
        "loinc": "CUSTOM-003",
        "members": [
            "2345-7",  # Glucose
            "4548-4",  # Hemoglobin A1c
            "2160-0",  # Creatinine
            "2089-1",  # LDL cholesterol
            "2085-9",  # HDL cholesterol
            "2571-8",  # Triglycerides
        ],
    }


# Create global instances
loinc_repository = LOINCRepository()
loinc_validator = LOINCValidator()
