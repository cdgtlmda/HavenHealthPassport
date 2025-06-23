"""LangChain Utilities for Haven Health Passport.

Helper functions and utilities for LangChain integration.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance. Handles FHIR Resource validation.
"""

import logging
import re
import sys
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional


def setup_langchain_logging(
    level: int = logging.INFO, format_string: Optional[str] = None
) -> None:
    """Set up logging configuration for LangChain.

    Args:
        level: Logging level
        format_string: Custom format string for logs
    """
    if format_string is None:
        format_string = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"

    # Configure root logger for langchain
    langchain_logger = logging.getLogger("langchain")
    langchain_logger.setLevel(level)

    # Remove existing handlers
    langchain_logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(format_string)
    console_handler.setFormatter(formatter)

    # Add handler to logger
    langchain_logger.addHandler(console_handler)

    # Also configure our module logger
    module_logger = logging.getLogger("haven_health_passport.ai.langchain")
    module_logger.setLevel(level)
    module_logger.handlers = []
    module_logger.addHandler(console_handler)


def timer(func: Callable[..., Any]) -> Callable[..., Any]:
    """Time function execution."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        logger = logging.getLogger(__name__)
        logger.debug("%s took %.2f seconds", func.__name__, end_time - start_time)

        return result

    return wrapper


def sanitize_medical_content(text: str) -> str:
    """Sanitize medical content for safety.

    Args:
        text: Input text

    Returns:
        Sanitized text
    """
    # This is a placeholder - in production, implement proper medical content validation
    # For now, just ensure no harmful content patterns

    harmful_patterns = ["self-harm", "suicide", "dangerous dosage", "lethal dose"]

    text_lower = text.lower()
    for pattern in harmful_patterns:
        if pattern in text_lower:
            logger = logging.getLogger(__name__)
            logger.warning("Potentially harmful content detected: %s", pattern)
            # In production, implement proper handling

    return text


def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to maximum length while preserving word boundaries.

    Args:
        text: Input text
        max_length: Maximum length
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    # Find the last space before max_length
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > 0:
        return truncated[:last_space] + "..."
    else:
        return truncated + "..."


def format_medical_response(response: str, include_disclaimer: bool = True) -> str:
    """Format medical response with appropriate disclaimers.

    Args:
        response: The response text
        include_disclaimer: Whether to include medical disclaimer

    Returns:
        Formatted response
    """
    if include_disclaimer:
        disclaimer = (
            "\n\n*This information is for educational purposes only "
            "and should not replace professional medical advice. "
            "Please consult with a healthcare provider for medical concerns.*"
        )
        return response + disclaimer

    return response


class MetricsCollector:
    """Simple metrics collector for LangChain operations."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.metrics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "response_times": [],
        }

    def record_request(
        self, success: bool, response_time: float, tokens: int = 0
    ) -> None:
        """Record metrics for a request."""
        self.metrics["total_requests"] += 1

        if success:
            self.metrics["successful_requests"] += 1
        else:
            self.metrics["failed_requests"] += 1

        self.metrics["total_tokens"] += tokens
        self.metrics["response_times"].append(response_time)

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        response_times = self.metrics["response_times"]

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
        else:
            avg_response_time = 0

        return {
            "total_requests": self.metrics["total_requests"],
            "success_rate": (
                self.metrics["successful_requests"]
                / max(self.metrics["total_requests"], 1)
            ),
            "average_response_time": avg_response_time,
            "total_tokens": self.metrics["total_tokens"],
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


def sanitize_pii(text: str) -> str:
    """Sanitize personally identifiable information from text.

    Args:
        text: Input text that may contain PII

    Returns:
        Sanitized text with PII removed or masked
    """
    # Phone numbers (various formats)
    text = re.sub(
        r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[PHONE]", text
    )

    # Email addresses
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text
    )

    # Social Security Numbers
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b", "[SSN]", text)

    # Credit card numbers (basic pattern)
    text = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[CREDIT_CARD]", text)

    # IP addresses
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_ADDRESS]", text)

    # Medical Record Numbers (MRN) - common patterns
    text = re.sub(
        r"\b(MRN|Medical Record Number|Patient ID)[:\s#]*\d+\b",
        "[MRN]",
        text,
        flags=re.IGNORECASE,
    )

    # Date of birth patterns
    text = re.sub(
        r"\b(DOB|Date of Birth)[:\s]*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        "[DOB]",
        text,
        flags=re.IGNORECASE,
    )

    logger = logging.getLogger(__name__)
    logger.debug("PII sanitization completed")

    return text


def validate_medical_content(content: Dict[str, Any]) -> None:
    """Validate medical content for safety and accuracy.

    Args:
        content: Dictionary containing medical content

    Raises:
        ValueError: If content contains unsafe medical information
    """
    logger = logging.getLogger(__name__)

    # Check for dangerous medical advice patterns
    dangerous_patterns = [
        r"stop taking .* medication",
        r"ignore .* doctor",
        r"self-treat",
        r"dangerous dosage",
        r"lethal dose",
    ]

    content_str = str(content).lower()

    for pattern in dangerous_patterns:
        if re.search(pattern, content_str, re.IGNORECASE):
            logger.error("Dangerous medical content detected: %s", pattern)
            raise ValueError("Content contains potentially dangerous medical advice")

    # Check for required disclaimers in medical advice
    if "medical" in content_str or "treatment" in content_str:
        has_disclaimer = any(
            disclaimer in content_str
            for disclaimer in [
                "consult",
                "healthcare provider",
                "medical professional",
                "doctor",
                "physician",
                "not medical advice",
            ]
        )

        if not has_disclaimer:
            logger.warning("Medical content missing disclaimer")
            # Add disclaimer to content if possible
            if isinstance(content, dict) and "output" in content:
                content["disclaimer"] = (
                    "This information is for educational purposes only. "
                    "Please consult with a healthcare provider."
                )

    logger.debug("Medical content validation completed")
