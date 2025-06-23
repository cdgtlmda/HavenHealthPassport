"""Translation Consistency Validation."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.translation.management.translation_memory import TranslationMemory
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConsistencyIssue:
    """Represents a consistency issue in translations."""

    issue_type: str  # 'terminology', 'style', 'formatting', 'placeholder'
    severity: str  # 'error', 'warning', 'info'
    language: str
    key: str
    current_value: str
    suggested_value: Optional[str] = None
    similar_translations: List[Dict[str, str]] = field(default_factory=list)
    description: str = ""


@dataclass
class ConsistencyReport:
    """Report of consistency validation results."""

    total_checked: int
    issues_found: int
    issues: List[ConsistencyIssue]
    validation_time: float
    languages_checked: List[str]
    namespaces_checked: List[str]


class ConsistencyValidator:
    """Validates translation consistency."""

    def __init__(
        self, project_root: str, translation_memory: Optional[TranslationMemory] = None
    ):
        """Initialize consistency validator."""
        self.project_root = Path(project_root)
        self.translation_memory = translation_memory
        self.glossary: Dict[str, Dict[str, str]] = {}
        self.style_rules: Dict[str, Any] = {}
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load consistency validation configuration."""
        config_file = self.project_root / ".translation" / "consistency_config.json"

        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.glossary = config.get("glossary", {})
                self.style_rules = config.get("style_rules", {})
        else:
            # Default style rules
            self.style_rules = {
                "capitalization": {
                    "title_case_keys": ["title", "heading", "button"],
                    "sentence_case_keys": ["description", "message", "help"],
                },
                "punctuation": {
                    "no_ending_punctuation": ["title", "heading", "button", "label"],
                    "require_ending_punctuation": ["description", "message", "help"],
                },
                "length": {
                    "max_length_ratio": 1.5  # Translation shouldn't be >1.5x source
                },
            }

    def load_glossary(self, glossary_path: str) -> None:
        """Load terminology glossary from file."""
        glossary_file = Path(glossary_path)

        if glossary_file.suffix == ".json":
            with open(glossary_file, "r", encoding="utf-8") as f:
                self.glossary = json.load(f)
        elif glossary_file.suffix == ".csv":
            # CSV loading would be implemented here
            pass

        logger.info(f"Loaded glossary with {len(self.glossary)} terms")

    def validate_all(
        self,
        languages: Optional[List[str]] = None,
        namespaces: Optional[List[str]] = None,
    ) -> ConsistencyReport:
        """Validate consistency across all translations."""
        start_time = datetime.now()
        issues = []
        total_checked = 0

        # Get translations to check
        translations = self._load_translations(languages, namespaces)

        # Run validation checks
        for lang, _namespace, key, value in self._iterate_translations(translations):
            total_checked += 1

            # Check terminology consistency
            term_issues = self._check_terminology(lang, key, value)
            issues.extend(term_issues)

            # Check style consistency
            style_issues = self._check_style(lang, key, value)
            issues.extend(style_issues)

            # Check formatting consistency
            format_issues = self._check_formatting(lang, key, value)
            issues.extend(format_issues)

            # Check placeholder consistency
            placeholder_issues = self._check_placeholders(lang, key, value)
            issues.extend(placeholder_issues)

        validation_time = (datetime.now() - start_time).total_seconds()

        return ConsistencyReport(
            total_checked=total_checked,
            issues_found=len(issues),
            issues=issues,
            validation_time=validation_time,
            languages_checked=languages or [],
            namespaces_checked=namespaces or [],
        )

    def _load_translations(
        self, languages: Optional[List[str]], namespaces: Optional[List[str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Load translations from files."""
        translations: Dict[str, Dict[str, Any]] = {}
        locales_dir = self.project_root / "public" / "locales"

        if not locales_dir.exists():
            locales_dir = self.project_root / "locales"

        if not locales_dir.exists():
            return translations

        # Determine languages to check
        if languages:
            lang_dirs = [locales_dir / lang for lang in languages]
        else:
            lang_dirs = [d for d in locales_dir.iterdir() if d.is_dir()]

        for lang_dir in lang_dirs:
            if not lang_dir.exists():
                continue

            lang = lang_dir.name
            translations[lang] = {}

            # Load namespace files
            for json_file in lang_dir.glob("*.json"):
                namespace = json_file.stem

                if namespaces and namespace not in namespaces:
                    continue

                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        translations[lang][namespace] = json.load(f)
                except (json.JSONDecodeError, OSError, ValueError) as e:
                    logger.error(f"Error loading {json_file}: {e}")

        return translations

    def _iterate_translations(
        self, translations: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, str, str, str]]:
        """Iterate through all translation strings."""
        results = []

        for lang, namespaces in translations.items():
            for namespace, content in namespaces.items():
                for key, value in self._flatten_dict(content).items():
                    results.append((lang, namespace, key, value))

        return results

    def _flatten_dict(
        self, d: Dict[str, Any], parent_key: str = "", sep: str = "."
    ) -> Dict[str, str]:
        """Flatten nested dictionary."""
        items: List[Tuple[str, str]] = []

        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, str(v)))

        return dict(items)

    def _check_terminology(
        self, language: str, key: str, value: str
    ) -> List[ConsistencyIssue]:
        """Check terminology consistency."""
        issues = []

        # Check against glossary
        for term, translations in self.glossary.items():
            if term.lower() in value.lower():
                expected = translations.get(language)
                if expected and expected.lower() not in value.lower():
                    issues.append(
                        ConsistencyIssue(
                            issue_type="terminology",
                            severity="warning",
                            language=language,
                            key=key,
                            current_value=value,
                            suggested_value=value.replace(term, expected),
                            description=f"Term '{term}' should be translated as '{expected}'",
                        )
                    )

        # Check consistency with translation memory
        if self.translation_memory:
            # Look for similar source texts
            # Implementation would check TM for consistency
            pass

        return issues

    def _check_style(
        self, language: str, key: str, value: str
    ) -> List[ConsistencyIssue]:
        """Check style consistency."""
        issues = []

        # Check capitalization
        for key_pattern in self.style_rules.get("capitalization", {}).get(
            "title_case_keys", []
        ):
            if key_pattern in key.lower():
                if value and not value[0].isupper():
                    issues.append(
                        ConsistencyIssue(
                            issue_type="style",
                            severity="warning",
                            language=language,
                            key=key,
                            current_value=value,
                            suggested_value=(
                                value[0].upper() + value[1:]
                                if len(value) > 1
                                else value.upper()
                            ),
                            description="Title/heading should start with capital letter",
                        )
                    )

        # Check punctuation
        no_punct_patterns = self.style_rules.get("punctuation", {}).get(
            "no_ending_punctuation", []
        )
        for pattern in no_punct_patterns:
            if pattern in key.lower() and value and value[-1] in ".!?":
                issues.append(
                    ConsistencyIssue(
                        issue_type="style",
                        severity="warning",
                        language=language,
                        key=key,
                        current_value=value,
                        suggested_value=value.rstrip(".!?"),
                        description="Buttons/labels should not end with punctuation",
                    )
                )

        return issues

    def _check_formatting(
        self, language: str, key: str, value: str
    ) -> List[ConsistencyIssue]:
        """Check formatting consistency."""
        issues = []

        # Check for double spaces
        if "  " in value:
            issues.append(
                ConsistencyIssue(
                    issue_type="formatting",
                    severity="warning",
                    language=language,
                    key=key,
                    current_value=value,
                    suggested_value=re.sub(r"\s+", " ", value),
                    description="Contains double spaces",
                )
            )

        # Check for leading/trailing whitespace
        if value != value.strip():
            issues.append(
                ConsistencyIssue(
                    issue_type="formatting",
                    severity="error",
                    language=language,
                    key=key,
                    current_value=value,
                    suggested_value=value.strip(),
                    description="Contains leading or trailing whitespace",
                )
            )

        return issues

    def _check_placeholders(
        self, language: str, key: str, value: str
    ) -> List[ConsistencyIssue]:
        """Check placeholder consistency."""
        issues = []

        # Find all placeholders in value
        placeholders = re.findall(r"\{(\w+)\}", value)

        # Check for unmatched braces
        open_braces = value.count("{")
        close_braces = value.count("}")

        if open_braces != close_braces:
            issues.append(
                ConsistencyIssue(
                    issue_type="placeholder",
                    severity="error",
                    language=language,
                    key=key,
                    current_value=value,
                    description="Unmatched curly braces in placeholders",
                )
            )

        # Check placeholder naming consistency
        for placeholder in placeholders:
            if not placeholder.islower():
                issues.append(
                    ConsistencyIssue(
                        issue_type="placeholder",
                        severity="warning",
                        language=language,
                        key=key,
                        current_value=value,
                        suggested_value=value.replace(
                            f"{{{placeholder}}}", f"{{{placeholder.lower()}}}"
                        ),
                        description=f"Placeholder '{placeholder}' should be lowercase",
                    )
                )

        return issues

    def generate_report_html(self, report: ConsistencyReport) -> str:
        """Generate HTML report of consistency issues."""
        # HTML generation would be implemented here
        return f"<html><body>Found {report.issues_found} issues</body></html>"
