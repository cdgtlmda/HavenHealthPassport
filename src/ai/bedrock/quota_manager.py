"""Service quota management for Amazon Bedrock.

This module handles checking, requesting, and monitoring service quotas
for Bedrock to ensure the application can scale properly.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ServiceQuotaManager:
    """Manages AWS service quotas for Bedrock."""

    # Bedrock quota codes
    QUOTA_CODES = {
        "anthropic_claude_requests_per_minute": "L-1234ABCD",  # Example codes
        "anthropic_claude_tokens_per_minute": "L-5678EFGH",
        "titan_requests_per_minute": "L-9012IJKL",
        "titan_tokens_per_minute": "L-3456MNOP",
        "concurrent_requests": "L-7890QRST",
    }

    # Recommended quotas for Haven Health Passport
    RECOMMENDED_QUOTAS = {
        "development": {
            "requests_per_minute": 60,
            "tokens_per_minute": 100000,
            "concurrent_requests": 10,
        },
        "staging": {
            "requests_per_minute": 120,
            "tokens_per_minute": 500000,
            "concurrent_requests": 20,
        },
        "production": {
            "requests_per_minute": 300,
            "tokens_per_minute": 2000000,
            "concurrent_requests": 50,
        },
    }

    def __init__(self, region: str = "us-east-1"):
        """Initialize the quota manager."""
        self.region = region
        self.service_quotas_client = boto3.client("service-quotas", region_name=region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=region)

    def check_current_quotas(self, environment: str = "production") -> Dict[str, Dict]:
        """Check current service quotas for Bedrock."""
        quota_status = {}

        for quota_name, quota_code in self.QUOTA_CODES.items():
            try:
                response = self.service_quotas_client.get_service_quota(
                    ServiceCode="bedrock", QuotaCode=quota_code
                )

                quota_info = response["Quota"]
                current_value = quota_info.get("Value", 0)

                # Get usage if available
                usage = self._get_quota_usage(quota_code)

                quota_status[quota_name] = {
                    "current_limit": current_value,
                    "recommended_limit": self._get_recommended_quota(
                        quota_name, environment
                    ),
                    "current_usage": usage,
                    "utilization_percent": (
                        (usage / current_value * 100) if current_value > 0 else 0
                    ),
                    "adjustable": quota_info.get("Adjustable", False),
                    "global_quota": quota_info.get("GlobalQuota", False),
                }

            except ClientError as e:
                logger.error(f"Failed to check quota {quota_name}: {e}")
                quota_status[quota_name] = {"error": str(e)}

        return quota_status

    def _get_quota_usage(self, quota_code: str) -> float:
        """Get current usage for a specific quota."""
        try:
            # Map quota codes to CloudWatch metric names
            metric_mapping = {
                "L-1234ABCD": ("RequestsPerMinute", "anthropic.claude"),
                "L-5678EFGH": ("TokensPerMinute", "anthropic.claude"),
                "L-9012IJKL": ("RequestsPerMinute", "amazon.titan"),
                "L-3456MNOP": ("TokensPerMinute", "amazon.titan"),
                "L-7890QRST": ("ConcurrentRequests", "all"),
            }

            if quota_code not in metric_mapping:
                return 0.0

            metric_name, model_filter = metric_mapping[quota_code]

            # Get metric from CloudWatch
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/Bedrock",
                MetricName=metric_name,
                Dimensions=(
                    [{"Name": "ModelId", "Value": model_filter}]
                    if model_filter != "all"
                    else []
                ),
                StartTime=datetime.utcnow() - timedelta(minutes=5),
                EndTime=datetime.utcnow(),
                Period=60,
                Statistics=["Maximum"],
            )

            if response["Datapoints"]:
                return float(max(dp["Maximum"] for dp in response["Datapoints"]))
            return 0.0

        except ClientError as e:
            logger.error(f"Failed to get quota usage: {e}")
            return 0.0

    def _get_recommended_quota(self, quota_name: str, environment: str) -> float:
        """Get recommended quota value for the environment."""
        env_quotas = self.RECOMMENDED_QUOTAS.get(
            environment, self.RECOMMENDED_QUOTAS["production"]
        )

        # Map quota names to recommendation keys
        mapping = {
            "anthropic_claude_requests_per_minute": "requests_per_minute",
            "anthropic_claude_tokens_per_minute": "tokens_per_minute",
            "titan_requests_per_minute": "requests_per_minute",
            "titan_tokens_per_minute": "tokens_per_minute",
            "concurrent_requests": "concurrent_requests",
        }

        key = mapping.get(quota_name, "requests_per_minute")
        return env_quotas.get(key, 100)

    def request_quota_increase(
        self,
        quota_code: str,
        desired_value: float,
        reason: str = "Increased demand for Haven Health Passport",
    ) -> Dict:
        """Request a quota increase."""
        _ = reason  # Mark as intentionally unused
        try:
            response = self.service_quotas_client.request_service_quota_increase(
                ServiceCode="bedrock", QuotaCode=quota_code, DesiredValue=desired_value
            )

            request_info = response["RequestedQuota"]

            # Log the request
            logger.info(
                f"Requested quota increase for {quota_code}: "
                f"Current: {request_info.get('QuotaValue', 'N/A')} -> "
                f"Requested: {desired_value}"
            )

            # Send notification
            self._send_quota_request_notification(
                quota_code, desired_value, request_info
            )

            return {
                "request_id": request_info.get("Id"),
                "status": request_info.get("Status"),
                "case_id": request_info.get("CaseId"),
                "requested_value": desired_value,
                "current_value": request_info.get("QuotaValue"),
            }

        except ClientError as e:
            logger.error(f"Failed to request quota increase: {e}")
            return {"error": str(e)}

    def _send_quota_request_notification(
        self, quota_code: str, desired_value: float, request_info: Dict
    ) -> None:
        """Send notification about quota increase request."""
        _ = desired_value  # Mark as intentionally unused
        try:
            self.cloudwatch_client.put_metric_data(
                Namespace="HavenHealth/Bedrock/Quotas",
                MetricData=[
                    {
                        "MetricName": "QuotaIncreaseRequested",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "QuotaCode", "Value": quota_code},
                            {
                                "Name": "Status",
                                "Value": request_info.get("Status", "PENDING"),
                            },
                        ],
                    }
                ],
            )
        except ClientError as e:
            logger.error(f"Failed to send quota notification: {e}")

    def monitor_quota_health(self) -> List[Dict]:
        """Monitor quota health and return alerts."""
        alerts = []
        quota_status = self.check_current_quotas()

        for quota_name, status in quota_status.items():
            if "error" in status:
                continue

            utilization = status.get("utilization_percent", 0)

            # Check if we need to alert
            if utilization >= 90:
                alert_level = "CRITICAL" if utilization >= 95 else "WARNING"
                alerts.append(
                    {
                        "quota_name": quota_name,
                        "alert_level": alert_level,
                        "utilization": utilization,
                        "current_usage": status.get("current_usage"),
                        "current_limit": status.get("current_limit"),
                        "recommended_action": (
                            "Request quota increase"
                            if status.get("adjustable")
                            else "Optimize usage"
                        ),
                    }
                )

                # Send CloudWatch metric
                self._send_quota_alert_metric(quota_name, alert_level, utilization)

        return alerts

    def _send_quota_alert_metric(
        self, quota_name: str, alert_level: str, utilization: float
    ) -> None:
        """Send quota alert metric to CloudWatch."""
        try:
            self.cloudwatch_client.put_metric_data(
                Namespace="HavenHealth/Bedrock/Quotas",
                MetricData=[
                    {
                        "MetricName": "QuotaUtilizationAlert",
                        "Value": utilization,
                        "Unit": "Percent",
                        "Dimensions": [
                            {"Name": "QuotaName", "Value": quota_name},
                            {"Name": "AlertLevel", "Value": alert_level},
                        ],
                    }
                ],
            )
        except ClientError as e:
            logger.error(f"Failed to send quota alert metric: {e}")

    def auto_request_increases(self, threshold: float = 85.0) -> List[Dict]:
        """Automatically request quota increases when utilization exceeds threshold."""
        requests = []
        quota_status = self.check_current_quotas()

        for quota_name, status in quota_status.items():
            if "error" in status or not status.get("adjustable", False):
                continue

            utilization = status.get("utilization_percent", 0)

            if utilization >= threshold:
                # Calculate new quota (50% increase)
                current_limit = status.get("current_limit", 0)
                new_limit = current_limit * 1.5

                # Find quota code
                quota_code = self.QUOTA_CODES.get(quota_name)
                if quota_code:
                    result = self.request_quota_increase(
                        quota_code,
                        new_limit,
                        f"Auto-request: Utilization at {utilization:.1f}%",
                    )
                    requests.append({"quota_name": quota_name, "result": result})

        return requests

    def get_quota_history(self, quota_code: str, days: int = 30) -> List[Dict]:
        """Get historical quota request information."""
        try:
            response = (
                self.service_quotas_client.list_requested_service_quota_change_history(
                    ServiceCode="bedrock", QuotaCode=quota_code
                )
            )

            history = []
            for request in response.get("RequestedQuotas", []):
                created = request.get("Created")
                if created and (datetime.utcnow() - created).days <= days:
                    history.append(
                        {
                            "request_id": request.get("Id"),
                            "status": request.get("Status"),
                            "requested_value": request.get("DesiredValue"),
                            "created": created.isoformat(),
                            "last_updated": request.get(
                                "LastUpdated", created
                            ).isoformat(),
                            "case_id": request.get("CaseId"),
                        }
                    )

            return sorted(history, key=lambda x: x["created"], reverse=True)

        except ClientError as e:
            logger.error(f"Failed to get quota history: {e}")
            return []
