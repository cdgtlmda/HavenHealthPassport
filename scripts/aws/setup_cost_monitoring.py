#!/usr/bin/env python3
"""Setup cost monitoring alerts for Bedrock usage."""

import json
import os
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Load AWS credentials
env_path = Path(__file__).parent.parent.parent / ".env.aws"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ[key] = value


def create_cost_budget(environment: str):
    """Create or update AWS Budget for Bedrock costs."""
    budgets_client = boto3.client("budgets")
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    budget_limits = {"development": 500.0, "staging": 1000.0, "production": 5000.0}

    budget_name = f"haven-health-bedrock-{environment}"
    budget_amount = budget_limits.get(environment, 500.0)

    budget = {
        "BudgetName": budget_name,
        "BudgetLimit": {"Amount": str(budget_amount), "Unit": "USD"},
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
        "CostFilters": {"Service": ["Amazon Bedrock"]},
        "CostTypes": {
            "IncludeTax": True,
            "IncludeSubscription": True,
            "UseBlended": False,
            "IncludeRefund": False,
            "IncludeCredit": False,
            "IncludeUpfront": True,
            "IncludeRecurring": True,
            "IncludeOtherSubscription": True,
            "IncludeSupport": True,
            "IncludeDiscount": True,
            "UseAmortized": False,
        },
    }

    # Define notification thresholds
    notifications = [
        {"threshold": 50, "type": "ACTUAL", "severity": "INFO"},
        {"threshold": 80, "type": "ACTUAL", "severity": "WARNING"},
        {"threshold": 90, "type": "ACTUAL", "severity": "CRITICAL"},
        {"threshold": 100, "type": "ACTUAL", "severity": "ALERT"},
        {"threshold": 110, "type": "FORECASTED", "severity": "WARNING"},
    ]

    try:
        # Check if budget exists
        try:
            existing = budgets_client.describe_budget(
                AccountId=account_id, BudgetName=budget_name
            )
            print(f"Updating existing budget: {budget_name}")

            # Update budget
            budgets_client.update_budget(AccountId=account_id, NewBudget=budget)
        except ClientError as e:
            if "not found" in str(e).lower():
                print(f"Creating new budget: {budget_name}")
                # Create new budget
                budgets_client.create_budget(AccountId=account_id, Budget=budget)
            else:
                raise

        # Create notifications for each threshold
        for notif in notifications:
            create_budget_notification(
                budgets_client,
                account_id,
                budget_name,
                notif["threshold"],
                notif["type"],
                notif["severity"],
            )

        print(f"✅ Budget '{budget_name}' configured with ${budget_amount} limit")
        return True

    except ClientError as e:
        print(f"❌ Error creating budget: {e}")
        return False


def create_budget_notification(
    budgets_client,
    account_id: str,
    budget_name: str,
    threshold: float,
    notification_type: str,
    severity: str,
):
    """Create budget notification."""

    # Get SNS topic ARN from environment or create default
    sns_topic_arn = os.environ.get(
        "BEDROCK_BUDGET_SNS_TOPIC",
        f"arn:aws:sns:{boto3.Session().region_name}:{account_id}:haven-health-bedrock-budget-alerts",
    )

    notification = {
        "NotificationType": notification_type,
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": threshold,
        "ThresholdType": "PERCENTAGE",
    }

    subscribers = [{"SubscriptionType": "SNS", "Address": sns_topic_arn}]

    # Add email subscribers if configured
    if os.environ.get("BUDGET_ALERT_EMAIL"):
        subscribers.append(
            {"SubscriptionType": "EMAIL", "Address": os.environ["BUDGET_ALERT_EMAIL"]}
        )

    try:
        budgets_client.create_notification(
            AccountId=account_id,
            BudgetName=budget_name,
            Notification=notification,
            Subscribers=subscribers,
        )
        print(f"  ✅ Created {severity} notification at {threshold}% threshold")
    except ClientError as e:
        if "already exists" in str(e).lower():
            print(f"  ℹ️  Notification at {threshold}% already exists")
        else:
            print(f"  ❌ Error creating notification: {e}")


