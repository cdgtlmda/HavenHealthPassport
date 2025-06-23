"""Alerting configuration for various notification channels."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
import httpx

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertChannel(str, Enum):
    """Alert notification channels."""

    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


class AlertRule:
    """Define alert rules and conditions."""

    def __init__(
        self,
        name: str,
        condition: str,
        threshold: Any,
        severity: AlertSeverity,
        channels: List[AlertChannel],
        description: str = "",
        cooldown_minutes: int = 30,
    ):
        """Initialize alert rule."""
        self.name = name
        self.condition = condition
        self.threshold = threshold
        self.severity = severity
        self.channels = channels
        self.description = description
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered = None

    def should_trigger(self, value: Any) -> bool:
        """Check if alert should trigger based on condition."""
        if self.condition == "greater_than":
            return bool(value > self.threshold)
        elif self.condition == "less_than":
            return bool(value < self.threshold)
        elif self.condition == "equals":
            return bool(value == self.threshold)
        elif self.condition == "not_equals":
            return bool(value != self.threshold)
        elif self.condition == "contains":
            return self.threshold in str(value)
        return False


class AlertManager:
    """Manage alert routing and notifications."""

    def __init__(self) -> None:
        """Initialize alert manager."""
        settings = get_settings()
        self.rules: List[AlertRule] = []
        self.channels: Dict[AlertChannel, Any] = {}

        # Initialize channels based on configuration
        if hasattr(settings, "slack_webhook_url"):
            self.channels[AlertChannel.SLACK] = SlackAlertChannel(
                settings.slack_webhook_url
            )

        if hasattr(settings, "pagerduty_integration_key"):
            self.channels[AlertChannel.PAGERDUTY] = PagerDutyAlertChannel(
                settings.pagerduty_integration_key
            )

        if settings.environment in ["production", "staging"]:
            self.channels[AlertChannel.EMAIL] = EmailAlertChannel()
            self.channels[AlertChannel.SMS] = SMSAlertChannel()

        # Define default alert rules
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Set up default alerting rules."""
        # Critical alerts
        self.add_rule(
            AlertRule(
                name="HighErrorRate",
                condition="greater_than",
                threshold=50,  # errors per minute
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.PAGERDUTY, AlertChannel.SLACK],
                description="Error rate exceeds threshold",
            )
        )

        self.add_rule(
            AlertRule(
                name="DatabaseConnectionFailure",
                condition="equals",
                threshold=False,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.PAGERDUTY, AlertChannel.SMS],
                description="Database connection failed",
            )
        )

        # High severity alerts
        self.add_rule(
            AlertRule(
                name="HighAPILatency",
                condition="greater_than",
                threshold=5000,  # milliseconds
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.SLACK, AlertChannel.EMAIL],
                description="API latency exceeds 5 seconds",
            )
        )

        self.add_rule(
            AlertRule(
                name="LowDiskSpace",
                condition="less_than",
                threshold=10,  # percentage
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.SLACK, AlertChannel.EMAIL],
                description="Disk space below 10%",
            )
        )

        # Medium severity alerts
        self.add_rule(
            AlertRule(
                name="HighMemoryUsage",
                condition="greater_than",
                threshold=80,  # percentage
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.SLACK],
                description="Memory usage above 80%",
            )
        )

        # Security alerts
        self.add_rule(
            AlertRule(
                name="SuspiciousActivity",
                condition="greater_than",
                threshold=10,  # failed login attempts
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.SLACK, AlertChannel.EMAIL],
                description="Multiple failed login attempts detected",
            )
        )

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self.rules.append(rule)

    def check_and_alert(
        self,
        metric_name: str,
        value: Any,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Check metric against rules and send alerts if needed."""
        for rule in self.rules:
            if rule.name == metric_name and rule.should_trigger(value):
                self.send_alert(rule, value, additional_context)

    def send_alert(
        self, rule: AlertRule, value: Any, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send alert through configured channels."""
        alert_data = {
            "rule_name": rule.name,
            "severity": rule.severity,
            "description": rule.description,
            "current_value": value,
            "threshold": rule.threshold,
            "condition": rule.condition,
            "context": context or {},
        }

        for channel in rule.channels:
            if channel in self.channels:
                try:
                    self.channels[channel].send(alert_data)
                    logger.info(f"Alert sent via {channel}: {rule.name}")
                except (ConnectionError, ValueError, RuntimeError) as e:
                    logger.error(f"Failed to send alert via {channel}: {e}")


class SlackAlertChannel:
    """Send alerts to Slack."""

    def __init__(self, webhook_url: str):
        """Initialize Slack channel."""
        self.webhook_url = webhook_url

    async def send(self, alert_data: Dict[str, Any]) -> None:
        """Send alert to Slack."""
        color_map = {
            AlertSeverity.CRITICAL: "#FF0000",
            AlertSeverity.HIGH: "#FF9900",
            AlertSeverity.MEDIUM: "#FFCC00",
            AlertSeverity.LOW: "#00CC00",
            AlertSeverity.INFO: "#0099CC",
        }

        message = {
            "attachments": [
                {
                    "color": color_map.get(alert_data["severity"], "#808080"),
                    "title": f"🚨 {alert_data['rule_name']}",
                    "text": alert_data["description"],
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert_data["severity"].upper(),
                            "short": True,
                        },
                        {
                            "title": "Current Value",
                            "value": str(alert_data["current_value"]),
                            "short": True,
                        },
                        {
                            "title": "Threshold",
                            "value": f"{alert_data['condition']} {alert_data['threshold']}",
                            "short": True,
                        },
                    ],
                    "footer": "Haven Health Alert System",
                    "ts": int(datetime.now().timestamp()),
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=message)


class PagerDutyAlertChannel:
    """Send alerts to PagerDuty."""

    def __init__(self, integration_key: str):
        """Initialize PagerDuty channel."""
        self.integration_key = integration_key
        self.api_url = "https://events.pagerduty.com/v2/enqueue"

    async def send(self, alert_data: Dict[str, Any]) -> None:
        """Send alert to PagerDuty."""
        severity_map = {
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.HIGH: "error",
            AlertSeverity.MEDIUM: "warning",
            AlertSeverity.LOW: "info",
            AlertSeverity.INFO: "info",
        }

        event = {
            "routing_key": self.integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"{alert_data['rule_name']}: {alert_data['description']}",
                "severity": severity_map.get(alert_data["severity"], "error"),
                "source": "haven-health-passport",
                "custom_details": alert_data,
            },
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.api_url, json=event)


