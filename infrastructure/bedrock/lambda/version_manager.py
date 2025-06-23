"""
Bedrock Model Version Manager
Handles model version selection, rollback, and A/B testing
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
ssm = boto3.client("ssm")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
VERSION_TABLE_NAME = os.environ["VERSION_TABLE_NAME"]
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
REGION = os.environ["REGION"]
ENVIRONMENT = os.environ["ENVIRONMENT"]

# DynamoDB tables
version_table = dynamodb.Table(VERSION_TABLE_NAME)
config_table = dynamodb.Table(CONFIG_TABLE_NAME)


class VersionManager:
    """Manages model versions, rollbacks, and A/B testing"""

    def __init__(self):
        self.ab_config = self.load_ab_config()
        self.version_cache = {}
        self.cache_ttl = 300  # 5 minutes

    def load_ab_config(self) -> Dict[str, Any]:
        """Load A/B testing configuration from SSM"""
        try:
            response = ssm.get_parameter(
                Name="/haven-health-passport/bedrock/ab-testing/config"
            )
            return json.loads(response["Parameter"]["Value"])
        except Exception as e:
            logger.error(f"Failed to load A/B config: {str(e)}")
            return {"active_tests": [], "default_split": {"control": 100, "test": 0}}

    def select_version(
        self, model_family: str, channel: str = "stable", user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Select appropriate model version based on channel and A/B tests"""
        # Check for active A/B tests
        test_version = self.check_ab_test(model_family, user_id)
        if test_version:
            return test_version

        # Get version from cache or database
        cache_key = f"{model_family}:{channel}"
        if cache_key in self.version_cache:
            cached_version, timestamp = self.version_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_version

        # Query version history
        version = self.get_latest_version(model_family, channel)

        # Update cache
        self.version_cache[cache_key] = (version, time.time())

        return version

    def check_ab_test(
        self, model_family: str, user_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if user should be in an A/B test"""
        for test in self.ab_config.get("active_tests", []):
            if test["model_family"] == model_family and test["status"] == "active":
                # Determine test group based on user_id or random
                if user_id:
                    group = (
                        "test"
                        if hash(user_id) % 100 < test["split"]["test"]
                        else "control"
                    )
                else:
                    group = (
                        "test"
                        if random.random() * 100 < test["split"]["test"]
                        else "control"
                    )

                if group == "test":
                    return self.get_version_by_id(test["test_version_id"])

        return None

    def get_latest_version(self, model_family: str, channel: str) -> Dict[str, Any]:
        """Get latest version for model family and channel"""
        try:
            response = version_table.query(
                KeyConditionExpression="model_family = :family",
                FilterExpression="#status = :channel",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":family": model_family,
                    ":channel": channel,
                },
                ScanIndexForward=False,
                Limit=1,
            )

            if response["Items"]:
                return response["Items"][0]
            else:
                raise Exception(f"No {channel} version found for {model_family}")

        except Exception as e:
            logger.error(f"Failed to get version: {str(e)}")
            # Return default stable version
            return {
                "model_family": model_family,
                "model_id": f"{model_family}-default",
                "version": "fallback",
                "status": "fallback",
            }

    def get_version_by_id(self, version_id: str) -> Dict[str, Any]:
        """Get specific version by ID"""
        # Implementation would query version table by version_id
        return {"model_id": version_id, "version": "test"}

    def record_version_change(
        self, model_family: str, old_version: str, new_version: str, reason: str
    ):
        """Record version change in history"""
        timestamp = int(time.time() * 1000)

        version_table.put_item(
            Item={
                "model_family": model_family,
                "timestamp": timestamp,
                "old_version": old_version,
                "new_version": new_version,
                "reason": reason,
                "environment": ENVIRONMENT,
                "status": "active",
                "expiration": timestamp + (90 * 24 * 60 * 60 * 1000),  # 90 days
            }
        )

    def rollback_version(
        self, model_family: str, target_timestamp: Optional[int] = None
    ):
        """Rollback to a previous version"""
        try:
            # Get version history
            if target_timestamp:
                # Rollback to specific timestamp
                response = version_table.get_item(
                    Key={"model_family": model_family, "timestamp": target_timestamp}
                )
                if "Item" in response:
                    old_version = response["Item"]["old_version"]
                    self.record_version_change(
                        model_family,
                        "current",
                        old_version,
                        f"Rollback to timestamp {target_timestamp}",
                    )
                    return old_version
            else:
                # Rollback to last stable version
                return self.get_latest_version(model_family, "stable")

        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            raise


def handler(event, context):
    """Lambda handler for version management"""
    try:
        # Parse request
        body = json.loads(event.get("body", "{}"))
        action = body.get("action", "select")

        # Initialize version manager
        manager = VersionManager()

        if action == "select":
            # Select version
            result = manager.select_version(
                model_family=body.get("model_family", "claude"),
                channel=body.get("channel", "stable"),
                user_id=body.get("user_id"),
            )
        elif action == "rollback":
            # Rollback version
            result = manager.rollback_version(
                model_family=body.get("model_family", "claude"),
                target_timestamp=body.get("target_timestamp"),
            )

        elif action == "record_change":
            # Record version change
            manager.record_version_change(
                model_family=body.get("model_family"),
                old_version=body.get("old_version"),
                new_version=body.get("new_version"),
                reason=body.get("reason", "Manual change"),
            )
            result = {"status": "recorded"}

        else:
            raise ValueError(f"Unknown action: {action}")

        # Log metrics
        log_version_metrics(action, body.get("model_family"), result)

        return {
            "statusCode": 200,
            "body": json.dumps(result, default=str),
            "headers": {"Content-Type": "application/json"},
        }

    except Exception as e:
        logger.error(f"Version management error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "Version management failed", "message": str(e)}
            ),
            "headers": {"Content-Type": "application/json"},
        }


def log_version_metrics(action: str, model_family: str, result: Any):
    """Log version management metrics to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace="HavenHealthPassport/Bedrock",
            MetricData=[
                {
                    "MetricName": "VersionAction",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Action", "Value": action},
                        {"Name": "ModelFamily", "Value": model_family or "unknown"},
                        {"Name": "Environment", "Value": ENVIRONMENT},
                    ],
                }
            ],
        )
    except Exception as e:
        logger.warning(f"Failed to log metrics: {str(e)}")
