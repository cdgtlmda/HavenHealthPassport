"""Risk analysis utilities for risk-based authentication.

This module contains analysis methods for various risk factors.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models.auth import LoginAttempt, UserAuth
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskAnalyzer:
    """Utilities for analyzing authentication risk factors."""

    def __init__(self, db: Session):
        """Initialize risk analyzer."""
        self.db = db

    def analyze_time_pattern(
        self, timestamp: datetime, user: Optional[UserAuth]
    ) -> Dict[str, Any]:
        """Analyze time-based risk factors."""
        result: Dict[str, Any] = {"is_suspicious": False, "details": {}}

        current_hour = timestamp.hour

        # Check for unusual hours (2 AM - 5 AM local time)
        if 2 <= current_hour <= 5:
            result["is_suspicious"] = True
            details = result["details"]
            if isinstance(details, dict):
                details["reason"] = "unusual_hour"

        if user:
            # Analyze user's typical login patterns
            # In production, this would analyze recent login history
            _ = (
                self.db.query(LoginAttempt)
                .filter(
                    and_(
                        LoginAttempt.user_id == user.id,
                        LoginAttempt.success.is_(True),
                        LoginAttempt.attempted_at
                        > datetime.utcnow() - timedelta(days=30),
                    )
                )
                .all()
            )

        return result
