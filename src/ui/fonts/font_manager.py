"""
Font Management System for Multi-Language Support.

This module provides comprehensive font management for supporting multiple
writing systems and languages in the Haven Health Passport application.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class WritingSystem(str, Enum):
    """Writing systems supported."""

    LATIN = "latin"
    ARABIC = "arabic"
    DEVANAGARI = "devanagari"  # Hindi, Nepali
    BENGALI = "bengali"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    KOREAN = "korean"
    CYRILLIC = "cyrillic"
    GREEK = "greek"
    HEBREW = "hebrew"
    THAI = "thai"
    ETHIOPIC = "ethiopic"  # Amharic


class FontWeight(str, Enum):
    """Font weight values."""

    THIN = "100"
    EXTRA_LIGHT = "200"
    LIGHT = "300"
    REGULAR = "400"
    MEDIUM = "500"
    SEMI_BOLD = "600"
    BOLD = "700"
    EXTRA_BOLD = "800"
    BLACK = "900"


class FontCategory(str, Enum):
    """Font categories for different uses."""

    UI = "ui"  # Interface elements
    READING = "reading"  # Body text
    DISPLAY = "display"  # Headers, titles
    MEDICAL = "medical"  # Medical terminology
    HANDWRITING = "handwriting"  # Signatures, notes
    MONOSPACE = "monospace"  # Code, numbers


@dataclass
class FontDefinition:
    """Definition of a font family."""

    family_name: str
    display_name: str
    writing_systems: List[WritingSystem]
    weights: List[FontWeight]
    category: FontCategory
    fallbacks: List[str]
    features: Dict[str, bool]  # OpenType features
    subset_ranges: Optional[List[str]] = None
    local_name: Optional[Dict[str, str]] = None  # Localized font names
    file_urls: Optional[Dict[str, str]] = None  # weight -> URL


@dataclass
class FontStack:
    """Font stack for a specific use case."""

    name: str
    primary_font: str
    fallback_fonts: List[str]
    system_fonts: List[str]
    writing_systems: List[WritingSystem]
    css_value: str


class FontManager:
    """Manages fonts for multi-language support."""

    # System font stacks by platform
    SYSTEM_FONTS = {
        "general": {
            "windows": ["Segoe UI", "Arial", "sans-serif"],
            "mac": ["SF Pro Text", "Helvetica Neue", "sans-serif"],
            "linux": ["Ubuntu", "DejaVu Sans", "sans-serif"],
            "android": ["Roboto", "Droid Sans", "sans-serif"],
            "ios": ["SF Pro Text", "-apple-system", "sans-serif"],
        },
        "arabic": {
            "windows": ["Segoe UI", "Arial", "Tahoma"],
            "mac": ["SF Arabic", "Geeza Pro", "Arial"],
            "android": ["Noto Sans Arabic", "Droid Arabic Naskh"],
            "ios": ["SF Arabic", "-apple-system"],
        },
        "chinese": {
            "windows": ["Microsoft YaHei", "SimHei", "sans-serif"],
            "mac": ["PingFang SC", "Hiragino Sans GB", "sans-serif"],
            "android": ["Noto Sans CJK SC", "Droid Sans Fallback"],
            "ios": ["PingFang SC", "-apple-system"],
        },
        "devanagari": {
            "windows": ["Nirmala UI", "Mangal", "sans-serif"],
            "mac": ["Devanagari MT", "ITF Devanagari", "sans-serif"],
            "android": ["Noto Sans Devanagari", "Droid Sans Devanagari"],
            "ios": ["Devanagari Sangam MN", "-apple-system"],
        },
    }

    # Font stacks for different use cases
    DEFAULT_STACKS = {
        "ui": {
            "latin": ["Inter", "Segoe UI", "Roboto", "sans-serif"],
            "arabic": ["IBM Plex Sans Arabic", "Segoe UI", "Arial"],
            "chinese": ["Noto Sans SC", "Microsoft YaHei", "sans-serif"],
            "devanagari": ["Noto Sans Devanagari", "Nirmala UI", "sans-serif"],
        },
        "reading": {
            "latin": ["Source Serif Pro", "Georgia", "serif"],
            "arabic": ["Noto Naskh Arabic", "Traditional Arabic", "serif"],
            "chinese": ["Noto Serif SC", "SimSun", "serif"],
            "devanagari": ["Noto Serif Devanagari", "Kokila", "serif"],
        },
        "medical": {
            "latin": ["IBM Plex Sans", "Arial", "sans-serif"],
            "arabic": ["IBM Plex Sans Arabic", "Arial", "sans-serif"],
            "chinese": ["Source Han Sans SC", "Microsoft YaHei", "sans-serif"],
            "devanagari": ["Noto Sans Devanagari", "Arial Unicode MS", "sans-serif"],
        },
    }

    # OpenType features for different languages
    OPENTYPE_FEATURES = {
        "arabic": {
            "liga": True,  # Ligatures
            "calt": True,  # Contextual alternates
            "init": True,  # Initial forms
            "medi": True,  # Medial forms
            "fina": True,  # Final forms
            "isol": True,  # Isolated forms
            "mark": True,  # Mark positioning
            "mkmk": True,  # Mark to mark positioning
            "kern": True,  # Kerning
        },
        "devanagari": {
            "locl": True,  # Localized forms
            "akhn": True,  # Akhands
            "rphf": True,  # Reph forms
            "rkrf": True,  # Rakar forms
            "blwf": True,  # Below-base forms
            "half": True,  # Half forms
            "vatu": True,  # Vattu variants
            "pres": True,  # Pre-base substitutions
            "abvs": True,  # Above-base substitutions
            "blws": True,  # Below-base substitutions
            "psts": True,  # Post-base substitutions
            "haln": True,  # Halant forms
        },
        "latin": {
            "liga": True,  # Ligatures
            "kern": True,  # Kerning
            "calt": True,  # Contextual alternates
            "case": True,  # Case-sensitive forms
            "tnum": True,  # Tabular numbers
            "onum": False,  # Oldstyle numbers
            "smcp": False,  # Small caps
            "c2sc": False,  # Capitals to small caps
        },
    }

    def __init__(self) -> None:
        """Initialize font manager."""
        self.font_definitions: Dict[str, FontDefinition] = {}
        self.font_stacks: Dict[str, FontStack] = {}
        self.loaded_fonts: Set[str] = set()
        self._initialize_fonts()

    def _initialize_fonts(self) -> None:
        """Initialize font definitions."""
        # Inter - Primary UI font for Latin
        self.font_definitions["Inter"] = FontDefinition(
            family_name="Inter",
            display_name="Inter",
            writing_systems=[WritingSystem.LATIN],
            weights=[
                FontWeight.REGULAR,
                FontWeight.MEDIUM,
                FontWeight.SEMI_BOLD,
                FontWeight.BOLD,
            ],
            category=FontCategory.UI,
            fallbacks=["Segoe UI", "Roboto", "sans-serif"],
            features={"kern": True, "liga": True, "calt": True, "tnum": True},
            subset_ranges=["latin", "latin-ext"],
            file_urls={
                FontWeight.REGULAR: "https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2",
                FontWeight.MEDIUM: "https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuI6fAZ9hiA.woff2",
                FontWeight.BOLD: "https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuFuYAZ9hiA.woff2",
            },
        )

        # IBM Plex Sans Arabic - Primary Arabic font
        self.font_definitions["IBM Plex Sans Arabic"] = FontDefinition(
            family_name="IBM Plex Sans Arabic",
            display_name="IBM Plex Sans Arabic",
            writing_systems=[WritingSystem.ARABIC],
            weights=[FontWeight.REGULAR, FontWeight.MEDIUM, FontWeight.BOLD],
            category=FontCategory.UI,
            fallbacks=["Segoe UI", "Arial"],
            features=self.OPENTYPE_FEATURES["arabic"],
            subset_ranges=["arabic"],
            local_name={"ar": "آي بي إم بلكس سانس عربي"},
        )

        # Noto Sans Devanagari - Primary Devanagari font
        self.font_definitions["Noto Sans Devanagari"] = FontDefinition(
            family_name="Noto Sans Devanagari",
            display_name="Noto Sans Devanagari",
            writing_systems=[WritingSystem.DEVANAGARI],
            weights=[FontWeight.REGULAR, FontWeight.MEDIUM, FontWeight.BOLD],
            category=FontCategory.UI,
            fallbacks=["Nirmala UI", "Arial Unicode MS"],
            features=self.OPENTYPE_FEATURES["devanagari"],
            subset_ranges=["devanagari"],
        )

        # Noto Sans Bengali - Primary Bengali font
        self.font_definitions["Noto Sans Bengali"] = FontDefinition(
            family_name="Noto Sans Bengali",
            display_name="Noto Sans Bengali",
            writing_systems=[WritingSystem.BENGALI],
            weights=[FontWeight.REGULAR, FontWeight.MEDIUM, FontWeight.BOLD],
            category=FontCategory.UI,
            fallbacks=["Vrinda", "Arial Unicode MS"],
            features={
                "locl": True,
                "init": True,
                "akhn": True,
                "rphf": True,
                "blwf": True,
                "half": True,
                "pstf": True,
                "vatu": True,
                "cjct": True,
            },
            subset_ranges=["bengali"],
        )

        # Create default font stacks
        self._create_font_stacks()

    def _create_font_stacks(self) -> None:
        """Create font stacks for different use cases."""
        # UI font stack
        self.font_stacks["ui-primary"] = FontStack(
            name="ui-primary",
            primary_font="Inter",
            fallback_fonts=["Segoe UI", "Roboto", "Helvetica Neue"],
            system_fonts=["system-ui", "-apple-system", "sans-serif"],
            writing_systems=[WritingSystem.LATIN],
            css_value='Inter, "Segoe UI", Roboto, "Helvetica Neue", system-ui, -apple-system, sans-serif',
        )

        # Arabic UI font stack
        self.font_stacks["ui-arabic"] = FontStack(
            name="ui-arabic",
            primary_font="IBM Plex Sans Arabic",
            fallback_fonts=["Segoe UI", "Arial"],
            system_fonts=["system-ui", "sans-serif"],
            writing_systems=[WritingSystem.ARABIC],
            css_value='"IBM Plex Sans Arabic", "Segoe UI", Arial, system-ui, sans-serif',
        )

        # Medical terminology font stack
        self.font_stacks["medical"] = FontStack(
            name="medical",
            primary_font="IBM Plex Sans",
            fallback_fonts=["Source Sans Pro", "Arial"],
            system_fonts=["sans-serif"],
            writing_systems=[WritingSystem.LATIN],
            css_value='"IBM Plex Sans", "Source Sans Pro", Arial, sans-serif',
        )

    def get_font_stack(
        self,
        category: FontCategory,
        writing_system: WritingSystem,
        language: Optional[str] = None,
    ) -> FontStack:
        """Get appropriate font stack for use case."""
        # Find matching font stack
        for stack_name, stack in self.font_stacks.items():
            if writing_system in stack.writing_systems:
                if category.value in stack_name:
                    return stack

        # Create dynamic font stack if not found
        return self._create_dynamic_stack(category, writing_system, language)

    def _create_dynamic_stack(
        self,
        category: FontCategory,
        writing_system: WritingSystem,
        language: Optional[str] = None,
    ) -> FontStack:
        """Create dynamic font stack for specific needs."""
        # Get fonts supporting this writing system
        suitable_fonts = []
        for font_name, font_def in self.font_definitions.items():
            if (
                writing_system in font_def.writing_systems
                and font_def.category == category
            ):
                suitable_fonts.append(font_name)

        # Get system fonts
        system_fonts = self._get_system_fonts(writing_system)

        # Build CSS value
        all_fonts = suitable_fonts + system_fonts
        css_value = ", ".join(f'"{f}"' if " " in f else f for f in all_fonts)

        return FontStack(
            name=f"dynamic-{category.value}-{writing_system.value}",
            primary_font=suitable_fonts[0] if suitable_fonts else system_fonts[0],
            fallback_fonts=suitable_fonts[1:] if len(suitable_fonts) > 1 else [],
            system_fonts=system_fonts,
            writing_systems=[writing_system],
            css_value=css_value,
        )

    def _get_system_fonts(self, writing_system: WritingSystem) -> List[str]:
        """Get system fonts for writing system."""
        # Map writing systems to font categories
        category_map = {
            WritingSystem.ARABIC: "arabic",
            WritingSystem.CHINESE: "chinese",
            WritingSystem.DEVANAGARI: "devanagari",
            WritingSystem.BENGALI: "devanagari",  # Similar fallbacks
        }

        category = category_map.get(writing_system, "general")

        # Get cross-platform fonts
        all_fonts = []
        for platform_fonts in self.SYSTEM_FONTS.get(category, {}).values():
            all_fonts.extend(platform_fonts)

        # Remove duplicates while preserving order
        seen = set()
        unique_fonts = []
        for font in all_fonts:
            if font not in seen:
                seen.add(font)
                unique_fonts.append(font)

        return unique_fonts

    async def load_web_font(
        self,
        font_name: str,
        weights: Optional[List[FontWeight]] = None,
        subsets: Optional[List[str]] = None,
    ) -> bool:
        """Load web font dynamically."""
        font_def = self.font_definitions.get(font_name)
        if not font_def:
            logger.error(f"Font definition not found: {font_name}")
            return False

        if font_name in self.loaded_fonts:
            logger.info(f"Font already loaded: {font_name}")
            return True

        try:
            # Generate @font-face CSS
            css_rules = self._generate_font_face(font_def, weights, subsets)

            # Inject CSS
            await self._inject_font_css(css_rules)

            # Preload critical fonts
            if font_def.category in [FontCategory.UI, FontCategory.MEDICAL]:
                await self._preload_font(font_def, weights)

            self.loaded_fonts.add(font_name)
            logger.info(f"Successfully loaded font: {font_name}")
            return True

        except Exception as e:
            logger.error(f"Error loading font {font_name}: {e}")
            return False

    def _generate_font_face(
        self,
        font_def: FontDefinition,
        weights: Optional[List[FontWeight]] = None,
        subsets: Optional[List[str]] = None,
    ) -> str:
        """Generate @font-face CSS rules."""
        weights = weights or font_def.weights
        subsets = subsets or font_def.subset_ranges or []

        css_rules = []

        for weight in weights:
            if weight not in font_def.weights:
                continue

            url = font_def.file_urls.get(weight) if font_def.file_urls else None
            if not url:
                continue

            # Unicode ranges for subsets
            unicode_ranges = self._get_unicode_ranges(subsets)

            rule = f"""
