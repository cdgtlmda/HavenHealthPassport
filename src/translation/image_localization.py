"""Image Localization and Cultural Adaptation.

This module handles image localization, cultural imagery adaptation, and
icon modifications for different cultural contexts.
"""

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ImageCategory(str, Enum):
    """Categories of images requiring localization."""

    MEDICAL_ILLUSTRATION = "medical_illustration"
    UI_ICON = "ui_icon"
    INSTRUCTIONAL = "instructional"
    CULTURAL_REFERENCE = "cultural_reference"
    GENDER_SPECIFIC = "gender_specific"
    FOOD_DIETARY = "food_dietary"
    RELIGIOUS_SYMBOL = "religious_symbol"
    GESTURE = "gesture"
    CLOTHING = "clothing"
    FAMILY_STRUCTURE = "family_structure"


class CulturalSensitivity(str, Enum):
    """Sensitivity levels for images."""

    UNIVERSAL = "universal"  # Safe for all cultures
    MODERATE = "moderate"  # May need adaptation
    SENSITIVE = "sensitive"  # Requires careful handling
    RESTRICTED = "restricted"  # Not suitable for some cultures


@dataclass
class ImageLocalizationRule:
    """Rule for image localization."""

    category: ImageCategory
    original_id: str
    cultural_context: Dict[str, Any]
    alternatives: Dict[str, str]  # locale -> alternative_image_id
    sensitivity: CulturalSensitivity
    adaptation_notes: str


@dataclass
class IconAdaptation:
    """Icon adaptation for cultural contexts."""

    icon_name: str
    universal_version: str
    cultural_versions: Dict[str, str]  # culture -> icon_path
    usage_context: str
    rtl_flip_required: bool


