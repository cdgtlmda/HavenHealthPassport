"""GDPR compliance module for voice data."""

from typing import Dict, List


class GDPRCompliance:
    """Handles GDPR compliance for voice data processing."""

    def __init__(self) -> None:
        """Initialize GDPR compliance manager."""
        self.consent_records: Dict[str, Dict] = {}

    def check_consent(self, user_id: str, data_type: str) -> bool:
        """Check if user has given consent for data processing."""
        user_consent = self.consent_records.get(user_id, {})
        consent_value = user_consent.get(data_type, False)
        return bool(consent_value)

    def record_consent(self, user_id: str, data_type: str, granted: bool) -> None:
        """Record user consent for data processing."""
        if user_id not in self.consent_records:
            self.consent_records[user_id] = {}
        self.consent_records[user_id][data_type] = granted

    def get_user_rights(self, user_id: str) -> List[str]:
        """Get list of GDPR rights for user."""
        # User-specific rights could vary based on user status
        base_rights = [
            "right_to_access",
            "right_to_rectification",
            "right_to_erasure",
            "right_to_portability",
            "right_to_object",
            "right_to_restrict_processing",
        ]
        # Could add user-specific logic here
        _ = user_id  # Use the parameter
        return base_rights
