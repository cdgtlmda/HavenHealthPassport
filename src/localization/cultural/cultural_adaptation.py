"""Cultural Adaptation System for Healthcare.

This module provides cultural adaptation features including image localization,
cultural imagery, icon adaptation, color meanings, and content filtering.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.hipaa_access_control import require_phi_access  # noqa: F401
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CulturalContext(str, Enum):
    """Cultural context categories."""

    MEDICAL = "medical"
    RELIGIOUS = "religious"
    DIETARY = "dietary"
    SOCIAL = "social"
    GENDER = "gender"
    AGE = "age"
    DISABILITY = "disability"


class ContentSensitivity(str, Enum):
    """Content sensitivity levels."""

    UNIVERSAL = "universal"  # Appropriate for all cultures
    CULTURALLY_AWARE = "culturally_aware"  # Requires cultural adaptation
    SENSITIVE = "sensitive"  # Requires careful handling
    RESTRICTED = "restricted"  # May be inappropriate in some cultures


class ColorMeaning(str, Enum):
    """Cultural meanings of colors."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    SACRED = "sacred"
    MOURNING = "mourning"
    HEALING = "healing"
    WARNING = "warning"


@dataclass
class CulturalProfile:
    """Cultural profile for a region/group."""

    culture_code: str
    name: str
    languages: List[str]
    regions: List[str]
    religious_considerations: Dict[str, Any]
    dietary_restrictions: List[str]
    color_meanings: Dict[str, ColorMeaning]
    taboo_imagery: List[str]
    preferred_imagery: List[str]
    gender_norms: Dict[str, Any]
    age_considerations: Dict[str, Any]


@dataclass
class ImageLocalization:
    """Localized image information."""

    default_image: str
    localized_versions: Dict[str, str]  # culture_code -> image_path
    alt_text: Dict[str, str]  # language -> alt text
    cultural_notes: Dict[str, str]
    sensitivity_level: ContentSensitivity


@dataclass
class IconAdaptation:
    """Culturally adapted icon."""

    icon_name: str
    default_icon: str
    cultural_variants: Dict[str, str]  # culture_code -> icon_path
    meanings: Dict[str, str]  # culture_code -> meaning
    avoid_in_cultures: List[str]