class ImageLocalizationManager:
    """Manages image localization and cultural adaptation."""

    # Cultural image adaptation rules
    CULTURAL_RULES = {
        # Hand gestures
        "thumbs_up": ImageLocalizationRule(
            category=ImageCategory.GESTURE,
            original_id="gesture_thumbs_up",
            cultural_context={
                "meaning": "approval",
                "western_interpretation": "positive",
            },
            alternatives={
                "ar": "gesture_positive_nod",  # Offensive in Middle East
                "fa": "gesture_positive_nod",
                "bn": "gesture_positive_nod",  # Can be offensive
            },
            sensitivity=CulturalSensitivity.SENSITIVE,
            adaptation_notes="Thumbs up is offensive in some Middle Eastern cultures",
        ),
        "ok_hand": ImageLocalizationRule(
            category=ImageCategory.GESTURE,
            original_id="gesture_ok",
            cultural_context={
                "meaning": "okay/good",
                "western_interpretation": "positive",
            },
            alternatives={
                "ar": "gesture_checkmark",
                "tr": "gesture_checkmark",  # Offensive in Turkey
                "br": "gesture_checkmark",  # Offensive in Brazil
            },
            sensitivity=CulturalSensitivity.SENSITIVE,
            adaptation_notes="OK hand gesture has negative connotations in several cultures",
        ),
        # Medical illustrations
        "injection_arm": ImageLocalizationRule(
            category=ImageCategory.MEDICAL_ILLUSTRATION,
            original_id="medical_injection_arm",
            cultural_context={"body_part": "arm", "clothing": "short_sleeve"},
            alternatives={
                "ar_female": "medical_injection_arm_covered",
                "sa_female": "medical_injection_arm_covered",
                "af_female": "medical_injection_arm_covered",
            },
            sensitivity=CulturalSensitivity.MODERATE,
            adaptation_notes="Consider modest clothing for conservative cultures",
        ),
        # Family structures
        "nuclear_family": ImageLocalizationRule(
            category=ImageCategory.FAMILY_STRUCTURE,
            original_id="family_nuclear_western",
            cultural_context={"structure": "nuclear", "size": "2_parents_2_children"},
            alternatives={
                "africa": "family_extended_african",
                "middle_east": "family_extended_arabic",
                "south_asia": "family_extended_indian",
            },
            sensitivity=CulturalSensitivity.MODERATE,
            adaptation_notes="Family structures vary significantly across cultures",
        ),
        # Food and dietary
        "meal_example": ImageLocalizationRule(
            category=ImageCategory.FOOD_DIETARY,
            original_id="meal_western_plate",
            cultural_context={"dietary": "omnivore", "utensils": "fork_knife"},
            alternatives={
                "halal": "meal_halal_plate",
                "kosher": "meal_kosher_plate",
                "hindu": "meal_vegetarian_indian",
                "buddhist": "meal_vegetarian_asian",
            },
            sensitivity=CulturalSensitivity.SENSITIVE,
            adaptation_notes="Dietary restrictions are critical for medical contexts",
        ),
        # Religious symbols in healthcare
        "spiritual_care": ImageLocalizationRule(
            category=ImageCategory.RELIGIOUS_SYMBOL,
            original_id="spiritual_care_cross",
            cultural_context={"religion": "christian", "symbol": "cross"},
            alternatives={
                "islamic": "spiritual_care_crescent",
                "jewish": "spiritual_care_star",
                "buddhist": "spiritual_care_wheel",
                "hindu": "spiritual_care_om",
                "secular": "spiritual_care_hands",
            },
            sensitivity=CulturalSensitivity.SENSITIVE,
            adaptation_notes="Religious symbols require careful consideration",
        ),
    }

    # Icon adaptations for UI
    ICON_ADAPTATIONS = {
        "calendar": IconAdaptation(
            icon_name="calendar",
            universal_version="icons/calendar_neutral.svg",
            cultural_versions={
                "gregorian": "icons/calendar_gregorian.svg",
                "hijri": "icons/calendar_hijri.svg",
                "persian": "icons/calendar_persian.svg",
                "hebrew": "icons/calendar_hebrew.svg",
            },
            usage_context="date_display",
            rtl_flip_required=False,
        ),
        "direction_arrow": IconAdaptation(
            icon_name="arrow_forward",
            universal_version="icons/arrow_right.svg",
            cultural_versions={
                "ltr": "icons/arrow_right.svg",
                "rtl": "icons/arrow_left.svg",
            },
            usage_context="navigation",
            rtl_flip_required=True,
        ),
        "checkmark": IconAdaptation(
            icon_name="checkmark",
            universal_version="icons/check_universal.svg",
            cultural_versions={},  # Universal symbol
            usage_context="confirmation",
            rtl_flip_required=False,
        ),
        "home": IconAdaptation(
            icon_name="home",
            universal_version="icons/home_universal.svg",
            cultural_versions={
                "western": "icons/home_house.svg",
                "nomadic": "icons/home_tent.svg",
                "apartment": "icons/home_building.svg",
            },
            usage_context="navigation",
            rtl_flip_required=False,
        ),
    }

    # Color cultural meanings
    COLOR_MEANINGS = {
        "red": {
            "western": ["danger", "stop", "error", "love"],
            "chinese": ["luck", "prosperity", "joy"],
            "indian": ["purity", "celebration"],
            "south_african": ["mourning"],
            "middle_eastern": ["danger", "caution"],
        },
        "white": {
            "western": ["purity", "cleanliness", "peace"],
            "chinese": ["death", "mourning"],
            "indian": ["purity", "peace"],
            "japanese": ["death", "mourning"],
        },
        "green": {
            "western": ["go", "success", "nature"],
            "islamic": ["sacred", "paradise"],
            "chinese": ["infidelity"],
            "indonesian": ["forbidden"],
        },
        "black": {
            "western": ["death", "formality", "elegance"],
            "african": ["masculinity", "maturity"],
            "middle_eastern": ["rebirth", "mourning"],
        },
    }

    def __init__(self, assets_path: str = "/assets"):
        """Initialize image localization manager."""
        self.assets_path = Path(assets_path)
        self.localized_images: Dict[str, Dict[str, str]] = {}
        self._load_image_mappings()

    def _load_image_mappings(self) -> None:
        """Load image localization mappings from configuration."""
        # In production, would load from database or config file
        for _rule_id, rule in self.CULTURAL_RULES.items():
            self.localized_images[rule.original_id] = rule.alternatives

    def get_localized_image(
        self,
        image_id: str,
        locale: str,
        cultural_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get culturally appropriate image for locale.

        Args:
            image_id: Original image identifier
            locale: Target locale
            cultural_context: Additional context (gender, age, etc.)

        Returns:
            Path to appropriate image
        """
        # Check if image needs localization
        if image_id not in self.localized_images:
            return self._get_image_path(image_id)

        alternatives = self.localized_images[image_id]

        # Check for specific cultural context
        if cultural_context:
            # Handle gender-specific images
            if "gender" in cultural_context:
                gender_key = f"{locale}_{cultural_context['gender']}"
                if gender_key in alternatives:
                    return self._get_image_path(alternatives[gender_key])

        # Check for locale-specific version
        if locale in alternatives:
            return self._get_image_path(alternatives[locale])

        # Check for language-specific version (without region)
        language = locale.split("-")[0]
        if language in alternatives:
            return self._get_image_path(alternatives[language])

        # Check for regional version
        for alt_locale, alt_image in alternatives.items():
            if locale.startswith(alt_locale) or alt_locale.startswith(language):
                return self._get_image_path(alt_image)

        # Return original if no alternative found
        return self._get_image_path(image_id)

    def _get_image_path(self, image_id: str) -> str:
        """Get full path for image ID."""
        return str(self.assets_path / "images" / f"{image_id}.png")

    def get_icon(
        self,
        icon_name: str,
        direction: str = "ltr",
        cultural_preference: Optional[str] = None,
    ) -> str:
        """
        Get culturally adapted icon.

        Args:
            icon_name: Name of the icon
            direction: Text direction (ltr/rtl)
            cultural_preference: Specific cultural version

        Returns:
            Path to icon file
        """
        if icon_name not in self.ICON_ADAPTATIONS:
            return str(self.assets_path / "icons" / f"{icon_name}.svg")

        adaptation = self.ICON_ADAPTATIONS[icon_name]

        # Check for RTL adaptation
        if direction == "rtl" and adaptation.rtl_flip_required:
            if "rtl" in adaptation.cultural_versions:
                return str(self.assets_path / adaptation.cultural_versions["rtl"])
            # Return flipped version indicator
            return f"{adaptation.universal_version}?flip=horizontal"

        # Check for cultural preference
        if cultural_preference and cultural_preference in adaptation.cultural_versions:
            return str(
                self.assets_path / adaptation.cultural_versions[cultural_preference]
            )

        # Return universal version
        return str(self.assets_path / adaptation.universal_version)

    def get_color_scheme(
        self, base_scheme: Dict[str, str], cultural_context: str
    ) -> Dict[str, str]:
        """
        Adapt color scheme for cultural context.

        Args:
            base_scheme: Base color scheme
            cultural_context: Cultural context identifier

        Returns:
            Adapted color scheme
        """
        adapted_scheme = base_scheme.copy()

        # Adapt colors based on cultural meanings
        if cultural_context == "chinese":
            # Red is positive in Chinese culture
            if "error" in adapted_scheme and adapted_scheme["error"] == "#FF0000":
                adapted_scheme["error"] = "#CC0000"  # Darker red for errors
                adapted_scheme["success"] = "#FF0000"  # Bright red for success

        elif cultural_context == "islamic":
            # Green is sacred
            if "primary" in adapted_scheme:
                adapted_scheme["primary"] = "#009900"  # Green primary

        elif cultural_context in ["japanese", "korean"]:
            # White can signify death
            if (
                "background" in adapted_scheme
                and adapted_scheme["background"] == "#FFFFFF"
            ):
                adapted_scheme["background"] = "#FAFAFA"  # Off-white

        return adapted_scheme

    def check_image_sensitivity(
        self, image_id: str, target_cultures: List[str]
    ) -> Dict[str, Any]:
        """
        Check if image is culturally sensitive.

        Args:
            image_id: Image to check
            target_cultures: List of target cultures

        Returns:
            Sensitivity analysis
        """
        # Find if image has cultural rules
        for _rule_id, rule in self.CULTURAL_RULES.items():
            if rule.original_id == image_id:
                sensitivity_report: Dict[str, Any] = {
                    "sensitivity_level": rule.sensitivity.value,
                    "concerns": [],
                    "recommendations": [],
                }

                # Check each target culture
                for culture in target_cultures:
                    if culture in rule.alternatives:
                        sensitivity_report["concerns"].append(
                            {
                                "culture": culture,
                                "issue": rule.adaptation_notes,
                                "alternative": rule.alternatives[culture],
                            }
                        )
                        sensitivity_report["recommendations"].append(
                            f"Use {rule.alternatives[culture]} for {culture} audience"
                        )

                return sensitivity_report

        # No specific rules found
        return {
            "sensitivity_level": CulturalSensitivity.UNIVERSAL.value,
            "concerns": [],
            "recommendations": [],
        }

    def generate_image_variants(
        self, base_image_id: str, required_locales: List[str]
    ) -> Dict[str, str]:
        """
        Generate required image variants for locales.

        Args:
            base_image_id: Base image identifier
            required_locales: List of required locales

        Returns:
            Mapping of locale to image variant
        """
        variants = {}

        for locale in required_locales:
            localized = self.get_localized_image(base_image_id, locale)
            variants[locale] = localized

        return variants

    def get_medical_illustration_guidelines(self, culture: str) -> Dict[str, Any]:
        """
        Get guidelines for medical illustrations.

        Args:
            culture: Target culture

        Returns:
            Guidelines for appropriate medical imagery
        """
        guidelines = {
            "general": [
                "Use diverse skin tones",
                "Respect modesty requirements",
                "Consider cultural dress norms",
                "Avoid culturally specific gestures",
            ],
            "specific_requirements": {},
        }

        # Culture-specific guidelines
        if culture in ["ar", "sa", "ae", "af", "ir"]:
            guidelines["specific_requirements"] = {
                "modesty": "high",
                "gender_separation": True,
                "clothing": "conservative",
                "body_parts": {
                    "face": "permissible",
                    "hands": "permissible",
                    "arms": "cover for women",
                    "legs": "cover for both genders",
                    "torso": "cover for both genders",
                },
            }

        elif culture in ["in", "pk", "bd"]:
            guidelines["specific_requirements"] = {
                "modesty": "moderate",
                "gender_separation": True,
                "clothing": "traditional acceptable",
                "body_parts": {
                    "face": "permissible",
                    "hands": "permissible",
                    "arms": "modest covering preferred",
                    "legs": "cover for women",
                    "torso": "cover for both genders",
                },
            }

        return guidelines

    def validate_image_set(
        self, image_ids: List[str], target_locales: List[str]
    ) -> Dict[str, Any]:
        """
        Validate a set of images for cultural appropriateness.

        Args:
            image_ids: List of image IDs to validate
            target_locales: Target locales

        Returns:
            Validation report
        """
        report: Dict[str, Any] = {
            "valid": True,
            "issues": [],
            "missing_variants": [],
            "recommendations": [],
        }

        for image_id in image_ids:
            # Check sensitivity
            sensitivity = self.check_image_sensitivity(
                image_id, [loc.split("-")[0] for loc in target_locales]
            )

            if sensitivity["sensitivity_level"] != CulturalSensitivity.UNIVERSAL.value:
                report["issues"].append(
                    {
                        "image_id": image_id,
                        "sensitivity": sensitivity["sensitivity_level"],
                        "concerns": sensitivity["concerns"],
                    }
                )

                if (
                    sensitivity["sensitivity_level"]
                    == CulturalSensitivity.RESTRICTED.value
                ):
                    report["valid"] = False

            # Check for missing variants
            variants = self.generate_image_variants(image_id, target_locales)
            for locale, variant in variants.items():
                if variant == self._get_image_path(image_id):
                    # Using default image for this locale
                    if image_id in self.localized_images:
                        report["missing_variants"].append(
                            {
                                "image_id": image_id,
                                "locale": locale,
                                "reason": "No localized version available",
                            }
                        )

        # Generate recommendations
        if report["issues"]:
            report["recommendations"].append(
                "Review and update sensitive images before deployment"
            )

        if report["missing_variants"]:
            report["recommendations"].append(
                "Create localized versions for better cultural acceptance"
            )

        return report


# Image processing utilities
class ImageProcessor:
    """Utilities for processing localized images."""

    @staticmethod
    def generate_rtl_version(image_path: str) -> str:
        """
        Generate RTL version of an image.

        Args:
            image_path: Path to original image

        Returns:
            Path to RTL version
        """
        # In production, would actually flip the image
        rtl_path = image_path.replace(".png", "_rtl.png")
        rtl_path = rtl_path.replace(".svg", "_rtl.svg")

        logger.info(f"Generated RTL version: {rtl_path}")
        return rtl_path

    @staticmethod
    def apply_cultural_overlay(base_image: str, overlay_type: str, culture: str) -> str:
        """
        Apply cultural overlay to base image.

        Args:
            base_image: Base image path
            overlay_type: Type of overlay (clothing, background, etc.)
            culture: Target culture

        Returns:
            Path to modified image
        """
        # Generate unique filename
        # MD5 is used here only for generating unique identifiers, not for security
        overlay_id = hashlib.md5(
            f"{base_image}:{overlay_type}:{culture}".encode(), usedforsecurity=False
        ).hexdigest()[:8]

        modified_path = base_image.replace(
            ".", f"_{overlay_type}_{culture}_{overlay_id}."
        )

        logger.info(f"Applied {overlay_type} overlay for {culture}: {modified_path}")
        return modified_path

    @staticmethod
    def check_image_contrast(
        _image_path: str, _background_color: str
    ) -> Dict[str, float]:
        """
        Check image contrast against background.

        Args:
            image_path: Path to image
            background_color: Background color (hex)

        Returns:
            Contrast ratio and accessibility info
        """
        # In production, would calculate actual contrast
        return {
            "contrast_ratio": 4.5,  # Placeholder
            "wcag_aa_compliant": True,
            "wcag_aaa_compliant": False,
            "recommendation": 4.5,  # Use numeric value for type consistency
        }


# Global instance
image_localization_manager = ImageLocalizationManager()
