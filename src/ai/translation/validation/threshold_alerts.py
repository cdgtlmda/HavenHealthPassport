"""
Threshold Alert Configuration System for Translation Quality.

This module provides a comprehensive alerting system that monitors translation
quality metrics and triggers alerts when configured thresholds are breached.
Supports multiple alert types, severity levels, and notification channels.
"""

import asyncio
import json
import logging
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .confidence_scorer import DetailedConfidenceScore
from .pipeline import ValidationResult, ValidationStatus

if TYPE_CHECKING:
    from .pipeline import TranslationValidationPipeline

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts that can be triggered."""

    CONFIDENCE_LOW = "confidence_low"
    ERROR_RATE_HIGH = "error_rate_high"
    VALIDATION_FAILURE = "validation_failure"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    CRITICAL_CONTENT_ERROR = "critical_content_error"
    VOLUME_SPIKE = "volume_spike"
    RESPONSE_TIME_HIGH = "response_time_high"
    HUMAN_REVIEW_BACKLOG = "human_review_backlog"
    TERMINOLOGY_MISMATCH = "terminology_mismatch"
    SIMILARITY_LOW = "similarity_low"


class AlertSeverity(Enum):
    """Severity levels for alerts."""

    INFO = 1  # Informational only
    WARNING = 2  # Should be investigated
    ERROR = 3  # Requires attention
    CRITICAL = 4  # Immediate action required


class AlertStatus(Enum):
    """Status of an alert."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


@dataclass
class ThresholdDefinition:
    """Definition of a threshold for monitoring."""

    metric_name: str
    threshold_value: float
    comparison: str  # "greater_than", "less_than", "equals"
    alert_type: AlertType
    severity: AlertSeverity

    # Advanced threshold options
    duration_seconds: Optional[int] = None  # Must breach for this duration
    occurrence_count: Optional[int] = None  # Must occur N times
    time_window_seconds: Optional[int] = None  # Within this time window

    # Alert configuration
    cooldown_minutes: int = 30  # Don't re-alert for this period
    auto_resolve_minutes: Optional[int] = None  # Auto-resolve if condition clears
    escalation_minutes: Optional[int] = 60  # Escalate if not acknowledged

    def evaluate(self, value: float) -> bool:
        """Evaluate if threshold is breached."""
        if self.comparison == "greater_than":
            return value > self.threshold_value
        elif self.comparison == "less_than":
            return value < self.threshold_value
        elif self.comparison == "equals":
            return value == self.threshold_value
        else:
            raise ValueError(f"Unknown comparison: {self.comparison}")


