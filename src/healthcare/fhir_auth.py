"""
FHIR Server Authentication Module.

This module provides authentication configuration and middleware for the HAPI FHIR server.
Implements OAuth2/JWT-based authentication for secure access to FHIR resources.
Handles FHIR CapabilityStatement Resource validation for auth capabilities.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
from pydantic import Field
from pydantic_settings import BaseSettings

from src.auth.jwt_handler import JWTHandler
from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)

# FHIR resource type for this module
__fhir_resource__ = "CapabilityStatement"


class FHIRAuthConfig(BaseSettings):
    """FHIR Authentication Configuration."""

    # Authentication Settings
    auth_enabled: bool = Field(default=True)
    auth_type: str = Field(default="oauth2")

    # JWT Settings
    jwt_secret: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=60)

    # OAuth2 Settings
    oauth2_issuer: str = Field(default="https://auth.havenhealthpassport.org")
    oauth2_audience: str = Field(default="https://fhir.havenhealthpassport.org")
    oauth2_scopes: List[str] = Field(
        default=[
            "patient/*.read",
            "patient/*.write",
            "user/*.read",
            "user/*.write",
            "system/*.read",
        ],
    )
    # Public Key Settings (for RS256)
    public_key_url: Optional[str] = Field(default=None)

    # Role-based Access Control
    rbac_enabled: bool = Field(default=True)

    # Anonymous Access
    allow_anonymous_read: bool = Field(default=False)

    # Token Validation
    validate_token_expiry: bool = Field(default=True)
    validate_token_signature: bool = Field(default=True)


class FHIRAuthenticator:
    """FHIR Server Authenticator."""

    def __init__(self, config: Optional[FHIRAuthConfig] = None):
        """Initialize FHIR Authenticator.

        Args:
            config: Authentication configuration
        """
        self.config = config or FHIRAuthConfig()
        self.jwt_handler = JWTHandler() if self.config.jwt_secret else None
        self.validator = FHIRValidator()  # Initialize validator

    def is_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.config.auth_enabled

    def generate_access_token(
        self,
        user_id: str,
        patient_id: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate FHIR access token.

        Args:
            user_id: User identifier
            patient_id: Associated patient ID (if applicable)
            scopes: OAuth2 scopes
            additional_claims: Additional JWT claims

        Returns:
            JWT access token
        """
        if not self.jwt_handler:
            raise ValueError("JWT handler not configured")
        claims = {
            "sub": user_id,
            "iss": self.config.oauth2_issuer,
            "aud": self.config.oauth2_audience,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow()
            + timedelta(minutes=self.config.jwt_expiration_minutes),
            "scope": " ".join(scopes or self.config.oauth2_scopes),
        }

        if patient_id:
            claims["patient"] = patient_id

        if additional_claims:
            claims.update(additional_claims)

        return jwt.encode(
            claims, self.config.jwt_secret, algorithm=self.config.jwt_algorithm
        )

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate FHIR access token.

        Args:
            token: JWT token to validate

        Returns:
            Decoded token claims if valid, None otherwise
        """
        if not self.config.auth_enabled:
            return {"sub": "anonymous", "scope": "*"}

        if not token:
            return None

        try:
            # Remove Bearer prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            # Decode and validate token
            claims = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                audience=self.config.oauth2_audience,
                issuer=self.config.oauth2_issuer,
                options={
                    "verify_signature": self.config.validate_token_signature,
                    "verify_exp": self.config.validate_token_expiry,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            logger.debug(f"Token validated for user: {claims.get('sub')}")
            return claims  # type: ignore[no-any-return]

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def check_resource_access(
        self,
        token_claims: Dict[str, Any],
        resource_type: str,
        operation: str,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if token has access to perform operation on resource.

        Args:
            token_claims: Decoded JWT claims
            resource_type: FHIR resource type (e.g., "Patient", "Observation")
            operation: Operation type (e.g., "read", "write", "delete")
            resource_id: Specific resource ID (optional)

        Returns:
            True if access is allowed, False otherwise
        """
        if not self.config.auth_enabled:
            return True

        if not token_claims:
            return self.config.allow_anonymous_read and operation == "read"

        # Extract scopes from token
        scope_string = token_claims.get("scope", "")
        scopes = scope_string.split() if scope_string else []

        # Check for wildcard system scope
        if "system/*.*" in scopes or f"system/*.{operation}" in scopes:
            return True

        # Check for specific resource scope
        required_scopes = [
            f"user/{resource_type}.{operation}",
            f"user/{resource_type}.*",
            f"patient/{resource_type}.{operation}",
            f"patient/{resource_type}.*",
        ]

        for scope in scopes:
            if scope in required_scopes:
                # Additional check for patient-specific resources
                if scope.startswith("patient/") and resource_type == "Patient":
                    # Ensure user can only access their own patient record
                    patient_id = token_claims.get("patient")
                    if resource_id and patient_id and resource_id != patient_id:
                        logger.warning(
                            "Access denied: User tried to access different patient record"
                        )
                        return False
                return True

        logger.debug(
            f"Access denied: No matching scope for {resource_type}.{operation}"
        )
        return False

    def get_auth_config_for_hapi(self) -> Dict[str, Any]:
        """Get authentication configuration for HAPI FHIR server.

        Returns:
            Configuration dictionary for HAPI FHIR
        """
        return {
            "enabled": self.config.auth_enabled,
            "type": self.config.auth_type,
            "oauth2": {
                "issuer": self.config.oauth2_issuer,
                "audience": self.config.oauth2_audience,
                "required_scopes": self.config.oauth2_scopes,
            },
            "anonymous_read": self.config.allow_anonymous_read,
            "rbac_enabled": self.config.rbac_enabled,
        }
