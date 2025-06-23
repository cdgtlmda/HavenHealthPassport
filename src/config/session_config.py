"""Session configuration and timeout policies.

This module defines session timeout policies and configuration
for the Haven Health Passport system.
"""

from typing import Any, Dict


class SessionTimeoutConfig:
    """Session timeout configuration."""

    # Default timeout values in minutes
    DEFAULT_CONFIGS = {
        "web": {
            "idle_timeout": 30,  # 30 minutes of inactivity
            "absolute_timeout": 480,  # 8 hours maximum
            "renewal_window": 5,  # 5 minutes before expiry
            "warning_threshold": 2,  # 2 minutes warning before timeout
            "max_renewals": 10,  # Maximum number of renewals
        },
        "mobile": {
            "idle_timeout": 720,  # 12 hours of inactivity
            "absolute_timeout": 10080,  # 7 days maximum
            "renewal_window": 60,  # 1 hour before expiry
            "warning_threshold": 30,  # 30 minutes warning
            "max_renewals": 20,  # Maximum number of renewals
        },
        "api": {
            "idle_timeout": 60,  # 1 hour of inactivity
            "absolute_timeout": 1440,  # 24 hours maximum
            "renewal_window": 10,  # 10 minutes before expiry
            "warning_threshold": 5,  # 5 minutes warning
            "max_renewals": 5,  # Maximum number of renewals
        },
        "admin": {
            "idle_timeout": 15,  # 15 minutes of inactivity
            "absolute_timeout": 240,  # 4 hours maximum
            "renewal_window": 2,  # 2 minutes before expiry
            "warning_threshold": 1,  # 1 minute warning
            "max_renewals": 3,  # Maximum number of renewals
        },
    }

    # Maximum concurrent sessions by type
    MAX_CONCURRENT_SESSIONS = {"web": 3, "mobile": 2, "api": 5, "admin": 1}

    # Session security settings
    SECURITY_SETTINGS = {
        "require_ip_consistency": False,  # Require same IP for session
        "require_device_consistency": True,  # Require same device
        "log_all_activity": True,  # Log all session activity
        "alert_on_suspicious_activity": True,  # Alert on suspicious patterns
        "auto_logout_on_suspicious": False,  # Auto-logout suspicious sessions
    }

    # Adaptive timeout thresholds
    ADAPTIVE_THRESHOLDS = {
        "high_activity": 0.5,  # Activities per minute
        "moderate_activity": 0.1,  # Activities per minute
        "low_activity": 0.05,  # Activities per minute
    }

    # Adaptive timeout multipliers
    ADAPTIVE_MULTIPLIERS = {
        "high_activity": 1.5,  # Extend timeout by 50%
        "moderate_activity": 1.0,  # Keep default timeout
        "low_activity": 0.75,  # Reduce timeout by 25%
    }

    @classmethod
    def get_config(cls, session_type: str) -> Dict[str, Any]:
        """Get configuration for session type.

        Args:
            session_type: Type of session

        Returns:
            Configuration dictionary
        """
        return cls.DEFAULT_CONFIGS.get(session_type, cls.DEFAULT_CONFIGS["web"])

    @classmethod
    def get_max_concurrent(cls, session_type: str) -> int:
        """Get maximum concurrent sessions for type.

        Args:
            session_type: Type of session

        Returns:
            Maximum concurrent sessions
        """
        return cls.MAX_CONCURRENT_SESSIONS.get(session_type, 5)

    @classmethod
    def get_security_setting(cls, setting: str) -> bool:
        """Get security setting value.

        Args:
            setting: Setting name

        Returns:
            Setting value
        """
        return cls.SECURITY_SETTINGS.get(setting, False)

    @classmethod
    def update_config(cls, session_type: str, config: Dict[str, Any]) -> None:
        """Update configuration for session type.

        Args:
            session_type: Type of session
            config: New configuration
        """
        if session_type in cls.DEFAULT_CONFIGS:
            cls.DEFAULT_CONFIGS[session_type].update(config)

    @classmethod
    def reset_to_defaults(cls) -> None:
        """Reset all configurations to defaults."""
        # Store original defaults
        cls.DEFAULT_CONFIGS = {
            "web": {
                "idle_timeout": 30,
                "absolute_timeout": 480,
                "renewal_window": 5,
                "warning_threshold": 2,
                "max_renewals": 10,
            },
            "mobile": {
                "idle_timeout": 720,
                "absolute_timeout": 10080,
                "renewal_window": 60,
                "warning_threshold": 30,
                "max_renewals": 20,
            },
            "api": {
                "idle_timeout": 60,
                "absolute_timeout": 1440,
                "renewal_window": 10,
                "warning_threshold": 5,
                "max_renewals": 5,
            },
            "admin": {
                "idle_timeout": 15,
                "absolute_timeout": 240,
                "renewal_window": 2,
                "warning_threshold": 1,
                "max_renewals": 3,
            },
        }


# Environment-specific overrides
class SessionConfigOverrides:
    """Environment-specific session configuration overrides."""

    PRODUCTION = {
        "admin": {
            "idle_timeout": 10,  # More restrictive in production
            "absolute_timeout": 120,  # 2 hours maximum
        }
    }

    DEVELOPMENT = {
        "web": {
            "idle_timeout": 120,  # More lenient in development
            "absolute_timeout": 1440,  # 24 hours
        },
        "admin": {
            "idle_timeout": 60,
            "absolute_timeout": 480,
        },
    }

    TESTING = {
        "web": {
            "idle_timeout": 5,  # Short timeouts for testing
            "absolute_timeout": 10,
        },
        "admin": {
            "idle_timeout": 2,
            "absolute_timeout": 5,
        },
    }

    @classmethod
    def apply_overrides(cls, environment: str) -> None:
        """Apply environment-specific overrides.

        Args:
            environment: Environment name (production, development, testing)
        """
        overrides = getattr(cls, environment.upper(), {})

        for session_type, config in overrides.items():
            if session_type in SessionTimeoutConfig.DEFAULT_CONFIGS:
                SessionTimeoutConfig.DEFAULT_CONFIGS[session_type].update(config)
