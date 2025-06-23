"""Notification Service for sending alerts and messages."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.notification import Notification, NotificationStatus
from src.services.base import BaseService
from src.services.unified_notification_service import (
    NotificationPriority,
    get_notification_service,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NotificationService(BaseService):
    """Service for handling notifications."""

    def __init__(self, db: Session):
        """Initialize notification service."""
        super().__init__(db)
        self.db = db
        self.unified_service = get_notification_service()

    async def send_notification(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a notification to a user."""
        # Use unified notification service
        return await self.unified_service.send_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data,
            priority=NotificationPriority.NORMAL,
        )

    async def get_user_notifications(
        self, user_id: UUID, unread_only: bool = False, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user."""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)

        if unread_only:
            query = query.filter(Notification.status == NotificationStatus.UNREAD)

        notifications = (
            query.order_by(Notification.created_at.desc()).limit(limit).all()
        )

        return [
            {
                "id": str(notif.id),
                "type": notif.notification_type,
                "title": notif.title,
                "message": notif.message,
                "status": notif.status.value,
                "created_at": notif.created_at.isoformat(),
                "read_at": notif.read_at.isoformat() if notif.read_at else None,
                "data": notif.data or {},
            }
            for notif in notifications
        ]

    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark notification as read."""
        notification = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )

        if not notification:
            return False

        notification.status = NotificationStatus.READ
        notification.read_at = datetime.utcnow()

        try:
            self.db.commit()
            return True
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to mark notification as read: {e}")
            self.db.rollback()
            return False

    async def send_bulk_notification(
        self, user_ids: List[UUID], notification_type: str, title: str, message: str
    ) -> Dict[str, Any]:
        """Send notification to multiple users."""
        sent_count = 0
        failed_count = 0

        for user_id in user_ids:
            try:
                await self.send_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                )
                sent_count += 1
            except (ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")
                failed_count += 1

        return {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "status": "completed",
            "total": len(user_ids),
        }
