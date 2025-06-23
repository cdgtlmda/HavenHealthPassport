"""Test WebAuthn settings configuration.

This module tests WebAuthn configuration loading from environment
variables and provides comprehensive coverage for medical compliance.
"""

import os
from typing import Any, Dict

from src.config.biometric_config import WebAuthnConfig
from src.config.webauthn_settings import (
    WebAuthnSettings,
    get_webauthn_settings,
    reload_webauthn_settings,
)


class TestWebAuthnSettings:
    """Test WebAuthn settings configuration."""

    def setup_method(self):
        """Set up test method."""
        # Clear environment variables
        self.env_vars_to_clear = [
            "WEBAUTHN_RP_NAME",
            "WEBAUTHN_RP_ID",
            "WEBAUTHN_RP_ORIGINS",
            "WEBAUTHN_USER_VERIFICATION",
            "WEBAUTHN_AUTHENTICATOR_ATTACHMENT",
            "WEBAUTHN_RESIDENT_KEY",
            "WEBAUTHN_ATTESTATION",
            "WEBAUTHN_REGISTRATION_TIMEOUT_MS",
            "WEBAUTHN_AUTHENTICATION_TIMEOUT_MS",
            "WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE",
            "WEBAUTHN_REQUIRE_BACKUP_STATE",
            "WEBAUTHN_ALGORITHMS",
            "WEBAUTHN_CHALLENGE_SIZE",
            "WEBAUTHN_CHALLENGE_TIMEOUT",
            "APP_URL",
            "API_URL",
            "ENVIRONMENT",
        ]

        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

        # Clear singleton instance
        import src.config.webauthn_settings

        # Note: WebAuthnSettingsSingleton uses _instance, not _settings_instance
        if hasattr(src.config.webauthn_settings, "WebAuthnSettingsSingleton"):
            src.config.webauthn_settings.WebAuthnSettingsSingleton._instance = None

    def teardown_method(self):
        """Clean up after test method."""
        # Clear environment variables
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

        # Clear singleton instance
        import src.config.webauthn_settings

        # Note: WebAuthnSettingsSingleton uses _instance, not _settings_instance
        if hasattr(src.config.webauthn_settings, "WebAuthnSettingsSingleton"):
            src.config.webauthn_settings.WebAuthnSettingsSingleton._instance = None

    def test_default_initialization(self):
        """Test WebAuthn settings with default values."""
        # Set environment to production to get expected default origins
        os.environ["ENVIRONMENT"] = "production"
        settings = WebAuthnSettings()

        # Test default values
        assert settings.rp_name == "Haven Health Passport"
        assert settings.rp_id == "havenhealthpassport.org"
        assert "https://havenhealthpassport.org" in settings.rp_origins
        assert settings.user_verification == "required"
        assert settings.authenticator_attachment == "platform"
        assert settings.resident_key == "preferred"
        assert settings.attestation_conveyance == "direct"
        assert settings.registration_timeout_ms == 60000
        assert settings.authentication_timeout_ms == 60000
        assert settings.require_backup_eligible is False
        assert settings.require_backup_state is False
        assert settings.public_key_algorithms == [-7, -257, -8]
        assert settings.challenge_size == 32
        assert settings.challenge_timeout_seconds == 300

    def test_environment_variable_initialization(self):
        """Test WebAuthn settings with environment variables."""
        os.environ["WEBAUTHN_RP_NAME"] = "Test RP Name"
        os.environ["WEBAUTHN_RP_ID"] = "test.example.com"
        os.environ["WEBAUTHN_RP_ORIGINS"] = "https://test.com,https://app.test.com"
        os.environ["WEBAUTHN_USER_VERIFICATION"] = "preferred"
        os.environ["WEBAUTHN_AUTHENTICATOR_ATTACHMENT"] = "cross-platform"
        os.environ["WEBAUTHN_RESIDENT_KEY"] = "required"
        os.environ["WEBAUTHN_ATTESTATION"] = "none"
        os.environ["WEBAUTHN_REGISTRATION_TIMEOUT_MS"] = "30000"
        os.environ["WEBAUTHN_AUTHENTICATION_TIMEOUT_MS"] = "45000"
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "true"
        os.environ["WEBAUTHN_REQUIRE_BACKUP_STATE"] = "true"
        os.environ["WEBAUTHN_ALGORITHMS"] = "-7,-257"
        os.environ["WEBAUTHN_CHALLENGE_SIZE"] = "64"
        os.environ["WEBAUTHN_CHALLENGE_TIMEOUT"] = "600"

        settings = WebAuthnSettings()

        assert settings.rp_name == "Test RP Name"
        assert settings.rp_id == "test.example.com"
        assert settings.rp_origins == ["https://test.com", "https://app.test.com"]
        assert settings.user_verification == "preferred"
        assert settings.authenticator_attachment == "cross-platform"
        assert settings.resident_key == "required"
        assert settings.attestation_conveyance == "none"
        assert settings.registration_timeout_ms == 30000
        assert settings.authentication_timeout_ms == 45000
        assert settings.require_backup_eligible is True
        assert settings.require_backup_state is True
        assert settings.public_key_algorithms == [-7, -257]
        assert settings.challenge_size == 64
        assert settings.challenge_timeout_seconds == 600

    def test_get_default_rp_id_with_app_url(self):
        """Test default RP ID extraction from APP_URL."""
        os.environ["APP_URL"] = "https://example.com:8080/app"
        settings = WebAuthnSettings()
        assert settings.rp_id == "example.com"

    def test_get_default_rp_id_localhost(self):
        """Test default RP ID with localhost."""
        os.environ["APP_URL"] = "http://localhost:3000"
        settings = WebAuthnSettings()
        assert settings.rp_id == "localhost"

    def test_get_default_rp_id_127_0_0_1(self):
        """Test default RP ID with 127.0.0.1."""
        os.environ["APP_URL"] = "http://127.0.0.1:3000"
        settings = WebAuthnSettings()
        assert settings.rp_id == "localhost"

    def test_get_default_origins_with_app_url(self):
        """Test default origins with APP_URL."""
        os.environ["APP_URL"] = "https://app.example.com"
        settings = WebAuthnSettings()
        assert "https://app.example.com" in settings.rp_origins

    def test_get_default_origins_with_api_url(self):
        """Test default origins with different API_URL."""
        os.environ["APP_URL"] = "https://app.example.com"
        os.environ["API_URL"] = "https://api.example.com"
        settings = WebAuthnSettings()
        assert "https://app.example.com" in settings.rp_origins
        assert "https://api.example.com" in settings.rp_origins

    def test_get_default_origins_development_environment(self):
        """Test default origins in development environment."""
        os.environ["ENVIRONMENT"] = "development"
        settings = WebAuthnSettings()

        assert "http://localhost:3000" in settings.rp_origins
        assert "http://localhost:8000" in settings.rp_origins
        assert "http://127.0.0.1:3000" in settings.rp_origins
        assert "http://127.0.0.1:8000" in settings.rp_origins

    def test_get_default_origins_no_urls_set(self):
        """Test default origins when no URLs are set."""
        # Set to production to avoid development localhost URLs
        os.environ["ENVIRONMENT"] = "production"
        settings = WebAuthnSettings()

        assert "https://havenhealthpassport.org" in settings.rp_origins
        assert "https://app.havenhealthpassport.org" in settings.rp_origins
        assert "https://api.havenhealthpassport.org" in settings.rp_origins

    def test_get_default_origins_duplicate_removal(self):
        """Test that duplicate origins are removed."""
        os.environ["APP_URL"] = "https://example.com"
        os.environ["API_URL"] = "https://example.com"  # Same as APP_URL
        settings = WebAuthnSettings()

        # Count occurrences of the URL
        count = sum(
            1 for origin in settings.rp_origins if origin == "https://example.com"
        )
        assert count == 1

    def test_get_algorithms_with_custom_env(self):
        """Test algorithm parsing from environment variable."""
        os.environ["WEBAUTHN_ALGORITHMS"] = "-7, -257, -8"
        settings = WebAuthnSettings()
        assert settings.public_key_algorithms == [-7, -257, -8]

    def test_get_algorithms_with_invalid_env(self):
        """Test algorithm parsing with invalid environment variable."""
        os.environ["WEBAUTHN_ALGORITHMS"] = "invalid,values"
        settings = WebAuthnSettings()
        # Should fall back to default algorithms
        assert settings.public_key_algorithms == [-7, -257, -8]

    def test_to_config(self):
        """Test conversion to WebAuthnConfig object."""
        settings = WebAuthnSettings()
        config = settings.to_config()

        assert isinstance(config, WebAuthnConfig)
        assert config.rp_name == settings.rp_name
        assert config.rp_id == settings.rp_id
        assert config.rp_origins == settings.rp_origins
        assert config.user_verification == settings.user_verification
        assert config.authenticator_attachment == settings.authenticator_attachment
        assert config.resident_key == settings.resident_key
        assert config.attestation_conveyance == settings.attestation_conveyance
        assert config.public_key_algorithms == settings.public_key_algorithms
        assert config.registration_timeout_ms == settings.registration_timeout_ms
        assert config.authentication_timeout_ms == settings.authentication_timeout_ms
        assert config.require_backup_eligible == settings.require_backup_eligible
        assert config.require_backup_state == settings.require_backup_state

    def test_is_origin_allowed_exact_match(self):
        """Test origin validation with exact match."""
        os.environ["WEBAUTHN_RP_ORIGINS"] = (
            "https://example.com,https://app.example.com"
        )
        settings = WebAuthnSettings()

        assert settings.is_origin_allowed("https://example.com") is True
        assert settings.is_origin_allowed("https://app.example.com") is True

    def test_is_origin_allowed_case_insensitive(self):
        """Test origin validation is case insensitive."""
        os.environ["WEBAUTHN_RP_ORIGINS"] = "https://Example.com"
        settings = WebAuthnSettings()

        assert settings.is_origin_allowed("https://example.com") is True
        assert settings.is_origin_allowed("https://EXAMPLE.com") is True

    def test_is_origin_allowed_trailing_slash_normalization(self):
        """Test origin validation normalizes trailing slashes."""
        os.environ["WEBAUTHN_RP_ORIGINS"] = "https://example.com"
        settings = WebAuthnSettings()

        assert settings.is_origin_allowed("https://example.com/") is True

    def test_is_origin_allowed_subdomain(self):
        """Test origin validation allows subdomains of RP ID."""
        os.environ["WEBAUTHN_RP_ID"] = "example.com"
        settings = WebAuthnSettings()

        assert settings.is_origin_allowed("https://sub.example.com") is True
        assert settings.is_origin_allowed("https://app.example.com") is True

    def test_is_origin_allowed_rp_id_match(self):
        """Test origin validation allows RP ID itself."""
        os.environ["WEBAUTHN_RP_ID"] = "example.com"
        settings = WebAuthnSettings()

        assert settings.is_origin_allowed("https://example.com") is True

    def test_is_origin_allowed_not_allowed(self):
        """Test origin validation rejects non-allowed origins."""
        os.environ["WEBAUTHN_RP_ORIGINS"] = "https://example.com"
        os.environ["WEBAUTHN_RP_ID"] = "example.com"
        settings = WebAuthnSettings()

        assert settings.is_origin_allowed("https://malicious.com") is False
        assert settings.is_origin_allowed("https://notallowed.org") is False

    def test_get_allowed_credentials_basic(self):
        """Test formatting allowed credentials for authentication."""
        settings = WebAuthnSettings()

        user_credentials = [
            {"credential_id": "cred123", "transports": ["usb", "nfc"]},
            {"credential_id": "cred456", "transports": ["internal"]},
        ]

        allowed = settings.get_allowed_credentials(user_credentials)

        assert len(allowed) == 2
        assert allowed[0]["type"] == "public-key"
        assert allowed[0]["id"] == "cred123"
        assert allowed[0]["transports"] == ["usb", "nfc"]
        assert allowed[1]["type"] == "public-key"
        assert allowed[1]["id"] == "cred456"
        assert allowed[1]["transports"] == ["internal"]

    def test_get_allowed_credentials_no_transports(self):
        """Test formatting credentials without transports."""
        settings = WebAuthnSettings()

        user_credentials = [{"credential_id": "cred123"}]

        allowed = settings.get_allowed_credentials(user_credentials)

        assert len(allowed) == 1
        assert allowed[0]["type"] == "public-key"
        assert allowed[0]["id"] == "cred123"
        assert "transports" not in allowed[0]

    def test_get_allowed_credentials_empty_transports(self):
        """Test formatting credentials with empty transports."""
        settings = WebAuthnSettings()

        user_credentials = [{"credential_id": "cred123", "transports": []}]

        allowed = settings.get_allowed_credentials(user_credentials)

        assert len(allowed) == 1
        assert allowed[0]["type"] == "public-key"
        assert allowed[0]["id"] == "cred123"
        assert "transports" not in allowed[0]

    def test_validate_authenticator_selection_backup_eligible_required(self):
        """Test authenticator validation when backup eligible is required."""
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "true"
        settings = WebAuthnSettings()

        # Test with backup eligible
        authenticator_data = {"backup_eligible": True}
        assert settings.validate_authenticator_selection(authenticator_data) is True

        # Test without backup eligible
        authenticator_data = {"backup_eligible": False}
        assert settings.validate_authenticator_selection(authenticator_data) is False

        # Test missing backup eligible field
        authenticator_data = {}
        assert settings.validate_authenticator_selection(authenticator_data) is False

    def test_validate_authenticator_selection_backup_state_required(self):
        """Test authenticator validation when backup state is required."""
        os.environ["WEBAUTHN_REQUIRE_BACKUP_STATE"] = "true"
        settings = WebAuthnSettings()

        # Test with backup state
        authenticator_data = {"backup_state": True}
        assert settings.validate_authenticator_selection(authenticator_data) is True

        # Test without backup state
        authenticator_data = {"backup_state": False}
        assert settings.validate_authenticator_selection(authenticator_data) is False

        # Test missing backup state field
        authenticator_data = {}
        assert settings.validate_authenticator_selection(authenticator_data) is False

    def test_validate_authenticator_selection_both_required(self):
        """Test authenticator validation when both backup options are required."""
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "true"
        os.environ["WEBAUTHN_REQUIRE_BACKUP_STATE"] = "true"
        settings = WebAuthnSettings()

        # Test with both requirements met
        authenticator_data = {"backup_eligible": True, "backup_state": True}
        assert settings.validate_authenticator_selection(authenticator_data) is True

        # Test with only one requirement met
        authenticator_data = {"backup_eligible": True, "backup_state": False}
        assert settings.validate_authenticator_selection(authenticator_data) is False

        authenticator_data = {"backup_eligible": False, "backup_state": True}
        assert settings.validate_authenticator_selection(authenticator_data) is False

    def test_validate_authenticator_selection_no_requirements(self):
        """Test authenticator validation when no backup requirements are set."""
        settings = WebAuthnSettings()

        # Should pass with any data
        authenticator_data: Dict[str, Any] = {}
        assert settings.validate_authenticator_selection(authenticator_data) is True

        authenticator_data = {"backup_eligible": False, "backup_state": False}
        assert settings.validate_authenticator_selection(authenticator_data) is True


