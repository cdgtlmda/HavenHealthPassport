"""Cost monitoring and alerting for Bedrock usage.

This module tracks Bedrock costs in real-time and provides
alerts when spending approaches configured thresholds.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from src.utils.logging import get_logger

logger = get_logger(__name__)


class BedrockCostMonitor:
    """Monitor and track Bedrock usage costs."""

    # Cost per 1000 tokens (approximate as of 2024)
    MODEL_COSTS = {
        "anthropic.claude-v2": {
            "input": 0.008,
            "output": 0.024,
        },
        "anthropic.claude-instant-v1": {
            "input": 0.0008,
            "output": 0.0024,
        },
        "anthropic.claude-3-sonnet-20240229-v1:0": {
            "input": 0.003,
            "output": 0.015,
        },
        "anthropic.claude-3-haiku-20240307-v1:0": {
            "input": 0.00025,
            "output": 0.00125,
        },
        "amazon.titan-text-express-v1": {
            "input": 0.0008,
            "output": 0.0016,
        },
        "amazon.titan-text-lite-v1": {
            "input": 0.0003,
            "output": 0.0004,
        },
    }

    def __init__(self) -> None:
        """Initialize cost monitor."""
        self.ce_client = boto3.client("ce")  # Cost Explorer
        self.cloudwatch = boto3.client("cloudwatch")
        self.budgets = boto3.client("budgets")
        self.usage_data: Dict[str, Dict] = {}
        self._load_budgets()

    def _load_budgets(self) -> None:
        """Load budget configurations."""
        try:
            account_id = boto3.client("sts").get_caller_identity()["Account"]
            response = self.budgets.describe_budgets(AccountId=account_id)
            self.budget_configs = {
                budget["BudgetName"]: budget
                for budget in response.get("Budgets", [])
                if "bedrock" in budget["BudgetName"].lower()
            }
        except ClientError as e:
            logger.error(f"Failed to load budgets: {e}")
            self.budget_configs = {}

    def calculate_token_cost(
        self, model_id: str, input_tokens: int, output_tokens: int
    ) -> Decimal:
        """Calculate cost for token usage."""
        if model_id not in self.MODEL_COSTS:
            logger.warning(f"Unknown model {model_id}, using default costs")
            costs = {"input": 0.001, "output": 0.002}
        else:
            costs = self.MODEL_COSTS[model_id]

        input_cost = (
            Decimal(str(costs["input"])) * Decimal(input_tokens) / Decimal(1000)
        )
        output_cost = (
            Decimal(str(costs["output"])) * Decimal(output_tokens) / Decimal(1000)
        )

        return input_cost + output_cost

    def track_usage(
        self,
        user_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        request_metadata: Optional[Dict] = None,
    ) -> None:
        """Track usage for a specific request."""
        _ = request_metadata  # Mark as intentionally unused
        cost = self.calculate_token_cost(model_id, input_tokens, output_tokens)

        # Update in-memory tracking
        if user_id not in self.usage_data:
            self.usage_data[user_id] = {
                "total_cost": Decimal("0"),
                "requests": 0,
                "tokens": {"input": 0, "output": 0},
                "by_model": {},
            }

        user_data = self.usage_data[user_id]
        user_data["total_cost"] += cost
        user_data["requests"] += 1
        user_data["tokens"]["input"] += input_tokens
        user_data["tokens"]["output"] += output_tokens

        if model_id not in user_data["by_model"]:
            user_data["by_model"][model_id] = {
                "cost": Decimal("0"),
                "requests": 0,
                "tokens": {"input": 0, "output": 0},
            }

        model_data = user_data["by_model"][model_id]
        model_data["cost"] += cost
        model_data["requests"] += 1
        model_data["tokens"]["input"] += input_tokens
        model_data["tokens"]["output"] += output_tokens

        # Send metrics to CloudWatch
        self._send_cloudwatch_metrics(
            user_id, model_id, cost, input_tokens, output_tokens
        )

        # Check thresholds
        self._check_cost_thresholds(user_id, user_data["total_cost"])

    def _send_cloudwatch_metrics(
        self,
        user_id: str,
        model_id: str,
        cost: Decimal,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Send usage metrics to CloudWatch."""
        try:
            self.cloudwatch.put_metric_data(
                Namespace="HavenHealth/Bedrock",
                MetricData=[
                    {
                        "MetricName": "TokenCost",
                        "Value": float(cost),
                        "Unit": "None",
                        "Dimensions": [
                            {"Name": "UserId", "Value": user_id},
                            {"Name": "ModelId", "Value": model_id},
                        ],
                    },
                    {
                        "MetricName": "InputTokens",
                        "Value": input_tokens,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "UserId", "Value": user_id},
                            {"Name": "ModelId", "Value": model_id},
                        ],
                    },
                    {
                        "MetricName": "OutputTokens",
                        "Value": output_tokens,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "UserId", "Value": user_id},
                            {"Name": "ModelId", "Value": model_id},
                        ],
                    },
                ],
            )
        except ClientError as e:
            logger.error(f"Failed to send CloudWatch metrics: {e}")

    def _check_cost_thresholds(self, user_id: str, total_cost: Decimal) -> None:
        """Check if user has exceeded cost thresholds."""
        # Define thresholds
        thresholds = {
            "warning": Decimal("50"),
            "alert": Decimal("100"),
            "critical": Decimal("200"),
        }

        for level, threshold in thresholds.items():
            if total_cost >= threshold:
                self._create_cost_alert(user_id, level, total_cost, threshold)

    def _create_cost_alert(
        self, user_id: str, level: str, cost: Decimal, threshold: Decimal
    ) -> None:
        """Create cost alert in CloudWatch."""
        try:
            self.cloudwatch.put_metric_data(
                Namespace="HavenHealth/Bedrock/Alerts",
                MetricData=[
                    {
                        "MetricName": "CostThresholdExceeded",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "UserId", "Value": user_id},
                            {"Name": "AlertLevel", "Value": level},
                        ],
                        "StorageResolution": 1,
                    }
                ],
            )
            logger.warning(
                f"Cost alert: User {user_id} exceeded {level} threshold "
                f"(${cost:.2f} > ${threshold:.2f})"
            )
        except ClientError as e:
            logger.error(f"Failed to create cost alert: {e}")

    def get_user_costs(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """Get cost data for a specific user."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                Filter={
                    "And": [
                        {
                            "Dimensions": {
                                "Key": "SERVICE",
                                "Values": ["Amazon Bedrock"],
                            }
                        },
                        {"Tags": {"Key": "UserId", "Values": [user_id]}},
                    ]
                },
                GroupBy=[{"Type": "TAG", "Key": "ModelId"}],
            )

            return self._format_cost_response(response)

        except ClientError as e:
            logger.error(f"Failed to get user costs: {e}")
            # Return in-memory data as fallback
            return self.usage_data.get(user_id, {})

    def _format_cost_response(self, response: Dict) -> Dict:
        """Format Cost Explorer response."""
        formatted: Dict[str, Any] = {
            "total_cost": Decimal("0"),
            "daily_costs": [],
            "by_model": {},
        }

        for result in response.get("ResultsByTime", []):
            date = result["TimePeriod"]["Start"]
            daily_total = Decimal("0")

            for group in result.get("Groups", []):
                model_id = group["Keys"][0] if group["Keys"] else "unknown"
                cost = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])

                daily_total += cost

                if model_id not in formatted["by_model"]:
                    formatted["by_model"][model_id] = Decimal("0")
                formatted["by_model"][model_id] += cost

            formatted["daily_costs"].append({"date": date, "cost": float(daily_total)})
            formatted["total_cost"] += daily_total

        return formatted

    def get_budget_status(self) -> List[Dict]:
        """Get status of all Bedrock-related budgets."""
        statuses = []

        for budget_name, budget_config in self.budget_configs.items():
            try:
                # Get actual spend
                actual_spend = self._get_budget_actual_spend(budget_name)
                budget_amount = float(budget_config["BudgetLimit"]["Amount"])

                utilization = (
                    (actual_spend / budget_amount * 100) if budget_amount > 0 else 0
                )

                statuses.append(
                    {
                        "budget_name": budget_name,
                        "budget_amount": budget_amount,
                        "actual_spend": actual_spend,
                        "utilization_percent": utilization,
                        "status": self._get_budget_health_status(utilization),
                    }
                )

            except (ClientError, KeyError, ValueError) as e:
                logger.error(f"Failed to get budget status for {budget_name}: {e}")

        return statuses

    def _get_budget_actual_spend(self, budget_name: str) -> float:
        """Get actual spend for a budget."""
        _ = budget_name  # Mark as intentionally unused
        try:
            # For monthly budgets, get current month spend
            start_date = datetime.now().replace(day=1)
            end_date = datetime.now()

            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                Filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Bedrock"]}},
            )

            if response["ResultsByTime"]:
                return float(
                    response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
                )
            return 0.0

        except ClientError as e:
            logger.error(f"Failed to get actual spend: {e}")
            return 0.0

    def _get_budget_health_status(self, utilization: float) -> str:
        """Determine budget health status based on utilization."""
        if utilization >= 100:
            return "EXCEEDED"
        elif utilization >= 90:
            return "CRITICAL"
        elif utilization >= 80:
            return "WARNING"
        else:
            return "HEALTHY"

    def create_cost_anomaly_detector(self) -> None:
        """Create anomaly detector for unusual cost patterns."""
        try:
            self.ce_client.create_anomaly_monitor(
                AnomalyMonitor={
                    "MonitorName": "haven-health-bedrock-anomaly-detector",
                    "MonitorType": "DIMENSIONAL",
                    "MonitorDimension": "SERVICE",
                    "MonitorSpecification": {
                        "Dimensions": {"Key": "SERVICE", "Values": ["Amazon Bedrock"]}
                    },
                }
            )
            logger.info("Created cost anomaly detector")
        except ClientError as e:
            if "already exists" not in str(e):
                logger.error(f"Failed to create anomaly detector: {e}")
