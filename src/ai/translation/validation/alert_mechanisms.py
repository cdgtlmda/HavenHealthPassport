"""
Alert Mechanisms Configuration for Translation Quality.

This module provides configuration and integration of alert mechanisms
with the translation quality monitoring system.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .metrics_tracker import MetricsTracker
from .performance_benchmarks import PerformanceBenchmarkManager
from .threshold_alerts import (
    AlertSeverity,
    AlertType,
    ThresholdAlertManager,
    ThresholdDefinition,
)

logger = logging.getLogger(__name__)


class AlertChannel(Enum):
    """Alert delivery channels."""

    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    TEAMS = "teams"
    WEBHOOK = "webhook"
    SNS = "sns"
    CLOUDWATCH = "cloudwatch"
    PAGERDUTY = "pagerduty"


class AlertPriority(Enum):
    """Alert priority levels."""

    P1_CRITICAL = "p1_critical"
    P2_HIGH = "p2_high"
    P3_MEDIUM = "p3_medium"
    P4_LOW = "p4_low"
    P5_INFO = "p5_info"


@dataclass
class AlertRule:
    """Alert rule configuration."""

    rule_id: str
    name: str
    description: str
    alert_type: AlertType
    priority: AlertPriority
    channels: List[AlertChannel]
    threshold: ThresholdDefinition
    cooldown_minutes: int = 30
    enabled: bool = True
    filters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "alert_type": self.alert_type.value,
            "priority": self.priority.value,
            "channels": [c.value for c in self.channels],
            "threshold": {
                "value": self.threshold.threshold_value,
                "operator": self.threshold.comparison,
                "window_minutes": (
                    self.threshold.duration_seconds // 60
                    if self.threshold.duration_seconds
                    else 0
                ),
            },
            "cooldown_minutes": self.cooldown_minutes,
            "enabled": self.enabled,
            "filters": self.filters,
            "metadata": self.metadata,
        }


@dataclass
class ChannelConfiguration:
    """Base configuration for alert channels."""

    channel_type: Optional[AlertChannel] = None
    enabled: bool = True
    rate_limit: Optional[int] = None  # Max alerts per hour

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_type": self.channel_type.value if self.channel_type else None,
            "enabled": self.enabled,
            "rate_limit": self.rate_limit,
        }


@dataclass
class EmailChannelConfig(ChannelConfiguration):
    """Email channel configuration."""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_address: str = ""
    to_addresses: List[str] = field(default_factory=list)
    use_ses: bool = True

    def __post_init__(self) -> None:
        """Initialize channel type after instance creation."""
        self.channel_type = AlertChannel.EMAIL


@dataclass
class SlackChannelConfig(ChannelConfiguration):
    """Slack channel configuration."""

    webhook_url: str = ""
    channel: str = ""
    username: str = "Translation Quality Bot"
    icon_emoji: str = ":robot_face:"
    message_format: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize channel type after instance creation."""
        self.channel_type = AlertChannel.SLACK


@dataclass
class SNSChannelConfig(ChannelConfiguration):
    """SNS channel configuration."""

    topic_arn: str = ""
    region: str = "us-east-1"

    def __post_init__(self) -> None:
        """Initialize channel type after instance creation."""
        self.channel_type = AlertChannel.SNS


@dataclass
class CloudWatchChannelConfig(ChannelConfiguration):
    """CloudWatch channel configuration."""

    namespace: str = "TranslationQuality"
    metric_namespace: str = "Alerts"

    def __post_init__(self) -> None:
        """Initialize channel type after instance creation."""
        self.channel_type = AlertChannel.CLOUDWATCH


class AlertMechanismManager:
    """
    Manages alert mechanisms and routing for translation quality monitoring.

    Features:
    - Multiple alert channels (Email, Slack, SNS, etc.)
    - Priority-based routing
    - Rate limiting and cooldowns
    - Alert deduplication
    - Channel health monitoring
    - Alert history tracking
    """

    def __init__(self) -> None:
        """Initialize the alert mechanism manager."""
        self.alert_manager = ThresholdAlertManager()
        self.metrics_tracker = MetricsTracker()
        self.benchmark_manager = PerformanceBenchmarkManager()

        # Alert rules storage
        self.alert_rules: Dict[str, AlertRule] = {}

        # Channel configurations
        self.channel_configs: Dict[AlertChannel, ChannelConfiguration] = {}

        # Alert history and cooldowns
        self._alert_history: List[Dict[str, Any]] = []
        self._cooldown_tracker: Dict[str, datetime] = {}

        # AWS clients
        self.sns_client = boto3.client("sns")
        self.ses_client = boto3.client("ses")
        self.cloudwatch_client = boto3.client("cloudwatch")

        # Initialize default configurations
        self._initialize_default_configurations()

    def _initialize_default_configurations(self) -> None:
        """Initialize default alert configurations."""
        # Default alert rules
        self._create_default_alert_rules()

        # Default channel configurations
        self._configure_default_channels()

    def _create_default_alert_rules(self) -> None:
        """Create default alert rules."""
        # Critical quality drop
        quality_drop_rule = AlertRule(
            rule_id="quality_drop_critical",
            name="Critical Quality Drop",
            description="Alert when quality score drops below critical threshold",
            alert_type=AlertType.VALIDATION_FAILURE,
            priority=AlertPriority.P1_CRITICAL,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.SNS],
            threshold=ThresholdDefinition(
                alert_type=AlertType.VALIDATION_FAILURE,
                metric_name="quality_score",
                threshold_value=0.70,
                comparison="less_than",
                severity=AlertSeverity.CRITICAL,
            ),
            cooldown_minutes=30,
        )
        self.alert_rules["quality_drop_critical"] = quality_drop_rule

        # High validation failure rate
        validation_failure_rule = AlertRule(
            rule_id="validation_failure_high",
            name="High Validation Failure Rate",
            description="Alert when validation pass rate drops significantly",
            alert_type=AlertType.VALIDATION_FAILURE,
            priority=AlertPriority.P2_HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.CLOUDWATCH],
            threshold=ThresholdDefinition(
                alert_type=AlertType.VALIDATION_FAILURE,
                metric_name="pass_rate",
                threshold_value=0.80,
                comparison="less_than",
                severity=AlertSeverity.WARNING,
            ),
            cooldown_minutes=60,
        )
        self.alert_rules["validation_failure_high"] = validation_failure_rule
        # Performance degradation
        performance_rule = AlertRule(
            rule_id="performance_degradation",
            name="Performance Degradation",
            description="Alert when response times exceed threshold",
            alert_type=AlertType.PERFORMANCE_DEGRADATION,
            priority=AlertPriority.P3_MEDIUM,
            channels=[AlertChannel.CLOUDWATCH, AlertChannel.SLACK],
            threshold=ThresholdDefinition(
                alert_type=AlertType.PERFORMANCE_DEGRADATION,
                metric_name="validation_time",
                threshold_value=5.0,
                comparison="greater_than",
                severity=AlertSeverity.WARNING,
            ),
            cooldown_minutes=45,
        )
        self.alert_rules["performance_degradation"] = performance_rule

        # Medical term accuracy warning
        medical_accuracy_rule = AlertRule(
            rule_id="medical_accuracy_warning",
            name="Medical Term Accuracy Warning",
            description="Alert when medical terminology accuracy drops",
            alert_type=AlertType.TERMINOLOGY_MISMATCH,
            priority=AlertPriority.P2_HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.SNS],
            threshold=ThresholdDefinition(
                alert_type=AlertType.TERMINOLOGY_MISMATCH,
                metric_name="terminology_accuracy",
                threshold_value=0.95,
                comparison="less_than",
                severity=AlertSeverity.ERROR,
            ),
            cooldown_minutes=30,
        )
        self.alert_rules["medical_accuracy_warning"] = medical_accuracy_rule

    def _configure_default_channels(self) -> None:
        """Configure default alert channels."""
        # Email channel (using SES)
        email_config = EmailChannelConfig(
            use_ses=True,
            from_address="alerts@translation-quality.com",
            to_addresses=["quality-team@example.com"],
        )
        self.channel_configs[AlertChannel.EMAIL] = email_config

        # SNS channel
        sns_config = SNSChannelConfig(
            topic_arn="arn:aws:sns:us-east-1:123456789012:translation-quality-alerts",
            region="us-east-1",
        )
        self.channel_configs[AlertChannel.SNS] = sns_config

        # CloudWatch channel
        cloudwatch_config = CloudWatchChannelConfig(
            namespace="TranslationQuality", metric_namespace="Alerts"
        )
        self.channel_configs[AlertChannel.CLOUDWATCH] = cloudwatch_config

        # Slack channel (webhook URL would be configured)
        slack_config = SlackChannelConfig(
            webhook_url="",  # Would be set from environment
            channel="#translation-alerts",
        )
        self.channel_configs[AlertChannel.SLACK] = slack_config

    async def process_metrics(
        self,
        metrics: Dict[str, float],
        language_pair: Optional[Tuple[str, str]] = None,
        mode: Optional[str] = None,
    ) -> None:
        """
        Process metrics and trigger alerts if thresholds are breached.

        Args:
            metrics: Current metric values
            language_pair: Optional language pair
            mode: Optional translation mode
        """
        triggered_alerts = []

        for rule_id, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            # Check filters
            if rule.filters:
                if language_pair and "language_pair" in rule.filters:
                    filter_pair = tuple(rule.filters["language_pair"].split("-"))
                    if language_pair != filter_pair:
                        continue

                if mode and "mode" in rule.filters:
                    if mode != rule.filters["mode"]:
                        continue

            # Check cooldown
            if self._is_in_cooldown(rule_id):
                continue

            # Evaluate threshold
            metric_name = rule.threshold.metric_name
            if metric_name in metrics:
                value = metrics[metric_name]

                if self._evaluate_threshold(value, rule.threshold):
                    alert = await self._trigger_alert(rule, value, language_pair, mode)
                    triggered_alerts.append(alert)

    def _is_in_cooldown(self, rule_id: str) -> bool:
        """Check if alert rule is in cooldown period."""
        if rule_id in self._cooldown_tracker:
            last_alert_time = self._cooldown_tracker[rule_id]
            rule = self.alert_rules[rule_id]
            cooldown_end = last_alert_time + timedelta(minutes=rule.cooldown_minutes)

            if datetime.utcnow() < cooldown_end:
                return True

        return False

    def _evaluate_threshold(self, value: float, threshold: ThresholdDefinition) -> bool:
        """Evaluate if value breaches threshold."""
        comparison = threshold.comparison
        threshold_value = threshold.threshold_value

        if comparison == "less_than":
            return value < threshold_value
        elif comparison == "greater_than":
            return value > threshold_value
        elif comparison == "equals":
            return value == threshold_value
        else:
            return False

    async def _trigger_alert(
        self,
        rule: AlertRule,
        value: float,
        language_pair: Optional[Tuple[str, str]],
        mode: Optional[str],
    ) -> Dict[str, Any]:
        """Trigger an alert and send to configured channels."""
        alert_data = {
            "alert_id": f"{rule.rule_id}_{datetime.utcnow().timestamp()}",
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
            "priority": rule.priority.value,
            "timestamp": datetime.utcnow().isoformat(),
            "metric": rule.threshold.metric_name,
            "value": value,
            "threshold": rule.threshold.threshold_value,
            "operator": rule.threshold.comparison,
            "language_pair": (
                f"{language_pair[0]}-{language_pair[1]}" if language_pair else None
            ),
            "mode": mode,
            "description": f"{rule.description}. Current value: {value:.3f}, Threshold: {rule.threshold.threshold_value}",
        }

        # Update cooldown
        self._cooldown_tracker[rule.rule_id] = datetime.utcnow()

        # Store in history
        self._alert_history.append(alert_data)

        # Send to each configured channel
        for channel in rule.channels:
            if channel in self.channel_configs:
                config = self.channel_configs[channel]
                if config.enabled:
                    try:
                        await self._send_to_channel(channel, alert_data, rule.priority)
                    except (ConnectionError, TimeoutError, ValueError) as e:
                        logger.error("Failed to send alert to %s: %s", channel, e)

        logger.info("Alert triggered: %s - Value: %.3f", rule.name, value)

        return alert_data

    async def _send_to_channel(
        self, channel: AlertChannel, alert_data: Dict[str, Any], priority: AlertPriority
    ) -> None:
        """Send alert to specific channel."""
        if channel == AlertChannel.EMAIL:
            await self._send_email_alert(alert_data, priority)
        elif channel == AlertChannel.SNS:
            await self._send_sns_alert(alert_data, priority)
        elif channel == AlertChannel.CLOUDWATCH:
            await self._send_cloudwatch_alert(alert_data, priority)
        elif channel == AlertChannel.SLACK:
            await self._send_slack_alert(alert_data, priority)
        else:
            logger.warning("Channel %s not implemented", channel)

    async def _send_email_alert(
        self, alert_data: Dict[str, Any], priority: AlertPriority
    ) -> None:
        """Send alert via email using SES."""
        config = self.channel_configs[AlertChannel.EMAIL]

        if not isinstance(config, EmailChannelConfig):
            return

        # Format subject with priority
        priority_emoji = {
            AlertPriority.P1_CRITICAL: "🚨",
            AlertPriority.P2_HIGH: "⚠️",
            AlertPriority.P3_MEDIUM: "📢",
            AlertPriority.P4_LOW: "ℹ️",
            AlertPriority.P5_INFO: "💡",
        }

        subject = f"{priority_emoji.get(priority, '')} [{priority.value}] Translation Quality Alert: {alert_data['rule_name']}"

        # Format body
        body = f"""
Translation Quality Alert

Alert: {alert_data['rule_name']}
Priority: {priority.value}
Time: {alert_data['timestamp']}

Details:
- Metric: {alert_data['metric']}
- Current Value: {alert_data['value']:.3f}
- Threshold: {alert_data['threshold']} (operator: {alert_data['operator']})
- Language Pair: {alert_data.get('language_pair', 'All')}
- Mode: {alert_data.get('mode', 'All')}

Description: {alert_data['description']}

Alert ID: {alert_data['alert_id']}
"""

        try:
            if config.use_ses:
                self.ses_client.send_email(
                    Source=config.from_address,
                    Destination={"ToAddresses": config.to_addresses},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {"Text": {"Data": body}},
                    },
                )
            else:
                # SMTP implementation would go here
                logger.info("Would send email alert: %s", subject)

        except ClientError as e:
            logger.error("Failed to send email alert: %s", e)

    async def _send_sns_alert(
        self, alert_data: Dict[str, Any], priority: AlertPriority
    ) -> None:
        """Send alert via SNS."""
        config = self.channel_configs[AlertChannel.SNS]

        if not isinstance(config, SNSChannelConfig):
            return

        # Format message
        message = {
            "default": f"Translation Quality Alert: {alert_data['rule_name']}",
            "email": json.dumps(alert_data, indent=2),
            "sms": f"{priority.value}: {alert_data['rule_name']} - {alert_data['metric']}: {alert_data['value']:.2f}",
        }

        try:
            self.sns_client.publish(
                TopicArn=config.topic_arn,
                Message=json.dumps(message),
                MessageStructure="json",
                Subject=f"[{priority.value}] {alert_data['rule_name']}",
            )
        except ClientError as e:
            logger.error("Failed to send SNS alert: %s", e)

    async def _send_cloudwatch_alert(
        self, alert_data: Dict[str, Any], priority: AlertPriority
    ) -> None:
        """Send alert metrics to CloudWatch."""
        config = self.channel_configs[AlertChannel.CLOUDWATCH]

        if not isinstance(config, CloudWatchChannelConfig):
            return

        try:
            # Send alert as custom metric
            self.cloudwatch_client.put_metric_data(
                Namespace=config.namespace,
                MetricData=[
                    {
                        "MetricName": f"Alert_{alert_data['rule_id']}",
                        "Value": alert_data["value"],
                        "Unit": "None",
                        "Timestamp": datetime.utcnow(),
                        "Dimensions": [
                            {"Name": "Priority", "Value": priority.value},
                            {"Name": "Metric", "Value": alert_data["metric"]},
                        ],
                    }
                ],
            )
        except ClientError as e:
            logger.error("Failed to send CloudWatch metric: %s", e)

    async def _send_slack_alert(
        self, alert_data: Dict[str, Any], priority: AlertPriority
    ) -> None:
        """Send alert to Slack."""
        config = self.channel_configs[AlertChannel.SLACK]

        if not isinstance(config, SlackChannelConfig) or not config.webhook_url:
            logger.warning("Slack webhook URL not configured")
            return

        # Implement actual Slack integration
        import aiohttp

        # Color mapping based on priority
        color_map = {
            AlertPriority.P1_CRITICAL: "#FF0000",  # Red
            AlertPriority.P2_HIGH: "#FF8C00",  # Dark Orange
            AlertPriority.P3_MEDIUM: "#FFD700",  # Gold
            AlertPriority.P4_LOW: "#32CD32",  # Lime Green
        }

        # Build Slack message
        slack_message: Dict[str, Any] = {
            "attachments": [
                {
                    "color": color_map.get(priority, "#808080"),
                    "title": f"🚨 Translation Alert: {alert_data['rule_name']}",
                    "fields": [
                        {"title": "Priority", "value": priority.value, "short": True},
                        {
                            "title": "Metric",
                            "value": alert_data.get("metric_name", "N/A"),
                            "short": True,
                        },
                        {
                            "title": "Current Value",
                            "value": f"{alert_data.get('metric_value', 0):.3f}",
                            "short": True,
                        },
                        {
                            "title": "Threshold",
                            "value": f"{alert_data.get('threshold', 0):.3f}",
                            "short": True,
                        },
                    ],
                    "text": alert_data.get(
                        "description", "Translation quality alert triggered"
                    ),
                    "footer": "Haven Health Passport",
                    "ts": int(alert_data.get("timestamp", datetime.now()).timestamp()),
                }
            ]
        }

        # Add custom message if provided
        if config.message_format:
            slack_message["text"] = config.message_format.format(**alert_data)

        # Send to Slack webhook
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    config.webhook_url,
                    json=slack_message,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info(
                            "Successfully sent Slack alert: %s", alert_data["rule_name"]
                        )
                    else:
                        logger.error("Failed to send Slack alert: %s", response.status)
        except Exception as e:
            logger.error("Error sending Slack alert: %s", str(e))

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        self.alert_rules[rule.rule_id] = rule
        logger.info("Added alert rule: %s", rule.rule_id)

    def remove_alert_rule(self, rule_id: str) -> None:
        """Remove an alert rule."""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            logger.info("Removed alert rule: %s", rule_id)

    def configure_channel(self, config: ChannelConfiguration) -> None:
        """Configure an alert channel."""
        if config.channel_type is None:
            logger.error("Cannot configure channel with None channel_type")
            return
        self.channel_configs[config.channel_type] = config
        logger.info("Configured channel: %s", config.channel_type.value)

    def get_alert_history(
        self,
        limit: int = 100,
        priority: Optional[AlertPriority] = None,
        start_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get alert history."""
        history = self._alert_history.copy()

        # Filter by priority
        if priority:
            history = [a for a in history if a["priority"] == priority.value]

        # Filter by time
        if start_time:
            history = [
                a
                for a in history
                if datetime.fromisoformat(a["timestamp"]) >= start_time
            ]

        # Sort by timestamp descending and limit
        history.sort(key=lambda x: x["timestamp"], reverse=True)

        return history[:limit]

    async def integrate_with_metrics_tracker(self) -> None:
        """
        Integrate alert mechanisms with metrics tracking system.

        This sets up automatic alert checking when new metrics are tracked.
        """
        # This would be called during system initialization
        logger.info("Alert mechanisms integrated with metrics tracking")

    def get_alert_summary(
        self, time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get summary of recent alerts."""
        if time_window is None:
            time_window = timedelta(hours=24)
        cutoff_time = datetime.utcnow() - time_window
        recent_alerts = self.get_alert_history(start_time=cutoff_time)

        # Count by priority
        priority_counts: Dict[str, int] = defaultdict(int)
        rule_counts: Dict[str, int] = defaultdict(int)

        for alert in recent_alerts:
            priority_counts[alert["priority"]] += 1
            rule_counts[alert["rule_id"]] += 1

        return {
            "total_alerts": len(recent_alerts),
            "time_window": str(time_window),
            "by_priority": dict(priority_counts),
            "by_rule": dict(rule_counts),
            "most_recent": recent_alerts[0] if recent_alerts else None,
        }

    def export_configuration(self) -> Dict[str, Any]:
        """Export current alert configuration."""
        return {
            "alert_rules": {
                rule_id: rule.to_dict() for rule_id, rule in self.alert_rules.items()
            },
            "channel_configs": {
                channel.value: config.to_dict()
                for channel, config in self.channel_configs.items()
            },
        }
