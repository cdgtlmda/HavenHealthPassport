"""Session middleware for FastAPI and Flask applications.

This module provides middleware to validate sessions, enforce timeout policies,
and track session activity for the Haven Health Passport system.
"""

import logging
from datetime import datetime
from typing import Any, Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session as DBSession

try:
    from flask import Response, abort, current_app, g
    from flask import request as flask_request

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    # Dummy placeholders to prevent NameError
    g = None
    flask_request = None
    current_app = None

    def abort(*args: Any, **kwargs: Any) -> Any:
        """Abort function placeholder when Flask is not installed."""
        raise NotImplementedError("Flask is not installed")


from starlette.middleware.base import BaseHTTPMiddleware

from src.auth.session_manager import SessionManager
from src.auth.token_decoder import decode_access_token
from src.models.auth import UserSession
from src.utils.exceptions import SessionExpiredException, SessionInvalidException

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for session management."""

    # Paths that don't require session validation
    EXEMPT_PATHS = [
        "/auth/login",
        "/auth/register",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    def __init__(self, app: Any, db_session_maker: Callable[[], DBSession]) -> None:
        """Initialize session middleware.

        Args:
            app: FastAPI application
            db_session_maker: Database session factory
        """
        super().__init__(app)
        self.db_session_maker = db_session_maker

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Process request and validate session.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Check if path is exempt
        if self._is_exempt_path(request.url.path):
            return await call_next(request)

        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid authorization header"},
            )

        # Extract token
        token = auth_header.split(" ")[1]

        # Decode JWT to get session ID
        try:
            payload = decode_access_token(token)
            session_id = payload.get("session_id")

            if not session_id:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid token: missing session ID"},
                )

        except (ValueError, KeyError) as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Invalid token: {str(e)}"},
            )

        # Get database session
        db = self.db_session_maker()

        try:
            # Create session manager
            session_manager = SessionManager(db)

            # Get session token from database using session ID
            session = db.query(UserSession).filter(UserSession.id == session_id).first()

            if not session:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Session not found"},
                )

            # Validate session
            try:
                validated_session, user = session_manager.validate_session(
                    session_token=str(session.token),
                    update_activity=True,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                )

                # Attach session and user to request state
                request.state.session = validated_session
                request.state.user = user
                request.state.db = db

            except SessionExpiredException:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Session has expired"},
                )
            except SessionInvalidException as e:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(e)}
                )

            # Process request
            response = await call_next(request)

            # Check if session should be renewed (close to expiry)
            if self._should_renew_session(validated_session):
                try:
                    renewed_session = session_manager.renew_session(validated_session)
                    # Add new token to response headers
                    response.headers["X-New-Session-Token"] = renewed_session.token
                except (SessionExpiredException, SessionInvalidException):
                    # Log but don't fail the request
                    pass

            return response

        finally:
            # Close database session
            db.close()

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from session validation.

        Args:
            path: Request path

        Returns:
            True if exempt
        """
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return True
        return False

    def _should_renew_session(self, session: "UserSession") -> bool:
        """Check if session should be renewed.

        Args:
            session: Current session

        Returns:
            True if should renew
        """
        # Get renewal window from session metadata
        metadata = session.metadata or {}
        timeout_config = metadata.get("timeout_config", {})
        renewal_window = timeout_config.get("renewal_window", 5)  # Default 5 minutes

        # Check if within renewal window
        now = datetime.utcnow()
        time_until_expiry = (session.expires_at - now).total_seconds() / 60

        return bool(time_until_expiry <= renewal_window)


def flask_session_middleware(
    db_session_maker: Callable[[], DBSession],
) -> Callable[[], None]:
    """Flask middleware for session management.

    Args:
        db_session_maker: Database session factory

    Returns:
        Middleware function
    """
    if not FLASK_AVAILABLE:
        raise ImportError(
            "Flask is not installed. Please install Flask to use this middleware."
        )

    def middleware() -> None:
        """Validate session before request."""
        # Check if path is exempt
        exempt_paths = [
            "/auth/login",
            "/auth/register",
            "/auth/forgot-password",
            "/auth/reset-password",
            "/health",
        ]

        for path in exempt_paths:
            if flask_request.path.startswith(path):
                return

        # Get authorization header
        auth_header = flask_request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            abort(401, "Missing or invalid authorization header")

        # Extract token
        token = auth_header.split(" ")[1]

        # Decode JWT to get session ID
        try:
            payload = decode_access_token(token)
            session_id = payload.get("session_id")

            if not session_id:
                abort(401, "Invalid token: missing session ID")

        except (ValueError, KeyError) as e:
            abort(401, f"Invalid token: {str(e)}")

        # Get database session
        db = db_session_maker()
        g.db = db

        try:
            # Create session manager
            session_manager = SessionManager(db)

            # Get session token from database
            session = db.query(UserSession).filter(UserSession.id == session_id).first()

            if not session:
                abort(401, "Session not found")

            # Validate session
            assert session is not None  # For type checker
            try:
                validated_session, user = session_manager.validate_session(
                    session_token=str(session.token),
                    update_activity=True,
                    ip_address=flask_request.remote_addr,
                    user_agent=flask_request.headers.get("User-Agent"),
                )

                # Attach to Flask g object
                g.session = validated_session
                g.user = user

                # Check if should renew
                if _should_renew_session_flask(validated_session):
                    try:
                        renewed_session = session_manager.renew_session(
                            validated_session
                        )
                        g.new_session_token = renewed_session.token
                    except (ValueError, RuntimeError) as e:
                        # Log the error but continue - session renewal is not critical
                        logger.warning("Failed to renew session: %s", str(e))

            except SessionExpiredException:
                abort(401, "Session has expired")
            except SessionInvalidException as e:
                abort(401, str(e))

        except (TypeError, ValidationError, ValueError) as e:
            db.close()
            raise e

    # Register cleanup handler
    @current_app.after_request  # type: ignore[misc]
    def cleanup_after_request(response: Response) -> Response:
        """Clean up after request."""
        db = g.get("db")
        if db:
            db.close()

        # Add new session token to response if renewed
        new_token = g.get("new_session_token")
        if new_token:
            response.headers["X-New-Session-Token"] = new_token

        return response

    return middleware


def _should_renew_session_flask(session: "UserSession") -> bool:
    """Check if session should be renewed (Flask version).

    Args:
        session: Current session

    Returns:
        True if should renew
    """
    # Get renewal window from session metadata
    metadata = session.metadata or {}
    timeout_config = metadata.get("timeout_config", {})
    renewal_window = timeout_config.get("renewal_window", 5)

    # Check if within renewal window
    now = datetime.utcnow()
    time_until_expiry = (session.expires_at - now).total_seconds() / 60

    return bool(time_until_expiry <= renewal_window)


# Session cleanup task (to be run periodically)
async def cleanup_expired_sessions(db_session_maker: Callable[[], DBSession]) -> None:
    """Clean up expired sessions periodically.

    Args:
        db_session_maker: Database session factory
    """
    db = db_session_maker()
    try:
        session_manager = SessionManager(db)
        cleaned = session_manager.cleanup_expired_sessions()
        print(f"Cleaned up {cleaned} expired sessions")
    finally:
        db.close()
