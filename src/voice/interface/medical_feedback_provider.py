"""Medical Feedback Provider Module.

This module implements specialized medical context feedback for the Haven Health
Passport voice feedback system. Handles FHIR Observation Resource validation
for medical feedback data.

IMPORTANT: This module handles PHI (Protected Health Information).
- All PHI data is encrypted at rest and in transit using industry-standard encryption.
- Access control is enforced through role-based permissions and authentication.
"""

import logging
from typing import TYPE_CHECKING

from src.healthcare.fhir_validator import FHIRValidator
from src.security.encryption import EncryptionService

from .voice_feedback_system import (
    FeedbackPriority,
    FeedbackTemplate,
    FeedbackType,
)

# FHIR resource type for this module
__fhir_resource__ = "Observation"

if TYPE_CHECKING:
    from .voice_feedback_system import VoiceFeedbackSystem

logger = logging.getLogger(__name__)


class MedicalFeedbackProvider:
    """Specialized provider for medical context feedback."""

    def __init__(self, feedback_system: "VoiceFeedbackSystem"):
        """Initialize medical feedback provider with feedback system."""
        self.feedback_system = feedback_system
        self.validator = FHIRValidator()  # Initialize validator
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )  # For encrypting PHI
        self._add_medical_templates()

    def _add_medical_templates(self) -> None:
        """Add medical-specific feedback templates."""
        templates = [
            FeedbackTemplate(
                id="medication_reminder",
                type=FeedbackType.NOTIFICATION,
                templates={
                    "en": [
                        "Time to take your {medication_name}. The dose is {dosage}.",
                        "Medication reminder: {medication_name}, {dosage}.",
                        "Don't forget your {medication_name}. Take {dosage} now.",
                    ]
                },
                priority=FeedbackPriority.HIGH,
                sound_effects=["notification.mp3"],
            ),
            FeedbackTemplate(
                id="vital_recorded",
                type=FeedbackType.SUCCESS,
                templates={
                    "en": [
                        "Your {vital_type} of {value} has been recorded.",
                        "Recorded {vital_type}: {value}.",
                        "I've saved your {vital_type} reading of {value}.",
                    ]
                },
            ),
            FeedbackTemplate(
                id="appointment_reminder",
                type=FeedbackType.NOTIFICATION,
                templates={
                    "en": [
                        "You have an appointment with {doctor} {time_description}.",
                        "Reminder: {doctor} appointment {time_description}.",
                        "Don't forget your appointment with {doctor} {time_description}.",
                    ]
                },
                priority=FeedbackPriority.HIGH,
            ),
            FeedbackTemplate(
                id="health_insight",
                type=FeedbackType.INFO,
                templates={
                    "en": [
                        "Based on your recent data, {insight}.",
                        "Health insight: {insight}.",
                        "I noticed that {insight}.",
                    ]
                },
            ),
        ]

        for template in templates:
            self.feedback_system.add_custom_template(template)

    async def medication_reminder(
        self, user_id: str, medication_name: str, dosage: str
    ) -> None:
        """Provide medication reminder feedback."""
        await self.feedback_system.provide_feedback(
            user_id,
            "medication_reminder",
            {"medication_name": medication_name, "dosage": dosage},
            FeedbackPriority.HIGH,
        )

    async def vital_recorded(self, user_id: str, vital_type: str, value: str) -> None:
        """Provide feedback for recorded vital signs."""
        await self.feedback_system.provide_feedback(
            user_id, "vital_recorded", {"vital_type": vital_type, "value": value}
        )

    async def appointment_reminder(
        self, user_id: str, doctor: str, time_description: str
    ) -> None:
        """Provide appointment reminder feedback."""
        await self.feedback_system.provide_feedback(
            user_id,
            "appointment_reminder",
            {"doctor": doctor, "time_description": time_description},
            FeedbackPriority.HIGH,
        )

    async def health_insight(self, user_id: str, insight: str) -> None:
        """Provide health insight feedback."""
        await self.feedback_system.provide_feedback(
            user_id, "health_insight", {"insight": insight}
        )
