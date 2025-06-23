"""Risk-based authentication integration module.

This module integrates risk-based authentication into the existing auth flow.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.auth import UserAuth
from src.services.risk_based_auth_service import (
    AuthenticationContext,
    RiskBasedAuthService,
    RiskLevel,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskBasedAuthIntegration:
    """Integration layer for risk-based authentication."""

    def __init__(self, db: Session):
        """Initialize integration."""
        self.db = db
        self.risk_service = RiskBasedAuthService(db)

    async def check_authentication_risk(
        self, request: Request, email: str, user: Optional[UserAuth] = None
    ) -> Dict[str, Any]:
        """Check authentication risk and return requirements.

        Args:
            request: FastAPI request object
            email: User email
            user: User object if available

        Returns:
            Authentication requirements based on risk
        """
        # Build authentication context
        context = AuthenticationContext(
            user_id=str(user.id) if user else None,
            email=email,
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("User-Agent", ""),
            device_fingerprint=request.headers.get("X-Device-Fingerprint"),
            request_headers=dict(request.headers),
            timestamp=datetime.utcnow(),
            session_data=None,
        )
        # Assess risk
        risk_score = await self.risk_service.assess_authentication_risk(context, user)

        # Determine authentication requirements
        auth_requirements = {
            "allow_login": True,
            "mfa_required": False,
            "mfa_methods": [],
            "additional_steps": [],
        }

        if risk_score.level == RiskLevel.MEDIUM:
            auth_requirements["mfa_required"] = True
            auth_requirements["mfa_methods"] = ["totp", "sms", "email", "fido2"]

        elif risk_score.level == RiskLevel.HIGH:
            auth_requirements["mfa_required"] = True
            auth_requirements["mfa_methods"] = ["totp", "fido2"]
            auth_requirements["additional_steps"] = ["security_questions"]

        elif risk_score.level == RiskLevel.CRITICAL:
            auth_requirements["allow_login"] = False

        logger.info(
            f"Risk assessment - Email: {email}, "
            f"Risk: {risk_score.level.value} ({risk_score.score:.2f}), "
            f"Factors: {[f.value for f in risk_score.factors]}"
        )

        return {
            "risk_level": risk_score.level.value,
            "risk_score": risk_score.score,
            "risk_factors": [f.value for f in risk_score.factors],
            "auth_requirements": auth_requirements,
        }