@font-face {{
    font-family: '{font_def.family_name}';
    font-style: normal;
    font-weight: {weight.value};
    font-display: swap;
    src: url('{url}') format('woff2');
    {f"unicode-range: {', '.join(unicode_ranges)};" if unicode_ranges else ""}
}}"""
            css_rules.append(rule)

        return "\n".join(css_rules)

    def _get_unicode_ranges(self, subsets: List[str]) -> List[str]:
        """Get Unicode ranges for font subsets."""
        ranges = {
            "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
            "latin-ext": "U+0100-024F, U+0259, U+1E00-1EFF, U+2020, U+20A0-20AB, U+20AD-20CF, U+2113, U+2C60-2C7F, U+A720-A7FF",
            "arabic": "U+0600-06FF, U+200C-200E, U+2010-2011, U+204F, U+2E41, U+FB50-FDFF, U+FE70-FEFF",
            "devanagari": "U+0900-097F, U+1CD0-1CF6, U+1CF8-1CF9, U+200C-200D, U+20A8, U+20B9, U+25CC, U+A830-A839, U+A8E0-A8FB",
            "bengali": "U+0980-09FF, U+200C-200D, U+20B9, U+25CC",
        }

        return [ranges[subset] for subset in subsets if subset in ranges]

    async def _inject_font_css(self, css_rules: str) -> None:
        """Inject font CSS into document.

        CRITICAL: This ensures proper font rendering for multiple languages
        in refugee healthcare communications.
        """
        try:
            # Create a unique style element ID
            style_id = f"haven-fonts-{hash(css_rules) % 10000}"

            # For server-side rendering, return injectable HTML
            style_element = f"""
