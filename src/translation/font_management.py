"""Font Management System for Multi-Language Support.

This module handles font loading, subsetting, and rendering optimization
for multiple scripts and languages in the Haven Health Passport system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScriptType(str, Enum):
    """Writing scripts supported by the system."""

    LATIN = "latin"
    ARABIC = "arabic"
    DEVANAGARI = "devanagari"  # Hindi, Nepali
    BENGALI = "bengali"
    CYRILLIC = "cyrillic"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    KOREAN = "korean"
    THAI = "thai"
    ETHIOPIC = "ethiopic"  # Amharic
    HEBREW = "hebrew"


@dataclass
class FontConfiguration:
    """Configuration for a font family."""

    family_name: str
    script_support: List[ScriptType]
    weights: List[int]  # 100-900
    styles: List[str]  # normal, italic
    subset_ranges: Dict[str, str]  # Unicode ranges for subsetting
    fallback_order: int
    web_font_url: Optional[str] = None
    local_path: Optional[str] = None
    features: List[str] = field(default_factory=list)  # OpenType features


class FontManager:
    """Manages fonts for multi-language support."""

    # Font stack configurations by script
    FONT_STACKS = {
        ScriptType.LATIN: [
            FontConfiguration(
                family_name="Inter",
                script_support=[ScriptType.LATIN],
                weights=[400, 500, 600, 700],
                styles=["normal"],
                subset_ranges={"latin": "U+0000-00FF", "latin-ext": "U+0100-024F"},
                fallback_order=1,
                features=["liga", "kern"],
            ),
            FontConfiguration(
                family_name="Roboto",
                script_support=[ScriptType.LATIN],
                weights=[400, 500, 700],
                styles=["normal", "italic"],
                subset_ranges={"latin": "U+0000-00FF"},
                fallback_order=2,
            ),
        ],
        ScriptType.ARABIC: [
            FontConfiguration(
                family_name="Noto Sans Arabic",
                script_support=[ScriptType.ARABIC],
                weights=[400, 600, 700],
                styles=["normal"],
                subset_ranges={
                    "arabic": "U+0600-06FF",
                    "arabic-supplement": "U+0750-077F",
                    "arabic-extended": "U+08A0-08FF",
                },
                fallback_order=1,
                features=["liga", "calt", "init", "medi", "fina", "isol"],
            ),
            FontConfiguration(
                family_name="Vazirmatn",
                script_support=[ScriptType.ARABIC],
                weights=[400, 500, 600, 700],
                styles=["normal"],
                subset_ranges={"arabic": "U+0600-06FF", "persian": "U+FB50-FDFF"},
                fallback_order=2,
            ),
        ],
        ScriptType.DEVANAGARI: [
            FontConfiguration(
                family_name="Noto Sans Devanagari",
                script_support=[ScriptType.DEVANAGARI],
                weights=[400, 600, 700],
                styles=["normal"],
                subset_ranges={
                    "devanagari": "U+0900-097F",
                    "devanagari-extended": "U+A8E0-A8FF",
                },
                fallback_order=1,
                features=[
                    "locl",
                    "nukt",
                    "akhn",
                    "rphf",
                    "rkrf",
                    "blwf",
                    "half",
                    "vatu",
                    "pres",
                    "abvs",
                    "blws",
                    "psts",
                    "haln",
                ],
            )
        ],
        ScriptType.BENGALI: [
            FontConfiguration(
                family_name="Noto Sans Bengali",
                script_support=[ScriptType.BENGALI],
                weights=[400, 600, 700],
                styles=["normal"],
                subset_ranges={"bengali": "U+0980-09FF"},
                fallback_order=1,
                features=[
                    "locl",
                    "nukt",
                    "akhn",
                    "rphf",
                    "blwf",
                    "half",
                    "pstf",
                    "vatu",
                    "init",
                    "pres",
                    "abvs",
                    "blws",
                    "psts",
                    "haln",
                ],
            )
        ],
    }

    # Language to script mapping
    LANGUAGE_SCRIPTS = {
        "en": ScriptType.LATIN,
        "es": ScriptType.LATIN,
        "fr": ScriptType.LATIN,
        "ar": ScriptType.ARABIC,
        "fa": ScriptType.ARABIC,
        "ps": ScriptType.ARABIC,
        "ur": ScriptType.ARABIC,
        "hi": ScriptType.DEVANAGARI,
        "ne": ScriptType.DEVANAGARI,
        "bn": ScriptType.BENGALI,
        "sw": ScriptType.LATIN,
        "am": ScriptType.ETHIOPIC,
        "he": ScriptType.HEBREW,
        "ru": ScriptType.CYRILLIC,
        "zh": ScriptType.CHINESE,
        "ja": ScriptType.JAPANESE,
        "ko": ScriptType.KOREAN,
        "th": ScriptType.THAI,
    }

    # Font loading strategies
    LOADING_STRATEGIES = {
        "critical": ["latin", "arabic"],  # Load immediately
        "prefetch": ["devanagari", "bengali"],  # Load after critical
        "lazy": ["chinese", "japanese", "korean"],  # Load on demand
    }

    def __init__(self) -> None:
        """Initialize font manager."""
        self.loaded_fonts: Dict[str, bool] = {}
        self.font_cache: Dict[str, FontConfiguration] = {}
        self._init_font_cache()

    def _init_font_cache(self) -> None:
        """Initialize font cache with configurations."""
        for script, fonts in self.FONT_STACKS.items():
            for font in fonts:
                cache_key = f"{font.family_name}:{script.value}"
                self.font_cache[cache_key] = font

    def get_font_stack(self, language: str) -> List[str]:
        """
        Get CSS font stack for a language.

        Args:
            language: Language code

        Returns:
            List of font families in order
        """
        script = self.LANGUAGE_SCRIPTS.get(language, ScriptType.LATIN)
        fonts = self.FONT_STACKS.get(script, [])

        # Build font stack
        stack = []
        for font in sorted(fonts, key=lambda f: f.fallback_order):
            stack.append(f'"{font.family_name}"')

        # Add system fallbacks
        if script == ScriptType.ARABIC:
            stack.extend(['"Segoe UI"', '"Tahoma"', '"Arial Unicode MS"'])
        elif script in [ScriptType.DEVANAGARI, ScriptType.BENGALI]:
            stack.extend(['"Segoe UI"', '"Arial Unicode MS"'])

        # Always add generic fallbacks
        stack.extend(["system-ui", "-apple-system", "sans-serif"])

        return stack

    def get_font_css(self, language: str) -> str:
        """
        Generate CSS for font loading.

        Args:
            language: Language code

        Returns:
            CSS string with @font-face declarations
        """
        script = self.LANGUAGE_SCRIPTS.get(language, ScriptType.LATIN)
        fonts = self.FONT_STACKS.get(script, [])

        css_rules = []

        for font in fonts:
            for weight in font.weights:
                for style in font.styles:
                    # Generate @font-face rule
                    rule = self._generate_font_face(font, weight, style)
                    css_rules.append(rule)

        return "\n".join(css_rules)

    def _generate_font_face(
        self, font: FontConfiguration, weight: int, style: str
    ) -> str:
        """Generate @font-face CSS rule."""
        # Determine font file name
        weight_name = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}.get(
            weight, str(weight)
        )

        style_suffix = "-Italic" if style == "italic" else ""
        font_file = f"{font.family_name}-{weight_name}{style_suffix}"

        # Build unicode-range
        unicode_ranges = ", ".join(font.subset_ranges.values())

        # Font loading strategy
        display = "swap"  # Always use font-display: swap for better UX

        css = f"""
