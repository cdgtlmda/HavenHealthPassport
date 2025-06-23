"""WebAuthn middleware for origin validation and security checks.

This module provides middleware for WebAuthn authentication requests,
including origin validation, challenge verification, and security headers.
"""

import json
import logging
import secrets
import time
from typing import Callable, Optional, cast

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.config.webauthn_settings import get_webauthn_settings
from src.utils.cache import get_redis_client

logger = logging.getLogger(__name__)


class WebAuthnMiddleware(BaseHTTPMiddleware):
    """Middleware for WebAuthn authentication endpoints."""

    def __init__(self, app: ASGIApp):
        """Initialize WebAuthn middleware.

        Args:
            app: ASGI application
        """
        super().__init__(app)
        self.settings = get_webauthn_settings()
        self.webauthn_endpoints = [
            "/biometric/webauthn/register/begin",
            "/biometric/webauthn/register/complete",
            "/biometric/webauthn/authenticate/begin",
            "/biometric/webauthn/authenticate/complete",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process WebAuthn requests with security checks.

        Args:
            request: Incoming request
            call_next: Next middleware or endpoint

        Returns:
            Response with appropriate headers
        """
        # Check if this is a WebAuthn endpoint
        if not any(
            request.url.path.startswith(endpoint)
            for endpoint in self.webauthn_endpoints
        ):
            return cast(Response, await call_next(request))

        try:
            # Validate origin
            origin = request.headers.get("Origin")
            if not origin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Origin header is required for WebAuthn operations",
                )

            if not self.settings.is_origin_allowed(origin):
                logger.warning("WebAuthn request from disallowed origin: %s", origin)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Origin not allowed for WebAuthn operations",
                )

            # Process request
            response = await call_next(request)

            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Add CORS headers for WebAuthn
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

            return cast(Response, response)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("WebAuthn middleware error: %s", e)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )


class WebAuthnChallengeManager:
    """Manages WebAuthn challenges for registration and authentication."""

    def __init__(self) -> None:
        """Initialize challenge manager."""
        self.settings = get_webauthn_settings()
        self.redis_prefix = "webauthn:challenge:"

    async def create_challenge(self, user_id: str, operation: str) -> bytes:
        """Create and store a new challenge.

        Args:
            user_id: User ID
            operation: Operation type (register or authenticate)

        Returns:
            Challenge bytes
        """
        # Generate challenge
        challenge = secrets.token_bytes(self.settings.challenge_size)

        # Store in Redis with expiration
        key = f"{self.redis_prefix}{user_id}:{operation}"
        challenge_data = {
            "challenge": challenge.hex(),
            "created_at": int(time.time()),
            "operation": operation,
        }

        redis_client = await get_redis_client()
        await redis_client.setex(
            key, self.settings.challenge_timeout_seconds, json.dumps(challenge_data)
        )

        return challenge

    async def verify_challenge(
        self, user_id: str, operation: str, client_challenge: str
    ) -> bool:
        """Verify a challenge response.

        Args:
            user_id: User ID
            operation: Operation type
            client_challenge: Challenge from client

        Returns:
            True if challenge is valid
        """
        key = f"{self.redis_prefix}{user_id}:{operation}"

        # Get stored challenge
        redis_client = await get_redis_client()
        stored_data = await redis_client.get(key)
        if not stored_data:
            logger.warning(
                "No challenge found for user %s, operation %s", user_id, operation
            )
            return False

        try:
            challenge_data = json.loads(stored_data)
            stored_challenge = challenge_data["challenge"]

            # Compare challenges (in hex format)
            if stored_challenge == client_challenge:
                # Delete used challenge
                await redis_client.delete(key)
                return True

            return False

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Challenge verification error: %s", e)
            return False

    async def cleanup_expired_challenges(self) -> int:
        """Clean up expired challenges.

        Returns:
            Number of challenges cleaned up
        """
        # Redis automatically expires keys, but this can be used for manual cleanup
        redis_client = await get_redis_client()
        pattern = f"{self.redis_prefix}*"
        keys = await redis_client.keys(pattern)

        cleaned = 0
        current_time = int(time.time())

        for key in keys:
            try:
                data = await redis_client.get(key)
                if data:
                    challenge_data = json.loads(data)
                    created_at = challenge_data.get("created_at", 0)

                    # Check if expired
                    if (
                        current_time - created_at
                        > self.settings.challenge_timeout_seconds
                    ):
                        await redis_client.delete(key)
                        cleaned += 1
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("Error cleaning challenge %s: %s", key, e)

        return cleaned


def validate_webauthn_request(request: dict, operation: str) -> bool:
    """Validate WebAuthn request structure.

    Args:
        request: Request data
        operation: Operation type (register_begin, register_complete, etc.)

    Returns:
        True if request is valid

    Raises:
        ValueError: If request is invalid
    """
    required_fields = {
        "register_begin": [],
        "register_complete": ["credential", "deviceName"],
        "authenticate_begin": [],
        "authenticate_complete": ["assertion"],
    }

    fields = required_fields.get(operation, [])

    for field in fields:
        if field not in request:
            raise ValueError(f"Missing required field: {field}")

    # Validate specific fields
    if operation == "register_complete":
        credential = request["credential"]
        if not isinstance(credential, dict):
            raise ValueError("Credential must be an object")

        required_credential_fields = ["id", "rawId", "response", "type"]
        for field in required_credential_fields:
            if field not in credential:
                raise ValueError(f"Missing credential field: {field}")

    elif operation == "authenticate_complete":
        assertion = request["assertion"]
        if not isinstance(assertion, dict):
            raise ValueError("Assertion must be an object")

        required_assertion_fields = ["id", "rawId", "response", "type"]
        for field in required_assertion_fields:
            if field not in assertion:
                raise ValueError(f"Missing assertion field: {field}")

    return True


def get_webauthn_error_response(error: Exception) -> dict:
    """Get standardized WebAuthn error response.

    Args:
        error: Exception that occurred

    Returns:
        Error response dictionary
    """
    error_messages = {
        "NotAllowedError": "The operation was cancelled or not allowed",
        "InvalidStateError": "A credential is already registered for this account",
        "NotSupportedError": "WebAuthn is not supported on this device",
        "AbortError": "The operation was aborted",
        "ConstraintError": "The authenticator does not meet requirements",
        "UnknownError": "An unknown error occurred",
    }

    error_name = getattr(error, "name", "UnknownError")
    message = error_messages.get(error_name, str(error))

    return {"success": False, "error": error_name, "message": message}


class _ChallengeManagerSingleton:
    """Singleton holder for WebAuthn challenge manager."""

    instance: Optional[WebAuthnChallengeManager] = None


def get_challenge_manager() -> WebAuthnChallengeManager:
    """Get WebAuthn challenge manager singleton."""
    if _ChallengeManagerSingleton.instance is None:
        _ChallengeManagerSingleton.instance = WebAuthnChallengeManager()
    return _ChallengeManagerSingleton.instance