class CulturalAdaptationManager:
    """Manages cultural adaptation for healthcare content."""

    # Cultural profiles database
    CULTURAL_PROFILES = {
        "middle_eastern": CulturalProfile(
            culture_code="middle_eastern",
            name="Middle Eastern",
            languages=["ar", "fa", "ur"],
            regions=["SY", "JO", "IQ", "AF", "PK"],
            religious_considerations={
                "primary_religion": "Islam",
                "prayer_times": True,
                "gender_separation": True,
                "modest_imagery": True,
                "halal_required": True,
            },
            dietary_restrictions=["pork", "alcohol", "non_halal_meat"],
            color_meanings={
                "green": ColorMeaning.SACRED,
                "white": ColorMeaning.POSITIVE,
                "black": ColorMeaning.MOURNING,
                "red": ColorMeaning.WARNING,
            },
            taboo_imagery=[
                "pork",
                "alcohol",
                "immodest_dress",
                "left_hand",
                "feet_soles",
            ],
            preferred_imagery=["nature", "geometric_patterns", "calligraphy"],
            gender_norms={
                "prefer_same_gender_provider": True,
                "family_involvement": "high",
                "modest_examination": True,
            },
            age_considerations={
                "elder_respect": "very_high",
                "family_decision_making": True,
            },
        ),
        "south_asian": CulturalProfile(
            culture_code="south_asian",
            name="South Asian",
            languages=["hi", "bn", "ur", "ne"],
            regions=["IN", "BD", "PK", "NP"],
            religious_considerations={
                "diverse_religions": ["Hinduism", "Islam", "Buddhism", "Christianity"],
                "vegetarian_options": True,
                "religious_symbols": True,
            },
            dietary_restrictions=["beef", "pork", "meat_general"],
            color_meanings={
                "saffron": ColorMeaning.SACRED,
                "white": ColorMeaning.MOURNING,
                "red": ColorMeaning.POSITIVE,
                "green": ColorMeaning.POSITIVE,
            },
            taboo_imagery=["beef", "leather", "left_hand"],
            preferred_imagery=["family", "nature", "traditional_medicine"],
            gender_norms={"family_involvement": "high", "modest_examination": True},
            age_considerations={
                "elder_respect": "very_high",
                "joint_family_system": True,
            },
        ),
        "east_african": CulturalProfile(
            culture_code="east_african",
            name="East African",
            languages=["sw", "am", "so", "ar"],
            regions=["KE", "ET", "SO", "UG", "TZ"],
            religious_considerations={
                "diverse_religions": ["Christianity", "Islam", "Traditional"],
                "community_based": True,
            },
            dietary_restrictions=["varies_by_religion"],
            color_meanings={
                "white": ColorMeaning.POSITIVE,
                "red": ColorMeaning.WARNING,
                "black": ColorMeaning.NEUTRAL,
                "green": ColorMeaning.HEALING,
            },
            taboo_imagery=["culture_specific"],
            preferred_imagery=["community", "nature", "traditional_healing"],
            gender_norms={"community_involvement": "high", "traditional_roles": True},
            age_considerations={"elder_respect": "high", "community_elders": True},
        ),
        "western": CulturalProfile(
            culture_code="western",
            name="Western",
            languages=["en", "es", "fr", "de"],
            regions=["US", "GB", "CA", "AU", "EU"],
            religious_considerations={
                "secular_approach": True,
                "diverse_beliefs": True,
            },
            dietary_restrictions=["individual_based"],
            color_meanings={
                "green": ColorMeaning.POSITIVE,
                "red": ColorMeaning.WARNING,
                "blue": ColorMeaning.HEALING,
                "black": ColorMeaning.MOURNING,
            },
            taboo_imagery=["graphic_medical"],
            preferred_imagery=["professional", "clinical", "diverse_representation"],
            gender_norms={"patient_choice": True, "individual_focused": True},
            age_considerations={"patient_autonomy": True, "privacy_focused": True},
        ),
    }

    # Image localization database
    IMAGE_LOCALIZATIONS = {
        "doctor_consultation": ImageLocalization(
            default_image="doctor_consultation_default.jpg",
            localized_versions={
                "middle_eastern": "doctor_consultation_hijab.jpg",
                "south_asian": "doctor_consultation_sari.jpg",
                "east_african": "doctor_consultation_african.jpg",
            },
            alt_text={
                "en": "Doctor consulting with patient",
                "ar": "طبيب يستشير مع المريض",
                "hi": "डॉक्टर रोगी से परामर्श कर रहे हैं",
            },
            cultural_notes={
                "middle_eastern": "Shows female doctor wearing hijab with female patient",
                "south_asian": "Shows doctor in traditional attire",
            },
            sensitivity_level=ContentSensitivity.CULTURALLY_AWARE,
        ),
        "family_health": ImageLocalization(
            default_image="family_health_default.jpg",
            localized_versions={
                "middle_eastern": "family_health_extended.jpg",
                "south_asian": "family_health_joint.jpg",
                "east_african": "family_health_community.jpg",
            },
            alt_text={
                "en": "Family healthcare scene",
                "ar": "مشهد الرعاية الصحية للأسرة",
                "sw": "Mwonekano wa huduma za afya za familia",
            },
            cultural_notes={
                "middle_eastern": "Shows extended family with modest dress",
                "south_asian": "Depicts joint family system",
            },
            sensitivity_level=ContentSensitivity.CULTURALLY_AWARE,
        ),
    }

    # Icon adaptations
    ICON_ADAPTATIONS = {
        "meal": IconAdaptation(
            icon_name="meal",
            default_icon="meal_default.svg",
            cultural_variants={
                "middle_eastern": "meal_halal.svg",
                "south_asian": "meal_vegetarian.svg",
                "western": "meal_balanced.svg",
            },
            meanings={
                "middle_eastern": "Halal meal",
                "south_asian": "Vegetarian meal",
                "western": "Balanced meal",
            },
            avoid_in_cultures=[],
        ),
        "prayer": IconAdaptation(
            icon_name="prayer",
            default_icon="prayer_generic.svg",
            cultural_variants={
                "middle_eastern": "prayer_islamic.svg",
                "south_asian": "prayer_multi_faith.svg",
                "east_african": "prayer_diverse.svg",
            },
            meanings={
                "middle_eastern": "Prayer room direction",
                "south_asian": "Multi-faith prayer space",
                "western": "Quiet reflection room",
            },
            avoid_in_cultures=[],
        ),
    }

    # Gesture meanings by culture
    GESTURE_MEANINGS = {
        "thumbs_up": {
            "western": "positive",
            "middle_eastern": "offensive",
            "south_asian": "positive",
        },
        "ok_sign": {
            "western": "okay",
            "middle_eastern": "offensive",
            "south_asian": "okay",
        },
        "pointing": {
            "western": "neutral",
            "middle_eastern": "use_open_hand",
            "south_asian": "use_open_hand",
        },
        "left_hand": {
            "western": "neutral",
            "middle_eastern": "avoid",
            "south_asian": "avoid",
        },
    }

    # Dietary symbols and meanings
    DIETARY_SYMBOLS = {
        "halal": {
            "symbol": "☪",
            "image": "halal_certified.svg",
            "cultures": ["middle_eastern", "south_asian"],
            "meaning": "Permissible under Islamic law",
        },
        "vegetarian": {
            "symbol": "🌱",
            "image": "vegetarian.svg",
            "cultures": ["south_asian", "western"],
            "meaning": "No meat products",
        },
        "vegan": {
            "symbol": "Ⓥ",
            "image": "vegan.svg",
            "cultures": ["western"],
            "meaning": "No animal products",
        },
        "kosher": {
            "symbol": "✡",
            "image": "kosher.svg",
            "cultures": ["western"],
            "meaning": "符合犹太饮食法规",
        },
    }

    def __init__(self) -> None:
        """Initialize cultural adaptation manager."""
        self.user_cultural_preferences: Dict[str, str] = {}
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.content_filters: Dict[str, List[str]] = {}

    def get_cultural_profile(
        self,
        culture_code: Optional[str] = None,
        country_code: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[CulturalProfile]:
        """Get cultural profile based on various identifiers."""
        if culture_code:
            return self.CULTURAL_PROFILES.get(culture_code)

        # Try to determine from country or language
        for profile in self.CULTURAL_PROFILES.values():
            if country_code and country_code in profile.regions:
                return profile
            if language and language in profile.languages:
                return profile

        return self.CULTURAL_PROFILES.get("western")  # Default

    def get_localized_image(
        self, image_key: str, culture_code: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Get culturally appropriate image."""
        localization = self.IMAGE_LOCALIZATIONS.get(image_key)
        if not localization:
            return {
                "image_path": f"{image_key}_default.jpg",
                "alt_text": image_key.replace("_", " ").title(),
                "cultural_note": None,
            }

        # Get culture-specific version or default
        image_path = localization.localized_versions.get(
            culture_code, localization.default_image
        )

        # Get localized alt text
        alt_text = localization.alt_text.get(
            language, localization.alt_text.get("en", "")
        )

        # Get cultural notes
        cultural_note = localization.cultural_notes.get(culture_code)

        return {
            "image_path": image_path,
            "alt_text": alt_text,
            "cultural_note": cultural_note,
            "sensitivity_level": localization.sensitivity_level.value,
        }

    def get_adapted_icon(self, icon_name: str, culture_code: str) -> Dict[str, Any]:
        """Get culturally adapted icon."""
        adaptation = self.ICON_ADAPTATIONS.get(icon_name)
        if not adaptation:
            return {
                "icon_path": f"{icon_name}_default.svg",
                "meaning": icon_name.replace("_", " ").title(),
                "suitable": True,
            }

        # Check if suitable for culture
        if culture_code in adaptation.avoid_in_cultures:
            return {
                "icon_path": None,
                "meaning": "Not suitable for this culture",
                "suitable": False,
                "alternative": "text_only",
            }

        # Get culture-specific variant
        icon_path = adaptation.cultural_variants.get(
            culture_code, adaptation.default_icon
        )

        meaning = adaptation.meanings.get(culture_code, icon_name)

        return {"icon_path": icon_path, "meaning": meaning, "suitable": True}

    def check_color_appropriateness(
        self, color: str, usage_context: str, culture_code: str
    ) -> Dict[str, Any]:
        """Check if color is appropriate for cultural context."""
        profile = self.get_cultural_profile(culture_code)
        if not profile:
            return {"appropriate": True, "meaning": "neutral"}

        color_meaning = profile.color_meanings.get(color.lower())

        # Determine appropriateness based on context
        appropriate = True
        recommendation = None

        if usage_context == "success" and color_meaning == ColorMeaning.MOURNING:
            appropriate = False
            recommendation = "Use positive color instead"
        elif usage_context == "error" and color_meaning == ColorMeaning.SACRED:
            appropriate = False
            recommendation = "Avoid using sacred colors for errors"
        elif usage_context == "warning" and color_meaning not in [
            ColorMeaning.WARNING,
            ColorMeaning.NEGATIVE,
        ]:
            recommendation = "Consider using traditional warning color"

        return {
            "appropriate": appropriate,
            "meaning": color_meaning.value if color_meaning else "neutral",
            "recommendation": recommendation,
        }

    def check_gesture_appropriateness(
        self, gesture: str, culture_code: str
    ) -> Dict[str, Any]:
        """Check if gesture is appropriate for culture."""
        gesture_meanings = self.GESTURE_MEANINGS.get(gesture, {})
        meaning = gesture_meanings.get(culture_code, "unknown")

        appropriate = meaning not in ["offensive", "avoid"]

        alternatives = []
        if not appropriate:
            if gesture == "thumbs_up":
                alternatives = ["checkmark", "smile", "nod"]
            elif gesture == "pointing":
                alternatives = ["open_hand_gesture", "arrow"]

        return {
            "appropriate": appropriate,
            "meaning": meaning,
            "alternatives": alternatives,
        }

    def filter_content_for_culture(
        self, content: str, content_type: str, culture_code: str
    ) -> Tuple[bool, Optional[str], List[str]]:
        """Filter content for cultural appropriateness."""
        profile = self.get_cultural_profile(culture_code)
        if not profile:
            return True, None, []

        issues = []
        filtered_content = content

        # Check for taboo imagery descriptions
        for taboo in profile.taboo_imagery:
            if taboo.lower() in content.lower():
                issues.append(f"Contains reference to {taboo}")
                # In production, would actually filter/replace

        # Check dietary restrictions
        if content_type == "dietary":
            for restriction in profile.dietary_restrictions:
                if restriction.lower() in content.lower():
                    issues.append(f"Contains restricted item: {restriction}")

        # Check religious considerations
        if profile.religious_considerations.get("modest_imagery"):
            modesty_terms = ["revealing", "undressed", "intimate"]
            for term in modesty_terms:
                if term in content.lower():
                    issues.append("May violate modesty requirements")

        is_appropriate = len(issues) == 0

        return is_appropriate, filtered_content if not is_appropriate else None, issues

    def get_age_appropriate_content(
        self, content_rating: str, user_age: int, culture_code: str
    ) -> Dict[str, Any]:
        """Determine age-appropriate content based on culture."""
        profile = self.get_cultural_profile(culture_code)

        # Age categories vary by culture
        age_categories = {
            "child": (0, 12),
            "teen": (13, 17),
            "adult": (18, 64),
            "elder": (65, 999),
        }

        # Determine user category
        user_category = "adult"
        for category, (min_age, max_age) in age_categories.items():
            if min_age <= user_age <= max_age:
                user_category = category
                break

        # Check appropriateness
        appropriate = True
        modifications = []

        if user_category == "child":
            if content_rating in ["mature", "explicit"]:
                appropriate = False
                modifications.append("Use child-friendly language")
                modifications.append("Simplify medical terms")
                modifications.append("Add visual aids")

        if user_category == "elder" and profile:
            if profile.age_considerations.get("elder_respect") == "very_high":
                modifications.append("Use respectful honorifics")
                modifications.append("Consider family involvement")

        return {
            "appropriate": appropriate,
            "user_category": user_category,
            "modifications": modifications,
            "family_involvement_recommended": user_category in ["child", "elder"],
        }

    def get_religious_considerations(
        self, service_type: str, culture_code: str
    ) -> Dict[str, Any]:
        """Get religious considerations for healthcare service."""
        profile = self.get_cultural_profile(culture_code)
        if not profile:
            return {"considerations": []}

        considerations = []
        accommodations = []

        religious_config = profile.religious_considerations

        # Prayer times
        if religious_config.get("prayer_times"):
            considerations.append("Schedule appointments around prayer times")
            accommodations.append("Provide prayer space and washing facilities")

        # Gender preferences
        if religious_config.get("gender_separation"):
            considerations.append("Offer same-gender healthcare providers")
            accommodations.append("Ensure privacy during examinations")

        # Dietary requirements
        if religious_config.get("halal_required"):
            considerations.append("Ensure medications are halal-certified")
            accommodations.append("Provide halal meal options")

        # Modesty requirements
        if religious_config.get("modest_imagery"):
            considerations.append("Use modest imagery in materials")
            accommodations.append("Provide appropriate gowns/coverings")

        return {
            "considerations": considerations,
            "accommodations": accommodations,
            "primary_religion": religious_config.get("primary_religion"),
            "diverse_beliefs": religious_config.get("diverse_religions", []),
        }

    def get_dietary_symbols_for_culture(
        self, culture_code: str
    ) -> List[Dict[str, Any]]:
        """Get relevant dietary symbols for a culture."""
        relevant_symbols = []

        for symbol_key, symbol_info in self.DIETARY_SYMBOLS.items():
            if culture_code in symbol_info["cultures"]:
                relevant_symbols.append(
                    {
                        "key": symbol_key,
                        "symbol": symbol_info["symbol"],
                        "image": symbol_info["image"],
                        "meaning": symbol_info["meaning"],
                    }
                )

        return relevant_symbols

    def validate_content_sensitivity(
        self, content: Dict[str, Any], target_cultures: List[str]
    ) -> Dict[str, Any]:
        """Validate content sensitivity across multiple cultures."""
        sensitivity_issues = []
        max_sensitivity = ContentSensitivity.UNIVERSAL

        for culture in target_cultures:
            profile = self.get_cultural_profile(culture)
            if not profile:
                continue

            # Check various aspects
            if content.get("images"):
                for image in content["images"]:
                    if any(taboo in image.lower() for taboo in profile.taboo_imagery):
                        sensitivity_issues.append(
                            {
                                "culture": culture,
                                "type": "imagery",
                                "issue": "Contains taboo imagery",
                            }
                        )

            if content.get("colors"):
                for color, usage in content["colors"].items():
                    result = self.check_color_appropriateness(color, usage, culture)
                    if not result["appropriate"]:
                        sensitivity_issues.append(
                            {
                                "culture": culture,
                                "type": "color",
                                "issue": result["recommendation"],
                            }
                        )

        # Determine overall sensitivity level
        if sensitivity_issues:
            if any(
                issue["type"] in ["imagery", "religious"]
                for issue in sensitivity_issues
            ):
                max_sensitivity = ContentSensitivity.SENSITIVE
            else:
                max_sensitivity = ContentSensitivity.CULTURALLY_AWARE

        return {
            "sensitivity_level": max_sensitivity.value,
            "issues": sensitivity_issues,
            "requires_adaptation": len(sensitivity_issues) > 0,
            "affected_cultures": list(
                set(issue["culture"] for issue in sensitivity_issues)
            ),
        }


# Global cultural adaptation manager
cultural_manager = CulturalAdaptationManager()