def create_cost_anomaly_detector():
    """Create Cost Anomaly Detector for Bedrock."""
    ce_client = boto3.client("ce")

    try:
        # Create anomaly monitor
        monitor_response = ce_client.create_anomaly_monitor(
            AnomalyMonitor={
                "MonitorName": "haven-health-bedrock-anomaly-monitor",
                "MonitorType": "DIMENSIONAL",
                "MonitorDimension": "SERVICE",
                "MonitorSpecification": {
                    "Dimensions": {
                        "Key": "SERVICE",
                        "Values": ["Amazon Bedrock"],
                        "MatchOptions": ["EQUALS"],
                    }
                },
            }
        )

        monitor_arn = monitor_response["MonitorArn"]
        print(f"✅ Created anomaly monitor: {monitor_arn}")

        # Create anomaly subscription
        subscription_response = ce_client.create_anomaly_subscription(
            AnomalySubscription={
                "SubscriptionName": "haven-health-bedrock-anomaly-alerts",
                "AccountId": boto3.client("sts").get_caller_identity()["Account"],
                "MonitorArnList": [monitor_arn],
                "Subscribers": [
                    {
                        "Address": os.environ.get(
                            "ANOMALY_ALERT_EMAIL", "alerts@haven-health.org"
                        ),
                        "Type": "EMAIL",
                        "Status": "CONFIRMED",
                    }
                ],
                "Threshold": 100.0,  # Alert on anomalies over $100
                "Frequency": "DAILY",
            }
        )

        print(
            f"✅ Created anomaly subscription: {subscription_response['SubscriptionArn']}"
        )

    except ClientError as e:
        if "already exists" in str(e).lower():
            print("ℹ️  Anomaly detector already exists")
        else:
            print(f"❌ Error creating anomaly detector: {e}")


def create_cloudwatch_dashboard(environment: str):
    """Create CloudWatch dashboard for Bedrock monitoring."""
    cloudwatch = boto3.client("cloudwatch")
    region = boto3.Session().region_name

    dashboard_name = f"haven-health-bedrock-{environment}"

    dashboard_body = {
        "widgets": [
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["HavenHealth/Bedrock", "TokenCost", {"stat": "Sum"}],
                        ["...", {"stat": "Average"}],
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": region,
                    "title": "Bedrock Token Costs",
                },
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["HavenHealth/Bedrock", "InputTokens", {"stat": "Sum"}],
                        [".", "OutputTokens", {"stat": "Sum"}],
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": region,
                    "title": "Token Usage",
                },
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        ["AWS/Bedrock", "InvocationLatency", {"stat": "Average"}],
                        ["...", {"stat": "p99"}],
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": region,
                    "title": "Model Latency",
                },
            },
            {
                "type": "metric",
                "properties": {
                    "metrics": [
                        [
                            "HavenHealth/Bedrock/Alerts",
                            "CostThresholdExceeded",
                            {"stat": "Sum"},
                        ]
                    ],
                    "period": 3600,
                    "stat": "Sum",
                    "region": region,
                    "title": "Cost Alerts",
                },
            },
        ]
    }

    try:
        cloudwatch.put_dashboard(
            DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body)
        )
        print(f"✅ Created CloudWatch dashboard: {dashboard_name}")
    except ClientError as e:
        print(f"❌ Error creating dashboard: {e}")


def create_cost_allocation_tags():
    """Create cost allocation tags for Bedrock resources."""
    ce_client = boto3.client("ce")

    tags = ["Environment", "UserId", "ModelId", "UseCase", "Department", "Project"]

    try:
        for tag in tags:
            ce_client.create_cost_category_definition(
                Name=f"haven-health-bedrock-{tag.lower()}",
                RuleVersion="CostCategoryExpression.v1",
                Rules=[
                    {
                        "Value": "Tagged",
                        "Rule": {"Tags": {"Key": tag, "Values": ["*"]}},
                    },
                    {
                        "Value": "Untagged",
                        "Rule": {"Not": {"Tags": {"Key": tag, "Values": ["*"]}}},
                    },
                ],
            )
            print(f"✅ Created cost category for tag: {tag}")
    except ClientError as e:
        if "already exists" in str(e).lower():
            print("ℹ️  Cost categories already exist")
        else:
            print(f"❌ Error creating cost categories: {e}")


def main():
    """Main setup function."""
    print("🚀 Setting up Bedrock cost monitoring for Haven Health Passport\n")

    # Get environment
    environment = os.environ.get("ENVIRONMENT", "development")
    print(f"Environment: {environment}\n")

    # Create budget with notifications
    print("📊 Creating AWS Budget...")
    create_cost_budget(environment)

    # Create anomaly detector
    print("\n🔍 Creating Cost Anomaly Detector...")
    create_cost_anomaly_detector()

    # Create CloudWatch dashboard
    print("\n📈 Creating CloudWatch Dashboard...")
    create_cloudwatch_dashboard(environment)

    # Create cost allocation tags
    print("\n🏷️  Creating Cost Allocation Tags...")
    create_cost_allocation_tags()

    print("\n✅ Cost monitoring setup complete!")
    print("\n📝 Next steps:")
    print("  1. Verify budget notifications in AWS Budgets console")
    print("  2. Check CloudWatch dashboard for metrics")
    print("  3. Activate cost allocation tags in Billing console")
    print("  4. Configure SNS topic subscribers for alerts")


if __name__ == "__main__":
    main()