@font-face {{
    font-family: '{font.family_name}';
    font-style: {style};
    font-weight: {weight};
    font-display: {display};
    src: url('/fonts/{font_file}.woff2') format('woff2'),
         url('/fonts/{font_file}.woff') format('woff');
    unicode-range: {unicode_ranges};
}}"""

        return css.strip()

    def get_dynamic_subset(
        self, text: str, font_family: str, _script: ScriptType
    ) -> str:
        """
        Generate dynamic font subset for specific text.

        Args:
            text: Text to subset for
            font_family: Font family name
            script: Script type

        Returns:
            Base64 encoded font subset
        """
        # In production, would use fonttools to create subset
        # This is a placeholder
        logger.info(f"Generating subset for {font_family} with text length {len(text)}")

        # Extract unique characters
        unique_chars = set(text)

        # Would subset font file here
        return f"subset_{font_family}_{len(unique_chars)}"

    def load_font_async(self, language: str) -> Dict[str, Any]:
        """
        Get font loading configuration for async loading.

        Args:
            language: Language code

        Returns:
            Configuration for frontend font loader
        """
        script = self.LANGUAGE_SCRIPTS.get(language, ScriptType.LATIN)
        fonts = self.FONT_STACKS.get(script, [])

        config: Dict[str, Any] = {
            "fonts": [],
            "strategy": self._get_loading_strategy(script),
            "timeout": 3000,  # 3 second timeout
        }

        for font in fonts:
            for weight in font.weights[:2]:  # Load only essential weights initially
                config["fonts"].append(
                    {
                        "family": font.family_name,
                        "weight": weight,
                        "style": "normal",
                        "url": f"/fonts/{font.family_name}-{weight}.woff2",
                        "unicodeRange": font.subset_ranges,
                    }
                )

        return config

    def _get_loading_strategy(self, script: ScriptType) -> str:
        """Determine loading strategy for script."""
        script_value = script.value

        for strategy, scripts in self.LOADING_STRATEGIES.items():
            if script_value in scripts:
                return strategy

        return "lazy"

    def get_opentype_features(self, language: str) -> List[str]:
        """
        Get OpenType features to enable for a language.

        Args:
            language: Language code

        Returns:
            List of OpenType feature tags
        """
        script = self.LANGUAGE_SCRIPTS.get(language, ScriptType.LATIN)

        # Common features for all scripts
        features = ["kern", "liga"]

        # Script-specific features
        if script == ScriptType.ARABIC:
            features.extend(
                [
                    "init",  # Initial forms
                    "medi",  # Medial forms
                    "fina",  # Final forms
                    "isol",  # Isolated forms
                    "liga",  # Ligatures
                    "calt",  # Contextual alternates
                    "mark",  # Mark positioning
                    "mkmk",  # Mark to mark positioning
                ]
            )
        elif script in [ScriptType.DEVANAGARI, ScriptType.BENGALI]:
            features.extend(
                [
                    "locl",  # Localized forms
                    "nukt",  # Nukta forms
                    "akhn",  # Akhand ligatures
                    "rphf",  # Reph forms
                    "blwf",  # Below base forms
                    "half",  # Half forms
                    "vatu",  # Vattu variants
                    "pres",  # Pre-base substitutions
                    "abvs",  # Above base substitutions
                    "blws",  # Below base substitutions
                    "psts",  # Post base substitutions
                    "haln",  # Halant forms
                ]
            )

        return features

    def generate_font_preload_tags(
        self, languages: List[str], critical_only: bool = True
    ) -> List[str]:
        """
        Generate HTML preload tags for fonts.

        Args:
            languages: List of language codes
            critical_only: Only preload critical fonts

        Returns:
            List of HTML link tags
        """
        tags = []
        processed_fonts = set()

        for language in languages:
            script = self.LANGUAGE_SCRIPTS.get(language, ScriptType.LATIN)

            if critical_only:
                strategy = self._get_loading_strategy(script)
                if strategy != "critical":
                    continue

            fonts = self.FONT_STACKS.get(script, [])

            for font in fonts[:1]:  # Only preload primary font
                font_key = f"{font.family_name}-400"

                if font_key not in processed_fonts:
                    processed_fonts.add(font_key)

                    tag = (
                        f'<link rel="preload" '
                        f'href="/fonts/{font.family_name}-Regular.woff2" '
                        f'as="font" type="font/woff2" crossorigin>'
                    )
                    tags.append(tag)

        return tags

    def get_font_metrics(self, font_family: str) -> Dict[str, Union[int, float]]:
        """
        Get font metrics for layout calculations.

        Args:
            font_family: Font family name

        Returns:
            Dictionary of font metrics
        """
        # Predefined metrics for common fonts
        # In production, would extract from font files
        metrics: Dict[str, Dict[str, Union[int, float]]] = {
            "Inter": {
                "unitsPerEm": 2048,
                "ascent": 1900,
                "descent": -500,
                "lineGap": 0,
                "capHeight": 1456,
                "xHeight": 1072,
            },
            "Noto Sans Arabic": {
                "unitsPerEm": 2048,
                "ascent": 2189,
                "descent": -600,
                "lineGap": 0,
                "capHeight": 1462,
                "xHeight": 1098,
            },
            "Noto Sans Devanagari": {
                "unitsPerEm": 2048,
                "ascent": 2300,
                "descent": -700,
                "lineGap": 0,
                "capHeight": 1462,
                "xHeight": 1000,
            },
        }

        return metrics.get(font_family, metrics["Inter"])

    def optimize_font_loading(self, user_languages: List[str]) -> Dict[str, Any]:
        """
        Optimize font loading based on user's language preferences.

        Args:
            user_languages: Ordered list of user's languages

        Returns:
            Optimized loading configuration
        """
        config: Dict[str, Any] = {
            "immediate": [],
            "prefetch": [],
            "lazy": [],
            "subset_text": {},
        }

        # Prioritize fonts based on user languages
        for idx, language in enumerate(user_languages):
            script = self.LANGUAGE_SCRIPTS.get(language, ScriptType.LATIN)
            fonts = self.FONT_STACKS.get(script, [])

            if idx == 0:  # Primary language
                config["immediate"].extend([f.family_name for f in fonts[:1]])
            elif idx < 3:  # Secondary languages
                config["prefetch"].extend([f.family_name for f in fonts[:1]])
            else:  # Other languages
                config["lazy"].extend([f.family_name for f in fonts[:1]])

        # Remove duplicates while preserving order
        config["immediate"] = list(dict.fromkeys(config["immediate"]))
        config["prefetch"] = list(dict.fromkeys(config["prefetch"]))
        config["lazy"] = list(dict.fromkeys(config["lazy"]))

        return config


# Font optimization utilities
class FontOptimizer:
    """Utilities for font optimization."""

    @staticmethod
    def calculate_subset_size(text: str, font_config: FontConfiguration) -> int:
        """Calculate estimated subset size for text."""
        unique_chars = len(set(text))

        # Rough estimation: ~1KB per 100 characters
        base_size = (unique_chars / 100) * 1024

        # Add overhead for font tables
        overhead = 2048  # 2KB base overhead

        # Add feature complexity
        feature_multiplier = 1 + (len(font_config.features or []) * 0.1)

        return int((base_size + overhead) * feature_multiplier)

    @staticmethod
    def should_subset_font(
        text: str,
        font_config: FontConfiguration,
        full_font_size: int = 100000,  # 100KB default
    ) -> bool:
        """Determine if font subsetting is beneficial."""
        subset_size = FontOptimizer.calculate_subset_size(text, font_config)

        # Subset if it saves more than 50% size
        return subset_size < (full_font_size * 0.5)

    @staticmethod
    def get_critical_unicode_ranges(script: ScriptType) -> List[str]:
        """Get critical Unicode ranges for initial load."""
        critical_ranges = {
            ScriptType.LATIN: ["U+0020-007F"],  # Basic Latin
            ScriptType.ARABIC: ["U+0600-06FF"],  # Basic Arabic
            ScriptType.DEVANAGARI: ["U+0900-097F"],  # Basic Devanagari
            ScriptType.BENGALI: ["U+0980-09FF"],  # Basic Bengali
            ScriptType.CHINESE: ["U+4E00-9FFF"],  # CJK Unified Ideographs
        }

        return critical_ranges.get(script, [])


# Global font manager instance
font_manager = FontManager()