class TestWebAuthnSettingsSingleton:
    """Test WebAuthn settings singleton functions."""

    def setup_method(self):
        """Set up test method."""
        # Clear singleton instance
        import src.config.webauthn_settings

        # Note: WebAuthnSettingsSingleton uses _instance, not _settings_instance
        if hasattr(src.config.webauthn_settings, "WebAuthnSettingsSingleton"):
            src.config.webauthn_settings.WebAuthnSettingsSingleton._instance = None

    def teardown_method(self):
        """Clean up after test method."""
        # Clear singleton instance
        import src.config.webauthn_settings

        # Note: WebAuthnSettingsSingleton uses _instance, not _settings_instance
        if hasattr(src.config.webauthn_settings, "WebAuthnSettingsSingleton"):
            src.config.webauthn_settings.WebAuthnSettingsSingleton._instance = None

    def test_get_webauthn_settings_creates_instance(self):
        """Test that get_webauthn_settings creates singleton instance."""
        settings1 = get_webauthn_settings()
        settings2 = get_webauthn_settings()

        assert isinstance(settings1, WebAuthnSettings)
        assert settings1 is settings2  # Same instance

    def test_reload_webauthn_settings(self):
        """Test that reload_webauthn_settings creates new instance."""
        settings1 = get_webauthn_settings()
        settings2 = reload_webauthn_settings()

        assert isinstance(settings2, WebAuthnSettings)
        assert settings1 is not settings2  # Different instances

        # Get settings again should return the new instance
        settings3 = get_webauthn_settings()
        assert settings2 is settings3


