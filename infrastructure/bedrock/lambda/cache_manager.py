"""
Bedrock Response Cache Manager
Handles multi-tier caching for model responses
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import boto3
import redis

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client("s3")
secrets_manager = boto3.client("secretsmanager")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
CACHE_CONFIGS = json.loads(os.environ["CACHE_CONFIGS_JSON"])
REDIS_ENDPOINT = os.environ["REDIS_ENDPOINT"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
CACHE_BUCKET = os.environ["CACHE_BUCKET"]
AUTH_TOKEN_SECRET_ID = os.environ["AUTH_TOKEN_SECRET_ID"]
ENVIRONMENT = os.environ["ENVIRONMENT"]


@dataclass
class CacheKey:
    """Represents a cache key with components"""

    use_case: str
    key_components: Dict[str, str]

    def to_string(self) -> str:
        """Convert to string key"""
        components = [f"{k}:{v}" for k, v in sorted(self.key_components.items())]
        key_data = f"{self.use_case}:{':'.join(components)}"
        return hashlib.sha256(key_data.encode()).hexdigest()


class CacheManager:
    """Manages multi-tier response caching"""

    def __init__(self):
        self.redis_client = self._init_redis()
        self.cache_configs = CACHE_CONFIGS

    def _init_redis(self) -> redis.Redis:
        """Initialize Redis client with auth"""
        try:
            # Get auth token from Secrets Manager
            response = secrets_manager.get_secret_value(SecretId=AUTH_TOKEN_SECRET_ID)
            auth_token = response["SecretString"]

            # Create Redis client
            return redis.Redis(
                host=REDIS_ENDPOINT,
                port=REDIS_PORT,
                password=auth_token,
                ssl=True,
                decode_responses=True,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
            return None

    def get_cached_response(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if available"""
        use_case = request.get("use_case", "general")
        config = self.cache_configs.get(use_case, {})

        if not config.get("enabled", False):
            return None

        # Generate cache key
        cache_key = self._generate_cache_key(request, config)

        # Try hot cache (Redis)
        cached = self._get_from_hot_cache(cache_key)
        if cached:
            self._log_cache_hit("hot", use_case)
            return cached

        # Try warm cache (S3)
        cached = self._get_from_warm_cache(cache_key)
        if cached:
            self._log_cache_hit("warm", use_case)
            # Promote to hot cache
            self._set_hot_cache(cache_key, cached, config["ttl_seconds"])
            return cached

        self._log_cache_miss(use_case)
        return None

    def set_cached_response(
        self, request: Dict[str, Any], response: Dict[str, Any]
    ) -> bool:
        """Cache a response"""
        use_case = request.get("use_case", "general")
        config = self.cache_configs.get(use_case, {})

        if not config.get("enabled", False):
            return False

        try:
            cache_key = self._generate_cache_key(request, config)
            ttl = config["ttl_seconds"]

            # Set in hot cache
            self._set_hot_cache(cache_key, response, ttl)

            # Set in warm cache for larger TTL items
            if ttl > 3600:  # > 1 hour
                self._set_warm_cache(cache_key, response, ttl)

            return True

        except Exception as e:
            logger.error(f"Failed to cache response: {str(e)}")
            return False

    def check_similarity(
        self, request: Dict[str, Any], threshold: float
    ) -> Optional[Dict[str, Any]]:
        """Check for similar cached requests"""
        # This would implement semantic similarity checking
        # For embeddings or when exact match isn't found
        # Simplified for this implementation
        return None

    def _generate_cache_key(
        self, request: Dict[str, Any], config: Dict[str, Any]
    ) -> str:
        """Generate cache key from request"""
        key_components = {}

        for key_field in config["cache_keys"]:
            if key_field == "messages_hash":
                messages = request.get("messages", [])
                key_components[key_field] = hashlib.sha256(
                    json.dumps(messages, sort_keys=True).encode()
                ).hexdigest()[:8]
            elif key_field == "text_hash":
                text = request.get("text", "")
                key_components[key_field] = hashlib.sha256(text.encode()).hexdigest()[
                    :8
                ]
            else:
                key_components[key_field] = str(request.get(key_field, ""))
        cache_key = CacheKey(
            use_case=request.get("use_case", "general"), key_components=key_components
        )

        return cache_key.to_string()

    def _get_from_hot_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from Redis cache"""
        if not self.redis_client:
            return None

        try:
            cached = self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis get failed: {str(e)}")

        return None

    def _set_hot_cache(self, key: str, value: Dict[str, Any], ttl: int):
        """Set in Redis cache"""
        if not self.redis_client:
            return

        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis set failed: {str(e)}")

    def _get_from_warm_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from S3 cache"""
        try:
            response = s3.get_object(Bucket=CACHE_BUCKET, Key=f"cache/{key}.json")
            return json.loads(response["Body"].read())
        except s3.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.warning(f"S3 get failed: {str(e)}")
            return None

    def _set_warm_cache(self, key: str, value: Dict[str, Any], ttl: int):
        """Set in S3 cache"""
        try:
            s3.put_object(
                Bucket=CACHE_BUCKET,
                Key=f"cache/{key}.json",
                Body=json.dumps(value),
                Metadata={"ttl": str(ttl), "created_at": str(int(time.time()))},
            )
        except Exception as e:
            logger.warning(f"S3 set failed: {str(e)}")

    def _log_cache_hit(self, tier: str, use_case: str):
        """Log cache hit metrics"""
        try:
            cloudwatch.put_metric_data(
                Namespace="HavenHealthPassport/Bedrock",
                MetricData=[
                    {
                        "MetricName": "CacheHit",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "Tier", "Value": tier},
                            {"Name": "UseCase", "Value": use_case},
                            {"Name": "Environment", "Value": ENVIRONMENT},
                        ],
                    }
                ],
            )
        except Exception as e:
            logger.warning(f"Failed to log metrics: {str(e)}")

    def _log_cache_miss(self, use_case: str):
        """Log cache miss metrics"""
        try:
            cloudwatch.put_metric_data(
                Namespace="HavenHealthPassport/Bedrock",
                MetricData=[
                    {
                        "MetricName": "CacheMiss",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "UseCase", "Value": use_case},
                            {"Name": "Environment", "Value": ENVIRONMENT},
                        ],
                    }
                ],
            )
        except Exception as e:
            logger.warning(f"Failed to log metrics: {str(e)}")


def handler(event, context):
    """Lambda handler for cache operations"""
    try:
        action = event.get("action", "get")
        request = event.get("request", {})

        # Initialize cache manager
        manager = CacheManager()

        if action == "get":
            # Get cached response
            cached = manager.get_cached_response(request)

            return {
                "statusCode": 200,
                "body": json.dumps({"cached": cached is not None, "response": cached}),
                "headers": {"Content-Type": "application/json"},
            }

        elif action == "set":
            # Set cached response
            response = event.get("response", {})
            success = manager.set_cached_response(request, response)

            return {
                "statusCode": 200,
                "body": json.dumps({"success": success}),
                "headers": {"Content-Type": "application/json"},
            }

        else:
            raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        logger.error(f"Cache operation error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Cache operation failed", "message": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }
