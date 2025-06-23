"""
Amazon Bedrock Endpoint Selector Lambda Function
Handles dynamic model endpoint selection based on use case, availability, and cost optimization
"""

import json
import logging
import os
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
bedrock = boto3.client("bedrock-runtime")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
CONFIG_TABLE_NAME = os.environ["CONFIG_TABLE_NAME"]
REGION = os.environ["REGION"]
ENVIRONMENT = os.environ["ENVIRONMENT"]

# DynamoDB table
config_table = dynamodb.Table(CONFIG_TABLE_NAME)


class EndpointSelector:
    """Handles intelligent endpoint selection for Bedrock models"""

    def __init__(self):
        self.rate_limit_cache = {}
        self.model_health_cache = {}
        self.config_cache = None
        self.config_cache_timestamp = None
        self.cache_ttl = 300  # 5 minutes

    def get_active_config(self) -> Dict[str, Any]:
        """Retrieve active endpoint configuration from DynamoDB with caching"""
        current_time = time.time()

        # Check cache validity
        if (
            self.config_cache
            and self.config_cache_timestamp
            and current_time - self.config_cache_timestamp < self.cache_ttl
        ):
            return self.config_cache

        try:
            # Query for active configuration
            response = config_table.query(
                IndexName="active-configs-index",
                KeyConditionExpression="active = :active",
                ExpressionAttributeValues={":active": "true"},
                ScanIndexForward=False,
                Limit=1,
            )

            if response["Items"]:
                self.config_cache = response["Items"][0]
                self.config_cache_timestamp = current_time
                return self.config_cache
            else:
                raise Exception("No active configuration found")

        except Exception as e:
            logger.error(f"Error retrieving configuration: {str(e)}")
            # Return default configuration
            return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration when database is unavailable"""
        return {
            "model_endpoints": {
                "claude_3_sonnet": {
                    "model_id": "anthropic.claude-3-sonnet-20240229",
                    "max_tokens": 4096,
                    "temperature": 0.5,
                }
            },
            "rate_limits": {
                "claude_3_sonnet": {
                    "requests_per_minute": 50,
                    "tokens_per_minute": 200000,
                }
            },
        }

    def check_rate_limit(self, model_id: str) -> bool:
        """Check if model is within rate limits"""
        current_minute = datetime.now().strftime("%Y-%m-%d-%H-%M")
        cache_key = f"{model_id}:{current_minute}"

        config = self.get_active_config()
        rate_limits = config.get("rate_limits", {}).get(model_id, {})

        if not rate_limits:
            return True  # No rate limit configured

        # Get current usage from cache
        current_usage = self.rate_limit_cache.get(
            cache_key, {"requests": 0, "tokens": 0}
        )

        # Check limits
        max_requests = rate_limits.get("requests_per_minute", float("inf"))
        max_tokens = rate_limits.get("tokens_per_minute", float("inf"))

        if (
            current_usage["requests"] >= max_requests
            or current_usage["tokens"] >= max_tokens
        ):
            logger.warning(f"Rate limit exceeded for model {model_id}")
            return False

        return True

    def update_rate_limit_usage(self, model_id: str, tokens_used: int):
        """Update rate limit usage tracking"""
        current_minute = datetime.now().strftime("%Y-%m-%d-%H-%M")
        cache_key = f"{model_id}:{current_minute}"

        if cache_key not in self.rate_limit_cache:
            self.rate_limit_cache[cache_key] = {"requests": 0, "tokens": 0}

        self.rate_limit_cache[cache_key]["requests"] += 1
        self.rate_limit_cache[cache_key]["tokens"] += tokens_used

        # Clean old cache entries
        self.clean_rate_limit_cache()

    def clean_rate_limit_cache(self):
        """Remove old rate limit cache entries"""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(minutes=2)

        keys_to_remove = []
        for key in self.rate_limit_cache:
            time_str = key.split(":")[1]
            key_time = datetime.strptime(time_str, "%Y-%m-%d-%H-%M")
            if key_time < cutoff_time:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.rate_limit_cache[key]

    def check_model_health(self, model_id: str) -> bool:
        """Check if model endpoint is healthy"""
        cache_key = f"{model_id}:health"
        current_time = time.time()

        # Check cache
        if cache_key in self.model_health_cache:
            cached_health, timestamp = self.model_health_cache[cache_key]
            if current_time - timestamp < 60:  # 1 minute cache
                return cached_health

        try:
            # Simple health check - try to invoke with minimal input
            response = bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(
                    {"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10}
                ),
            )

            # Cache successful result
            self.model_health_cache[cache_key] = (True, current_time)
            return True

        except Exception as e:
            logger.error(f"Model health check failed for {model_id}: {str(e)}")
            self.model_health_cache[cache_key] = (False, current_time)
            return False

    def select_model(
        self, use_case: str, request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Select optimal model based on use case and current conditions"""
        config = self.get_active_config()
        selection_rules = config.get("model_selection_rules", {})
        model_endpoints = config.get("model_endpoints", {})

        # Get model selection rule for use case
        rule = selection_rules.get(use_case, {})
        if not rule:
            raise ValueError(f"No selection rule for use case: {use_case}")

        # Try primary model first
        primary_model = rule.get("primary_model")
        if primary_model and self.is_model_available(primary_model):
            return self.prepare_model_config(primary_model, model_endpoints)

        # Try fallback model
        fallback_model = rule.get("fallback_model")
        if fallback_model and self.is_model_available(fallback_model):
            logger.info(f"Using fallback model {fallback_model} for {use_case}")
            return self.prepare_model_config(fallback_model, model_endpoints)

        # No available models
        raise Exception(f"No available models for use case: {use_case}")

    def is_model_available(self, model_key: str) -> bool:
        """Check if model is available (rate limits and health)"""
        return self.check_rate_limit(model_key) and self.check_model_health(model_key)

    def prepare_model_config(self, model_key: str, endpoints: Dict) -> Dict[str, Any]:
        """Prepare model configuration for response"""
        model_config = endpoints.get(model_key, {})

        return {
            "model_key": model_key,
            "model_id": model_config.get("model_id"),
            "model_arn": model_config.get("model_arn"),
            "inference_params": {
                "max_tokens": model_config.get("max_tokens", 4096),
                "temperature": model_config.get("temperature", 0.7),
                "top_p": model_config.get("top_p", 1.0),
                "stop_sequences": model_config.get("stop_sequences", []),
            },
            "timeout_seconds": model_config.get("timeout_seconds", 300),
            "retry_attempts": model_config.get("retry_attempts", 3),
        }


def handler(event, context):
    """Lambda handler for endpoint selection"""
    try:
        # Parse request
        body = json.loads(event.get("body", "{}"))
        use_case = body.get("use_case", "general_chat")
        request_context = body.get("context", {})

        # Initialize selector
        selector = EndpointSelector()

        # Select model
        model_config = selector.select_model(use_case, request_context)

        # Log metrics
        log_selection_metrics(use_case, model_config["model_key"])

        # Return response
        return {
            "statusCode": 200,
            "body": json.dumps(model_config),
            "headers": {
                "Content-Type": "application/json",
                "X-Model-Selected": model_config["model_key"],
            },
        }

    except Exception as e:
        logger.error(f"Endpoint selection error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Model selection failed", "message": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }


def log_selection_metrics(use_case: str, model_key: str):
    """Log model selection metrics to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace="HavenHealthPassport/Bedrock",
            MetricData=[
                {
                    "MetricName": "ModelSelection",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "UseCase", "Value": use_case},
                        {"Name": "Model", "Value": model_key},
                        {"Name": "Environment", "Value": ENVIRONMENT},
                    ],
                }
            ],
        )
    except Exception as e:
        logger.warning(f"Failed to log metrics: {str(e)}")
