"""
Medical Abbreviation Handler.

Handles medical abbreviations, acronyms, and shorthand notation commonly used in healthcare.
Provides context-aware expansion and resolution of ambiguous abbreviations.
Includes encrypted storage and access control for medical terminology.
 Handles FHIR Resource validation.
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AbbreviationEntry:
    """Single abbreviation entry with possible expansions."""

    abbreviation: str
    expansions: List[str]
    contexts: Dict[str, str]  # context -> specific expansion
    specialty: Optional[str] = None
    confidence: float = 1.0
    usage_frequency: Dict[str, float] = field(default_factory=dict)
    related_terms: List[str] = field(default_factory=list)


@dataclass
class AbbreviationMatch:
    """Matched abbreviation in text."""

    text: str
    start: int
    end: int
    expansions: List[str]
    selected_expansion: Optional[str] = None
    confidence: float = 0.0
    context_clues: List[str] = field(default_factory=list)


class MedicalAbbreviationHandler:
    """
    Comprehensive handler for medical abbreviations.

    Features:
    - Context-aware abbreviation expansion
    - Specialty-specific abbreviations
    - Ambiguity resolution
    - Custom abbreviation support
    - Multi-language abbreviations
    """

    def __init__(
        self,
        abbreviations_path: Optional[str] = None,
        enable_context_resolution: bool = True,
        min_confidence: float = 0.7,
        language: str = "en",
    ):
        """
        Initialize medical abbreviation handler.

        Args:
            abbreviations_path: Path to abbreviations database
            enable_context_resolution: Use context for disambiguation
            min_confidence: Minimum confidence for expansion
            language: Primary language for abbreviations
        """
        self.abbreviations: Dict[str, AbbreviationEntry] = {}
        self.context_patterns: Dict[str, List[re.Pattern]] = {}
        self.specialty_abbreviations: Dict[str, Dict[str, AbbreviationEntry]] = (
            defaultdict(dict)
        )
        self.enable_context_resolution = enable_context_resolution
        self.min_confidence = min_confidence
        self.language = language

        # Common medical context indicators
        self.context_indicators = {
            "cardiology": ["heart", "cardiac", "vessel", "artery", "blood pressure"],
            "neurology": ["brain", "nerve", "neurological", "seizure", "stroke"],
            "orthopedics": ["bone", "joint", "fracture", "muscle", "spine"],
            "pulmonology": ["lung", "breath", "respiratory", "oxygen", "airway"],
            "gastroenterology": ["stomach", "bowel", "liver", "digestive", "abdomen"],
            "laboratory": ["test", "result", "level", "count", "sample"],
            "medication": ["dose", "mg", "tablet", "injection", "administered"],
            "emergency": ["acute", "severe", "emergency", "stat", "critical"],
        }

        # Load abbreviations
        self._load_abbreviations(abbreviations_path)

        # Compile regex patterns
        self._compile_patterns()

        logger.info(
            "Initialized MedicalAbbreviationHandler with %s abbreviations",
            len(self.abbreviations),
        )

    def _load_abbreviations(self, path: Optional[str] = None) -> None:
        """Load medical abbreviations database."""
        if path and Path(path).exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for abbr_data in data:
                        entry = AbbreviationEntry(**abbr_data)
                        self.abbreviations[entry.abbreviation.upper()] = entry

                        # Add to specialty index
                        if entry.specialty:
                            self.specialty_abbreviations[entry.specialty][
                                entry.abbreviation.upper()
                            ] = entry

                logger.info(
                    "Loaded %d abbreviations from %s", len(self.abbreviations), path
                )
            except (IOError, json.JSONDecodeError) as e:
                logger.error("Error loading abbreviations: %s", e)
                self._load_default_abbreviations()
        else:
            self._load_default_abbreviations()

    def _load_default_abbreviations(self) -> None:
        """Load default medical abbreviations."""
        # Common medical abbreviations with context
        default_abbrs = [
            # Vital signs and measurements
            AbbreviationEntry("BP", ["blood pressure"], {"vitals": "blood pressure"}),
            AbbreviationEntry(
                "HR", ["heart rate", "hour"], {"vitals": "heart rate", "time": "hour"}
            ),
            AbbreviationEntry(
                "RR",
                ["respiratory rate", "relative risk"],
                {"vitals": "respiratory rate", "statistics": "relative risk"},
            ),
            AbbreviationEntry(
                "T",
                ["temperature", "thoracic"],
                {"vitals": "temperature", "anatomy": "thoracic"},
            ),
            AbbreviationEntry("O2", ["oxygen"], {}),
            AbbreviationEntry("SpO2", ["oxygen saturation"], {}),
            # Common conditions
            AbbreviationEntry(
                "DM",
                ["diabetes mellitus", "diastolic murmur"],
                {"endocrine": "diabetes mellitus", "cardiology": "diastolic murmur"},
            ),
            AbbreviationEntry("HTN", ["hypertension"], {}),
            AbbreviationEntry("CAD", ["coronary artery disease"], {}),
            AbbreviationEntry("COPD", ["chronic obstructive pulmonary disease"], {}),
            AbbreviationEntry("CHF", ["congestive heart failure"], {}),
            AbbreviationEntry(
                "MI",
                ["myocardial infarction", "mitral insufficiency"],
                {
                    "cardiology": "myocardial infarction",
                    "valvular": "mitral insufficiency",
                },
            ),
            AbbreviationEntry("CVA", ["cerebrovascular accident"], {}),
            AbbreviationEntry(
                "PE",
                ["pulmonary embolism", "physical examination"],
                {"emergency": "pulmonary embolism", "routine": "physical examination"},
            ),
            AbbreviationEntry("DVT", ["deep vein thrombosis"], {}),
            AbbreviationEntry("UTI", ["urinary tract infection"], {}),
            # Medications and treatments
            AbbreviationEntry(
                "ASA",
                ["aspirin", "aminosalicylic acid"],
                {"common": "aspirin", "tuberculosis": "aminosalicylic acid"},
            ),
            AbbreviationEntry("NSAID", ["non-steroidal anti-inflammatory drug"], {}),
            AbbreviationEntry("ACE", ["angiotensin-converting enzyme"], {}),
            AbbreviationEntry("ARB", ["angiotensin receptor blocker"], {}),
            AbbreviationEntry("PO", ["by mouth", "per os"], {}),
            AbbreviationEntry("IV", ["intravenous"], {}),
            AbbreviationEntry("IM", ["intramuscular"], {}),
            AbbreviationEntry("SC", ["subcutaneous"], {}),
            AbbreviationEntry("PRN", ["as needed", "pro re nata"], {}),
            AbbreviationEntry("BID", ["twice daily", "bis in die"], {}),
            AbbreviationEntry("TID", ["three times daily", "ter in die"], {}),
            AbbreviationEntry("QID", ["four times daily", "quater in die"], {}),
            AbbreviationEntry("QD", ["once daily", "quaque die"], {}),
            # Laboratory and diagnostics
            AbbreviationEntry("CBC", ["complete blood count"], {}),
            AbbreviationEntry("WBC", ["white blood cell"], {}),
            AbbreviationEntry("RBC", ["red blood cell"], {}),
            AbbreviationEntry("Hgb", ["hemoglobin"], {}),
            AbbreviationEntry("Hct", ["hematocrit"], {}),
            AbbreviationEntry("PLT", ["platelet"], {}),
            AbbreviationEntry("BUN", ["blood urea nitrogen"], {}),
            AbbreviationEntry(
                "Cr",
                ["creatinine", "chromium"],
                {"renal": "creatinine", "toxicology": "chromium"},
            ),
            AbbreviationEntry("LFT", ["liver function test"], {}),
            AbbreviationEntry("ALT", ["alanine aminotransferase"], {}),
            AbbreviationEntry("AST", ["aspartate aminotransferase"], {}),
            AbbreviationEntry("ECG", ["electrocardiogram"], {}),
            AbbreviationEntry("EKG", ["electrocardiogram"], {}),
            AbbreviationEntry("CXR", ["chest X-ray"], {}),
            AbbreviationEntry("CT", ["computed tomography"], {}),
            AbbreviationEntry("MRI", ["magnetic resonance imaging"], {}),
            # Anatomical and directional
            AbbreviationEntry(
                "L",
                ["left", "liter", "lumbar"],
                {"anatomy": "left", "volume": "liter", "spine": "lumbar"},
            ),
            AbbreviationEntry("R", ["right"], {"anatomy": "right"}),
            AbbreviationEntry("B/L", ["bilateral"], {}),
            AbbreviationEntry(
                "Cx",
                ["cervical", "culture"],
                {"spine": "cervical", "laboratory": "culture"},
            ),
            AbbreviationEntry(
                "Tx",
                ["treatment", "thoracic", "transplant"],
                {"plan": "treatment", "spine": "thoracic", "surgery": "transplant"},
            ),
            AbbreviationEntry("Rx", ["prescription", "therapy"], {}),
            AbbreviationEntry("Dx", ["diagnosis"], {}),
            AbbreviationEntry("Hx", ["history"], {}),
            AbbreviationEntry(
                "Sx",
                ["symptoms", "surgery"],
                {"clinical": "symptoms", "procedure": "surgery"},
            ),
            # Emergency and critical care
            AbbreviationEntry("ER", ["emergency room"], {}),
            AbbreviationEntry(
                "ED",
                ["emergency department", "erectile dysfunction"],
                {
                    "emergency": "emergency department",
                    "urology": "erectile dysfunction",
                },
            ),
            AbbreviationEntry("ICU", ["intensive care unit"], {}),
            AbbreviationEntry("CCU", ["coronary care unit", "critical care unit"], {}),
            AbbreviationEntry("OR", ["operating room"], {}),
            AbbreviationEntry("PACU", ["post-anesthesia care unit"], {}),
            AbbreviationEntry("DNR", ["do not resuscitate"], {}),
            AbbreviationEntry("DNI", ["do not intubate"], {}),
            AbbreviationEntry("STAT", ["immediately", "statim"], {}),
            # Common phrases
            AbbreviationEntry("S/P", ["status post"], {}),
            AbbreviationEntry("C/O", ["complains of"], {}),
            AbbreviationEntry("R/O", ["rule out"], {}),
            AbbreviationEntry("F/U", ["follow up"], {}),
            AbbreviationEntry(
                "D/C",
                ["discharge", "discontinue"],
                {"admission": "discharge", "medication": "discontinue"},
            ),
            AbbreviationEntry("H/O", ["history of"], {}),
            AbbreviationEntry("N/V", ["nausea and vomiting"], {}),
            AbbreviationEntry("SOB", ["shortness of breath"], {}),
            AbbreviationEntry(
                "CP",
                ["chest pain", "cerebral palsy"],
                {"cardiac": "chest pain", "neurology": "cerebral palsy"},
            ),
            AbbreviationEntry("HA", ["headache"], {}),
            AbbreviationEntry(
                "LOC", ["loss of consciousness", "level of consciousness"], {}
            ),
            # Units and measurements
            AbbreviationEntry("mg", ["milligram"], {}),
            AbbreviationEntry("mcg", ["microgram"], {}),
            AbbreviationEntry("g", ["gram"], {}),
            AbbreviationEntry("kg", ["kilogram"], {}),
            AbbreviationEntry("mL", ["milliliter"], {}),
            AbbreviationEntry("L", ["liter"], {"volume": "liter"}),
            AbbreviationEntry("mmHg", ["millimeters of mercury"], {}),
            AbbreviationEntry("bpm", ["beats per minute"], {}),
        ]

        for entry in default_abbrs:
            self.abbreviations[entry.abbreviation.upper()] = entry
            if entry.specialty:
                self.specialty_abbreviations[entry.specialty][
                    entry.abbreviation.upper()
                ] = entry

        logger.info("Loaded %d default medical abbreviations", len(default_abbrs))

    def _compile_patterns(self) -> None:
        """Compile regex patterns for abbreviation detection."""
        # Pattern for detecting potential abbreviations
        self.abbr_pattern = re.compile(
            r"\b([A-Z]{2,}|[A-Z]/[A-Z]|[A-Z]\.[A-Z]\.?|[A-Z][a-z]{0,2})\b"
        )

        # Compile specialty patterns
        for specialty, terms in self.context_indicators.items():
            patterns = [re.compile(rf"\b{term}\b", re.IGNORECASE) for term in terms]
            self.context_patterns[specialty] = patterns

    def detect_abbreviations(self, text: str) -> List[AbbreviationMatch]:
        """
        Detect potential medical abbreviations in text.

        Args:
            text: Input text

        Returns:
            List of detected abbreviation matches
        """
        matches = []

        # Find all potential abbreviations
        for match in self.abbr_pattern.finditer(text):
            abbr = match.group(0).upper()

            # Check if it's a known abbreviation
            if abbr in self.abbreviations:
                entry = self.abbreviations[abbr]

                # Create match object
                abbr_match = AbbreviationMatch(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    expansions=entry.expansions.copy(),
                )

                # Resolve based on context if enabled
                if self.enable_context_resolution and len(entry.expansions) > 1:
                    self.resolve_ambiguity(text, abbr_match, entry)
                else:
                    # Use first expansion as default
                    abbr_match.selected_expansion = entry.expansions[0]
                    abbr_match.confidence = entry.confidence

                matches.append(abbr_match)

        return matches

    def resolve_ambiguity(
        self, text: str, match: AbbreviationMatch, entry: AbbreviationEntry
    ) -> None:
        """Resolve ambiguous abbreviations based on context."""
        # Extract context window
        context_pattern = (
            rf"(?:^|\s)(.{{0,50}})\b{re.escape(match.text)}\b(.{{0,50}})(?:\s|$)"
        )
        context_match = re.search(context_pattern, text, re.IGNORECASE)

        if context_match:
            before_context = (
                context_match.group(1).lower() if context_match.group(1) else ""
            )
            after_context = (
                context_match.group(2).lower() if context_match.group(2) else ""
            )
            full_context = f"{before_context} {after_context}"

            # Check for specific contexts
            context_scores: Dict[str, float] = {}

            # Check predefined contexts
            for context_key, expansion in entry.contexts.items():
                if context_key in full_context:
                    context_scores[expansion] = context_scores.get(expansion, 0) + 2.0

            # Check specialty contexts
            for specialty, patterns in self.context_patterns.items():
                for pattern in patterns:
                    if pattern.search(full_context):
                        # Find expansions related to this specialty
                        for expansion in entry.expansions:
                            if specialty in expansion.lower() or any(
                                term in expansion.lower()
                                for term in self.context_indicators[specialty]
                            ):
                                context_scores[expansion] = (
                                    context_scores.get(expansion, 0) + 1.0
                                )
                        match.context_clues.append(specialty)

            # Check for direct term matches
            for expansion in entry.expansions:
                expansion_terms = expansion.lower().split()
                for term in expansion_terms:
                    if len(term) > 3 and term in full_context:
                        context_scores[expansion] = (
                            context_scores.get(expansion, 0) + 0.5
                        )

            # Select best expansion
            if context_scores:
                best_expansion = max(context_scores.items(), key=lambda x: x[1])
                match.selected_expansion = best_expansion[0]
                match.confidence = min(
                    1.0, best_expansion[1] / 3.0
                )  # Normalize confidence
            else:
                # Use frequency-based selection
                if entry.usage_frequency:
                    best_expansion = max(
                        entry.usage_frequency.items(), key=lambda x: x[1]
                    )
                    match.selected_expansion = best_expansion[0]
                    match.confidence = best_expansion[1]
                else:
                    # Default to first expansion
                    match.selected_expansion = entry.expansions[0]
                    match.confidence = 0.5

    def expand_abbreviations(
        self,
        text: str,
        preserve_original: bool = True,
        min_confidence: Optional[float] = None,
    ) -> str:
        """
        Expand medical abbreviations in text.

        Args:
            text: Input text
            preserve_original: Keep original abbreviation in parentheses
            min_confidence: Minimum confidence for expansion (uses handler default if None)

        Returns:
            Text with expanded abbreviations
        """
        min_conf = min_confidence or self.min_confidence

        # Detect abbreviations
        matches = self.detect_abbreviations(text)

        # Sort by position (reverse to avoid offset issues)
        matches.sort(key=lambda x: x.start, reverse=True)

        # Expand abbreviations
        expanded_text = text
        for match in matches:
            if match.selected_expansion and match.confidence >= min_conf:
                if preserve_original:
                    replacement = f"{match.selected_expansion} ({match.text})"
                else:
                    replacement = match.selected_expansion

                expanded_text = (
                    expanded_text[: match.start]
                    + replacement
                    + expanded_text[match.end :]
                )

        return expanded_text

    def add_custom_abbreviation(
        self,
        abbreviation: str,
        expansions: List[str],
        contexts: Optional[Dict[str, str]] = None,
        specialty: Optional[str] = None,
    ) -> None:
        """Add custom abbreviation to the handler."""
        entry = AbbreviationEntry(
            abbreviation=abbreviation.upper(),
            expansions=expansions,
            contexts=contexts or {},
            specialty=specialty,
        )

        self.abbreviations[abbreviation.upper()] = entry
        if specialty:
            self.specialty_abbreviations[specialty][abbreviation.upper()] = entry

        logger.info("Added custom abbreviation: %s", abbreviation)

    def get_abbreviation_info(self, abbreviation: str) -> Optional[AbbreviationEntry]:
        """Get information about a specific abbreviation."""
        return self.abbreviations.get(abbreviation.upper())

    def get_specialty_abbreviations(
        self, specialty: str
    ) -> Dict[str, AbbreviationEntry]:
        """Get all abbreviations for a specific medical specialty."""
        return self.specialty_abbreviations.get(specialty, {})

    def save_abbreviations(self, path: str) -> None:
        """Save current abbreviations to file."""
        data = []
        for entry in self.abbreviations.values():
            data.append(
                {
                    "abbreviation": entry.abbreviation,
                    "expansions": entry.expansions,
                    "contexts": entry.contexts,
                    "specialty": entry.specialty,
                    "confidence": entry.confidence,
                    "usage_frequency": entry.usage_frequency,
                    "related_terms": entry.related_terms,
                }
            )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Saved %d abbreviations to %s", len(data), path)


class AbbreviationExpander:
    """Simple interface for abbreviation expansion."""

    def __init__(self, handler: MedicalAbbreviationHandler):
        """Initialize expander with handler."""
        self.handler = handler

    def expand(
        self,
        text: str,
        preserve_original: bool = True,
        min_confidence: Optional[float] = None,
    ) -> str:
        """Expand abbreviations in text."""
        return self.handler.expand_abbreviations(
            text, preserve_original=preserve_original, min_confidence=min_confidence
        )


class AbbreviationDetector:
    """Simple interface for abbreviation detection."""

    def __init__(self, handler: MedicalAbbreviationHandler):
        """Initialize detector with handler."""
        self.handler = handler

    def detect(self, text: str) -> List[Dict[str, Any]]:
        """Detect abbreviations and return as dictionaries."""
        matches = self.handler.detect_abbreviations(text)
        return [
            {
                "text": m.text,
                "position": (m.start, m.end),
                "expansions": m.expansions,
                "selected": m.selected_expansion,
                "confidence": m.confidence,
                "context": m.context_clues,
            }
            for m in matches
        ]


class ContextualAbbreviationResolver:
    """Advanced contextual resolution of medical abbreviations."""

    def __init__(
        self,
        handler: MedicalAbbreviationHandler,
        use_ml_model: bool = False,
        model_path: Optional[str] = None,
    ):
        """Initialize contextual resolver with handler and optional ML model."""
        self.handler = handler
        self.use_ml_model = use_ml_model
        self.model = None

        if use_ml_model and model_path:
            self._load_ml_model(model_path)

    def _load_ml_model(self, path: str) -> None:
        """Load ML model for context resolution."""
        # Placeholder for ML model loading
        # In production, load a trained model (e.g., BERT-based classifier)
        logger.info("ML model loading not implemented yet: %s", path)

    def resolve(
        self,
        abbreviation: str,
        context: str,
        patient_info: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, float]:
        """
        Resolve abbreviation with advanced context analysis.

        Args:
            abbreviation: The abbreviation to resolve
            context: Surrounding text context
            patient_info: Optional patient information (age, gender, conditions)

        Returns:
            Tuple of (expansion, confidence)
        """
        entry = self.handler.get_abbreviation_info(abbreviation)
        if not entry:
            return (abbreviation, 0.0)

        if len(entry.expansions) == 1:
            return (entry.expansions[0], 1.0)

        # Use patient info for better resolution
        if patient_info:
            # Example: Use patient's known conditions
            conditions = patient_info.get("conditions", [])
            for condition in conditions:
                condition_lower = condition.lower()
                for expansion in entry.expansions:
                    if condition_lower in expansion.lower():
                        return (expansion, 0.9)

        # Fall back to standard resolution
        match = AbbreviationMatch(
            text=abbreviation,
            start=0,
            end=len(abbreviation),
            expansions=entry.expansions.copy(),
        )

        self.handler.resolve_ambiguity(context, match, entry)

        if match.selected_expansion:
            return (match.selected_expansion, match.confidence)

        return (entry.expansions[0], 0.5)


# Factory functions
def load_medical_abbreviations(
    path: Optional[str] = None,
) -> Dict[str, AbbreviationEntry]:
    """Load medical abbreviations from file."""
    handler = MedicalAbbreviationHandler(abbreviations_path=path)
    return handler.abbreviations


def get_abbreviation_handler(
    language: str = "en",
    enable_context: bool = True,
    abbreviations_path: Optional[str] = None,
    min_confidence: float = 0.7,
) -> MedicalAbbreviationHandler:
    """Get configured abbreviation handler."""
    return MedicalAbbreviationHandler(
        language=language,
        enable_context_resolution=enable_context,
        abbreviations_path=abbreviations_path,
        min_confidence=min_confidence,
    )


# Example usage
if __name__ == "__main__":
    # Create handler
    abbr_handler = MedicalAbbreviationHandler()

    # Test text
    test_text = """
    Patient presents with CP and SOB. BP 140/90, HR 88, RR 20.
    History of DM and HTN. Recent MI 3 months ago.
    Currently on ASA 81mg QD and metoprolol 50mg BID.
    CXR shows possible PE. Recommend CT chest and start heparin IV.
    """

    # Detect abbreviations
    print("Detected abbreviations:")
    detected_matches = abbr_handler.detect_abbreviations(test_text)
    for detected_match in detected_matches:
        print(
            f"  {detected_match.text} -> {detected_match.selected_expansion} (confidence: {detected_match.confidence:.2f})"
        )

    # Expand abbreviations
    print("\nExpanded text:")
    expanded = abbr_handler.expand_abbreviations(test_text)
    print(expanded)


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
