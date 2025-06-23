"""AWS CloudWatch integration for logging and monitoring."""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CloudWatchLogger:
    """Send logs to AWS CloudWatch."""

    def __init__(self) -> None:
        """Initialize CloudWatch logger."""
        settings = get_settings()

        # Only initialize in non-local environments
        if settings.environment in ["production", "staging"]:
            self.client = boto3.client(
                "logs",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            self.log_group = f"/aws/haven-health/{settings.environment}"
            self.log_stream = (
                f"{settings.environment}-{datetime.now().strftime('%Y-%m-%d')}"
            )
            self._ensure_log_group_exists()
            self._ensure_log_stream_exists()
            self.sequence_token: Optional[str] = None
        else:
            self.client = None

    def _ensure_log_group_exists(self) -> None:
        """Create log group if it doesn't exist."""
        try:
            self.client.create_log_group(logGroupName=self.log_group)
            logger.info(f"Created CloudWatch log group: {self.log_group}")

            # Set retention policy (30 days)
            self.client.put_retention_policy(
                logGroupName=self.log_group, retentionInDays=30
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                logger.error(f"Failed to create log group: {e}")

    def _ensure_log_stream_exists(self) -> None:
        """Create log stream if it doesn't exist."""
        try:
            self.client.create_log_stream(
                logGroupName=self.log_group, logStreamName=self.log_stream
            )
            logger.info(f"Created CloudWatch log stream: {self.log_stream}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                logger.error(f"Failed to create log stream: {e}")

    def log(
        self, level: str, message: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send log to CloudWatch."""
        if not self.client:
            return

        log_event = {
            "timestamp": int(time.time() * 1000),
            "message": json.dumps(
                {
                    "level": level,
                    "message": message,
                    "environment": get_settings().environment,
                    **(extra or {}),
                }
            ),
        }

        try:
            kwargs = {
                "logGroupName": self.log_group,
                "logStreamName": self.log_stream,
                "logEvents": [log_event],
            }

            # Add sequence token if available
            if self.sequence_token is not None:
                kwargs["sequenceToken"] = self.sequence_token

            response = self.client.put_log_events(**kwargs)
            self.sequence_token = response.get("nextSequenceToken")

        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidSequenceTokenException":
                # Retry with the correct sequence token
                self.sequence_token = e.response["Error"]["expectedSequenceToken"]
                self.log(level, message, extra)
            else:
                logger.error(f"Failed to send log to CloudWatch: {e}")


class CloudWatchMetrics:
    """Send custom metrics to AWS CloudWatch."""

    def __init__(self) -> None:
        """Initialize CloudWatch metrics."""
        settings = get_settings()

        if settings.environment in ["production", "staging"]:
            self.client = boto3.client(
                "cloudwatch",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            self.namespace = f"HavenHealth/{settings.environment}"
        else:
            self.client = None

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Send a metric to CloudWatch."""
        if not self.client:
            return

        try:
            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.utcnow(),
            }

            if dimensions:
                metric_data["Dimensions"] = dimensions

            self.client.put_metric_data(
                Namespace=self.namespace, MetricData=[metric_data]
            )

        except ClientError as e:
            logger.error(f"Failed to send metric to CloudWatch: {e}")

    def record_api_latency(self, endpoint: str, latency_ms: float) -> None:
        """Record API endpoint latency."""
        self.put_metric(
            "APILatency",
            latency_ms,
            unit="Milliseconds",
            dimensions=[{"Name": "Endpoint", "Value": endpoint}],
        )

    def record_error(self, error_type: str, endpoint: Optional[str] = None) -> None:
        """Record application error."""
        dimensions = [{"Name": "ErrorType", "Value": error_type}]
        if endpoint:
            dimensions.append({"Name": "Endpoint", "Value": endpoint})

        self.put_metric("Errors", 1, dimensions=dimensions)

    def record_user_activity(
        self, activity_type: str, user_role: Optional[str] = None
    ) -> None:
        """Record user activity metrics."""
        dimensions = [{"Name": "ActivityType", "Value": activity_type}]
        if user_role:
            dimensions.append({"Name": "UserRole", "Value": user_role})

        self.put_metric("UserActivity", 1, dimensions=dimensions)


class CloudWatchAlarms:
    """Manage CloudWatch alarms."""

    def __init__(self) -> None:
        """Initialize CloudWatch alarms."""
        settings = get_settings()

        if settings.environment in ["production", "staging"]:
            self.client = boto3.client(
                "cloudwatch",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            self.sns_topic_arn = getattr(settings, "sns_alert_topic_arn", None)
        else:
            self.client = None

    def create_alarm(
        self,
        alarm_name: str,
        metric_name: str,
        threshold: float,
        comparison_operator: str = "GreaterThanThreshold",
        evaluation_periods: int = 1,
        period: int = 300,
    ) -> None:
        """Create a CloudWatch alarm."""
        if not self.client or not self.sns_topic_arn:
            return

        try:
            self.client.put_metric_alarm(
                AlarmName=alarm_name,
                ComparisonOperator=comparison_operator,
                EvaluationPeriods=evaluation_periods,
                MetricName=metric_name,
                Namespace=f"HavenHealth/{get_settings().environment}",
                Period=period,
                Statistic="Average",
                Threshold=threshold,
                ActionsEnabled=True,
                AlarmActions=[self.sns_topic_arn],
                AlarmDescription=f"Alarm for {metric_name}",
            )
            logger.info(f"Created CloudWatch alarm: {alarm_name}")

        except ClientError as e:
            logger.error(f"Failed to create alarm: {e}")

    def setup_default_alarms(self) -> None:
        """Set up default monitoring alarms."""
        # High API latency alarm
        self.create_alarm(
            "HighAPILatency",
            "APILatency",
            threshold=2000,  # 2 seconds
            comparison_operator="GreaterThanThreshold",
        )

        # High error rate alarm
        self.create_alarm(
            "HighErrorRate",
            "Errors",
            threshold=10,  # More than 10 errors in 5 minutes
            comparison_operator="GreaterThanThreshold",
            period=300,
        )

        # Low health check success rate
        self.create_alarm(
            "LowHealthCheckSuccessRate",
            "HealthCheck",
            threshold=0.95,  # Less than 95% success rate
            comparison_operator="LessThanThreshold",
            evaluation_periods=2,
        )


# Global instances
cloudwatch_logger = CloudWatchLogger()
cloudwatch_metrics = CloudWatchMetrics()
cloudwatch_alarms = CloudWatchAlarms()
