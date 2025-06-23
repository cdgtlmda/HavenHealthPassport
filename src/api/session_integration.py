"""Session management integration for Haven Health Passport API.

This module provides integration examples for session management
in FastAPI and Flask applications.
"""

import asyncio
import os
from typing import Any  # , cast  # Available if needed for future use

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth.session_manager import SessionManager
from src.config.session_config import SessionConfigOverrides
from src.core.database import get_db
from src.middleware.session_middleware import (
    SessionMiddleware,
    cleanup_expired_sessions,
    flask_session_middleware,
)
from src.models.auth import UserAuth, UserSession


# FastAPI Integration Example
def setup_fastapi_session_management(app: FastAPI) -> None:
    """Set up session management for FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Apply environment-specific configuration
    environment = os.getenv("ENVIRONMENT", "development")
    SessionConfigOverrides.apply_overrides(environment)

    # Add session middleware
    def get_db_session() -> Session:
        """Create a database session."""
        with get_db() as db:
            return db

    app.add_middleware(SessionMiddleware, db_session_maker=get_db_session)

    # Create security scheme
    security = HTTPBearer()

    # Local dependency variables to avoid B008 errors
    security_dependency = Depends(security)
    db_dependency = Depends(get_db)

    # Dependency to get current session
    async def get_current_session(
        credentials: HTTPAuthorizationCredentials = security_dependency,
        db: Session = db_dependency,
    ) -> UserSession:
        """Get current session from request."""
        # Session is validated by middleware and attached to request
        # This is a fallback for direct access
        session_manager = SessionManager(db)

        try:
            # Extract session from token (simplified - actual implementation
            # would decode JWT to get session ID)
            session, _ = session_manager.validate_session(
                session_token=credentials.credentials
            )
            return session
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
            ) from e

    # Local dependency for get_current_session
    get_current_session_dependency = Depends(get_current_session)

    # Dependency to get current user
    async def get_current_user(
        session: UserSession = get_current_session_dependency,
    ) -> UserAuth:
        """Get current user from session."""
        return session.user  # type: ignore[no-any-return]

    # Local dependency for get_current_user
    get_current_user_dependency = Depends(get_current_user)

    # Add session management endpoints
    @app.post("/api/v1/sessions/renew")
    async def renew_session(
        session: UserSession = get_current_session_dependency,
        db: Session = db_dependency,
    ) -> dict:
        """Renew current session."""
        session_manager = SessionManager(db)
        renewed_session = session_manager.renew_session(session)

        return {
            "status": "success",
            "session": {
                "token": renewed_session.token,
                "expires_at": renewed_session.expires_at.isoformat(),
                "absolute_expires_at": renewed_session.absolute_expires_at.isoformat(),
            },
        }

    @app.get("/api/v1/sessions/active")
    async def get_active_sessions(
        user: UserAuth = get_current_user_dependency, db: Session = db_dependency
    ) -> dict:
        """Get all active sessions for current user."""
        session_manager = SessionManager(db)
        sessions = session_manager.get_active_sessions(user)

        return {
            "status": "success",
            "sessions": [
                {
                    "id": str(s.id),
                    "type": s.session_type,
                    "created_at": s.created_at.isoformat(),
                    "last_activity": s.last_activity_at.isoformat(),
                    "expires_at": s.expires_at.isoformat(),
                    "device": s.device_fingerprint,
                    "ip_address": s.ip_address,
                }
                for s in sessions
            ],
        }

    @app.delete("/api/v1/sessions/{session_id}")
    async def terminate_session(
        session_id: str,
        user: UserAuth = get_current_user_dependency,
        current_session: UserSession = get_current_session_dependency,
        db: Session = db_dependency,
    ) -> dict:
        """Terminate a specific session."""
        # Verify user owns the session
        target_session = (
            db.query(UserSession)
            .filter(UserSession.id == session_id, UserSession.user_id == user.id)
            .first()
        )

        if not target_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Don't allow terminating current session via this endpoint
        if target_session.id == current_session.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot terminate current session",
            )

        session_manager = SessionManager(db)
        session_manager.terminate_session(target_session, "User requested termination")

        return {"status": "success", "message": "Session terminated"}

    @app.post("/api/v1/sessions/terminate-all")
    async def terminate_all_sessions(
        user: UserAuth = get_current_user_dependency,
        current_session: UserSession = get_current_session_dependency,
        db: Session = db_dependency,
    ) -> dict:
        """Terminate all sessions except current."""
        session_manager = SessionManager(db)
        count = session_manager.terminate_all_user_sessions(
            user,
            except_session=current_session,
            reason="User requested bulk termination",
        )

        return {"status": "success", "terminated_count": count}

    # Schedule periodic cleanup task
    async def session_cleanup_task() -> None:
        """Periodic task to clean up expired sessions."""
        while True:
            await asyncio.sleep(3600)  # Run every hour
            await cleanup_expired_sessions(get_db_session)

    # Start cleanup task on startup
    @app.on_event("startup")
    async def startup_event() -> None:
        asyncio.create_task(session_cleanup_task())


# Flask Integration Example
def setup_flask_session_management(app: Any) -> None:
    """Set up session management for Flask application.

    Args:
        app: Flask application instance
    """
    try:
        from flask import Flask, g, jsonify  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise ImportError("Flask is required for Flask session integration") from exc

    if not isinstance(app, Flask):
        raise TypeError("app must be a Flask instance")
    # Apply environment-specific configuration
    environment = os.getenv("ENVIRONMENT", "development")
    SessionConfigOverrides.apply_overrides(environment)

    # Create session maker function
    def get_db_session() -> Session:
        """Create a database session."""
        with get_db() as db:
            return db

    # Get middleware function
    middleware = flask_session_middleware(get_db_session)

    # Register middleware
    app.before_request(middleware)

    # Add session management routes
    @app.route("/api/v1/sessions/renew", methods=["POST"])  # type: ignore[misc]
    def renew_session() -> Any:
        """Renew current session."""
        session_manager = SessionManager(g.db)
        renewed_session = session_manager.renew_session(g.session)

        return jsonify(
            {
                "status": "success",
                "session": {
                    "token": renewed_session.token,
                    "expires_at": renewed_session.expires_at.isoformat(),
                    "absolute_expires_at": renewed_session.absolute_expires_at.isoformat(),
                },
            }
        )

    @app.route("/api/v1/sessions/active", methods=["GET"])  # type: ignore[misc]
    def get_active_sessions() -> Any:
        """Get all active sessions for current user."""
        session_manager = SessionManager(g.db)
        sessions = session_manager.get_active_sessions(g.user)

        return jsonify(
            {
                "status": "success",
                "sessions": [
                    {
                        "id": str(s.id),
                        "type": s.session_type,
                        "created_at": s.created_at.isoformat(),
                        "last_activity": s.last_activity_at.isoformat(),
                        "expires_at": s.expires_at.isoformat(),
                        "device": s.device_fingerprint,
                        "ip_address": s.ip_address,
                    }
                    for s in sessions
                ],
            }
        )

    # Add error handler for session errors
    @app.errorhandler(401)  # type: ignore[misc]
    def handle_unauthorized(e: Any) -> Any:
        """Handle unauthorized errors."""
        return (
            jsonify({"status": "error", "message": str(e), "code": "UNAUTHORIZED"}),
            401,
        )


# Session monitoring and analytics
class SessionMonitor:
    """Monitor and analyze session activity."""

    @staticmethod
    async def get_session_metrics(db_session_maker: Any) -> dict:
        """Get session metrics for monitoring."""
        db = db_session_maker()
        try:
            session_manager = SessionManager(db)

            # Get analytics for last 24 hours
            analytics = session_manager.get_session_analytics(days=1)

            # Add real-time metrics
            active_sessions = (
                db.query(UserSession).filter(UserSession.is_active.is_(True)).count()
            )

            return {
                "active_sessions": active_sessions,
                "analytics": analytics,
                "health": "healthy" if active_sessions < 10000 else "degraded",
            }
        finally:
            db.close()