<style id="{style_id}" type="text/css">
{css_rules}
</style>
"""

            # Store in a class variable for retrieval by the web framework
            if not hasattr(self, "_injected_styles"):
                self._injected_styles = {}

            self._injected_styles[style_id] = {
                "css": css_rules,
                "html": style_element,
                "timestamp": datetime.now(),
            }

            # For client-side injection (when running in browser context)
            # This would be handled by the JavaScript layer
            injection_script = f"""
<script>
(function() {{
    // Check if style already exists
    if (document.getElementById('{style_id}')) {{
        return;
    }}
    // Create and inject style element
    var style = document.createElement('style');
    style.id = '{style_id}';
    style.type = 'text/css';
    style.innerHTML = `{css_rules.replace('`', '\\`')}`;
    // Add to head
    document.head.appendChild(style);
    // Log for debugging
    console.log('Injected font CSS for Haven Health Passport: {style_id}');
}})();
</script>
"""

            # Store the injection script for web frameworks to use
            self._injected_styles[style_id]["script"] = injection_script

            logger.info(
                f"Prepared font CSS injection: {style_id} ({len(css_rules)} chars)"
            )

        except Exception as e:
            logger.error(f"Failed to inject font CSS: {e}")
            raise

    async def _preload_font(
        self, font_def: FontDefinition, weights: Optional[List[FontWeight]] = None
    ) -> None:
        """Preload critical font files.

        CRITICAL: Ensures medical information renders immediately for refugees,
        preventing delays that could impact healthcare delivery.
        """
        weights = weights or [FontWeight.REGULAR, FontWeight.BOLD]

        preload_links = []

        for weight in weights:
            url = font_def.file_urls.get(weight) if font_def.file_urls else None
            if url:
                # Create preload link element
                preload_link = f"""<link