class TestWebAuthnSettingsIntegration:
    """Integration tests for WebAuthn settings."""

    def setup_method(self):
        """Set up test method."""
        # Clear environment variables
        self.env_vars_to_clear = [
            "WEBAUTHN_RP_NAME",
            "WEBAUTHN_RP_ID",
            "WEBAUTHN_RP_ORIGINS",
            "APP_URL",
            "API_URL",
            "ENVIRONMENT",
        ]

        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

    def teardown_method(self):
        """Clean up after test method."""
        # Clear environment variables
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

    def test_production_configuration(self):
        """Test production-like configuration."""
        os.environ["APP_URL"] = "https://havenhealthpassport.org"
        os.environ["API_URL"] = "https://api.havenhealthpassport.org"
        os.environ["ENVIRONMENT"] = "production"
        os.environ["WEBAUTHN_RP_NAME"] = "Haven Health Passport"
        os.environ["WEBAUTHN_USER_VERIFICATION"] = "required"
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "true"

        settings = WebAuthnSettings()
        config = settings.to_config()

        # Verify production settings
        assert settings.rp_name == "Haven Health Passport"
        assert settings.rp_id == "havenhealthpassport.org"
        assert "https://havenhealthpassport.org" in settings.rp_origins
        assert "https://api.havenhealthpassport.org" in settings.rp_origins
        assert settings.user_verification == "required"
        assert settings.require_backup_eligible is True

        # Verify config conversion
        assert config.rp_name == "Haven Health Passport"
        assert config.user_verification == "required"
        assert config.require_backup_eligible is True

    def test_development_configuration(self):
        """Test development configuration."""
        os.environ["ENVIRONMENT"] = "development"
        os.environ["APP_URL"] = "http://localhost:3000"

        settings = WebAuthnSettings()

        # Verify development settings
        assert settings.rp_id == "localhost"
        assert "http://localhost:3000" in settings.rp_origins
        assert "http://localhost:8000" in settings.rp_origins
        assert "http://127.0.0.1:3000" in settings.rp_origins
        assert "http://127.0.0.1:8000" in settings.rp_origins

    def test_comprehensive_workflow(self):
        """Test comprehensive WebAuthn configuration workflow."""
        # Setup environment
        os.environ["WEBAUTHN_RP_NAME"] = "Test Haven Health"
        os.environ["WEBAUTHN_RP_ORIGINS"] = (
            "https://test.haven.org,https://api.test.haven.org"
        )
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "true"

        # Create settings
        settings = WebAuthnSettings()

        # Test origin validation
        assert settings.is_origin_allowed("https://test.haven.org") is True
        assert settings.is_origin_allowed("https://api.test.haven.org") is True
        assert settings.is_origin_allowed("https://malicious.com") is False

        # Test credential formatting
        credentials = [
            {"credential_id": "test123", "transports": ["usb", "nfc"]},
            {"credential_id": "test456"},
        ]
        allowed = settings.get_allowed_credentials(credentials)  # type: ignore
        assert len(allowed) == 2
        assert all(cred["type"] == "public-key" for cred in allowed)

        # Test authenticator validation
        auth_data = {"backup_eligible": True}
        assert settings.validate_authenticator_selection(auth_data) is True

        auth_data = {"backup_eligible": False}
        assert settings.validate_authenticator_selection(auth_data) is False

        # Test config conversion
        config = settings.to_config()
        assert isinstance(config, WebAuthnConfig)
        assert config.rp_name == "Test Haven Health"
        assert config.require_backup_eligible is True

    def test_get_default_origins_production_fallback_only(self):
        """Test that fallback URLs are used in production when no URLs are set."""
        os.environ["ENVIRONMENT"] = "production"
        # Ensure no APP_URL or API_URL is set
        if "APP_URL" in os.environ:
            del os.environ["APP_URL"]
        if "API_URL" in os.environ:
            del os.environ["API_URL"]

        settings = WebAuthnSettings()

        # Should use fallback URLs
        assert "https://havenhealthpassport.org" in settings.rp_origins
        assert "https://app.havenhealthpassport.org" in settings.rp_origins
        assert "https://api.havenhealthpassport.org" in settings.rp_origins
        # Should not have localhost URLs in production
        assert "http://localhost:3000" not in settings.rp_origins

    def test_get_default_origins_development_with_localhost_addition(self):
        """Test that development environment adds localhost URLs to existing URLs."""
        os.environ["ENVIRONMENT"] = "development"
        os.environ["APP_URL"] = "https://dev.example.com"

        settings = WebAuthnSettings()

        # Should include both APP_URL and localhost URLs
        assert "https://dev.example.com" in settings.rp_origins
        assert "http://localhost:3000" in settings.rp_origins
        assert "http://localhost:8000" in settings.rp_origins
        assert "http://127.0.0.1:3000" in settings.rp_origins
        assert "http://127.0.0.1:8000" in settings.rp_origins

    def test_get_default_origins_development_empty_list_fallback(self):
        """Test that development environment falls back to production URLs when no URLs are set."""
        os.environ["ENVIRONMENT"] = "development"
        # Ensure no APP_URL or API_URL is set
        if "APP_URL" in os.environ:
            del os.environ["APP_URL"]
        if "API_URL" in os.environ:
            del os.environ["API_URL"]

        settings = WebAuthnSettings()

        # In development with no URLs set, should get localhost first, then fallback
        assert "http://localhost:3000" in settings.rp_origins
        assert "http://localhost:8000" in settings.rp_origins
        assert "http://127.0.0.1:3000" in settings.rp_origins
        assert "http://127.0.0.1:8000" in settings.rp_origins

    def test_get_default_rp_id_hostname_extraction(self):
        """Test hostname extraction from APP_URL."""
        os.environ["APP_URL"] = "https://subdomain.example.com:443/path"
        settings = WebAuthnSettings()
        assert settings.rp_id == "subdomain.example.com"

    def test_get_default_rp_id_no_hostname_fallback(self):
        """Test fallback when parsed URL has no hostname."""
        # Test with invalid URL that would result in no hostname
        os.environ["APP_URL"] = "not-a-valid-url"
        settings = WebAuthnSettings()
        # Should fallback to default
        assert settings.rp_id == "havenhealthpassport.org"

    def test_get_algorithms_empty_string_fallback(self):
        """Test algorithm parsing with empty string."""
        os.environ["WEBAUTHN_ALGORITHMS"] = ""
        settings = WebAuthnSettings()
        # Should fall back to default algorithms
        assert settings.public_key_algorithms == [-7, -257, -8]

    def test_get_algorithms_value_error_fallback(self):
        """Test algorithm parsing when ValueError occurs."""
        os.environ["WEBAUTHN_ALGORITHMS"] = "not-an-integer,also-not-integer"
        settings = WebAuthnSettings()
        # Should fall back to default algorithms
        assert settings.public_key_algorithms == [-7, -257, -8]

    def test_is_origin_allowed_hostname_extraction_edge_cases(self):
        """Test origin validation with edge cases for hostname extraction."""
        os.environ["WEBAUTHN_RP_ID"] = "example.com"
        settings = WebAuthnSettings()

        # Test with URL that has no hostname after parsing
        assert settings.is_origin_allowed("not-a-url") is False

        # Test with empty hostname
        assert settings.is_origin_allowed("://example.com") is False

    def test_validate_authenticator_selection_missing_fields_individually(self):
        """Test authenticator validation with individual missing fields."""
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "true"
        settings = WebAuthnSettings()

        # Test with completely empty dict
        authenticator_data: Dict[str, Any] = {}
        assert settings.validate_authenticator_selection(authenticator_data) is False

        # Test with None value
        authenticator_data = {"backup_eligible": None}
        assert settings.validate_authenticator_selection(authenticator_data) is False

        # Test backup state requirements separately
        os.environ["WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE"] = "false"
        os.environ["WEBAUTHN_REQUIRE_BACKUP_STATE"] = "true"
        settings_backup_state = WebAuthnSettings()

        authenticator_data = {}
        assert (
            settings_backup_state.validate_authenticator_selection(authenticator_data)
            is False
        )

        authenticator_data = {"backup_state": None}
        assert (
            settings_backup_state.validate_authenticator_selection(authenticator_data)
            is False
        )
