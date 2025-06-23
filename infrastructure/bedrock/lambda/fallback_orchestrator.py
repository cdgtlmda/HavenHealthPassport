"""
Bedrock Fallback Orchestrator
Manages model failover, circuit breaking, and response caching
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
FALLBACK_CHAINS = json.loads(os.environ["FALLBACK_CHAINS_JSON"])
FALLBACK_TRIGGERS = json.loads(os.environ["FALLBACK_TRIGGERS_JSON"])
CIRCUIT_BREAKER = json.loads(os.environ["CIRCUIT_BREAKER_JSON"])
FALLBACK_STATE_TABLE = os.environ["FALLBACK_STATE_TABLE"]
CACHE_BUCKET = os.environ.get("CACHE_BUCKET", "")
ENVIRONMENT = os.environ["ENVIRONMENT"]

# DynamoDB table
state_table = dynamodb.Table(FALLBACK_STATE_TABLE)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class FallbackOrchestrator:
    """Orchestrates model fallback with circuit breaking"""

    def __init__(self):
        self.circuit_states = {}
        self.failure_counts = {}
        self.success_counts = {}
        self.last_state_change = {}

    def invoke_with_fallback(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke model with automatic fallback on failure"""
        use_case = request.get("use_case", "general")
        fallback_chain = FALLBACK_CHAINS.get(use_case, {})

        if not fallback_chain:
            raise ValueError(f"No fallback chain defined for use case: {use_case}")

        # Try cached response first if available
        cache_key = self.generate_cache_key(request)
        cached_response = self.get_cached_response(cache_key)
        if cached_response:
            logger.info(f"Returning cached response for {cache_key}")
            return cached_response

        # Iterate through fallback chain
        last_error = None
        for level, config in fallback_chain.items():
            model_key = config["model_key"]

            # Skip if circuit is open
            if self.get_circuit_state(model_key) == CircuitState.OPEN:
                logger.warning(f"Circuit open for {model_key}, skipping")
                continue

            # Special handling for cached_response fallback
            if model_key == "cached_response":
                return self.get_generic_cached_response(use_case)

            try:
                # Attempt model invocation
                response = self.invoke_model(model_key, request, config)

                # Record success
                self.record_circuit_success(model_key)

                # Cache successful response
                if level == "primary":  # Only cache primary responses
                    self.cache_response(cache_key, response)

                # Log metrics
                self.log_invocation_metrics(model_key, level, True)

                return response

            except Exception as e:
                last_error = e
                logger.error(f"Model {model_key} failed: {str(e)}")
                self.record_circuit_failure(model_key)
                self.log_invocation_metrics(model_key, level, False)
                # Check if error is retryable
                if not self.is_retryable_error(e):
                    raise

        # All models failed
        raise Exception(f"All fallback models failed. Last error: {last_error}")

    def invoke_model(
        self, model_key: str, request: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke a specific model with retries"""
        max_retries = config.get("max_retries", 3)
        timeout_ms = config.get("timeout_ms", 300000)

        for attempt in range(max_retries):
            try:
                start_time = time.time()

                # Get model configuration
                model_config = self.get_model_config(model_key)

                # Invoke model
                response = bedrock.invoke_model(
                    modelId=model_config["model_id"],
                    body=json.dumps(request["body"]),
                    contentType="application/json",
                    accept="application/json",
                )

                # Check latency
                latency_ms = (time.time() - start_time) * 1000
                if latency_ms > FALLBACK_TRIGGERS["latency_threshold_ms"]:
                    logger.warning(f"High latency detected: {latency_ms}ms")

                return json.loads(response["body"].read())

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    raise

    def get_circuit_state(self, model_key: str) -> CircuitState:
        """Get current circuit state for a model"""
        if model_key not in self.circuit_states:
            self.circuit_states[model_key] = CircuitState.CLOSED

        state = self.circuit_states[model_key]

        # Check if half-open circuit should transition
        if state == CircuitState.HALF_OPEN:
            if (
                self.success_counts.get(model_key, 0)
                >= CIRCUIT_BREAKER["success_threshold"]
            ):
                self.transition_circuit(model_key, CircuitState.CLOSED)

        # Check if open circuit should transition to half-open
        elif state == CircuitState.OPEN:
            last_change = self.last_state_change.get(model_key, 0)
            if time.time() - last_change > CIRCUIT_BREAKER["timeout_seconds"]:
                self.transition_circuit(model_key, CircuitState.HALF_OPEN)

        return self.circuit_states[model_key]

    def record_circuit_failure(self, model_key: str):
        """Record a failure for circuit breaker"""
        self.failure_counts[model_key] = self.failure_counts.get(model_key, 0) + 1

        # Check if circuit should open
        if self.failure_counts[model_key] >= CIRCUIT_BREAKER["failure_threshold"]:
            if self.circuit_states.get(model_key) != CircuitState.OPEN:
                self.transition_circuit(model_key, CircuitState.OPEN)

    def record_circuit_success(self, model_key: str):
        """Record a success for circuit breaker"""
        current_state = self.circuit_states.get(model_key, CircuitState.CLOSED)

        if current_state == CircuitState.HALF_OPEN:
            self.success_counts[model_key] = self.success_counts.get(model_key, 0) + 1
        elif current_state == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            self.failure_counts[model_key] = 0

    def transition_circuit(self, model_key: str, new_state: CircuitState):
        """Transition circuit to new state"""
        old_state = self.circuit_states.get(model_key, CircuitState.CLOSED)
        self.circuit_states[model_key] = new_state
        self.last_state_change[model_key] = time.time()

        # Reset counters based on transition
        if new_state == CircuitState.CLOSED:
            self.failure_counts[model_key] = 0
            self.success_counts[model_key] = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_counts[model_key] = 0

        logger.info(f"Circuit {model_key}: {old_state.value} -> {new_state.value}")

        # Record state change
        self.record_state_change(model_key, old_state.value, new_state.value)

    def generate_cache_key(self, request: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        # Create deterministic key from request
        key_data = json.dumps(request, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response from S3"""
        if not CACHE_BUCKET:
            return None

        try:
            response = s3.get_object(
                Bucket=CACHE_BUCKET, Key=f"bedrock-cache/{cache_key}.json"
            )
            return json.loads(response["Body"].read())
        except:
            return None

    def cache_response(self, cache_key: str, response: Dict[str, Any]):
        """Cache response to S3"""
        if not CACHE_BUCKET:
            return

        try:
            s3.put_object(
                Bucket=CACHE_BUCKET,
                Key=f"bedrock-cache/{cache_key}.json",
                Body=json.dumps(response),
                Metadata={"timestamp": str(int(time.time()))},
            )
        except Exception as e:
            logger.warning(f"Failed to cache response: {str(e)}")

    def get_generic_cached_response(self, use_case: str) -> Dict[str, Any]:
        """Return a generic cached response for ultimate fallback"""
        return {
            "response": "Service temporarily unavailable. Please try again later.",
            "fallback": True,
            "use_case": use_case,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable"""
        error_str = str(error)
        return any(trigger in error_str for trigger in FALLBACK_TRIGGERS["error_codes"])

    def get_model_config(self, model_key: str) -> Dict[str, Any]:
        """Get model configuration (would integrate with endpoint selector)"""
        # Simplified for example - would call endpoint selector Lambda
        return {"model_id": f"anthropic.{model_key}"}

    def record_state_change(self, model_key: str, old_state: str, new_state: str):
        """Record circuit state change in DynamoDB"""
        timestamp = int(time.time() * 1000)
        state_table.put_item(
            Item={
                "model_key": model_key,
                "timestamp": timestamp,
                "old_state": old_state,
                "new_state": new_state,
                "environment": ENVIRONMENT,
                "expiration": timestamp + (7 * 24 * 60 * 60 * 1000),  # 7 days
            }
        )

    def log_invocation_metrics(self, model_key: str, level: str, success: bool):
        """Log metrics to CloudWatch"""
        try:
            cloudwatch.put_metric_data(
                Namespace="HavenHealthPassport/Bedrock",
                MetricData=[
                    {
                        "MetricName": "FallbackInvocation",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "ModelKey", "Value": model_key},
                            {"Name": "Level", "Value": level},
                            {"Name": "Success", "Value": str(success)},
                            {"Name": "Environment", "Value": ENVIRONMENT},
                        ],
                    }
                ],
            )
        except Exception as e:
            logger.warning(f"Failed to log metrics: {str(e)}")


def handler(event, context):
    """Lambda handler for fallback orchestration"""
    try:
        # Parse request
        body = json.loads(event.get("body", "{}"))

        # Initialize orchestrator
        orchestrator = FallbackOrchestrator()

        # Invoke with fallback
        response = orchestrator.invoke_with_fallback(body)

        return {
            "statusCode": 200,
            "body": json.dumps(response),
            "headers": {"Content-Type": "application/json"},
        }

    except Exception as e:
        logger.error(f"Fallback orchestration error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "All models failed", "message": str(e), "fallback": True}
            ),
            "headers": {"Content-Type": "application/json"},
        }
