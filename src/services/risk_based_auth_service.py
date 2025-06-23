"""Risk-based authentication service.

This module implements adaptive authentication based on risk scoring,
analyzing factors like device, location, behavior, and context.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import geoip2.database
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from src.models.auth import DeviceInfo, LoginAttempt, UserAuth, UserSession
from src.services.device_tracking_service import DeviceTrackingService
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskLevel(Enum):
    """Risk level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactor(Enum):
    """Risk factors for authentication."""

    NEW_DEVICE = "new_device"
    NEW_LOCATION = "new_location"
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    SUSPICIOUS_TIME = "suspicious_time"
    FAILED_ATTEMPTS = "failed_attempts"
    VPN_DETECTED = "vpn_detected"
    TOR_DETECTED = "tor_detected"
    BEHAVIORAL_ANOMALY = "behavioral_anomaly"
    CREDENTIAL_BREACH = "credential_breach"
    BOT_DETECTED = "bot_detected"


@dataclass
class RiskScore:
    """Risk score result."""

    score: float
    level: RiskLevel
    factors: List[RiskFactor]
    details: Dict[str, Any]
    recommended_actions: List[str]


@dataclass
class AuthenticationContext:
    """Context for authentication attempt."""

    user_id: Optional[str]
    email: str
    ip_address: str
    user_agent: str
    device_fingerprint: Optional[str]
    request_headers: Dict[str, str]
    timestamp: datetime
    session_data: Optional[Dict[str, Any]]


