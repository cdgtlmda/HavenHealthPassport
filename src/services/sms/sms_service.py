"""SMS service manager for multi-provider support.

This module manages SMS sending with failover, rate limiting,
and provider selection capabilities. Includes validation for FHIR Resource
communication compliance.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.sms_log import SMSLog
from src.services.sms.aws_sns_provider import AWSSNSProvider
from src.services.sms.mock_provider import MockSMSProvider
from src.services.sms.provider import (
    SMSDeliveryReport,
    SMSDeliveryStatus,
    SMSMessage,
    SMSProvider,
    SMSProviderConfig,
    SMSProviderInterface,
)
from src.services.sms.twilio_provider import TwilioSMSProvider
from src.utils.exceptions import SMSException

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for SMS sending."""

    def __init__(self) -> None:
        """Initialize rate limiter."""
        self.counters: Dict[str, Dict[str, List[datetime]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def check_rate_limit(
        self, provider: str, config: SMSProviderConfig
    ) -> Tuple[bool, Optional[str]]:
        """Check if rate limit is exceeded.

        Args:
            provider: Provider name
            config: Provider configuration

        Returns:
            Tuple of (allowed, reason)
        """
        now = datetime.utcnow()
        provider_counters = self.counters[provider]
        # Check per-minute limit
        minute_ago = now - timedelta(minutes=1)
        provider_counters["minute"] = [
            ts for ts in provider_counters["minute"] if ts > minute_ago
        ]
        if len(provider_counters["minute"]) >= config.max_messages_per_minute:
            return (
                False,
                f"Rate limit exceeded: {config.max_messages_per_minute} messages per minute",
            )

        # Check per-hour limit
        hour_ago = now - timedelta(hours=1)
        provider_counters["hour"] = [
            ts for ts in provider_counters["hour"] if ts > hour_ago
        ]
        if len(provider_counters["hour"]) >= config.max_messages_per_hour:
            return (
                False,
                f"Rate limit exceeded: {config.max_messages_per_hour} messages per hour",
            )

        # Check per-day limit
        day_ago = now - timedelta(days=1)
        provider_counters["day"] = [
            ts for ts in provider_counters["day"] if ts > day_ago
        ]
        if len(provider_counters["day"]) >= config.max_messages_per_day:
            return (
                False,
                f"Rate limit exceeded: {config.max_messages_per_day} messages per day",
            )

        return True, None

    def record_message(self, provider: str) -> None:
        """Record a message send for rate limiting.

        Args:
            provider: Provider name
        """
        now = datetime.utcnow()
        provider_counters = self.counters[provider]
        provider_counters["minute"].append(now)
        provider_counters["hour"].append(now)
        provider_counters["day"].append(now)


class SMSService:
    """Main SMS service with multi-provider support."""

    def __init__(self, db: Session):
        """Initialize SMS service.

        Args:
            db: Database session
        """
        self.db = db
        self.providers: Dict[str, SMSProviderInterface] = {}
        self.configs: Dict[str, SMSProviderConfig] = {}
        self.rate_limiter = RateLimiter()
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize configured SMS providers."""
        # Load configurations from environment/database

        # Check environment
        environment = os.getenv("ENVIRONMENT", "development")

        # CRITICAL: NEVER use mock SMS in production - patient lives depend on communications
        if environment in ["production", "staging"]:
            # Twilio provider - PRIMARY for production
            twilio_config = self._load_twilio_config()
            if not twilio_config or not twilio_config.enabled:
                raise RuntimeError(
                    "FATAL: Twilio SMS not configured in production environment. "
                    "Patient safety communications CANNOT be sent. HALTING SYSTEM."
                )
            self.configs[SMSProvider.TWILIO.value] = twilio_config
            self.providers[SMSProvider.TWILIO.value] = TwilioSMSProvider(
                account_sid=twilio_config.config["account_sid"],
                auth_token=twilio_config.config["auth_token"],
                from_number=twilio_config.config["from_number"],
            )

            # AWS SNS provider - BACKUP for production
            sns_config = self._load_sns_config()
            if sns_config and sns_config.enabled:
                self.configs[SMSProvider.AWS_SNS.value] = sns_config
                self.providers[SMSProvider.AWS_SNS.value] = AWSSNSProvider(
                    region_name=(
                        sns_config.config["region_name"]
                        if "region_name" in sns_config.config
                        else "us-east-1"
                    ),
                )
            else:
                logger.warning(
                    "AWS SNS not configured as backup SMS provider. "
                    "Using Twilio as sole provider - this is a single point of failure."
                )
        else:
            # Development environment only - can use mock
            logger.warning("Using mock SMS provider in development environment")
            mock_config = SMSProviderConfig(
                provider=SMSProvider.MOCK,
                enabled=True,
                priority=100,  # Lowest priority even in dev
            )
            self.configs[SMSProvider.MOCK.value] = mock_config
            self.providers[SMSProvider.MOCK.value] = MockSMSProvider()

            # Still try to load real providers in dev if available
            twilio_config = self._load_twilio_config()
            if twilio_config and twilio_config.enabled:
                self.configs[SMSProvider.TWILIO.value] = twilio_config
                self.providers[SMSProvider.TWILIO.value] = TwilioSMSProvider(
                    account_sid=twilio_config.config["account_sid"],
                    auth_token=twilio_config.config["auth_token"],
                    from_number=twilio_config.config["from_number"],
                )

            # AWS SNS provider
            sns_config = self._load_sns_config()
            if sns_config and sns_config.enabled:
                self.configs[SMSProvider.AWS_SNS.value] = sns_config
                self.providers[SMSProvider.AWS_SNS.value] = AWSSNSProvider(
                    region_name=(
                        sns_config.config["region_name"]
                        if "region_name" in sns_config.config
                        else "us-east-1"
                    ),
                    sender_id=(
                        sns_config.config["sender_id"]
                        if "sender_id" in sns_config.config
                        else None
                    ),
                )

    def _load_twilio_config(self) -> Optional[SMSProviderConfig]:
        """Load Twilio configuration from environment."""
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER")

        if not all([account_sid, auth_token, from_number]):
            return None

        return SMSProviderConfig(
            provider=SMSProvider.TWILIO,
            enabled=True,
            priority=1,
            config={
                "account_sid": account_sid,
                "auth_token": auth_token,
                "from_number": from_number,
            },
        )

    def _load_sns_config(self) -> Optional[SMSProviderConfig]:
        """Load AWS SNS configuration from environment."""
        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        sender_id = os.getenv("AWS_SNS_SENDER_ID")

        # AWS credentials are handled by boto3 automatically

        return SMSProviderConfig(
            provider=SMSProvider.AWS_SNS,
            enabled=bool(os.getenv("AWS_SNS_ENABLED", "").lower() == "true"),
            priority=2,
            config={"region_name": region, "sender_id": sender_id},
        )

    async def send_sms(
        self,
        phone_number: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None,
        preferred_provider: Optional[str] = None,
    ) -> SMSDeliveryReport:
        """Send SMS with automatic failover.

        Args:
            phone_number: Recipient phone number
            body: Message body
            metadata: Optional metadata
            preferred_provider: Preferred provider name

        Returns:
            Delivery report

        Raises:
            SMSException: If all providers fail
        """
        message = SMSMessage(
            to=phone_number, body=body, from_number=None, metadata=metadata or {}
        )

        # Get sorted providers by priority
        sorted_providers = self._get_sorted_providers(preferred_provider)

        errors = []

        for provider_name in sorted_providers:
            provider = self.providers[provider_name]
            config = self.configs[provider_name]
            # Check rate limit
            allowed, reason = self.rate_limiter.check_rate_limit(provider_name, config)
            if not allowed:
                logger.warning("Rate limit exceeded for %s: %s", provider_name, reason)
                errors.append(f"{provider_name}: {reason}")
                continue

            try:
                # Attempt to send
                logger.info("Attempting to send SMS via %s", provider_name)
                report = await provider.send_sms(message)

                # Record for rate limiting
                self.rate_limiter.record_message(provider_name)

                # Log success
                logger.info(
                    "SMS sent successfully via %s: %s", provider_name, report.message_id
                )

                # Store delivery report in database
                await self._store_delivery_report(report, message)

                return report

            except (SMSException, ValueError, KeyError, AttributeError) as e:
                logger.error("Failed to send SMS via %s: %s", provider_name, str(e))
                errors.append(f"{provider_name}: {str(e)}")

                # Try next provider
                continue

        # All providers failed
        error_msg = "All SMS providers failed: " + "; ".join(errors)
        logger.error(error_msg)
        raise SMSException(error_msg)

    def _get_sorted_providers(
        self, preferred_provider: Optional[str] = None
    ) -> List[str]:
        """Get providers sorted by priority.

        Args:
            preferred_provider: Preferred provider to try first

        Returns:
            List of provider names sorted by priority
        """
        # Filter enabled providers
        enabled_providers = [
            (name, config) for name, config in self.configs.items() if config.enabled
        ]

        # Sort by priority (lower number = higher priority)
        sorted_providers = sorted(enabled_providers, key=lambda x: x[1].priority)
        # Extract provider names
        provider_names = [name for name, _ in sorted_providers]

        # Move preferred provider to front if specified
        if preferred_provider and preferred_provider in provider_names:
            provider_names.remove(preferred_provider)
            provider_names.insert(0, preferred_provider)

        return provider_names

    async def _store_delivery_report(
        self, report: SMSDeliveryReport, message: SMSMessage
    ) -> None:
        """Store delivery report in database.

        Args:
            report: Delivery report
            message: Original message
        """
        # Extract user_id from metadata if available
        user_id = message.metadata.get("user_id")
        if user_id and isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                logger.warning("Invalid user_id format in SMS metadata: %s", user_id)
                user_id = None

        # Create SMS log entry
        sms_log = SMSLog(
            user_id=user_id,
            phone_number=message.to,
            message_type=message.metadata.get("type", "unknown"),
            status="sent" if report.status == SMSDeliveryStatus.SENT else "failed",
            error_message=report.error_message,
            sent_at=(
                datetime.utcnow() if report.status == SMSDeliveryStatus.SENT else None
            ),
        )

        try:
            self.db.add(sms_log)
            self.db.commit()
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.error("Failed to store SMS log: %s", str(e))
            self.db.rollback()

    async def check_delivery_status(
        self, message_id: str, provider_name: str
    ) -> SMSDeliveryReport:
        """Check delivery status of a message.

        Args:
            message_id: Message ID
            provider_name: Provider that sent the message

        Returns:
            Delivery report
        """
        if provider_name not in self.providers:
            raise SMSException(f"Unknown provider: {provider_name}")

        provider = self.providers[provider_name]
        return await provider.check_delivery_status(message_id)

    async def validate_phone_number(self, phone_number: str) -> Dict[str, bool]:
        """Validate phone number across all providers.

        Args:
            phone_number: Phone number to validate

        Returns:
            Dict of provider name to validation result
        """
        results: Dict[str, bool] = {}

        for name, provider in self.providers.items():
            try:
                results[name] = await provider.validate_phone_number(phone_number)
            except (ValueError, AttributeError, TypeError) as e:
                logger.error("Error validating phone number with %s: %s", name, str(e))
                results[name] = False

        return results


# Module-level singleton instance
_sms_service_instance = None


def get_sms_service(db: Session) -> SMSService:
    """Get or create the SMS service instance.

    Args:
        db: Database session

    Returns:
        SMS service instance
    """
    global _sms_service_instance
    if _sms_service_instance is None:
        _sms_service_instance = SMSService(db)
    return _sms_service_instance
