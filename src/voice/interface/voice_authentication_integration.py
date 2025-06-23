"""
Voice Authentication Integration Module.

This module provides integration between voice authentication and the broader
authentication system for the Haven Health Passport.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.voice.interface.voice_authentication import AuthenticationMethod

if TYPE_CHECKING:
    from src.auth.models import User


class VoiceAuthenticationIntegration:
    """Integration with the broader authentication system."""

    def __init__(
        self,
        voice_engine: Any,
        auth_service: Optional[Any] = None,
    ):
        """Initialize voice authentication integration.

        Args:
            voice_engine: The voice authentication engine
            auth_service: Optional authentication service instance
        """
        self.voice_engine = voice_engine
        self.auth_service = auth_service

    async def enroll_user_voice(self, user: "User") -> Dict[str, Any]:
        """Enroll user for voice authentication."""
        # Start enrollment
        session_id = await self.voice_engine.start_enrollment(
            user.id, AuthenticationMethod.TEXT_INDEPENDENT
        )

        return {
            "session_id": session_id,
            "user_id": user.id,
            "instructions": "Please provide 3 voice samples for enrollment",
        }

    async def authenticate_user(
        self, username: str, audio_data: bytes
    ) -> Dict[str, Any]:
        """Authenticate user with voice."""
        if not self.auth_service:
            return {"authenticated": False, "error": "Auth service not configured"}

        # Get user
        user = await self.auth_service.get_user_by_username(username)
        if not user:
            return {"authenticated": False, "error": "User not found"}

        # Perform voice authentication
        result = await self.voice_engine.authenticate(user.id, audio_data)

        if result["result"] == "success":
            # Create session token
            token = await self.auth_service.create_session(user.id)

            return {
                "authenticated": True,
                "token": token,
                "user_id": user.id,
                "confidence": result["confidence"],
                "assurance_level": result["assurance_level"],
            }

        return {
            "authenticated": False,
            "reason": result["result"],
            "details": result.get("details", {}),
        }

    async def setup_multi_factor(
        self, user_id: str, factors: List[str]
    ) -> Dict[str, Any]:
        """Set up multi-factor authentication including voice."""
        if "voice" not in factors:
            return {"error": "Voice must be included in multi-factor setup"}

        # Start voice enrollment
        session_id = await self.voice_engine.start_enrollment(
            user_id, AuthenticationMethod.MULTI_FACTOR
        )

        return {
            "voice_session_id": session_id,
            "other_factors": [f for f in factors if f != "voice"],
            "status": "setup_in_progress",
        }
