"""Device tracking and management service.

This module handles device fingerprinting, tracking, trust management,
and integration with risk-based authentication.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models.auth import DeviceInfo, UserAuth, UserSession
from src.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from user_agents import parse as parse_user_agent

    USER_AGENTS_AVAILABLE = True
except ImportError:
    USER_AGENTS_AVAILABLE = False
    logger.warning("user_agents package not available, device parsing will be limited")


class DeviceTrackingService:
    """Service for device tracking and management."""

    def __init__(self, db: Session):
        """Initialize device tracking service."""
        self.db = db
        self.trust_duration_days = 90
        self.max_trusted_devices = 10

    def generate_device_fingerprint(
        self,
        request_headers: Dict[str, str],
        client_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a device fingerprint from request data."""
        fingerprint_data = {
            "user_agent": request_headers.get("User-Agent", ""),
            "accept_language": request_headers.get("Accept-Language", ""),
            "accept_encoding": request_headers.get("Accept-Encoding", ""),
            "accept": request_headers.get("Accept", ""),
        }

        if client_data:
            fingerprint_data.update(
                {
                    "screen_resolution": client_data.get("screen_resolution", ""),
                    "timezone": client_data.get("timezone", ""),
                    "canvas_fingerprint": client_data.get("canvas_fingerprint", ""),
                }
            )
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    def parse_device_info(
        self, user_agent: str, request_headers: Dict[str, str]
    ) -> Dict[str, str]:
        """Parse device information from user agent and headers."""
        # Mark request_headers as intentionally unused for now
        _ = request_headers

        if USER_AGENTS_AVAILABLE:
            ua = parse_user_agent(user_agent)

            # Determine device type
            if ua.is_mobile:
                device_type = "mobile"
            elif ua.is_tablet:
                device_type = "tablet"
            elif ua.is_pc:
                device_type = "desktop"
            else:
                device_type = "unknown"

            # Generate device name
            device_name = f"{ua.browser.family} on {ua.os.family}"
            if ua.device.family != "Other":
                device_name = f"{ua.device.family} - {device_name}"

            return {
                "device_name": device_name,
                "device_type": device_type,
                "platform": ua.os.family,
                "platform_version": ua.os.version_string,
                "browser": ua.browser.family,
                "browser_version": ua.browser.version_string,
            }
        else:
            # Fallback parsing when user_agents is not available
            return {
                "device_name": "Unknown Device",
                "device_type": "unknown",
                "platform": "unknown",
                "platform_version": "unknown",
                "browser": "unknown",
                "browser_version": "unknown",
            }

    async def track_device(
        self,
        user: UserAuth,
        device_fingerprint: str,
        ip_address: str,
        user_agent: str,
        request_headers: Dict[str, str],
    ) -> DeviceInfo:
        """Track a device for a user."""
        # Check if device already exists
        device = (
            self.db.query(DeviceInfo)
            .filter(
                and_(
                    DeviceInfo.user_id == user.id,
                    DeviceInfo.device_fingerprint == device_fingerprint,
                )
            )
            .first()
        )

        if device:
            # Update existing device
            device.last_seen_at = datetime.utcnow()
            device.login_count += 1
            device.ip_address = ip_address
            device.user_agent = user_agent

            logger.info(
                f"Known device tracked for user {user.id}: {device.device_name}"
            )
        else:
            # Create new device
            device_info = self.parse_device_info(user_agent, request_headers)

            device = DeviceInfo(
                user_id=user.id,
                device_fingerprint=device_fingerprint,
                device_name=device_info["device_name"],
                device_type=device_info["device_type"],
                platform=device_info["platform"],
                platform_version=device_info["platform_version"],
                browser=device_info["browser"],
                browser_version=device_info["browser_version"],
                ip_address=ip_address,
                user_agent=user_agent,
                is_trusted=False,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                login_count=1,
            )

            self.db.add(device)
            logger.info(f"New device tracked for user {user.id}: {device.device_name}")
        self.db.commit()
        return device

    def trust_device(
        self, user: UserAuth, device_id: str, duration_days: Optional[int] = None
    ) -> bool:
        """Mark a device as trusted."""
        device = (
            self.db.query(DeviceInfo)
            .filter(and_(DeviceInfo.id == device_id, DeviceInfo.user_id == user.id))
            .first()
        )

        if not device:
            logger.warning(f"Device {device_id} not found for user {user.id}")
            return False

        # Check trusted device limit
        trusted_count = (
            self.db.query(DeviceInfo)
            .filter(
                and_(DeviceInfo.user_id == user.id, DeviceInfo.is_trusted.is_(True))
            )
            .count()
        )

        if trusted_count >= self.max_trusted_devices and not device.is_trusted:
            logger.warning(f"User {user.id} has reached trusted device limit")
            return False

        # Trust the device
        device.is_trusted = True
        device.trusted_at = datetime.utcnow()
        device.trust_expires_at = datetime.utcnow() + timedelta(
            days=duration_days or self.trust_duration_days
        )

        self.db.commit()
        logger.info(f"Device {device.device_name} trusted for user {user.id}")
        return True

    def revoke_device_trust(self, user: UserAuth, device_id: str) -> bool:
        """Revoke trust for a device."""
        device = (
            self.db.query(DeviceInfo)
            .filter(and_(DeviceInfo.id == device_id, DeviceInfo.user_id == user.id))
            .first()
        )

        if not device:
            return False

        device.is_trusted = False
        device.trusted_at = None
        device.trust_expires_at = None

        self.db.commit()
        logger.info(f"Device trust revoked for {device.device_name}")
        return True

    def get_user_devices(
        self, user: UserAuth, include_inactive: bool = False
    ) -> List[DeviceInfo]:
        """Get all devices for a user."""
        query = self.db.query(DeviceInfo).filter(DeviceInfo.user_id == user.id)

        if not include_inactive:
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            query = query.filter(DeviceInfo.last_seen_at > cutoff_date)

        return query.order_by(DeviceInfo.last_seen_at.desc()).all()

    def is_device_trusted(self, user: UserAuth, device_fingerprint: str) -> bool:
        """Check if a device is trusted."""
        device = (
            self.db.query(DeviceInfo)
            .filter(
                and_(
                    DeviceInfo.user_id == user.id,
                    DeviceInfo.device_fingerprint == device_fingerprint,
                    DeviceInfo.is_trusted.is_(True),
                )
            )
            .first()
        )
        if not device:
            return False

        # Check if trust has expired
        if device.trust_expires_at and device.trust_expires_at < datetime.utcnow():
            device.is_trusted = False
            device.trust_expires_at = None
            self.db.commit()
            return False

        return True

    def delete_device(self, user: UserAuth, device_id: str) -> bool:
        """Delete a device record."""
        device = (
            self.db.query(DeviceInfo)
            .filter(and_(DeviceInfo.id == device_id, DeviceInfo.user_id == user.id))
            .first()
        )

        if not device:
            return False

        # Don't delete if it's the current device
        active_sessions = (
            self.db.query(UserSession)
            .filter(
                and_(
                    UserSession.device_id == device_id, UserSession.is_active.is_(True)
                )
            )
            .count()
        )

        if active_sessions > 0:
            logger.warning(f"Cannot delete active device {device_id}")
            return False

        self.db.delete(device)
        self.db.commit()
        logger.info(f"Device {device.device_name} deleted for user {user.id}")
        return True

    async def get_device_risk_score(
        self, user: UserAuth, device_fingerprint: str
    ) -> float:
        """Calculate risk score for a device."""
        device = (
            self.db.query(DeviceInfo)
            .filter(
                and_(
                    DeviceInfo.user_id == user.id,
                    DeviceInfo.device_fingerprint == device_fingerprint,
                )
            )
            .first()
        )

        if not device:
            # New device = high risk
            return 0.8

        # Calculate risk based on device history
        risk_score = 0.0

        # Trust status
        if not device.is_trusted:
            risk_score += 0.3

        # Device age
        device_age_days = (datetime.utcnow() - device.first_seen_at).days
        if device_age_days < 7:
            risk_score += 0.2
        elif device_age_days < 30:
            risk_score += 0.1

        # Login frequency
        if device.login_count < 5:
            risk_score += 0.1

        # Last seen
        days_since_seen = (datetime.utcnow() - device.last_seen_at).days
        if days_since_seen > 30:
            risk_score += 0.2
        elif days_since_seen > 14:
            risk_score += 0.1

        return min(1.0, risk_score)
