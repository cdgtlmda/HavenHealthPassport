"""WebAuthn configuration settings management.

This module handles WebAuthn/FIDO2 configuration loading from environment
variables and provides a centralized configuration interface.
"""

import os
import threading
from typing import List
from urllib.parse import urlparse

from src.config.biometric_config import WebAuthnConfig


class WebAuthnSettings:
    """Manages WebAuthn configuration with environment variable support."""

    def __init__(self) -> None:
        """Initialize WebAuthn settings from environment."""
        self._load_from_environment()

    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        # Basic RP settings
        self.rp_name = os.getenv("WEBAUTHN_RP_NAME", "Haven Health Passport")
        self.rp_id = os.getenv("WEBAUTHN_RP_ID", self._get_default_rp_id())

        # Origins
        origins_str = os.getenv("WEBAUTHN_RP_ORIGINS", "")
        if origins_str:
            self.rp_origins = [origin.strip() for origin in origins_str.split(",")]
        else:
            self.rp_origins = self._get_default_origins()

        # Authentication settings
        self.user_verification = os.getenv("WEBAUTHN_USER_VERIFICATION", "required")
        self.authenticator_attachment = os.getenv(
            "WEBAUTHN_AUTHENTICATOR_ATTACHMENT", "platform"
        )
        self.resident_key = os.getenv("WEBAUTHN_RESIDENT_KEY", "preferred")

        # Attestation settings
        self.attestation_conveyance = os.getenv("WEBAUTHN_ATTESTATION", "direct")

        # Timeout settings (in milliseconds)
        self.registration_timeout_ms = int(
            os.getenv("WEBAUTHN_REGISTRATION_TIMEOUT_MS", "60000")
        )
        self.authentication_timeout_ms = int(
            os.getenv("WEBAUTHN_AUTHENTICATION_TIMEOUT_MS", "60000")
        )

        # Security settings
        self.require_backup_eligible = (
            os.getenv("WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE", "false").lower() == "true"
        )
        self.require_backup_state = (
            os.getenv("WEBAUTHN_REQUIRE_BACKUP_STATE", "false").lower() == "true"
        )

        # Algorithm preferences
        self.public_key_algorithms = self._get_algorithms()

        # Challenge settings
        self.challenge_size = int(os.getenv("WEBAUTHN_CHALLENGE_SIZE", "32"))
        self.challenge_timeout_seconds = int(
            os.getenv("WEBAUTHN_CHALLENGE_TIMEOUT", "300")
        )

    def _get_default_rp_id(self) -> str:
        """Get default RP ID from environment or use fallback."""
        # Try to get from APP_URL environment variable
        app_url = os.getenv("APP_URL", "https://havenhealthpassport.org")
        parsed = urlparse(app_url)

        # Extract hostname without port
        hostname = parsed.hostname or "havenhealthpassport.org"

        # For localhost development
        if hostname in ["localhost", "127.0.0.1"]:
            return "localhost"

        return hostname

    def _get_default_origins(self) -> List[str]:
        """Get default allowed origins."""
        origins = []

        # Add APP_URL if set
        app_url = os.getenv("APP_URL")
        if app_url:
            origins.append(app_url.rstrip("/"))

        # Add API_URL if different
        api_url = os.getenv("API_URL")
        if api_url and api_url != app_url:
            origins.append(api_url.rstrip("/"))

        # Add localhost for development
        if os.getenv("ENVIRONMENT", "development") == "development":
            origins.extend(
                [
                    "http://localhost:3000",
                    "http://localhost:8000",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:8000",
                ]
            )

        # Fallback to default production URLs
        if not origins:
            origins = [
                "https://havenhealthpassport.org",
                "https://app.havenhealthpassport.org",
                "https://api.havenhealthpassport.org",
            ]

        return list(set(origins))  # Remove duplicates

    def _get_algorithms(self) -> List[int]:
        """Get supported public key algorithms."""
        # Default algorithms
        default_algorithms = [-7, -257, -8]  # ES256, RS256, EdDSA

        # Check if custom algorithms are specified
        algorithms_str = os.getenv("WEBAUTHN_ALGORITHMS")
        if algorithms_str:
            try:
                return [int(alg.strip()) for alg in algorithms_str.split(",")]
            except ValueError:
                # Fall back to defaults if parsing fails
                pass

        return default_algorithms

    def to_config(self) -> WebAuthnConfig:
        """Convert settings to WebAuthnConfig object."""
        return WebAuthnConfig(
            rp_name=self.rp_name,
            rp_id=self.rp_id,
            rp_origins=self.rp_origins,
            user_verification=self.user_verification,
            authenticator_attachment=self.authenticator_attachment,
            resident_key=self.resident_key,
            attestation_conveyance=self.attestation_conveyance,
            public_key_algorithms=self.public_key_algorithms,
            registration_timeout_ms=self.registration_timeout_ms,
            authentication_timeout_ms=self.authentication_timeout_ms,
            require_backup_eligible=self.require_backup_eligible,
            require_backup_state=self.require_backup_state,
        )

    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is allowed for WebAuthn operations.

        Args:
            origin: Origin to check

        Returns:
            True if origin is allowed
        """
        # Normalize origin
        origin = origin.rstrip("/").lower()

        # Check against allowed origins
        for allowed_origin in self.rp_origins:
            if origin == allowed_origin.lower():
                return True

        # Check if it's a subdomain of RP ID
        parsed = urlparse(origin)
        hostname = parsed.hostname or ""

        if hostname.endswith(f".{self.rp_id}") or hostname == self.rp_id:
            return True

        return False

    def get_allowed_credentials(self, user_credentials: List[dict]) -> List[dict]:
        """Format user credentials for WebAuthn authentication.

        Args:
            user_credentials: List of user's WebAuthn credentials

        Returns:
            Formatted allowed credentials list
        """
        allowed_credentials = []

        for cred in user_credentials:
            allowed_cred = {
                "type": "public-key",
                "id": cred.get("credential_id"),
            }

            # Add transports if available
            if "transports" in cred and cred["transports"]:
                allowed_cred["transports"] = cred["transports"]

            allowed_credentials.append(allowed_cred)

        return allowed_credentials

    def validate_authenticator_selection(self, authenticator_data: dict) -> bool:
        """Validate authenticator selection criteria.

        Args:
            authenticator_data: Authenticator data from registration

        Returns:
            True if authenticator meets requirements
        """
        # Check backup eligibility if required
        if self.require_backup_eligible:
            if not authenticator_data.get("backup_eligible", False):
                return False

        # Check backup state if required
        if self.require_backup_state:
            if not authenticator_data.get("backup_state", False):
                return False

        return True


# Thread-safe singleton for WebAuthn settings
class WebAuthnSettingsSingleton:
    """Thread-safe singleton for WebAuthn settings."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "WebAuthnSettingsSingleton":
        """Create or return the singleton instance of WebAuthnSettingsSingleton."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._settings = (
                        WebAuthnSettings()
                    )  # Type defined in __new__
        return cls._instance

    def get_settings(self) -> WebAuthnSettings:
        """Get the WebAuthn settings instance."""
        return self._settings

    def reload_settings(self) -> WebAuthnSettings:
        """Reload WebAuthn settings from environment."""
        with self._lock:
            self._settings = (
                WebAuthnSettings()
            )  # pylint: disable=attribute-defined-outside-init
        return self._settings


def get_webauthn_settings() -> WebAuthnSettings:
    """Get the thread-safe WebAuthn settings instance."""
    singleton = WebAuthnSettingsSingleton()
    return singleton.get_settings()


def reload_webauthn_settings() -> WebAuthnSettings:
    """Reload WebAuthn settings from environment."""
    singleton = WebAuthnSettingsSingleton()
    return singleton.reload_settings()
