"""Patient Demographics Implementation.

This module implements comprehensive patient demographic data structures
with special considerations for refugee populations, including handling
of uncertain data, cultural sensitivities, and multi-jurisdiction requirements.
Handles FHIR Patient Resource validation and structure.

COMPLIANCE NOTE: This module handles extensive PHI including patient names,
dates of birth, addresses, phone numbers, SSNs, and other identifiers. All
demographic data must be encrypted at rest and in transit. Access control
is critical - implement role-based access with minimum necessary principles.
Special protection required for vulnerable populations (children, victims
of violence). Audit all access to demographic data.
"""

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, cast

from dateutil.relativedelta import relativedelta

from ..healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "Patient"

# Initialize validator for Patient Resource validation
validator = FHIRValidator()

logger = logging.getLogger(__name__)


class Gender(Enum):
    """Gender values following FHIR specifications with extensions."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"

    # Extended for comprehensive care
    TRANSGENDER_MALE = "transgender-male"
    TRANSGENDER_FEMALE = "transgender-female"
    NON_BINARY = "non-binary"
    PREFER_NOT_TO_SAY = "prefer-not-to-say"


class MaritalStatus(Enum):
    """Marital status codes."""

    # FHIR standard codes
    SINGLE = "S"  # Never Married
    MARRIED = "M"  # Married
    DIVORCED = "D"  # Divorced
    WIDOWED = "W"  # Widowed
    SEPARATED = "L"  # Legally Separated
    UNMARRIED = "U"  # Unmarried
    UNKNOWN = "UNK"  # Unknown

    # Extended for refugee contexts
    TRADITIONAL_MARRIAGE = "T"  # Traditional/customary marriage
    POLYGAMOUS = "P"  # Polygamous marriage
    CHILD_MARRIAGE = "C"  # Child marriage (for protection flagging)
    MISSING_SPOUSE = "MS"  # Spouse missing/separated during displacement


class Religion(Enum):
    """Religious affiliation codes."""

    # Major religions
    CHRISTIANITY = "1001"
    ISLAM = "1002"
    HINDUISM = "1003"
    BUDDHISM = "1004"
    JUDAISM = "1005"
    SIKHISM = "1006"
    BAHAI = "1007"
    JAINISM = "1008"
    SHINTO = "1009"
    TAOISM = "1010"

    # Traditional/Indigenous
    TRADITIONAL_AFRICAN = "1020"
    ANIMISM = "1021"

    # Other
    OTHER = "1099"
    NONE = "1100"
    PREFER_NOT_TO_SAY = "1101"
    UNKNOWN = "1102"


class Ethnicity:
    """Ethnicity classifications by region."""

    ETHNICITIES = {
        # East Africa
        "east_africa": {
            "tigray": {"code": "EA001", "countries": ["ET", "ER"]},
            "amhara": {"code": "EA002", "countries": ["ET"]},
            "oromo": {"code": "EA003", "countries": ["ET", "KE"]},
            "somali": {"code": "EA004", "countries": ["SO", "ET", "KE", "DJ"]},
            "afar": {"code": "EA005", "countries": ["ET", "ER", "DJ"]},
            "sidama": {"code": "EA006", "countries": ["ET"]},
            "tigrinya": {"code": "EA007", "countries": ["ER", "ET"]},
            "kikuyu": {"code": "EA008", "countries": ["KE"]},
            "luo": {"code": "EA009", "countries": ["KE", "UG", "TZ"]},
            "kalenjin": {"code": "EA010", "countries": ["KE"]},
            "baganda": {"code": "EA011", "countries": ["UG"]},
            "banyankole": {"code": "EA012", "countries": ["UG"]},
            "acholi": {"code": "EA013", "countries": ["UG", "SS"]},
        },
        # Middle East
        "middle_east": {
            "arab": {"code": "ME001", "countries": ["SY", "IQ", "JO", "LB", "PS"]},
            "kurdish": {"code": "ME002", "countries": ["SY", "IQ", "TR", "IR"]},
            "assyrian": {"code": "ME003", "countries": ["SY", "IQ"]},
            "turkmen": {"code": "ME004", "countries": ["SY", "IQ"]},
            "yazidi": {"code": "ME005", "countries": ["IQ", "SY"]},
            "druze": {"code": "ME006", "countries": ["SY", "LB"]},
            "palestinian": {"code": "ME007", "countries": ["PS", "JO", "LB", "SY"]},
        },
        # South Asia
        "south_asia": {
            "pashtun": {"code": "SA001", "countries": ["AF", "PK"]},
            "tajik": {"code": "SA002", "countries": ["AF", "TJ"]},
            "hazara": {"code": "SA003", "countries": ["AF"]},
            "uzbek": {"code": "SA004", "countries": ["AF", "UZ"]},
            "baloch": {"code": "SA005", "countries": ["PK", "AF", "IR"]},
            "sindhi": {"code": "SA006", "countries": ["PK"]},
            "punjabi": {"code": "SA007", "countries": ["PK", "IN"]},
            "bengali": {"code": "SA008", "countries": ["BD", "IN"]},
            "rohingya": {"code": "SA009", "countries": ["MM", "BD"]},
        },
    }

    @classmethod
    def get_ethnicity_code(cls, ethnicity_name: str) -> Optional[str]:
        """Get ethnicity code from name."""
        ethnicity_lower = ethnicity_name.lower()

        for _, ethnicities in cls.ETHNICITIES.items():
            for name, info in ethnicities.items():
                if name == ethnicity_lower:
                    return str(info["code"])

        return None

    @classmethod
    def get_ethnicity_info(cls, code: str) -> Optional[Dict]:
        """Get ethnicity information from code."""
        for region, ethnicities in cls.ETHNICITIES.items():
            for name, info in ethnicities.items():
                if info["code"] == code:
                    return {
                        "name": name,
                        "region": region,
                        "countries": info["countries"],
                    }

        return None


class DateAccuracy(Enum):
    """Accuracy levels for dates (especially birth dates)."""

    EXACT = "exact"  # Known exact date
    MONTH_YEAR = "month-year"  # Know month and year only
    YEAR_ONLY = "year"  # Know year only
    ESTIMATED = "estimated"  # Estimated based on appearance/events
    UNKNOWN = "unknown"  # Completely unknown


class AgeEstimator:
    """Utilities for estimating age when birth date is uncertain."""

    # Life events that can help estimate age
    LIFE_EVENTS = {
        "started_school": {"typical_age": 6, "range": (5, 8)},
        "finished_primary": {"typical_age": 12, "range": (10, 14)},
        "married": {"typical_age": 20, "range": (15, 30)},
        "first_child": {"typical_age": 22, "range": (16, 35)},
        "fled_country": {"typical_age": None, "range": None},  # Variable
    }

    @classmethod
    def estimate_birth_year_from_age(
        cls, estimated_age: int, reference_date: Optional[date] = None
    ) -> int:
        """Estimate birth year from current age estimate.

        Args:
            estimated_age: Estimated current age
            reference_date: Date of estimation (default: today)

        Returns:
            Estimated birth year
        """
        ref_date = reference_date or date.today()
        return ref_date.year - estimated_age

    @classmethod
    def estimate_age_from_events(cls, events: List[Dict[str, Any]]) -> Optional[int]:
        """Estimate current age from life events.

        Args:
            events: List of life events with dates

        Returns:
            Estimated current age or None
        """
        current_date = date.today()
        age_estimates: List[int] = []

        for event in events:
            event_type = event.get("type")
            event_date = event.get("date")

            if event_type in cls.LIFE_EVENTS and event_date:
                event_info = cls.LIFE_EVENTS[event_type]
                if cast(Dict[str, Any], event_info)["typical_age"]:
                    # Calculate age at event
                    years_since = relativedelta(current_date, event_date).years
                    estimated_age = (
                        cast(Dict[str, Any], event_info)["typical_age"] + years_since
                    )
                    age_estimates.append(estimated_age)

        if age_estimates:
            # Return average of estimates
            return int(sum(age_estimates) / len(age_estimates))

        return None

    @classmethod
    def create_estimated_birth_date(
        cls, estimated_age: int, accuracy: DateAccuracy
    ) -> Dict[str, Any]:
        """Create birth date structure with accuracy information.

        Args:
            estimated_age: Estimated age in years
            accuracy: Accuracy level of the estimate

        Returns:
            Birth date structure with metadata
        """
        birth_year = cls.estimate_birth_year_from_age(estimated_age)

        if accuracy == DateAccuracy.YEAR_ONLY:
            birth_date = f"{birth_year}"
            display = f"Born around {birth_year}"
        elif accuracy == DateAccuracy.ESTIMATED:
            birth_date = f"{birth_year}-07-01"  # Default to mid-year
            display = f"Approximately {estimated_age} years old"
        else:
            birth_date = f"{birth_year}-01-01"  # Default to Jan 1
            display = f"Age approximately {estimated_age}"

        return {
            "value": birth_date,
            "accuracy": accuracy.value,
            "estimated_age": estimated_age,
            "display": display,
            "extension": [
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/date-accuracy",
                    "valueCode": accuracy.value,
                }
            ],
        }


class Demographics:
    """Patient demographics structure."""

    def __init__(self) -> None:
        """Initialize demographics."""
        self.gender: Optional[Gender] = None
        self.birth_date: Optional[Dict[str, Any]] = None
        self.deceased: Optional[bool] = None
        self.deceased_date: Optional[date] = None
        self.marital_status: Optional[MaritalStatus] = None
        self.religion: Optional[Religion] = None
        self.ethnicity: Optional[str] = None
        self.nationality: Optional[str] = None
        self.languages: List[str] = []
        self.education_level: Optional[str] = None
        self.occupation: Optional[str] = None
        self.family_size: Optional[int] = None
        self.household_head: Optional[bool] = None
        self.special_needs: List[str] = []
        self.protection_concerns: List[str] = []
        self.validator = FHIRValidator()

    def validate(self) -> bool:
        """Validate demographics data.

        Returns:
            True if valid, False otherwise
        """
        try:
            # Validate required fields
            if not self.gender:
                return False

            # Validate birth date if present
            if self.birth_date:
                if "value" not in self.birth_date:
                    return False

            # Validate languages
            if self.languages and not all(
                isinstance(lang, str) for lang in self.languages
            ):
                return False

            return True
        except (AttributeError, KeyError, TypeError, ValueError):
            return False

    def set_gender(self, gender: Gender) -> "Demographics":
        """Set gender."""
        self.gender = gender
        return self

    def set_birth_date(
        self,
        birth_date: Union[str, date, Dict],
        accuracy: DateAccuracy = DateAccuracy.EXACT,
    ) -> "Demographics":
        """Set birth date with accuracy information."""
        if isinstance(birth_date, dict):
            self.birth_date = birth_date
        elif isinstance(birth_date, date):
            self.birth_date = {
                "value": birth_date.isoformat(),
                "accuracy": accuracy.value,
                "display": birth_date.strftime("%B %d, %Y"),
            }
        elif isinstance(birth_date, str):
            self.birth_date = {
                "value": birth_date,
                "accuracy": accuracy.value,
                "display": birth_date,
            }
        return self

    def set_estimated_age(
        self, estimated_age: int, accuracy: DateAccuracy = DateAccuracy.ESTIMATED
    ) -> "Demographics":
        """Set birth date from estimated age."""
        self.birth_date = AgeEstimator.create_estimated_birth_date(
            estimated_age, accuracy
        )
        return self

    def set_deceased(
        self, deceased: bool, deceased_date: Optional[date] = None
    ) -> "Demographics":
        """Set deceased status."""
        self.deceased = deceased
        self.deceased_date = deceased_date
        return self

    def set_marital_status(self, status: MaritalStatus) -> "Demographics":
        """Set marital status."""
        self.marital_status = status
        return self

    def set_religion(self, religion: Religion) -> "Demographics":
        """Set religion."""
        self.religion = religion
        return self

    def set_ethnicity(self, ethnicity: str) -> "Demographics":
        """Set ethnicity."""
        self.ethnicity = ethnicity
        return self

    def set_nationality(self, nationality: str) -> "Demographics":
        """Set nationality (ISO country code)."""
        self.nationality = nationality
        return self

    def add_language(self, language: str, is_primary: bool = False) -> "Demographics":
        """Add spoken language."""
        if is_primary:
            self.languages.insert(0, language)
        else:
            self.languages.append(language)
        return self

    def set_education_level(self, level: str) -> "Demographics":
        """Set education level."""
        self.education_level = level
        return self

    def set_occupation(self, occupation: str) -> "Demographics":
        """Set occupation."""
        self.occupation = occupation
        return self

    def set_family_size(self, size: int) -> "Demographics":
        """Set family size."""
        self.family_size = size
        return self

    def set_household_head(self, is_head: bool) -> "Demographics":
        """Set household head status."""
        self.household_head = is_head
        return self

    def add_special_need(self, need: str) -> "Demographics":
        """Add special need."""
        self.special_needs.append(need)
        return self

    def add_protection_concern(self, concern: str) -> "Demographics":
        """Add protection concern."""
        self.protection_concerns.append(concern)
        return self

    def to_fhir(self) -> Dict[str, Any]:
        """Convert to FHIR-compatible structure."""
        result: Dict[str, Any] = {}

        if self.gender:
            result["gender"] = self.gender.value

        if self.birth_date:
            result["birthDate"] = self.birth_date["value"]
            if "extension" in self.birth_date:
                result["_birthDate"] = {"extension": self.birth_date["extension"]}

        if self.deceased is not None:
            if self.deceased_date:
                result["deceasedDateTime"] = self.deceased_date.isoformat()
            else:
                result["deceasedBoolean"] = self.deceased

        if self.marital_status:
            result["maritalStatus"] = {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                        "code": self.marital_status.value,
                        "display": self.marital_status.name.replace("_", " ").title(),
                    }
                ]
            }

        # Add extensions for additional demographics
        extensions: List[Dict[str, Any]] = []

        if self.religion:
            extensions.append(
                {
                    "url": "http://hl7.org/fhir/StructureDefinition/patient-religion",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ReligiousAffiliation",
                                "code": self.religion.value,
                                "display": self.religion.name.replace("_", " ").title(),
                            }
                        ]
                    },
                }
            )

        if self.ethnicity:
            ethnicity_code = Ethnicity.get_ethnicity_code(self.ethnicity)
            if ethnicity_code:
                extensions.append(
                    {
                        "url": "http://havenhealthpassport.org/fhir/extension/ethnicity",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "http://havenhealthpassport.org/fhir/CodeSystem/ethnicity",
                                    "code": ethnicity_code,
                                    "display": self.ethnicity.title(),
                                }
                            ]
                        },
                    }
                )

        if self.nationality:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/nationality",
                    "valueCode": self.nationality,
                }
            )

        if self.education_level:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/education-level",
                    "valueString": self.education_level,
                }
            )

        if self.occupation:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/occupation",
                    "valueString": self.occupation,
                }
            )

        if self.family_size is not None:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/family-size",
                    "valueInteger": self.family_size,
                }
            )

        if self.household_head is not None:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/household-head",
                    "valueBoolean": self.household_head,
                }
            )

        if self.special_needs:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/special-needs",
                    "valueString": ", ".join(self.special_needs),
                }
            )

        if self.protection_concerns:
            extensions.append(
                {
                    "url": "http://havenhealthpassport.org/fhir/extension/protection-concerns",
                    "valueString": ", ".join(self.protection_concerns),
                }
            )

        if extensions:
            result["extension"] = extensions

        # Add communication preferences
        if self.languages:
            result["communication"] = []
            for i, lang in enumerate(self.languages):
                result["communication"].append(
                    {
                        "language": {
                            "coding": [{"system": "urn:ietf:bcp:47", "code": lang}]
                        },
                        "preferred": i == 0,  # First language is preferred
                    }
                )

        return result


class ProtectionConcerns:
    """Standard protection concerns for vulnerable populations."""

    CONCERNS = {
        # Child protection
        "UAM": "Unaccompanied Minor",
        "SC": "Separated Child",
        "CH": "Child-Headed Household",
        "CM": "Child Marriage",
        "CL": "Child Labor",
        "CA": "Child Associated with Armed Forces",
        # Gender-based violence
        "GBV": "Gender-Based Violence Survivor",
        "DV": "Domestic Violence",
        "SA": "Sexual Assault Survivor",
        "FGM": "Female Genital Mutilation",
        "HT": "Human Trafficking Survivor",
        # Disability and health
        "PD": "Physical Disability",
        "ID": "Intellectual Disability",
        "VI": "Visual Impairment",
        "HI": "Hearing Impairment",
        "MH": "Mental Health Concerns",
        "CD": "Chronic Disease",
        # Social vulnerabilities
        "EHH": "Elderly Head of Household",
        "SP": "Single Parent",
        "PW": "Pregnant Woman",
        "LW": "Lactating Woman",
        "LGBTI": "LGBTI Individual",
        "EM": "Ethnic Minority",
        "RM": "Religious Minority",
    }

    @classmethod
    def get_concern_description(cls, code: str) -> str:
        """Get description for protection concern code."""
        return cls.CONCERNS.get(code, code)

    @classmethod
    def validate_concern(cls, code: str) -> bool:
        """Check if protection concern code is valid."""
        return code in cls.CONCERNS


def calculate_age(
    birth_date: Union[str, date], reference_date: Optional[date] = None
) -> Optional[int]:
    """Calculate age from birth date.

    Args:
        birth_date: Birth date (string or date object)
        reference_date: Date to calculate age at (default: today)

    Returns:
        Age in years or None if invalid
    """
    try:
        if isinstance(birth_date, str):
            # Handle partial dates
            if len(birth_date) == 4:  # Year only
                birth_year = int(birth_date)
                birth_date = date(birth_year, 7, 1)  # Default to mid-year
            else:
                birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()

        ref_date = reference_date or date.today()
        age = relativedelta(ref_date, birth_date).years

        return age if age >= 0 else None

    except (ValueError, TypeError):
        logger.error("Invalid birth date for age calculation: %s", birth_date)
        return None


def format_demographics_summary(demographics: Demographics) -> str:
    """Format demographics for display summary.

    Args:
        demographics: Demographics object

    Returns:
        Formatted summary string
    """
    parts = []

    # Age and gender
    if demographics.birth_date:
        age = calculate_age(demographics.birth_date["value"])
        if age is not None:
            age_str = f"{age} years old"
            if demographics.birth_date.get("accuracy") != DateAccuracy.EXACT.value:
                age_str += " (estimated)"
            parts.append(age_str)

    if demographics.gender:
        parts.append(demographics.gender.name.lower())

    # Nationality and ethnicity
    if demographics.nationality:
        parts.append(f"from {demographics.nationality}")

    if demographics.ethnicity:
        parts.append(f"{demographics.ethnicity} ethnicity")

    # Languages
    if demographics.languages:
        lang_str = f"speaks {', '.join(demographics.languages[:2])}"
        if len(demographics.languages) > 2:
            lang_str += f" +{len(demographics.languages)-2} more"
        parts.append(lang_str)

    # Family
    if demographics.marital_status:
        parts.append(demographics.marital_status.name.lower().replace("_", " "))

    if demographics.family_size:
        parts.append(f"family of {demographics.family_size}")

    # Protection concerns
    if demographics.protection_concerns:
        parts.append(f"{len(demographics.protection_concerns)} protection concerns")

    return ", ".join(parts).capitalize()
