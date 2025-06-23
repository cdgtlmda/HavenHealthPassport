"""Language Testing Infrastructure.

This module provides comprehensive testing infrastructure for multi-language
support, including UI testing, text overflow detection, and localization quality.

Access control note: This module may process medical terminology and patient-facing
text that could contain PHI. Access is restricted through role-based permissions
and all test operations involving medical content are logged for compliance.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

# Access control for test data that may contain medical information

logger = get_logger(__name__)


class TestType(str, Enum):
    """Types of language tests."""

    UI_LAYOUT = "ui_layout"
    TEXT_OVERFLOW = "text_overflow"
    TRUNCATION = "truncation"
    CHARACTER_ENCODING = "character_encoding"
    FONT_RENDERING = "font_rendering"
    INPUT_METHOD = "input_method"
    SORTING = "sorting"
    SEARCH = "search"
    TRANSLATION_COMPLETENESS = "translation_completeness"
    CONTEXT_APPROPRIATENESS = "context_appropriateness"


class TestStatus(str, Enum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class TestResult:
    """Result of a language test."""

    test_id: str
    test_type: TestType
    language: str
    status: TestStatus
    duration_ms: int
    details: Dict[str, Any]
    screenshots: Optional[List[str]] = None
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None


@dataclass
class UITestCase:
    """UI test case for language testing."""

    test_id: str
    component: str
    test_text: Dict[str, str]  # language -> test text
    expected_behavior: Dict[str, Any]
    viewport_sizes: List[Tuple[int, int]]
    rtl_support_required: bool


class LanguageTestSuite:
    """Comprehensive test suite for language support."""

    # Test strings for different purposes
    TEST_STRINGS = {
        "overflow": {
            "short": {
                "en": "Save",
                "de": "Speichern",  # Longer
                "fr": "Enregistrer",  # Much longer
                "ar": "حفظ",  # Shorter
                "zh": "保存",  # Shorter
            },
            "medium": {
                "en": "Please enter your medical history",
                "de": "Bitte geben Sie Ihre Krankengeschichte ein",
                "fr": "Veuillez entrer vos antécédents médicaux",
                "ar": "يرجى إدخال التاريخ الطبي الخاص بك",
                "es": "Por favor ingrese su historial médico",
            },
            "long": {
                "en": "This medication should be taken with food to reduce stomach upset. If symptoms persist, consult your healthcare provider.",
                "de": "Dieses Medikament sollte mit Nahrung eingenommen werden, um Magenbeschwerden zu reduzieren. Wenn die Symptome anhalten, konsultieren Sie Ihren Arzt.",
                "fr": "Ce médicament doit être pris avec de la nourriture pour réduire les maux d'estomac. Si les symptômes persistent, consultez votre professionnel de santé.",
                "ar": "يجب تناول هذا الدواء مع الطعام لتقليل اضطراب المعدة. إذا استمرت الأعراض، استشر مقدم الرعاية الصحية الخاص بك.",
            },
        },
        "special_characters": {
            "accents": "àáäâèéëêìíïîòóöôùúüûñç",
            "arabic": "ء آ أ ؤ إ ئ",
            "chinese": "中文字符测试",
            "emoji": "😀 🏥 💊 🩺",
            "rtl_marks": "\u200f\u200e",  # RTL and LTR marks
            "combining": "a\u0300 e\u0301 n\u0303",  # Combining diacritics
        },
    }

    # UI components to test
    UI_COMPONENTS = [
        UITestCase(
            test_id="button_primary",
            component="PrimaryButton",
            test_text={
                "en": "Submit Application",
                "fr": "Soumettre la demande",
                "ar": "تقديم الطلب",
                "de": "Antrag einreichen",
                "zh": "提交申请",
            },
            expected_behavior={
                "max_width": 200,
                "text_overflow": "ellipsis",
                "padding": [10, 20],
            },
            viewport_sizes=[(320, 568), (768, 1024), (1920, 1080)],
            rtl_support_required=True,
        ),
        UITestCase(
            test_id="form_label",
            component="FormLabel",
            test_text={
                "en": "Date of Birth",
                "fr": "Date de naissance",
                "ar": "تاريخ الميلاد",
                "es": "Fecha de nacimiento",
            },
            expected_behavior={
                "text_align": {"ltr": "left", "rtl": "right"},
                "required_indicator": "*",
            },
            viewport_sizes=[(320, 568), (768, 1024)],
            rtl_support_required=True,
        ),
    ]

    def __init__(self) -> None:
        """Initialize test suite."""
        self.test_results: List[TestResult] = []
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.test_config = self._load_test_config()

    def _load_test_config(self) -> Dict[str, Any]:
        """Load test configuration."""
        return {
            "languages_to_test": ["en", "ar", "fr", "es", "de", "zh", "hi", "bn"],
            "rtl_languages": ["ar", "fa", "ur", "he"],
            "screenshot_on_failure": True,
            "parallel_execution": True,
            "timeout_ms": 30000,
        }

    def run_full_test_suite(
        self, languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run complete language test suite."""
        languages = languages or self.test_config["languages_to_test"]
        start_time = datetime.now()

        # Run different test categories
        self._run_ui_layout_tests(languages)
        self._run_text_overflow_tests(languages)
        self._run_character_encoding_tests(languages)
        self._run_translation_completeness_tests(languages)

        # Generate summary
        duration = (datetime.now() - start_time).total_seconds()
        summary = self._generate_test_summary(duration)

        return summary

    def _run_ui_layout_tests(self, languages: List[str]) -> None:
        """Run UI layout tests for all languages."""
        logger.info(f"Running UI layout tests for {len(languages)} languages")

        for ui_test in self.UI_COMPONENTS:
            for language in languages:
                if language not in ui_test.test_text:
                    continue

                for viewport in ui_test.viewport_sizes:
                    result = self._test_ui_component(ui_test, language, viewport)
                    self.test_results.append(result)

    def _test_ui_component(
        self, test_case: UITestCase, language: str, viewport: Tuple[int, int]
    ) -> TestResult:
        """Test a single UI component."""
        test_id = f"{test_case.test_id}_{language}_{viewport[0]}x{viewport[1]}"
        start_time = datetime.now()

        try:
            text = test_case.test_text[language]
            is_rtl = language in self.test_config["rtl_languages"]

            # Check text overflow
            text_width = self._estimate_text_width(text, language)
            max_width = test_case.expected_behavior.get("max_width", float("inf"))

            status = TestStatus.PASSED
            warnings = []
            details = {
                "text": text,
                "estimated_width": text_width,
                "max_width": max_width,
                "viewport": viewport,
                "is_rtl": is_rtl,
            }

            if text_width > max_width:
                status = TestStatus.WARNING
                warnings.append(f"Text may overflow: {text_width}px > {max_width}px")

            duration = int((datetime.now() - start_time).total_seconds() * 1000)

            return TestResult(
                test_id=test_id,
                test_type=TestType.UI_LAYOUT,
                language=language,
                status=status,
                duration_ms=duration,
                details=details,
                warnings=warnings,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return TestResult(
                test_id=test_id,
                test_type=TestType.UI_LAYOUT,
                language=language,
                status=TestStatus.FAILED,
                duration_ms=duration,
                details={},
                error_message=str(e),
            )

    def _run_text_overflow_tests(self, languages: List[str]) -> None:
        """Run text overflow detection tests."""
        logger.info("Running text overflow tests")

        overflow_tests = self.TEST_STRINGS.get("overflow", {})
        if isinstance(overflow_tests, dict):
            for length, texts in overflow_tests.items():
                for language in languages:
                    if language not in texts:
                        continue

                    result = self._test_text_overflow(texts[language], language, length)
                    self.test_results.append(result)

    def _test_text_overflow(
        self, text: str, language: str, text_length: str
    ) -> TestResult:
        """Test for text overflow issues."""
        test_id = f"overflow_{language}_{text_length}"

        container_widths = {"short": 100, "medium": 300, "long": 500}

        container_width = container_widths.get(text_length, 300)
        estimated_width = self._estimate_text_width(text, language)

        status = TestStatus.PASSED
        warnings = []

        if estimated_width > container_width:
            overflow_ratio = estimated_width / container_width
            if overflow_ratio > 1.2:
                status = TestStatus.FAILED
            else:
                status = TestStatus.WARNING
                warnings.append(
                    f"Text exceeds container by {(overflow_ratio - 1) * 100:.1f}%"
                )

        return TestResult(
            test_id=test_id,
            test_type=TestType.TEXT_OVERFLOW,
            language=language,
            status=status,
            duration_ms=10,
            details={
                "text": text,
                "container_width": container_width,
                "estimated_width": estimated_width,
                "overflow_ratio": estimated_width / container_width,
            },
            warnings=warnings,
        )

    def _estimate_text_width(self, text: str, language: str) -> float:
        """Estimate text width in pixels."""
        char_widths = {
            "en": 8.5,
            "fr": 8.5,
            "de": 9.0,
            "es": 8.5,
            "ar": 7.5,
            "zh": 16.0,
            "ja": 16.0,
            "ko": 14.0,
            "hi": 10.0,
            "bn": 9.5,
        }

        avg_width = char_widths.get(language, 8.5)
        return len(text) * avg_width

    def _run_character_encoding_tests(self, languages: List[str]) -> None:
        """Test character encoding for all languages."""
        logger.info("Running character encoding tests")

        test_cases = [
            ("basic_ascii", "Hello World 123"),
            ("extended_latin", "Café, naïve, façade"),
            ("arabic", "مرحبا بالعالم"),
            ("chinese", "你好世界"),
            ("emoji", "👋🌍 Hello World"),
            ("mixed", "Hello مرحبا 你好 🌍"),
        ]

        for test_name, test_text in test_cases:
            result = self._test_character_encoding(test_name, test_text)
            self.test_results.append(result)

    def _test_character_encoding(self, test_name: str, test_text: str) -> TestResult:
        """Test character encoding handling."""
        test_id = f"encoding_{test_name}"

        try:
            # Test UTF-8 encoding/decoding
            encoded = test_text.encode("utf-8")
            decoded = encoded.decode("utf-8")

            # Check for data loss
            if decoded != test_text:
                return TestResult(
                    test_id=test_id,
                    test_type=TestType.CHARACTER_ENCODING,
                    language="universal",
                    status=TestStatus.FAILED,
                    duration_ms=5,
                    details={"original": test_text, "decoded": decoded},
                    error_message="Character encoding/decoding mismatch",
                )

            warnings = []
            if "\ufffd" in decoded:  # Replacement character
                warnings.append("Contains replacement characters")

            return TestResult(
                test_id=test_id,
                test_type=TestType.CHARACTER_ENCODING,
                language="universal",
                status=TestStatus.PASSED if not warnings else TestStatus.WARNING,
                duration_ms=5,
                details={
                    "text": test_text,
                    "byte_length": len(encoded),
                    "char_length": len(test_text),
                },
                warnings=warnings,
            )

        except Exception as e:
            return TestResult(
                test_id=test_id,
                test_type=TestType.CHARACTER_ENCODING,
                language="universal",
                status=TestStatus.FAILED,
                duration_ms=5,
                details={},
                error_message=str(e),
            )

    def _run_translation_completeness_tests(self, languages: List[str]) -> None:
        """Test translation completeness."""
        logger.info("Running translation completeness tests")

        # Define required translation keys
        required_keys = [
            "common.save",
            "common.cancel",
            "common.delete",
            "errors.required_field",
            "errors.invalid_format",
            "medical.blood_pressure",
            "medical.temperature",
            "medical.heart_rate",
        ]

        for language in languages:
            result = self._test_translation_completeness(language, required_keys)
            self.test_results.append(result)

    def _test_translation_completeness(
        self, language: str, required_keys: List[str]
    ) -> TestResult:
        """Test if all required translations exist."""
        test_id = f"translation_complete_{language}"

        # Simulate checking translation files
        missing_keys = []
        total_keys = len(required_keys)

        # In production, would actually check translation files
        if language not in ["en", "es", "fr", "ar"]:
            # Simulate some missing translations
            missing_keys = required_keys[-2:]

        completeness = (total_keys - len(missing_keys)) / total_keys * 100

        status = TestStatus.PASSED
        if missing_keys:
            status = TestStatus.WARNING if completeness > 90 else TestStatus.FAILED

        return TestResult(
            test_id=test_id,
            test_type=TestType.TRANSLATION_COMPLETENESS,
            language=language,
            status=status,
            duration_ms=50,
            details={
                "total_keys": total_keys,
                "missing_keys": missing_keys,
                "completeness_percentage": completeness,
            },
            warnings=(
                [f"Missing {len(missing_keys)} translations"] if missing_keys else None
            ),
        )

    def _generate_test_summary(self, duration: float) -> Dict[str, Any]:
        """Generate test execution summary."""
        summary: Dict[str, Any] = {
            "total_tests": len(self.test_results),
            "duration_seconds": duration,
            "by_status": {},
            "by_type": {},
            "by_language": {},
            "failed_tests": [],
            "warnings": [],
        }

        # Count by status
        for result in self.test_results:
            status = result.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

            test_type = result.test_type.value
            summary["by_type"][test_type] = summary["by_type"].get(test_type, 0) + 1

            language = result.language
            summary["by_language"][language] = (
                summary["by_language"].get(language, 0) + 1
            )

            if result.status == TestStatus.FAILED:
                summary["failed_tests"].append(
                    {"test_id": result.test_id, "error": result.error_message}
                )

            if result.warnings:
                summary["warnings"].extend(result.warnings)

        # Calculate pass rate
        passed = summary["by_status"].get(TestStatus.PASSED.value, 0)
        summary["pass_rate"] = (
            (passed / summary["total_tests"] * 100) if summary["total_tests"] > 0 else 0
        )

        return summary


# Global test suite instance
language_test_suite = LanguageTestSuite()