class EmailAlertChannel:
    """Send alerts via email using AWS SES."""

    def __init__(self) -> None:
        """Initialize email channel."""
        settings = get_settings()
        self.ses_client = boto3.client(
            "ses",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.from_email = getattr(
            settings, "alert_from_email", "alerts@havenhealthpassport.org"
        )
        self.to_emails = getattr(
            settings, "alert_to_emails", ["ops@havenhealthpassport.org"]
        )

    async def send(self, alert_data: Dict[str, Any]) -> None:
        """Send alert via email."""
        subject = f"[{alert_data['severity'].upper()}] {alert_data['rule_name']}"

        body_html = f"""
        <html>
        <body>
            <h2>{alert_data['rule_name']}</h2>
            <p><strong>Description:</strong> {alert_data['description']}</p>
            <p><strong>Severity:</strong> {alert_data['severity'].upper()}</p>
            <p><strong>Current Value:</strong> {alert_data['current_value']}</p>
            <p><strong>Threshold:</strong> {alert_data['condition']} {alert_data['threshold']}</p>
            <hr>
            <p><small>Haven Health Alert System</small></p>
        </body>
        </html>
        """

        self.ses_client.send_email(
            Source=self.from_email,
            Destination={"ToAddresses": self.to_emails},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": body_html}},
            },
        )


class SMSAlertChannel:
    """Send alerts via SMS using AWS SNS."""

    def __init__(self) -> None:
        """Initialize SMS channel."""
        settings = get_settings()
        self.sns_client = boto3.client(
            "sns",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.phone_numbers = getattr(settings, "alert_phone_numbers", [])

    async def send(self, alert_data: Dict[str, Any]) -> None:
        """Send alert via SMS."""
        message = f"[{alert_data['severity'].upper()}] {alert_data['rule_name']}: {alert_data['description']}"

        for phone in self.phone_numbers:
            self.sns_client.publish(
                PhoneNumber=phone, Message=message[:160]  # SMS character limit
            )


# Global alert manager instance
alert_manager = AlertManager()
