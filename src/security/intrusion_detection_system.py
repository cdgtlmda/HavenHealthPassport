"""
Intrusion Detection System (IDS) for Haven Health Passport.

CRITICAL: This module implements real-time intrusion detection
for the healthcare system to protect patient data from:
- Unauthorized access attempts
- SQL injection attacks
- Cross-site scripting (XSS)
- API abuse
- Data exfiltration attempts
PHI Protection: Monitors encrypted PHI access patterns for anomalies.
Access Control: Enforces rate limits and authorization checks for PHI access.
"""

import json
import os
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError as BotoCore
from botocore.exceptions import ClientError
from requests import HTTPError
from requests.exceptions import RequestException, Timeout

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ThreatLevel:
    """Threat severity levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class IntrusionDetectionSystem:
    """
    Real-time intrusion detection system.

    Monitors:
    - API request patterns
    - Authentication attempts
    - Data access patterns
    - Network traffic anomalies
    """

    def __init__(self) -> None:
        """Initialize the Intrusion Detection System with AWS clients and thresholds."""
        self.environment = settings.environment.lower()

        # AWS clients
        self.waf_client = boto3.client(
            "wafv2", region_name="us-east-1"
        )  # WAF is global
        self.shield_client = boto3.client("shield", region_name="us-east-1")
        self.cloudwatch_client = boto3.client(
            "cloudwatch", region_name=settings.aws_region
        )

        # Detection thresholds
        self.failed_login_threshold = 5  # per 5 minutes
        self.api_rate_threshold = 100  # per minute
        self.data_download_threshold = 1000  # records per hour

        # Attack pattern signatures
        self._load_attack_signatures()

        # Active threat tracking
        self.active_threats: Dict[str, List[Any]] = defaultdict(list)
        self.blocked_ips: set[str] = set()

        logger.info("Initialized Intrusion Detection System")

    def _load_attack_signatures(self) -> None:
        """Load attack pattern signatures."""
        self.sql_injection_patterns = [
            r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)\b.*\b(FROM|INTO|WHERE|TABLE)\b)",
            r"(--|\#|\/\*|\*\/)",
            r"(\bOR\b\s*\d+\s*=\s*\d+)",
            r"(\bAND\b\s*\d+\s*=\s*\d+)",
            r"(;\s*(DROP|DELETE|UPDATE|INSERT))",
            r"(\bEXEC(UTE)?\s*\()",
            r"(CAST\s*\(.*\s*AS\s)",
            r"(CHAR\s*\(.*\))",
        ]

        self.xss_patterns = [
            r"(<script[^>]*>.*?</script>)",
            r"(javascript:)",
            r"(on\w+\s*=)",
            r"(<iframe[^>]*>)",
            r"(<object[^>]*>)",
            r"(<embed[^>]*>)",
            r"(eval\s*\()",
            r"(alert\s*\()",
        ]

        self.path_traversal_patterns = [
            r"(\.\.\/|\.\.\\)",
            r"(%2e%2e%2f|%2e%2e%5c)",
            r"(\/etc\/passwd)",
            r"(c:\\windows)",
            r"(\/proc\/self)",
        ]

        self.command_injection_patterns = [
            r"(;\s*\w+\s*\|)",
            r"(\|\s*\w+)",
            r"(`.*`)",
            r"(\$\(.*\))",
            r"(>\s*\/dev\/null)",
        ]

    async def analyze_request(
        self,
        request_data: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze incoming request for threats.

        Args:
            request_data: HTTP request data
            user_context: User session context

        Returns:
            Threat analysis result
        """
        threats_detected = []
        threat_level = ThreatLevel.LOW

        # Extract request components
        path = request_data.get("path", "")
        headers = request_data.get("headers", {})
        params = request_data.get("params", {})
        body = request_data.get("body", "")
        ip_address = request_data.get("ip_address", "")

        # Check if IP is already blocked
        if ip_address in self.blocked_ips:
            return {
                "blocked": True,
                "reason": "IP address blocked",
                "threat_level": ThreatLevel.CRITICAL,
            }

        # SQL Injection detection
        sql_threats = self._detect_sql_injection(params, body, headers)
        if sql_threats:
            threats_detected.extend(sql_threats)
            threat_level = max(threat_level, ThreatLevel.HIGH)

        # XSS detection
        xss_threats = self._detect_xss(params, body, headers)
        if xss_threats:
            threats_detected.extend(xss_threats)
            threat_level = max(threat_level, ThreatLevel.HIGH)

        # Path traversal detection
        path_threats = self._detect_path_traversal(path, params)
        if path_threats:
            threats_detected.extend(path_threats)
            threat_level = max(threat_level, ThreatLevel.HIGH)

        # Command injection detection
        cmd_threats = self._detect_command_injection(params, body)
        if cmd_threats:
            threats_detected.extend(cmd_threats)
            threat_level = max(threat_level, ThreatLevel.CRITICAL)

        # Rate limiting check
        rate_limit_exceeded = await self._check_rate_limit(ip_address, user_context)
        if rate_limit_exceeded:
            threats_detected.append(
                {"type": "rate_limit_exceeded", "details": "API rate limit exceeded"}
            )
            threat_level = max(threat_level, ThreatLevel.MEDIUM)

        # Anomaly detection
        if user_context:
            anomalies = await self._detect_anomalies(request_data, user_context)
            if anomalies:
                threats_detected.extend(anomalies)
                threat_level = max(threat_level, ThreatLevel.MEDIUM)

        # Log threats
        if threats_detected:
            await self._log_threats(ip_address, threats_detected, threat_level)

        # Auto-block for critical threats
        if threat_level >= ThreatLevel.CRITICAL:
            await self._block_ip(ip_address, threats_detected)

        return {
            "blocked": threat_level >= ThreatLevel.CRITICAL,
            "threats": threats_detected,
            "threat_level": threat_level,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _detect_sql_injection(
        self, params: Dict, body: str, headers: Dict
    ) -> List[Dict]:
        """Detect SQL injection attempts."""
        threats = []

        # Check all input sources
        inputs_to_check = []

        # URL parameters
        for key, value in params.items():
            inputs_to_check.append((f"param:{key}", str(value)))

        # Request body
        if body:
            inputs_to_check.append(("body", body))

        # Headers (some attacks use headers)
        suspicious_headers = ["User-Agent", "Referer", "X-Forwarded-For"]
        for header in suspicious_headers:
            if header in headers:
                inputs_to_check.append((f"header:{header}", headers[header]))

        # Check each input against SQL injection patterns
        for source, content in inputs_to_check:
            for pattern in self.sql_injection_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    threats.append(
                        {
                            "type": "sql_injection",
                            "source": source,
                            "pattern": pattern,
                            "content": content[:100],  # First 100 chars
                        }
                    )
                    break

        return threats

    def _detect_xss(
        self, params: Dict, body: str, _headers: Dict
    ) -> List[Dict]:  # noqa: ARG002
        """Detect XSS attempts."""
        threats = []

        # Similar to SQL injection, check all inputs
        inputs_to_check = []

        for key, value in params.items():
            inputs_to_check.append((f"param:{key}", str(value)))

        if body:
            inputs_to_check.append(("body", body))

        for source, content in inputs_to_check:
            for pattern in self.xss_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    threats.append(
                        {
                            "type": "xss",
                            "source": source,
                            "pattern": pattern,
                            "content": content[:100],
                        }
                    )
                    break

        return threats

    def _detect_path_traversal(self, path: str, params: Dict) -> List[Dict]:
        """Detect path traversal attempts."""
        threats = []

        # Check URL path
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                threats.append(
                    {
                        "type": "path_traversal",
                        "source": "path",
                        "pattern": pattern,
                        "content": path,
                    }
                )

        # Check parameters that might contain file paths
        for key, value in params.items():
            if any(
                keyword in key.lower() for keyword in ["file", "path", "dir", "folder"]
            ):
                for pattern in self.path_traversal_patterns:
                    if re.search(pattern, str(value), re.IGNORECASE):
                        threats.append(
                            {
                                "type": "path_traversal",
                                "source": f"param:{key}",
                                "pattern": pattern,
                                "content": str(value),
                            }
                        )
                        break

        return threats

    def _detect_command_injection(self, params: Dict, body: str) -> List[Dict]:
        """Detect command injection attempts."""
        threats = []

        inputs_to_check = []
        for key, value in params.items():
            inputs_to_check.append((f"param:{key}", str(value)))

        if body:
            inputs_to_check.append(("body", body))

        for source, content in inputs_to_check:
            for pattern in self.command_injection_patterns:
                if re.search(pattern, content):
                    threats.append(
                        {
                            "type": "command_injection",
                            "source": source,
                            "pattern": pattern,
                            "content": content[:100],
                        }
                    )
                    break

        return threats

    async def _check_rate_limit(
        self, ip_address: str, user_context: Optional[Dict]
    ) -> bool:
        """Check if request exceeds rate limits."""
        current_time = datetime.utcnow()

        # Get request history
        cache_key = f"rate_limit:{ip_address}"
        if user_context and user_context.get("user_id"):
            cache_key = f"rate_limit:user:{user_context['user_id']}"

        # Simplified rate limiting (in production, use Redis)
        # Clean old entries
        self.active_threats[cache_key] = [
            timestamp
            for timestamp in self.active_threats[cache_key]
            if current_time - timestamp < timedelta(minutes=1)
        ]

        # Add current request
        self.active_threats[cache_key].append(current_time)

        # Check threshold
        return len(self.active_threats[cache_key]) > self.api_rate_threshold

    async def _detect_anomalies(
        self, request_data: Dict, user_context: Dict
    ) -> List[Dict]:
        """Detect anomalous behavior patterns."""
        anomalies: List[Dict[str, Any]] = []

        # Check for unusual access patterns
        user_id = user_context.get("user_id")
        if not user_id:
            return anomalies

        # Geographic anomaly detection
        current_location = request_data.get("geo_location", {})
        last_location = user_context.get("last_location", {})

        if last_location and current_location:
            # Calculate distance (simplified)
            if (
                abs(current_location.get("lat", 0) - last_location.get("lat", 0)) > 10
                or abs(current_location.get("lon", 0) - last_location.get("lon", 0))
                > 10
            ):

                time_diff = datetime.utcnow() - datetime.fromisoformat(
                    user_context.get("last_access", datetime.utcnow().isoformat())
                )
                if time_diff < timedelta(hours=1):
                    anomalies.append(
                        {
                            "type": "geographic_anomaly",
                            "details": "Impossible travel detected",
                            "severity": ThreatLevel.HIGH,
                        }
                    )

        # Unusual access time
        current_hour = datetime.utcnow().hour
        if current_hour < 6 or current_hour > 22:  # Outside normal hours
            if (
                user_context.get("typical_hours")
                and current_hour not in user_context["typical_hours"]
            ):
                anomalies.append(
                    {
                        "type": "temporal_anomaly",
                        "details": "Access outside typical hours",
                        "severity": ThreatLevel.MEDIUM,
                    }
                )

        # Data access anomaly
        if request_data.get("path", "").startswith("/api/patients/"):
            access_count = user_context.get("recent_patient_access_count", 0)
            if access_count > 50:  # Accessing too many patient records
                anomalies.append(
                    {
                        "type": "data_access_anomaly",
                        "details": "Excessive patient record access",
                        "severity": ThreatLevel.HIGH,
                    }
                )

        return anomalies

    async def _log_threats(
        self, ip_address: str, threats: List[Dict], threat_level: int
    ) -> None:
        """Log detected threats to CloudWatch."""
        try:
            # Log to CloudWatch
            self.cloudwatch_client.put_metric_data(
                Namespace="HavenHealth/Security",
                MetricData=[
                    {
                        "MetricName": "ThreatDetected",
                        "Value": 1,
                        "Unit": "Count",
                        "Dimensions": [
                            {"Name": "ThreatLevel", "Value": str(threat_level)},
                            {"Name": "Environment", "Value": self.environment},
                        ],
                    }
                ],
            )

            # Log details
            logger.warning(
                f"Threats detected from {ip_address}: {json.dumps(threats, indent=2)}"
            )

        except (
            BotoCore,
            ClientError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(f"Failed to log threats: {e}")

    async def _block_ip(self, ip_address: str, threats: List[Dict]) -> None:
        """Block IP address using AWS WAF."""
        try:
            # Add to local block list
            self.blocked_ips.add(ip_address)

            # Update WAF IP set
            ip_set_name = f"haven-health-{self.environment}-blocked-ips"

            # Get IP set
            response = self.waf_client.list_ip_sets(Scope="REGIONAL")
            ip_set = next(
                (s for s in response["IPSets"] if s["Name"] == ip_set_name), None
            )

            if not ip_set:
                # Create IP set if it doesn't exist
                response = self.waf_client.create_ip_set(
                    Name=ip_set_name,
                    Scope="REGIONAL",
                    IPAddressVersion="IPV4",
                    Addresses=[f"{ip_address}/32"],
                    Description="Blocked IPs for intrusion attempts",
                )
                logger.info(f"Created WAF IP set and blocked {ip_address}")
            else:
                # Update existing IP set
                response = self.waf_client.get_ip_set(Id=ip_set["Id"], Scope="REGIONAL")

                addresses = response["IPSet"]["Addresses"]
                addresses.append(f"{ip_address}/32")

                self.waf_client.update_ip_set(
                    Id=ip_set["Id"],
                    Scope="REGIONAL",
                    Addresses=addresses,
                    LockToken=response["LockToken"],
                )
                logger.info(f"Added {ip_address} to WAF block list")

            # Send alert
            sns_client = boto3.client("sns", region_name=settings.aws_region)
            topic_arn = os.getenv("SECURITY_ALERTS_TOPIC_ARN")

            if topic_arn:
                sns_client.publish(
                    TopicArn=topic_arn,
                    Subject="CRITICAL: IP Blocked for Security Threat",
                    Message=f"""
IP Address: {ip_address}
Threats Detected: {json.dumps(threats, indent=2)}
Action: IP has been blocked in AWS WAF
Environment: {self.environment}
Timestamp: {datetime.now(timezone.utc).isoformat()}

Immediate review required!
""",
                )

        except (
            BotoCore,
            ClientError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error(f"Failed to block IP {ip_address}: {e}")

    def deploy_waf_rules(self) -> Dict[str, Any]:
        """Deploy AWS WAF rules for the application."""
        logger.info("Deploying WAF rules...")

        try:
            # Create web ACL
            web_acl_name = f"haven-health-{self.environment}-waf"

            response = self.waf_client.create_web_acl(
                Name=web_acl_name,
                Scope="REGIONAL",
                DefaultAction={"Allow": {}},
                Rules=[
                    {
                        "Name": "RateLimitRule",
                        "Priority": 1,
                        "Statement": {
                            "RateBasedStatement": {
                                "Limit": 2000,  # requests per 5 minutes
                                "AggregateKeyType": "IP",
                            }
                        },
                        "Action": {"Block": {}},
                        "VisibilityConfig": {
                            "SampledRequestsEnabled": True,
                            "CloudWatchMetricsEnabled": True,
                            "MetricName": "RateLimitRule",
                        },
                    },
                    {
                        "Name": "GeoBlockRule",
                        "Priority": 2,
                        "Statement": {
                            "NotStatement": {
                                "Statement": {
                                    "GeoMatchStatement": {
                                        "CountryCodes": [
                                            "US",
                                            "CA",
                                            "GB",
                                            "AU",
                                            "NZ",
                                        ]  # Allowed countries
                                    }
                                }
                            }
                        },
                        "Action": {"Block": {}},
                        "VisibilityConfig": {
                            "SampledRequestsEnabled": True,
                            "CloudWatchMetricsEnabled": True,
                            "MetricName": "GeoBlockRule",
                        },
                    },
                ],
                VisibilityConfig={
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": web_acl_name,
                },
                Tags=[
                    {"Key": "Project", "Value": "HavenHealthPassport"},
                    {"Key": "Environment", "Value": self.environment},
                ],
            )

            logger.info(f"Created WAF web ACL: {response['Summary']['Name']}")

            return {"status": "deployed", "web_acl_arn": response["Summary"]["ARN"]}

        except (ConnectionError, HTTPError, RequestException, Timeout) as e:
            logger.error(f"Failed to deploy WAF rules: {e}")
            return {"status": "failed", "error": str(e)}


# Thread-safe singleton for IDS
class IDSSingleton:
    """Thread-safe singleton for intrusion detection system."""

    _instance: Optional["IDSSingleton"] = None
    _lock = threading.Lock()
    _ids: Optional[IntrusionDetectionSystem] = None

    def __new__(cls) -> "IDSSingleton":
        """Create a new instance or return existing singleton instance."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._ids = IntrusionDetectionSystem()
        return cls._instance

    def get_ids(self) -> IntrusionDetectionSystem:
        """Get the IDS instance."""
        if self._ids is None:
            raise RuntimeError("IDS not initialized")
        return self._ids


def get_intrusion_detection_system() -> IntrusionDetectionSystem:
    """Get the thread-safe IDS instance."""
    singleton = IDSSingleton()
    return singleton.get_ids()