@dataclass
class Alert:
    """Represents an active alert."""

    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    threshold: ThresholdDefinition

    # Alert details
    triggered_at: datetime
    metric_value: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    # Alert state
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # Related data
    validation_result_id: Optional[str] = None
    language_pair: Optional[Tuple[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "triggered_at": self.triggered_at.isoformat(),
            "metric_value": self.metric_value,
            "message": self.message,
            "details": self.details,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "validation_result_id": self.validation_result_id,
            "language_pair": list(self.language_pair) if self.language_pair else None,
        }


@dataclass
class AlertConfiguration:
    """Configuration for the alerting system."""

    # Default thresholds
    default_thresholds: List[ThresholdDefinition] = field(
        default_factory=lambda: [
            # Confidence thresholds
            ThresholdDefinition(
                metric_name="confidence_score",
                threshold_value=0.6,
                comparison="less_than",
                alert_type=AlertType.CONFIDENCE_LOW,
                severity=AlertSeverity.WARNING,
                cooldown_minutes=15,
            ),
            ThresholdDefinition(
                metric_name="confidence_score",
                threshold_value=0.4,
                comparison="less_than",
                alert_type=AlertType.CONFIDENCE_LOW,
                severity=AlertSeverity.ERROR,
                cooldown_minutes=5,
            ),
            # Error rate thresholds
            ThresholdDefinition(
                metric_name="error_rate",
                threshold_value=0.1,  # 10% error rate
                comparison="greater_than",
                alert_type=AlertType.ERROR_RATE_HIGH,
                severity=AlertSeverity.WARNING,
                occurrence_count=5,
                time_window_seconds=300,  # 5 minutes
            ),
            # Performance thresholds
            ThresholdDefinition(
                metric_name="validation_time",
                threshold_value=5.0,  # 5 seconds
                comparison="greater_than",
                alert_type=AlertType.RESPONSE_TIME_HIGH,
                severity=AlertSeverity.INFO,
                duration_seconds=60,
            ),
            # Critical content
            ThresholdDefinition(
                metric_name="critical_content_errors",
                threshold_value=0,
                comparison="greater_than",
                alert_type=AlertType.CRITICAL_CONTENT_ERROR,
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=0,  # Always alert
            ),
            # Similarity thresholds
            ThresholdDefinition(
                metric_name="semantic_similarity",
                threshold_value=0.7,
                comparison="less_than",
                alert_type=AlertType.SIMILARITY_LOW,
                severity=AlertSeverity.WARNING,
            ),
        ]
    )

    # Notification settings
    enable_notifications: bool = True
    notification_channels: List[str] = field(default_factory=lambda: ["log", "metrics"])

    # Alert management
    max_alerts_per_type: int = 100
    alert_retention_days: int = 30
    enable_auto_resolve: bool = True
    enable_escalation: bool = True

    # Performance settings
    monitoring_interval_seconds: int = 60
    metric_aggregation_window: int = 300  # 5 minutes

    # Suppression rules
    suppression_rules: Dict[str, Any] = field(default_factory=dict)


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    async def send_alert(self, alert_obj: Alert) -> bool:
        """Send alert notification."""

    @abstractmethod
    def get_channel_name(self) -> str:
        """Get channel name."""


class LogNotificationChannel(NotificationChannel):
    """Log-based notification channel."""

    async def send_alert(self, alert_obj: Alert) -> bool:
        """Log the alert."""
        logger.warning(
            "ALERT [%s] %s: %s (value: %s)",
            alert_obj.severity.name,
            alert_obj.alert_type.value,
            alert_obj.message,
            alert_obj.metric_value,
        )
        return True

    def get_channel_name(self) -> str:
        """Return the channel name."""
        return "log"


class MetricsNotificationChannel(NotificationChannel):
    """Metrics/monitoring system notification channel."""

    async def send_alert(self, alert_obj: Alert) -> bool:
        """Send to metrics system (placeholder)."""
        # In production, this would send to CloudWatch, Datadog, etc.
        logger.info(
            "Metrics alert: %s - %s", alert_obj.alert_type.value, alert_obj.metric_value
        )
        return True

    def get_channel_name(self) -> str:
        """Return the channel name."""
        return "metrics"


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel (placeholder)."""

    def __init__(self, smtp_config: Dict[str, Any]):
        """Initialize email notification channel with SMTP configuration."""
        self.smtp_config = smtp_config

    async def send_alert(self, alert_obj: Alert) -> bool:
        """Send email alert (placeholder)."""
        # In production, this would use SMTP/SES
        logger.info("Email alert would be sent: %s", alert_obj.message)
        return True

    def get_channel_name(self) -> str:
        """Return the channel name."""
        return "email"


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel (placeholder)."""

    def __init__(self, webhook_url: str):
        """Initialize Slack notification channel with webhook URL."""
        self.webhook_url = webhook_url

    async def send_alert(self, alert_obj: Alert) -> bool:
        """Send Slack alert (placeholder)."""
        # In production, this would post to Slack
        logger.info("Slack alert would be sent: %s", alert_obj.message)
        return True

    def get_channel_name(self) -> str:
        """Return the channel name."""
        return "slack"


class ThresholdAlertManager:
    """Main threshold alert management system."""

    def __init__(self, config: Optional[AlertConfiguration] = None):
        """Initialize alert manager."""
        self.config = config or AlertConfiguration()

        # Alert storage
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=10000)

        # Metrics tracking
        self.metrics_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.metric_aggregates: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Threshold tracking
        self.thresholds: List[ThresholdDefinition] = (
            self.config.default_thresholds.copy()
        )
        self.threshold_breach_counts: Dict[str, int] = defaultdict(int)
        self.last_alert_times: Dict[str, datetime] = {}

        # Notification channels
        self.notification_channels: Dict[str, NotificationChannel] = {}
        self._init_notification_channels()

        # Background monitoring
        self._monitoring_task: Optional[asyncio.Task[None]] = None
        self._stop_monitoring = False

    def _init_notification_channels(self) -> None:
        """Initialize notification channels."""
        self.notification_channels["log"] = LogNotificationChannel()
        self.notification_channels["metrics"] = MetricsNotificationChannel()

    def add_threshold(self, threshold: ThresholdDefinition) -> None:
        """Add a new threshold definition."""
        self.thresholds.append(threshold)
        logger.info(
            "Added threshold for %s (%s)",
            threshold.metric_name,
            threshold.alert_type.value,
        )

    def remove_threshold(self, metric_name: str, alert_type: AlertType) -> bool:
        """Remove a threshold definition."""
        initial_count = len(self.thresholds)
        self.thresholds = [
            t
            for t in self.thresholds
            if not (t.metric_name == metric_name and t.alert_type == alert_type)
        ]
        removed = len(self.thresholds) < initial_count
        if removed:
            logger.info("Removed threshold for %s (%s)", metric_name, alert_type.value)
        return removed

    def update_threshold(
        self, metric_name: str, alert_type: AlertType, new_value: float
    ) -> bool:
        """Update an existing threshold value."""
        for threshold in self.thresholds:
            if (
                threshold.metric_name == metric_name
                and threshold.alert_type == alert_type
            ):
                threshold.threshold_value = new_value
                logger.info("Updated threshold for %s to %s", metric_name, new_value)
                return True
        return False

    def record_metric(
        self, metric_name: str, value: float, context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a metric value for monitoring."""
        timestamp = datetime.now()

        # Store in buffer
        self.metrics_buffer[metric_name].append(
            {"timestamp": timestamp, "value": value, "context": context or {}}
        )

        # Check thresholds immediately for critical metrics
        if context and context.get("check_immediately", False):
            self._check_metric_thresholds(metric_name, value, context)

    def record_validation_metrics(
        self,
        validation_result: ValidationResult,
        confidence_score: Optional[DetailedConfidenceScore] = None,
    ) -> None:
        """Record metrics from a validation result."""
        # Basic metrics
        if validation_result.metrics:
            self.record_metric(
                "validation_time", validation_result.metrics.validation_time
            )

            if (
                hasattr(validation_result.metrics, "semantic_similarity")
                and validation_result.metrics.semantic_similarity
            ):
                self.record_metric(
                    "semantic_similarity", validation_result.metrics.semantic_similarity
                )

        # Confidence score
        if confidence_score:
            self.record_metric(
                "confidence_score",
                confidence_score.overall_score,
                {
                    "category": confidence_score.confidence_category,
                    "requires_review": confidence_score.requires_human_review,
                    "check_immediately": confidence_score.overall_score < 0.5,
                },
            )

        # Error tracking
        error_rate = (
            validation_result.error_count / max(1, len(validation_result.issues))
            if validation_result.issues
            else 0
        )
        self.record_metric("error_rate", error_rate)

        # Critical content errors
        if self._has_critical_content_error(validation_result):
            self.record_metric(
                "critical_content_errors",
                1,
                {"validation_id": id(validation_result), "check_immediately": True},
            )

        # Language pair specific metrics
        lang_pair = f"{validation_result.source_lang}-{validation_result.target_lang}"
        self.record_metric(
            f"confidence_{lang_pair}",
            confidence_score.overall_score if confidence_score else 0.5,
        )

    def _has_critical_content_error(self, result: ValidationResult) -> bool:
        """Check if validation has critical content errors."""
        critical_keywords = [
            "dosage",
            "allergy",
            "contraindication",
            "fatal",
            "emergency",
        ]

        for issue in result.issues:
            if issue.severity == ValidationStatus.FAILED:
                if any(
                    keyword in issue.message.lower() for keyword in critical_keywords
                ):
                    return True

        return False

    def _check_metric_thresholds(
        self, metric_name: str, value: float, context: Dict[str, Any]
    ) -> None:
        """Check if metric breaches any thresholds."""
        for threshold in self.thresholds:
            if threshold.metric_name != metric_name:
                continue

            if threshold.evaluate(value):
                self._handle_threshold_breach(threshold, value, context)

    def _handle_threshold_breach(
        self, threshold: ThresholdDefinition, value: float, context: Dict[str, Any]
    ) -> None:
        """Handle a threshold breach."""
        # Check cooldown
        cooldown_key = f"{threshold.metric_name}:{threshold.alert_type.value}"
        if cooldown_key in self.last_alert_times:
            last_alert = self.last_alert_times[cooldown_key]
            if datetime.now() - last_alert < timedelta(
                minutes=threshold.cooldown_minutes
            ):
                return  # Still in cooldown

        # Check occurrence requirements
        if threshold.occurrence_count:
            self.threshold_breach_counts[cooldown_key] += 1
            if self.threshold_breach_counts[cooldown_key] < threshold.occurrence_count:
                return  # Not enough occurrences yet

        # Create alert
        alert = self._create_alert(threshold, value, context)

        # Store alert
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)

        # Update tracking
        self.last_alert_times[cooldown_key] = datetime.now()
        self.threshold_breach_counts[cooldown_key] = 0

        # Send notifications
        if self.config.enable_notifications:
            # Try to send notifications async if event loop is running
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._send_notifications(alert))
            except RuntimeError:
                # No event loop running, schedule for later or log
                logger.warning(
                    "No event loop available for sending notifications for alert: %s",
                    alert.alert_id,
                )

    def _create_alert(
        self, threshold: ThresholdDefinition, value: float, context: Dict[str, Any]
    ) -> Alert:
        """Create an alert from threshold breach."""
        alert_id = f"{threshold.alert_type.value}_{datetime.now().timestamp()}"

        message = self._generate_alert_message(threshold, value)

        alert = Alert(
            alert_id=alert_id,
            alert_type=threshold.alert_type,
            severity=threshold.severity,
            threshold=threshold,
            triggered_at=datetime.now(),
            metric_value=value,
            message=message,
            details=context,
        )

        # Add validation context if available
        if "validation_id" in context:
            alert.validation_result_id = str(context["validation_id"])

        return alert

    def _generate_alert_message(
        self, threshold: ThresholdDefinition, value: float
    ) -> str:
        """Generate human-readable alert message."""
        messages = {
            AlertType.CONFIDENCE_LOW: f"Translation confidence is low: {value:.2f} (threshold: {threshold.threshold_value})",
            AlertType.ERROR_RATE_HIGH: f"High error rate detected: {value:.2%} (threshold: {threshold.threshold_value:.2%})",
            AlertType.VALIDATION_FAILURE: f"Validation failures exceeding threshold: {value}",
            AlertType.PERFORMANCE_DEGRADATION: f"Performance degradation detected: {value:.2f}s",
            AlertType.CRITICAL_CONTENT_ERROR: "Critical medical content translation error detected",
            AlertType.RESPONSE_TIME_HIGH: f"High response time: {value:.2f}s (threshold: {threshold.threshold_value}s)",
            AlertType.SIMILARITY_LOW: f"Low semantic similarity: {value:.2f} (threshold: {threshold.threshold_value})",
        }

        return messages.get(
            threshold.alert_type,
            f"{threshold.metric_name} breached threshold: {value} (threshold: {threshold.threshold_value})",
        )

    async def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications through configured channels."""
        for channel_name in self.config.notification_channels:
            if channel_name in self.notification_channels:
                channel = self.notification_channels[channel_name]
                try:
                    await channel.send_alert(alert)
                except (ConnectionError, TimeoutError, ValueError) as e:
                    logger.error("Failed to send alert via %s: %s", channel_name, e)

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now()
            return True
        return False

    def resolve_alert(self, alert_id: str, resolved_by: Optional[str] = None) -> bool:
        """Resolve an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            if resolved_by:
                alert.details["resolved_by"] = resolved_by

            # Move to history
            del self.active_alerts[alert_id]
            return True
        return False

    def suppress_alert(self, alert_id: str, duration_minutes: int, reason: str) -> bool:
        """Suppress an alert for a specified duration."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.SUPPRESSED
            alert.details["suppressed_until"] = (
                datetime.now() + timedelta(minutes=duration_minutes)
            ).isoformat()
            alert.details["suppression_reason"] = reason
            return True
        return False

    async def start_monitoring(self) -> None:
        """Start background monitoring."""
        self._stop_monitoring = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Alert monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._stop_monitoring = True
        if self._monitoring_task:
            await self._monitoring_task
            logger.info("Alert monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring:
            try:
                # Aggregate metrics
                self._aggregate_metrics()

                # Check aggregated thresholds
                self._check_aggregated_thresholds()

                # Auto-resolve alerts
                if self.config.enable_auto_resolve:
                    self._auto_resolve_alerts()

                # Handle escalations
                if self.config.enable_escalation:
                    await self._handle_escalations()

                # Clean up old data
                self._cleanup_old_data()

            except (ValueError, KeyError, AttributeError) as e:
                logger.error("Error in monitoring loop: %s", e)

            # Wait for next interval
            await asyncio.sleep(self.config.monitoring_interval_seconds)

    def _aggregate_metrics(self) -> None:
        """Aggregate metrics over time windows."""
        current_time = datetime.now()
        window_start = current_time - timedelta(
            seconds=self.config.metric_aggregation_window
        )

        for metric_name, values in self.metrics_buffer.items():
            # Filter values within window
            window_values = [
                v["value"] for v in values if v["timestamp"] >= window_start
            ]

            if window_values:
                # Calculate aggregates
                self.metric_aggregates[metric_name] = {
                    "count": len(window_values),
                    "mean": statistics.mean(window_values),
                    "min": min(window_values),
                    "max": max(window_values),
                    "stddev": (
                        statistics.stdev(window_values) if len(window_values) > 1 else 0
                    ),
                }

    def _check_aggregated_thresholds(self) -> None:
        """Check thresholds against aggregated metrics."""
        for threshold in self.thresholds:
            metric_name = threshold.metric_name

            if metric_name in self.metric_aggregates:
                agg = self.metric_aggregates[metric_name]

                # Check against mean value
                if threshold.evaluate(agg["mean"]):
                    self._handle_threshold_breach(
                        threshold,
                        agg["mean"],
                        {"aggregation": "mean", "window_stats": agg},
                    )

    def _auto_resolve_alerts(self) -> None:
        """Auto-resolve alerts if conditions have cleared."""
        for alert_id, active_alert in list(self.active_alerts.items()):
            if active_alert.threshold.auto_resolve_minutes:
                # Check if condition has cleared
                metric_name = active_alert.threshold.metric_name
                if metric_name in self.metric_aggregates:
                    current_value = self.metric_aggregates[metric_name]["mean"]

                    if not active_alert.threshold.evaluate(current_value):
                        # Condition cleared - check duration
                        time_since_trigger = datetime.now() - active_alert.triggered_at
                        if time_since_trigger > timedelta(
                            minutes=active_alert.threshold.auto_resolve_minutes
                        ):
                            self.resolve_alert(alert_id, "auto-resolved")

    async def _handle_escalations(self) -> None:
        """Handle alert escalations."""
        for active_alert in list(self.active_alerts.values()):
            if (
                active_alert.status == AlertStatus.ACTIVE
                and active_alert.threshold.escalation_minutes
            ):

                time_since_trigger = datetime.now() - active_alert.triggered_at
                if time_since_trigger > timedelta(
                    minutes=active_alert.threshold.escalation_minutes
                ):
                    active_alert.status = AlertStatus.ESCALATED
                    active_alert.severity = AlertSeverity.CRITICAL  # Escalate severity

                    # Send escalation notification
                    await self._send_notifications(active_alert)

    def _cleanup_old_data(self) -> None:
        """Clean up old alert data."""
        cutoff_date = datetime.now() - timedelta(days=self.config.alert_retention_days)

        # Clean up resolved alerts from history
        while self.alert_history and self.alert_history[0].triggered_at < cutoff_date:
            self.alert_history.popleft()

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
    ) -> List[Alert]:
        """Get active alerts with optional filtering."""
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        active_by_severity: Dict[str, int] = defaultdict(int)
        active_by_type: Dict[str, int] = defaultdict(int)

        for active_alert in self.active_alerts.values():
            active_by_severity[active_alert.severity.name] += 1
            active_by_type[active_alert.alert_type.value] += 1

        # Historical stats
        history_by_type: Dict[str, int] = defaultdict(int)
        for history_alert in self.alert_history:
            history_by_type[history_alert.alert_type.value] += 1

        return {
            "active_alerts": {
                "total": len(self.active_alerts),
                "by_severity": dict(active_by_severity),
                "by_type": dict(active_by_type),
            },
            "historical": {
                "total": len(self.alert_history),
                "by_type": dict(history_by_type),
            },
            "metrics": {
                "tracked_metrics": list(self.metrics_buffer.keys()),
                "aggregated_metrics": {
                    name: stats for name, stats in self.metric_aggregates.items()
                },
            },
        }

    def export_alerts(
        self,
        filepath: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """Export alerts to file."""
        alerts = []

        # Add active alerts
        for active_alert in self.active_alerts.values():
            if self._alert_in_date_range(active_alert, start_date, end_date):
                alerts.append(active_alert.to_dict())

        # Add historical alerts
        for history_alert in self.alert_history:
            if self._alert_in_date_range(history_alert, start_date, end_date):
                alerts.append(history_alert.to_dict())

        # Export to JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "export_date": datetime.now().isoformat(),
                    "alerts": alerts,
                    "statistics": self.get_alert_statistics(),
                },
                f,
                indent=2,
            )

    def _alert_in_date_range(
        self, alert: Alert, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> bool:
        """Check if alert is within date range."""
        if start_date and alert.triggered_at < start_date:
            return False
        if end_date and alert.triggered_at > end_date:
            return False
        return True


# Integration with validation pipeline
def integrate_alert_manager(
    validation_pipeline: "TranslationValidationPipeline",
    alert_mgr: ThresholdAlertManager,
) -> None:
    """Integrate alert manager with validation pipeline."""
    # Store reference in pipeline
    setattr(validation_pipeline, "alert_manager", alert_mgr)

    # Hook into validation process
    original_validate = validation_pipeline.validate

    def validate_with_alerts(
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Enhanced validation with alert monitoring."""
        # Run validation
        result = original_validate(
            source_text, translated_text, source_lang, target_lang, metadata
        )

        # Record metrics for alerting
        confidence_score = None
        if "detailed_confidence_score" in result.metadata:
            confidence_score = result.metadata["detailed_confidence_score"]

        alert_mgr.record_validation_metrics(result, confidence_score)

        return result

    # Replace method
    setattr(validation_pipeline, "validate", validate_with_alerts)


# Example alert rules
def create_medical_translation_alerts() -> List[ThresholdDefinition]:
    """Create specialized alert rules for medical translations."""
    return [
        # Ultra-low confidence for medical content
        ThresholdDefinition(
            metric_name="confidence_score",
            threshold_value=0.5,
            comparison="less_than",
            alert_type=AlertType.CONFIDENCE_LOW,
            severity=AlertSeverity.CRITICAL,
            cooldown_minutes=0,  # Always alert for medical
        ),
        # Medical terminology accuracy
        ThresholdDefinition(
            metric_name="terminology_accuracy",
            threshold_value=0.85,
            comparison="less_than",
            alert_type=AlertType.TERMINOLOGY_MISMATCH,
            severity=AlertSeverity.ERROR,
            occurrence_count=3,
            time_window_seconds=600,
        ),
        # Volume spike detection
        ThresholdDefinition(
            metric_name="translation_volume",
            threshold_value=1000,  # translations per hour
            comparison="greater_than",
            alert_type=AlertType.VOLUME_SPIKE,
            severity=AlertSeverity.INFO,
            duration_seconds=300,
        ),
    ]


# Example usage
if __name__ == "__main__":
    # Create alert configuration
    alert_config = AlertConfiguration()

    # Add custom medical alerts
    alert_config.default_thresholds.extend(create_medical_translation_alerts())

    # Create alert manager
    alert_manager = ThresholdAlertManager(alert_config)

    # Simulate metrics
    alert_manager.record_metric("confidence_score", 0.45, {"check_immediately": True})
    alert_manager.record_metric("validation_time", 3.2)
    alert_manager.record_metric(
        "semantic_similarity", 0.65, {"check_immediately": True}
    )

    # Check active alerts
    active_alerts = alert_manager.get_active_alerts()
    print(f"Active alerts: {len(active_alerts)}")

    for alert_item in active_alerts:
        print(f"- [{alert_item.severity.name}] {alert_item.message}")

    # Get statistics
    stats = alert_manager.get_alert_statistics()
    print(f"\nAlert statistics: {json.dumps(stats, indent=2)}")
