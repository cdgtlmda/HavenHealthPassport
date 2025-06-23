"""Translation Extraction Tools.

This module provides tools for extracting translatable strings from
source code and managing them for the translation workflow.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TranslatableString:
    """Represents an extractable translatable string."""

    key: str
    default_text: str
    file_path: str
    line_number: int
    context: Optional[str] = None
    max_length: Optional[int] = None
    namespace: str = "common"
    description: Optional[str] = None
    placeholders: List[str] = field(default_factory=list)
    is_medical: bool = False
    requires_review: bool = False


@dataclass
class ExtractionResult:
    """Result of translation extraction."""

    total_strings: int
    new_strings: int
    updated_strings: int
    removed_strings: int
    files_processed: int
    errors: List[Dict[str, Any]]
    extraction_time: float


class TranslationExtractor:
    """Extracts translatable strings from source code."""

    # Patterns for different frameworks
    EXTRACTION_PATTERNS = {
        "react": {
            # i18next patterns
            "t_function": r't\(["\']([^"\']+)["\']\)',
            "trans_component": r'<Trans[^>]*i18nKey=["\']([^"\']+)["\']',
            "useTranslation": r'useTranslation\(["\']([^"\']+)["\']\)',
            # Custom patterns
            "translatable": r'<Translatable[^>]*id=["\']([^"\']+)["\']',
            "medical_term": r'<MedicalTerm[^>]*term=["\']([^"\']+)["\']',
        },
        "typescript": {
            "i18n_t": r'i18n\.t\(["\']([^"\']+)["\']\)',
            "translate": r'translate\(["\']([^"\']+)["\']\)',
            "gettext": r'_\(["\']([^"\']+)["\']\)',
        },
        "python": {
            "gettext": r'_\(["\']([^"\']+)["\']\)',
            "lazy_gettext": r'lazy_gettext\(["\']([^"\']+)["\']\)',
            "ngettext": r'ngettext\(["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']\s*,',
            "medical": r'medical_translate\(["\']([^"\']+)["\']\)',
        },
    }

    # File extensions to process
    SUPPORTED_EXTENSIONS = {
        ".tsx",
        ".ts",
        ".jsx",
        ".js",  # JavaScript/TypeScript
        ".py",  # Python
        ".html",
        ".vue",  # Templates
    }

    # Paths to exclude
    EXCLUDE_PATHS = {
        "node_modules",
        "build",
        "dist",
        ".git",
        "__pycache__",
        "venv",
        ".env",
        "test",
        "tests",
        "__tests__",
    }

    def __init__(self, project_root: str):
        """Initialize extractor with project root."""
        self.project_root = Path(project_root)
        self.existing_translations: Dict[str, TranslatableString] = {}
        self.extracted_strings: Dict[str, TranslatableString] = {}
        self.namespaces: Set[str] = {"common", "medical", "errors", "forms"}

    def extract_all(
        self,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ) -> ExtractionResult:
        """Extract all translatable strings from project."""
        start_time = datetime.now()

        # Load existing translations
        self._load_existing_translations()

        # Reset extracted strings
        self.extracted_strings.clear()

        # Determine paths to scan
        paths_to_scan = self._get_paths_to_scan(include_paths, exclude_paths)

        files_processed = 0
        errors = []

        for file_path in paths_to_scan:
            try:
                self._extract_from_file(file_path)
                files_processed += 1
            except (OSError, ValueError) as e:
                logger.error(f"Error extracting from {file_path}: {e}")
                errors.append({"file": str(file_path), "error": str(e)})

        # Compare with existing translations
        new_strings = set(self.extracted_strings.keys()) - set(
            self.existing_translations.keys()
        )
        removed_strings = set(self.existing_translations.keys()) - set(
            self.extracted_strings.keys()
        )

        # Find updated strings (same key, different text)
        updated_strings = []
        for key in set(self.extracted_strings.keys()) & set(
            self.existing_translations.keys()
        ):
            if (
                self.extracted_strings[key].default_text
                != self.existing_translations[key].default_text
            ):
                updated_strings.append(key)

        extraction_time = (datetime.now() - start_time).total_seconds()

        return ExtractionResult(
            total_strings=len(self.extracted_strings),
            new_strings=len(new_strings),
            updated_strings=len(updated_strings),
            removed_strings=len(removed_strings),
            files_processed=files_processed,
            errors=errors,
            extraction_time=extraction_time,
        )

    def _get_paths_to_scan(
        self, include_paths: Optional[List[str]], exclude_paths: Optional[List[str]]
    ) -> List[Path]:
        """Get list of files to scan."""
        paths = []

        # Use include paths if specified
        if include_paths:
            for include_path in include_paths:
                path = self.project_root / include_path
                if path.is_file():
                    paths.append(path)
                elif path.is_dir():
                    paths.extend(self._scan_directory(path, exclude_paths))
        else:
            # Scan entire project
            paths = self._scan_directory(self.project_root, exclude_paths)

        return paths

    def _scan_directory(
        self, directory: Path, exclude_paths: Optional[List[str]]
    ) -> List[Path]:
        """Recursively scan directory for supported files."""
        files = []
        exclude_set = set(self.EXCLUDE_PATHS)

        if exclude_paths:
            exclude_set.update(exclude_paths)

        for item in directory.iterdir():
            # Skip excluded paths
            if item.name in exclude_set:
                continue

            if item.is_file() and item.suffix in self.SUPPORTED_EXTENSIONS:
                files.append(item)
            elif item.is_dir():
                files.extend(self._scan_directory(item, exclude_paths))

        return files

    def _extract_from_file(self, file_path: Path) -> None:
        """Extract translatable strings from a single file."""
        content = file_path.read_text(encoding="utf-8")

        # Determine file type and patterns
        if file_path.suffix in [".tsx", ".ts", ".jsx", ".js"]:
            if ".tsx" in str(file_path) or ".jsx" in str(file_path):
                patterns = self.EXTRACTION_PATTERNS["react"]
            else:
                patterns = self.EXTRACTION_PATTERNS["typescript"]
        elif file_path.suffix == ".py":
            patterns = self.EXTRACTION_PATTERNS["python"]
        else:
            return

        # Extract strings using patterns
        for pattern_name, pattern in patterns.items():
            for match in re.finditer(pattern, content):
                key = match.group(1)

                # Get line number
                line_number = content[: match.start()].count("\n") + 1

                # Determine namespace
                namespace = self._determine_namespace(key, file_path)

                # Check if medical term
                is_medical = "medical" in pattern_name or "medical" in namespace

                # Extract context
                context = self._extract_context(content, match.start())

                # Create translatable string
                translatable = TranslatableString(
                    key=key,
                    default_text=self._extract_default_text(content, match),
                    file_path=str(file_path.relative_to(self.project_root)),
                    line_number=line_number,
                    context=context,
                    namespace=namespace,
                    is_medical=is_medical,
                    placeholders=self._extract_placeholders(key),
                )

                self.extracted_strings[key] = translatable

    def _determine_namespace(self, key: str, file_path: Path) -> str:
        """Determine namespace from key or file path."""
        # Check key prefix
        if "." in key:
            namespace = key.split(".")[0]
            if namespace in self.namespaces:
                return namespace

        # Check file path
        path_str = str(file_path).lower()
        if "medical" in path_str:
            return "medical"
        elif "error" in path_str:
            return "errors"
        elif "form" in path_str:
            return "forms"

        return "common"

    def _extract_default_text(self, content: str, match: re.Match) -> str:
        """Extract default text from source."""
        # Look for default text in nearby code
        # This is simplified - in production would use AST parsing

        # Try to find default value
        start_pos = match.end()
        default_match = re.search(
            r'(?:defaultMessage|default|fallback)\s*[:=]\s*["\']([^"\']+)["\']',
            content[start_pos : start_pos + 200],
        )

        if default_match:
            return default_match.group(1)

        # Use key as default
        key = match.group(1) or ""
        # Convert key to readable text
        return key.split(".")[-1].replace("_", " ").title()

    def _extract_context(self, content: str, position: int) -> str:
        """Extract context around translation key."""
        # Get surrounding lines
        lines = content.split("\n")
        line_num = content[:position].count("\n")

        # Get component or function name
        for i in range(line_num, -1, -1):
            line = lines[i]
            # React component
            component_match = re.search(r"(?:function|const|class)\s+(\w+)", line)
            if component_match:
                return f"Component: {component_match.group(1)}"

            # Python function
            func_match = re.search(r"def\s+(\w+)", line)
            if func_match:
                return f"Function: {func_match.group(1)}"

        return "Unknown context"

    def _extract_placeholders(self, key: str) -> List[str]:
        """Extract placeholder variables from key."""
        placeholders = []

        # Look for {variable} patterns
        for match in re.finditer(r"\{(\w+)\}", key):
            placeholders.append(match.group(1))

        # Look for %s, %d patterns
        if "%" in key:
            placeholders.append("format_string")

        return placeholders

    def _load_existing_translations(self) -> None:
        """Load existing translation files."""
        self.existing_translations.clear()

        # Look for translation files
        locale_dir = self.project_root / "public" / "locales"
        if not locale_dir.exists():
            locale_dir = self.project_root / "locales"

        if locale_dir.exists():
            # Load from default language (usually English)
            en_dir = locale_dir / "en"
            if en_dir.exists():
                for json_file in en_dir.glob("*.json"):
                    namespace = json_file.stem

                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            translations = json.load(f)

                        # Flatten nested structure
                        for key, value in self._flatten_json(translations, namespace):
                            self.existing_translations[key] = TranslatableString(
                                key=key,
                                default_text=value,
                                file_path="existing",
                                line_number=0,
                                namespace=namespace,
                            )
                    except (json.JSONDecodeError, OSError, ValueError) as e:
                        logger.error(f"Error loading {json_file}: {e}")

    def _flatten_json(
        self, obj: Dict[str, Any], prefix: str = "", separator: str = "."
    ) -> List[Tuple[str, str]]:
        """Flatten nested JSON structure."""
        items = []

        for key, value in obj.items():
            new_key = f"{prefix}{separator}{key}" if prefix else key

            if isinstance(value, dict):
                items.extend(self._flatten_json(value, new_key, separator))
            else:
                items.append((new_key, str(value)))

        return items

    def generate_translation_files(
        self, output_dir: str, languages: List[str], include_empty: bool = True
    ) -> None:
        """Generate translation JSON files."""
        output_path = Path(output_dir)

        # Group strings by namespace
        namespaced_strings: Dict[str, Dict[str, Any]] = defaultdict(dict)
        for key, translatable in self.extracted_strings.items():
            namespace = translatable.namespace

            # Remove namespace from key if present
            clean_key = key
            if key.startswith(f"{namespace}."):
                clean_key = key[len(namespace) + 1 :]

            # Create nested structure
            parts = clean_key.split(".")
            current = namespaced_strings[namespace]

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = {
                "_default": translatable.default_text,
                "_context": translatable.context,
                "_maxLength": translatable.max_length,
                "_placeholders": translatable.placeholders,
            }

        # Generate files for each language
        for language in languages:
            lang_dir = output_path / language
            lang_dir.mkdir(parents=True, exist_ok=True)

            for namespace, strings in namespaced_strings.items():
                file_path = lang_dir / f"{namespace}.json"

                # Clean up metadata for non-English languages
                if language != "en":
                    cleaned_strings = self._clean_translation_data(
                        strings, include_empty
                    )
                else:
                    cleaned_strings = self._clean_metadata(strings)

                # Write JSON file
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_strings, f, ensure_ascii=False, indent=2)

                logger.info(f"Generated {file_path}")

    def _clean_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean metadata from translation data."""
        cleaned = {}

        for key, value in data.items():
            if isinstance(value, dict):
                if "_default" in value:
                    # Extract just the default text
                    cleaned[key] = value["_default"]
                else:
                    # Recursive clean
                    cleaned[key] = self._clean_metadata(value)
            else:
                cleaned[key] = value

        return cleaned

    def _clean_translation_data(
        self, data: Dict[str, Any], include_empty: bool
    ) -> Dict[str, Any]:
        """Clean translation data for non-source languages."""
        cleaned: Dict[str, Any] = {}

        for key, value in data.items():
            if isinstance(value, dict):
                if "_default" in value:
                    # Include empty string or skip
                    if include_empty:
                        cleaned[key] = ""
                else:
                    # Recursive clean
                    sub_cleaned = self._clean_translation_data(value, include_empty)
                    if sub_cleaned:  # Only include if not empty
                        cleaned[key] = sub_cleaned
            else:
                if include_empty or value:
                    cleaned[key] = value

        return cleaned

    def validate_placeholders(self) -> List[Dict[str, Any]]:
        """Validate placeholder consistency."""
        issues = []

        for key, translatable in self.extracted_strings.items():
            if translatable.placeholders:
                # Check if placeholders are used in default text
                for placeholder in translatable.placeholders:
                    if f"{{{placeholder}}}" not in translatable.default_text:
                        issues.append(
                            {
                                "key": key,
                                "issue": f"Placeholder '{placeholder}' not found in default text",
                                "file": translatable.file_path,
                                "line": translatable.line_number,
                            }
                        )

        return issues

    def find_unused_translations(self) -> List[str]:
        """Find translations that are no longer used."""
        return list(
            set(self.existing_translations.keys()) - set(self.extracted_strings.keys())
        )

    def find_missing_translations(self, language: str) -> List[str]:
        """Find keys missing translations in a language."""
        missing = []

        lang_dir = self.project_root / "public" / "locales" / language
        if not lang_dir.exists():
            return list(self.extracted_strings.keys())

        # Load language translations
        lang_translations = set()
        for json_file in lang_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    translations = json.load(f)

                namespace = json_file.stem
                for key, _ in self._flatten_json(translations, namespace):
                    lang_translations.add(key)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.error(f"Error loading {json_file}: {e}")

        # Find missing
        for key in self.extracted_strings:
            if key not in lang_translations:
                missing.append(key)

        return missing

    def generate_extraction_report(self) -> Dict[str, Any]:
        """Generate detailed extraction report."""
        report: Dict[str, Any] = {
            "summary": {
                "total_strings": len(self.extracted_strings),
                "namespaces": list(self.namespaces),
                "medical_terms": sum(
                    1 for s in self.extracted_strings.values() if s.is_medical
                ),
                "with_placeholders": sum(
                    1 for s in self.extracted_strings.values() if s.placeholders
                ),
            },
            "by_namespace": {},
            "by_file": {},
            "placeholder_usage": {},
            "validation_issues": self.validate_placeholders(),
        }

        # Group by namespace
        for _key, translatable in self.extracted_strings.items():
            namespace = translatable.namespace
            if namespace not in report["by_namespace"]:
                report["by_namespace"][namespace] = 0
            report["by_namespace"][namespace] += 1

            # Group by file
            file_path = translatable.file_path
            if file_path not in report["by_file"]:
                report["by_file"][file_path] = 0
            report["by_file"][file_path] += 1

        return report


# Global extractor instance
translation_extractor = TranslationExtractor(".")