rel="preload"
href="{url}"
as="font"
type="font/woff2"
crossorigin="anonymous"
data-font-family="{font_def.family_name}"
data-font-weight="{weight.value}"
/>"""
                preload_links.append(preload_link)

                # Log for monitoring
                logger.info(
                    f"Preloading font: {font_def.family_name} {weight.value} from {url}"
                )

        # Store preload links for injection
        if not hasattr(self, "_preload_links"):
            self._preload_links = {}

        font_key = f"{font_def.family_name}-{'-'.join(w.value for w in weights)}"
        self._preload_links[font_key] = {
            "links": preload_links,
            "html": "\n".join(preload_links),
            "timestamp": datetime.now(),
            "font_family": font_def.family_name,
            "weights": [w.value for w in weights],
        }

        # For client-side dynamic preloading
        preload_script = f"""
<script>
(function() {{
    // Preload fonts for Haven Health Passport
    const fonts = {json.dumps([
            {{'family': font_def.family_name, 'weight': w.value, 'url': font_def.file_urls.get(w)}}
            for w in weights if font_def.file_urls and font_def.file_urls.get(w)
        ])};
    fonts.forEach(font => {{
        // Check if already preloaded
        const existing = document.querySelector(
            `link[rel="preload"][href="${{font.url}}"]`
        );
            if (!existing) {{
            const link = document.createElement('link');
            link.rel = 'preload';
            link.href = font.url;
            link.as = 'font';
            link.type = 'font/woff2';
            link.crossOrigin = 'anonymous';
            link.setAttribute('data-font-family', font.family);
            link.setAttribute('data-font-weight', font.weight);
                    document.head.appendChild(link);
                    // Also trigger actual font load for critical fonts
            if (font.weight === '400' || font.weight === '700') {{
                const fontFace = new FontFace(
                    font.family,
                    `url(${{font.url}})`,
                    {{ weight: font.weight }}
                );
                            fontFace.load().then(() => {{
                    document.fonts.add(fontFace);
                    console.log(`Loaded critical font: ${{font.family}} ${{font.weight}}`);
                }}).catch(err => {{
                    console.error(`Failed to load font: ${{font.family}}`, err);
                }});
            }}
        }}
    }});
}})();
</script>
"""

        self._preload_links[font_key]["script"] = preload_script

    def get_font_features_css(
        self, writing_system: WritingSystem, category: FontCategory = FontCategory.UI
    ) -> str:
        """Get CSS for OpenType features."""
        features = self.OPENTYPE_FEATURES.get(writing_system.value, {})

        if not features:
            return ""

        # Build font-feature-settings value
        enabled_features = []
        disabled_features = []

        for feature, enabled in features.items():
            if enabled:
                enabled_features.append(f'"{feature}"')
            else:
                disabled_features.append(f'"{feature}" 0')

        settings = enabled_features + disabled_features

        return f"font-feature-settings: {', '.join(settings)};"

    def get_font_css_variables(self) -> str:
        """Get CSS variables for fonts."""
        css = ":root {\n"

        # Font families
        for stack_name, stack in self.font_stacks.items():
            css += f"  --font-{stack_name}: {stack.css_value};\n"

        # Font weights
        for weight in FontWeight:
            css += f"  --font-weight-{weight.name.lower().replace('_', '-')}: {weight.value};\n"

        # Font sizes
        sizes = {
            "xs": "0.75rem",
            "sm": "0.875rem",
            "base": "1rem",
            "lg": "1.125rem",
            "xl": "1.25rem",
            "2xl": "1.5rem",
            "3xl": "1.875rem",
            "4xl": "2.25rem",
        }

        for size_name, size_value in sizes.items():
            css += f"  --font-size-{size_name}: {size_value};\n"

        # Line heights
        line_heights = {
            "tight": "1.25",
            "snug": "1.375",
            "normal": "1.5",
            "relaxed": "1.625",
            "loose": "2",
        }

        for height_name, height_value in line_heights.items():
            css += f"  --line-height-{height_name}: {height_value};\n"

        css += "}\n"

        return css

    def validate_font_support(
        self, text: str, font_stack: FontStack
    ) -> Tuple[bool, List[str]]:
        """Validate if font stack supports the text."""
        # Detect writing systems in text
        required_systems = self._detect_writing_systems(text)

        # Check if font stack supports all required systems
        unsupported = []
        for system in required_systems:
            if system not in font_stack.writing_systems:
                unsupported.append(system.value)

        return len(unsupported) == 0, unsupported

    def _detect_writing_systems(self, text: str) -> Set[WritingSystem]:
        """Detect writing systems used in text."""
        systems = set()

        # Unicode ranges for detection
        ranges = {
            WritingSystem.LATIN: (0x0000, 0x024F),
            WritingSystem.ARABIC: (0x0600, 0x06FF),
            WritingSystem.DEVANAGARI: (0x0900, 0x097F),
            WritingSystem.BENGALI: (0x0980, 0x09FF),
            WritingSystem.CHINESE: (0x4E00, 0x9FFF),
            WritingSystem.HEBREW: (0x0590, 0x05FF),
            WritingSystem.CYRILLIC: (0x0400, 0x04FF),
        }

        for char in text:
            code_point = ord(char)
            for system, (start, end) in ranges.items():
                if start <= code_point <= end:
                    systems.add(system)

        return systems or {WritingSystem.LATIN}

    def get_rendering_hints(
        self, writing_system: WritingSystem, font_size: int
    ) -> Dict[str, Any]:
        """Get font rendering hints for optimal display."""
        hints = {
            "font-smoothing": "antialiased",
            "-webkit-font-smoothing": "antialiased",
            "-moz-osx-font-smoothing": "grayscale",
            "text-rendering": "optimizeLegibility",
        }

        # Specific hints for Arabic
        if writing_system == WritingSystem.ARABIC:
            hints.update(
                {"text-align": "right", "direction": "rtl", "unicode-bidi": "embed"}
            )

        # Hinting for small sizes
        if font_size < 14:
            hints["text-rendering"] = "geometricPrecision"

        # CJK specific
        if writing_system in [
            WritingSystem.CHINESE,
            WritingSystem.JAPANESE,
            WritingSystem.KOREAN,
        ]:
            hints["font-variant-east-asian"] = "proportional-width"

        return hints

    def get_system_font_paths(self, font_family: str) -> List[str]:
        """Get system font file paths for a font family.

        CRITICAL: Used for rendering medical text in images with proper
        language support for refugee populations.
        """
        # Common font paths by platform and font family
        font_paths = {
            "Inter": [
                "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
                "/usr/local/share/fonts/Inter-Regular.ttf",
                "/System/Library/Fonts/Supplemental/Inter-Regular.otf",  # macOS
                "C:\\Windows\\Fonts\\Inter-Regular.ttf",  # Windows
            ],
            "IBM Plex Sans Arabic": [
                "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansArabic-Regular.ttf",
                "/usr/local/share/fonts/IBMPlexSansArabic-Regular.ttf",
                "/System/Library/Fonts/Supplemental/IBMPlexSansArabic-Regular.otf",
                "C:\\Windows\\Fonts\\IBMPlexSansArabic-Regular.ttf",
            ],
            "Noto Sans Devanagari": [
                "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
                "/usr/local/share/fonts/NotoSansDevanagari-Regular.ttf",
                "/System/Library/Fonts/Supplemental/NotoSansDevanagari-Regular.ttf",
                "C:\\Windows\\Fonts\\NotoSansDevanagari-Regular.ttf",
            ],
            "Noto Sans Bengali": [
                "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
                "/usr/local/share/fonts/NotoSansBengali-Regular.ttf",
                "/System/Library/Fonts/Supplemental/NotoSansBengali-Regular.ttf",
                "C:\\Windows\\Fonts\\NotoSansBengali-Regular.ttf",
            ],
            "Noto Sans SC": [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
                "/System/Library/Fonts/Supplemental/NotoSansSC-Regular.otf",
                "C:\\Windows\\Fonts\\NotoSansSC-Regular.ttf",
            ],
            # System font fallbacks
            "Arial": [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:\\Windows\\Fonts\\arial.ttf",
            ],
            "default": [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:\\Windows\\Fonts\\arial.ttf",
            ],
        }

        # Return paths for requested font or default paths
        return font_paths.get(font_family, font_paths["default"])

    def get_injectable_styles(self) -> Dict[str, Any]:
        """Get all injectable styles for server-side rendering.

        Returns dict with style elements ready for injection into HTML.
        """
        return getattr(self, "_injected_styles", {})

    def get_preload_links(self) -> Dict[str, Any]:
        """Get all font preload links for server-side rendering.

        Returns dict with preload link elements ready for injection into HTML head.
        """
        return getattr(self, "_preload_links", {})


# Global font manager instance
font_manager = FontManager()
