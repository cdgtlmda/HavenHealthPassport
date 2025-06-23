"""Rate limit bypass rules configuration.

This module defines bypass rules for rate limiting, allowing trusted sources
and internal services to bypass rate limits.
"""

import ipaddress
from typing import Any, List, Optional, Set

from fastapi import Request
from pydantic import BaseModel, Field, validator

from src.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitBypassRule(BaseModel):
    """Model for a rate limit bypass rule."""

    name: str = Field(..., description="Name of the bypass rule")
    description: str = Field(..., description="Description of why this rule exists")
    enabled: bool = Field(default=True, description="Whether the rule is active")

    # Bypass conditions (at least one must be specified)
    ip_addresses: Optional[List[str]] = Field(
        None, description="Whitelisted IP addresses"
    )
    ip_ranges: Optional[List[str]] = Field(
        None, description="Whitelisted IP ranges (CIDR notation)"
    )
    user_agents: Optional[List[str]] = Field(
        None, description="Whitelisted user agents"
    )
    api_key_prefixes: Optional[List[str]] = Field(
        None, description="API key prefixes to bypass"
    )
    api_key_tiers: Optional[List[str]] = Field(
        None, description="API key tiers to bypass"
    )
    paths: Optional[List[str]] = Field(None, description="URL paths to bypass")
    headers: Optional[dict] = Field(None, description="Required headers for bypass")

    @validator("ip_ranges")
    @classmethod
    def validate_ip_ranges(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate IP ranges are in CIDR notation."""
        if v:
            for ip_range in v:
                try:
                    ipaddress.ip_network(ip_range)
                except ValueError as e:
                    raise ValueError(f"Invalid IP range {ip_range}: {e}") from e
        return v


class RateLimitBypassConfig:
    """Configuration for rate limit bypass rules."""

    def __init__(self) -> None:
        """Initialize bypass configuration."""
        self.rules: List[RateLimitBypassRule] = []
        self._ip_whitelist: Set[str] = set()
        self._ip_networks: List[Any] = []
        self._path_whitelist: Set[str] = set()
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default bypass rules."""
        # Health check endpoints
        self.add_rule(
            RateLimitBypassRule(
                name="health_checks",
                description="Bypass rate limits for health check endpoints",
                ip_addresses=None,
                ip_ranges=None,
                user_agents=None,
                api_key_prefixes=None,
                api_key_tiers=None,
                paths=[
                    "/health",
                    "/ready",
                    "/metrics",
                    "/api/v1/health",
                    "/api/v2/health",
                ],
                headers=None,
            )
        )

        # Internal services (customize based on your infrastructure)
        self.add_rule(
            RateLimitBypassRule(
                name="internal_services",
                description="Bypass rate limits for internal service mesh",
                ip_addresses=None,
                ip_ranges=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
                user_agents=None,
                api_key_prefixes=None,
                api_key_tiers=None,
                paths=None,
                headers=None,
                enabled=False,  # Disabled by default for security
            )
        )

        # Monitoring services
        self.add_rule(
            RateLimitBypassRule(
                name="monitoring",
                description="Bypass rate limits for monitoring services",
                ip_addresses=None,
                ip_ranges=None,
                user_agents=["Prometheus/*", "Grafana/*", "DataDog/*", "NewRelic/*"],
                api_key_prefixes=None,
                api_key_tiers=None,
                paths=["/metrics", "/api/v1/metrics", "/api/v2/metrics"],
                headers=None,
            )
        )

        # Enterprise API keys
        self.add_rule(
            RateLimitBypassRule(
                name="enterprise_keys",
                description="Bypass rate limits for enterprise tier API keys",
                ip_addresses=None,
                ip_ranges=None,
                user_agents=None,
                api_key_prefixes=None,
                api_key_tiers=["enterprise"],
                paths=None,
                headers=None,
                enabled=False,  # Can be enabled if needed
            )
        )

        # Load balancer health checks
        self.add_rule(
            RateLimitBypassRule(
                name="load_balancer",
                description="Bypass rate limits for AWS ALB health checks",
                ip_addresses=None,
                ip_ranges=None,
                user_agents=["ELB-HealthChecker/*"],
                api_key_prefixes=None,
                api_key_tiers=None,
                paths=["/health", "/ready"],
                headers=None,
            )
        )

    def add_rule(self, rule: RateLimitBypassRule) -> None:
        """Add a bypass rule."""
        self.rules.append(rule)
        self._update_caches()

    def remove_rule(self, rule_name: str) -> None:
        """Remove a bypass rule by name."""
        self.rules = [r for r in self.rules if r.name != rule_name]
        self._update_caches()

    def _update_caches(self) -> None:
        """Update internal caches for faster lookup."""
        self._ip_whitelist = set()
        self._ip_networks = []
        self._path_whitelist = set()

        for rule in self.rules:
            if rule.enabled:
                if rule.ip_addresses:
                    self._ip_whitelist.update(rule.ip_addresses)
                if rule.ip_ranges:
                    for ip_range in rule.ip_ranges:
                        self._ip_networks.append(ipaddress.ip_network(ip_range))
                if rule.paths:
                    self._path_whitelist.update(rule.paths)

    def should_bypass(self, request: Request) -> bool:
        """Check if a request should bypass rate limiting."""
        for rule in self.rules:
            if not rule.enabled:
                continue

            if self._check_rule(rule, request):
                logger.info(f"Rate limit bypassed by rule: {rule.name}")
                return True

        return False

    def _check_rule(self, rule: RateLimitBypassRule, request: Request) -> bool:
        """Check if a request matches a bypass rule."""
        # Check IP address
        if rule.ip_addresses and self._check_ip_address(request, rule.ip_addresses):
            return True

        # Check IP ranges
        if rule.ip_ranges and self._check_ip_range(request):
            return True

        # Check user agent
        if rule.user_agents and self._check_user_agent(request, rule.user_agents):
            return True

        # Check API key prefix
        if rule.api_key_prefixes and self._check_api_key_prefix(
            request, rule.api_key_prefixes
        ):
            return True

        # Check API key tier
        if rule.api_key_tiers and self._check_api_key_tier(request, rule.api_key_tiers):
            return True

        # Check path
        if rule.paths and self._check_path(request, rule.paths):
            return True

        # Check headers
        if rule.headers and self._check_headers(request, rule.headers):
            return True

        return False

    def _check_ip_address(self, request: Request, ip_addresses: List[str]) -> bool:
        """Check if request IP is in whitelist."""
        client_ip = self._get_client_ip(request)
        return client_ip in ip_addresses

    def _check_ip_range(self, request: Request) -> bool:
        """Check if request IP is in any whitelisted range."""
        client_ip = self._get_client_ip(request)

        try:
            ip_obj = ipaddress.ip_address(client_ip)
            for network in self._ip_networks:
                if ip_obj in network:
                    return True
        except ValueError:
            pass

        return False

    def _check_user_agent(self, request: Request, user_agents: List[str]) -> bool:
        """Check if user agent matches any pattern."""
        request_ua = request.headers.get("User-Agent", "")

        for pattern in user_agents:
            if pattern.endswith("*"):
                if request_ua.startswith(pattern[:-1]):
                    return True
            elif pattern == request_ua:
                return True

        return False

    def _check_api_key_prefix(self, request: Request, prefixes: List[str]) -> bool:
        """Check if API key has a whitelisted prefix."""
        # Check various places for API key
        api_key = None

        # Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and auth_header[7:].startswith("hhp_"):
            api_key = auth_header[7:]

        # X-API-Key header
        if not api_key:
            api_key = request.headers.get("X-API-Key")

        # Query parameter
        if not api_key:
            api_key = request.query_params.get("api_key")

        if api_key:
            for prefix in prefixes:
                if api_key.startswith(prefix):
                    return True

        return False

    def _check_api_key_tier(self, request: Request, tiers: List[str]) -> bool:
        """Check if API key tier is whitelisted."""
        # This requires the API key to be validated first
        if hasattr(request.state, "api_key") and request.state.api_key:
            return request.state.api_key.tier in tiers
        return False

    def _check_path(self, request: Request, paths: List[str]) -> bool:
        """Check if request path is whitelisted."""
        return request.url.path in paths

    def _check_headers(self, request: Request, required_headers: dict) -> bool:
        """Check if request has required headers."""
        for header, value in required_headers.items():
            if request.headers.get(header) != value:
                return False
        return True

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        # Check X-Forwarded-For header
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


# Global bypass configuration instance
bypass_config = RateLimitBypassConfig()
