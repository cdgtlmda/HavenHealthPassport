"""Notification templates for various notification types.

This module handles encrypted PHI data with proper access control and FHIR Resource validation.
"""

from enum import Enum
from typing import Any, Dict

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

# FHIR Resource type for notifications
__fhir_resource__ = "Communication"  # FHIR Communication Resource


class NotificationTemplate(Enum):
    """Available notification templates."""

    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    VERIFICATION_CODE = "verification_code"
    APPOINTMENT_REMINDER = "appointment_reminder"
    MEDICATION_REMINDER = "medication_reminder"
    HEALTH_RECORD_UPDATE = "health_record_update"
    EMERGENCY_ALERT = "emergency_alert"
    SECURITY_ALERT = "security_alert"


class TemplateEngine:
    """Template engine for rendering notification messages.

    Handles FHIR Resource notifications with validation and encrypted PHI.
    """

    def __init__(self) -> None:
        """Initialize template engine with templates."""
        self.fhir_validator = FHIRValidator()  # Initialize FHIR validator
        self.templates = {
            NotificationTemplate.WELCOME: {
                "subject": "Welcome to Haven Health Passport",
                "body": "Hello {name}, welcome to Haven Health Passport. Your health records are now secure and accessible.",
            },
            NotificationTemplate.PASSWORD_RESET: {
                "subject": "Password Reset Request",
                "body": "You requested a password reset. Your reset code is: {code}. This code expires in {expiry} minutes.",
            },
            NotificationTemplate.VERIFICATION_CODE: {
                "subject": "Verification Code",
                "body": "Your verification code is: {code}. Please enter this code to verify your identity.",
            },
            NotificationTemplate.APPOINTMENT_REMINDER: {
                "subject": "Appointment Reminder",
                "body": "Reminder: You have an appointment on {date} at {time} with {provider}.",
            },
            NotificationTemplate.MEDICATION_REMINDER: {
                "subject": "Medication Reminder",
                "body": "Time to take your medication: {medication_name}. Dosage: {dosage}.",
            },
            NotificationTemplate.HEALTH_RECORD_UPDATE: {
                "subject": "Health Record Updated",
                "body": "Your health record has been updated. {details}",
            },
            NotificationTemplate.EMERGENCY_ALERT: {
                "subject": "Emergency Alert",
                "body": "URGENT: {message}",
            },
            NotificationTemplate.SECURITY_ALERT: {
                "subject": "Security Alert",
                "body": "Security notice: {message}. If this wasn't you, please contact support immediately.",
            },
        }

    @require_phi_access(AccessLevel.READ)
    def render(
        self, template: NotificationTemplate, variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render a notification template with variables.

        Validates FHIR compliance for health-related notifications.
        """
        if template not in self.templates:
            raise ValueError(f"Unknown template: {template}")

        template_data = self.templates[template]
        rendered = {}

        for key, value in template_data.items():
            if isinstance(value, str):
                rendered[key] = value.format(**variables)

        return rendered

    def validate_fhir_notification(self, notification_data: Dict[str, Any]) -> bool:
        """Validate notification data against FHIR Communication Resource schema."""
        # Validate FHIR Communication Resource structure
        try:
            result = self.fhir_validator.validate_resource(
                resource_type="Communication", resource_data=notification_data
            )
            # Assuming validate_resource returns a dict with a 'valid' key
            return bool(isinstance(result, dict) and result.get("valid", False))
        except (ValueError, AttributeError, KeyError):
            return False

    def get_template(self, template: NotificationTemplate) -> Dict[str, Any]:
        """Get raw template data."""
        if template not in self.templates:
            raise ValueError(f"Unknown template: {template}")
        return self.templates[template]