class RiskBasedAuthService:
    """Service for risk-based authentication."""

    def __init__(self, db: Session):
        """Initialize risk-based auth service.

        Args:
            db: Database session
        """
        self.db = db
        self.geoip_reader: Optional[geoip2.database.Reader] = None

        # Risk thresholds
        self.risk_thresholds = {
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.6,
            RiskLevel.HIGH: 0.8,
            RiskLevel.CRITICAL: 0.9,
        }

        # Risk weights
        self.risk_weights = {
            RiskFactor.NEW_DEVICE: 0.3,
            RiskFactor.NEW_LOCATION: 0.25,
            RiskFactor.IMPOSSIBLE_TRAVEL: 0.9,
            RiskFactor.SUSPICIOUS_TIME: 0.15,
            RiskFactor.FAILED_ATTEMPTS: 0.4,
            RiskFactor.VPN_DETECTED: 0.35,
            RiskFactor.TOR_DETECTED: 0.8,
            RiskFactor.BEHAVIORAL_ANOMALY: 0.5,
            RiskFactor.CREDENTIAL_BREACH: 0.7,
            RiskFactor.BOT_DETECTED: 0.85,
        }

        # Initialize GeoIP database (path should be configured)
        try:
            self.geoip_reader = geoip2.database.Reader(
                "/usr/share/GeoIP/GeoLite2-City.mmdb"
            )
        except (ImportError, OSError) as e:
            logger.warning(f"GeoIP database not available: {e}")
            self.geoip_reader = None

    async def assess_authentication_risk(
        self, context: AuthenticationContext, user: Optional[UserAuth] = None
    ) -> RiskScore:
        """Assess risk for authentication attempt.

        Args:
            context: Authentication context
            user: User if already identified

        Returns:
            Risk score with details
        """
        risk_factors = []
        risk_details = {}

        # 1. Device Analysis
        device_risk = await self._analyze_device(context, user)
        if device_risk["is_new"]:
            risk_factors.append(RiskFactor.NEW_DEVICE)
            risk_details["new_device"] = device_risk

        # 2. Location Analysis
        location_risk = await self._analyze_location(context, user)
        if location_risk.get("is_new"):
            risk_factors.append(RiskFactor.NEW_LOCATION)
            risk_details["new_location"] = location_risk

        if location_risk.get("impossible_travel"):
            risk_factors.append(RiskFactor.IMPOSSIBLE_TRAVEL)
            risk_details["impossible_travel"] = location_risk["travel_details"]

        # 3. Time Analysis
        time_risk = self._analyze_time_pattern(context, user)
        if time_risk["is_suspicious"]:
            risk_factors.append(RiskFactor.SUSPICIOUS_TIME)
            risk_details["suspicious_time"] = time_risk

        # 4. Failed Attempts
        failed_attempts = self._check_failed_attempts(context, user)
        if failed_attempts["count"] > 2:
            risk_factors.append(RiskFactor.FAILED_ATTEMPTS)
            risk_details["failed_attempts"] = failed_attempts

        # 5. Network Analysis
        network_risk = await self._analyze_network(context)
        if network_risk.get("is_vpn"):
            risk_factors.append(RiskFactor.VPN_DETECTED)
            risk_details["vpn"] = network_risk

        if network_risk.get("is_tor"):
            risk_factors.append(RiskFactor.TOR_DETECTED)
            risk_details["tor"] = network_risk

        # 6. Behavioral Analysis
        if user:
            behavioral_risk = await self._analyze_behavior(context, user)
            if behavioral_risk["is_anomalous"]:
                risk_factors.append(RiskFactor.BEHAVIORAL_ANOMALY)
                risk_details["behavioral"] = behavioral_risk

        # 7. Credential Check
        credential_risk = await self._check_credential_breach(context.email)
        if credential_risk["is_breached"]:
            risk_factors.append(RiskFactor.CREDENTIAL_BREACH)
            risk_details["credential_breach"] = credential_risk

        # 8. Bot Detection
        bot_risk = self._detect_bot(context)
        if bot_risk["is_bot"]:
            risk_factors.append(RiskFactor.BOT_DETECTED)
            risk_details["bot"] = bot_risk

        # Calculate overall risk score
        risk_score = self._calculate_risk_score(risk_factors)
        risk_level = self._determine_risk_level(risk_score)

        # Determine recommended actions
        recommended_actions = self._get_recommended_actions(risk_level, risk_factors)

        return RiskScore(
            score=risk_score,
            level=risk_level,
            factors=risk_factors,
            details=risk_details,
            recommended_actions=recommended_actions,
        )

    async def _analyze_device(
        self, context: AuthenticationContext, user: Optional[UserAuth]
    ) -> Dict[str, Any]:
        """Analyze device risk factors."""
        result = {"is_new": False, "device_trust_score": 1.0, "details": {}}

        if not user or not context.device_fingerprint:
            result["is_new"] = True
            return result

        # Use device tracking service for risk assessment
        device_service = DeviceTrackingService(self.db)

        # Get device risk score
        device_risk = await device_service.get_device_risk_score(
            user, context.device_fingerprint
        )

        # Check if device is trusted
        is_trusted = device_service.is_device_trusted(user, context.device_fingerprint)

        # Check if device exists
        known_device = (
            self.db.query(DeviceInfo)
            .filter(
                and_(
                    DeviceInfo.user_id == user.id,
                    DeviceInfo.device_fingerprint == context.device_fingerprint,
                )
            )
            .first()
        )

        if not known_device:
            result["is_new"] = True
            result["device_trust_score"] = 0.0
        else:
            result["device_trust_score"] = 1.0 - device_risk
            result["details"] = {
                "last_seen": known_device.last_seen_at.isoformat(),
                "login_count": known_device.login_count,
                "is_trusted": is_trusted,
                "device_risk_score": device_risk,
            }

        return result

    def _calculate_risk_score(self, risk_factors: List[RiskFactor]) -> float:
        """Calculate overall risk score from factors."""
        if not risk_factors:
            return 0.0

        # Calculate weighted score
        total_score = 0.0

        for factor in risk_factors:
            weight = self.risk_weights.get(factor, 0.5)
            total_score += weight

        # Normalize to 0-1 range based on maximum possible score
        max_possible = sum(self.risk_weights.values())
        return min(1.0, total_score / max_possible)

    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score."""
        if score >= self.risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif score >= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score >= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _get_recommended_actions(
        self, risk_level: RiskLevel, risk_factors: List[RiskFactor]
    ) -> List[str]:
        """Get recommended actions based on risk assessment."""
        _ = risk_factors  # Mark as intentionally unused
        actions = []

        # Base actions by risk level
        if risk_level == RiskLevel.LOW:
            actions.append("proceed_with_standard_auth")
        elif risk_level == RiskLevel.MEDIUM:
            actions.append("require_mfa")
            actions.append("send_notification")
        elif risk_level == RiskLevel.HIGH:
            actions.append("require_strong_mfa")
            actions.append("require_identity_verification")
            actions.append("send_alert")
        elif risk_level == RiskLevel.CRITICAL:
            actions.append("block_attempt")
            actions.append("require_manual_review")
            actions.append("send_security_alert")

        return actions

    async def _analyze_location(
        self, context: AuthenticationContext, user: Optional[UserAuth]
    ) -> Dict[str, Any]:
        """Analyze location risk factors."""
        # Simplified location analysis without GeoIP
        result: Dict[str, Any] = {
            "is_new": False,
            "impossible_travel": False,
            "location": None,
        }

        if user:
            # Check if IP is different from recent sessions
            last_session = (
                self.db.query(UserSession)
                .filter(UserSession.user_id == user.id)
                .order_by(UserSession.created_at.desc())
                .first()
            )

            if last_session and last_session.ip_address != context.ip_address:
                result["is_new"] = True

        return result

    def _analyze_time_pattern(
        self, context: AuthenticationContext, user: Optional[UserAuth]
    ) -> Dict[str, Any]:
        """Analyze time-based risk factors."""
        _ = user  # Mark as intentionally unused
        result: Dict[str, Any] = {"is_suspicious": False, "details": {}}

        current_hour = context.timestamp.hour

        # Check for unusual hours (2 AM - 5 AM)
        if 2 <= current_hour <= 5:
            result["is_suspicious"] = True
            result["details"]["reason"] = "unusual_hour"

        return result

    def _check_failed_attempts(
        self, context: AuthenticationContext, user: Optional[UserAuth]
    ) -> Dict[str, Any]:
        """Check recent failed login attempts."""
        _ = user  # Mark as intentionally unused
        result: Dict[str, Any] = {"count": 0, "details": {}}

        # Check by IP
        ip_attempts = (
            self.db.query(func.count(LoginAttempt.id))  # pylint: disable=not-callable
            .filter(
                and_(
                    LoginAttempt.ip_address == context.ip_address,
                    LoginAttempt.success.is_(False),
                    LoginAttempt.attempted_at > datetime.utcnow() - timedelta(hours=1),
                )
            )
            .scalar()
        )

        result["count"] = ip_attempts or 0
        return result

    async def _analyze_network(self, context: AuthenticationContext) -> Dict[str, Any]:
        """Analyze network-related risk factors."""
        result: Dict[str, Any] = {
            "is_vpn": False,
            "is_tor": False,
            "is_proxy": False,
            "details": {},
        }

        # Check headers for proxy indicators
        proxy_headers = ["X-Forwarded-For", "X-Real-IP", "Via", "X-Proxy-ID"]
        for header in proxy_headers:
            if header in context.request_headers:
                result["is_proxy"] = True
                result["details"]["proxy_header"] = header
                break

        return result

    async def _analyze_behavior(
        self,
        context: AuthenticationContext,
        user: UserAuth,
    ) -> Dict[str, Any]:
        """Analyze user behavioral patterns."""
        # Basic behavioral analysis
        details: Dict[str, Any] = {
            "user_id": str(user.id),
            "login_time": context.timestamp.isoformat(),
            "device_info": context.device_fingerprint,
        }

        # Check for unusual login time
        current_hour = context.timestamp.hour
        is_unusual_time = current_hour < 6 or current_hour > 22

        anomaly_score = 0.0
        if is_unusual_time:
            anomaly_score += 0.3
            details["unusual_time"] = True

        return {
            "is_anomalous": anomaly_score > 0.5,
            "anomaly_score": anomaly_score,
            "details": details,
        }

    async def _check_credential_breach(self, email: str) -> Dict[str, Any]:
        """Check if credentials have been compromised."""
        # Basic email validation for known breach patterns
        details: Dict[str, Any] = {"email": email}

        # Check for commonly breached domains (simplified example)
        breached_domains = ["test.com", "example.com"]
        domain = email.split("@")[-1].lower()

        is_breached = domain in breached_domains
        if is_breached:
            details["reason"] = "domain_in_breach_list"

        return {"is_breached": is_breached, "details": details}

    def _detect_bot(self, context: AuthenticationContext) -> Dict[str, Any]:
        """Detect bot/automated behavior."""
        result: Dict[str, Any] = {"is_bot": False, "confidence": 0.0, "details": {}}

        # Simple bot detection
        ua = context.user_agent.lower()
        bot_indicators = ["bot", "crawler", "spider", "scraper"]

        for indicator in bot_indicators:
            if indicator in ua:
                result["is_bot"] = True
                result["confidence"] = 0.9
                break

        return result
