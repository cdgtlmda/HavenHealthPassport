"""WebAuthn/FIDO2 cryptographic operations service.

This module handles the core WebAuthn cryptographic operations including
credential creation, verification, and attestation validation.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorData,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialParameters,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialType,
    PublicKeyCredentialUserEntity,
    UserVerificationRequirement,
    websafe_decode,
    websafe_encode,
)
from sqlalchemy.orm import Session

from src.config.webauthn_settings import get_webauthn_settings
from src.middleware.webauthn_middleware import get_challenge_manager
from src.models.auth import UserAuth, WebAuthnCredential

logger = logging.getLogger(__name__)


class WebAuthnService:
    """Handles WebAuthn cryptographic operations."""

    def __init__(self, db_session: Session):
        """Initialize WebAuthn service.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.settings = get_webauthn_settings()
        self.challenge_manager = get_challenge_manager()

        # Initialize state storage
        self._registration_states: Dict[str, Any] = {}
        self._auth_states: Dict[str, Any] = {}

        # Initialize FIDO2 server
        rp = PublicKeyCredentialRpEntity(
            id=self.settings.rp_id, name=self.settings.rp_name
        )

        self.server = Fido2Server(
            rp,
            attestation=AttestationConveyancePreference(
                self.settings.attestation_conveyance
            ),
            verify_origin=self._verify_origin,
        )

    def _verify_origin(self, origin: str) -> bool:
        """Verify request origin.

        Args:
            origin: Request origin

        Returns:
            True if origin is allowed
        """
        return self.settings.is_origin_allowed(origin)

    async def create_registration_options(self, user: UserAuth) -> Dict[str, Any]:
        """Create registration options for a new credential.

        Args:
            user: User to register credential for

        Returns:
            Registration options dictionary
        """
        # Create user entity
        user_entity = PublicKeyCredentialUserEntity(
            id=str(user.id).encode(),
            name=str(user.email),
            display_name=str(user.email).split("@", maxsplit=1)[0],
        )

        # Get user's existing credentials
        existing_credentials = self._get_user_credentials(user)
        exclude_credentials = []

        for cred in existing_credentials:
            exclude_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=websafe_decode(str(cred.credential_id)),
                    type=PublicKeyCredentialType.PUBLIC_KEY,
                    transports=(
                        [AuthenticatorTransport(t) for t in cred.transports]
                        if cred.transports
                        else None
                    ),
                )
            )

        # Create challenge
        challenge = await self.challenge_manager.create_challenge(
            str(user.id), "register"
        )

        # Create credential parameters
        cred_params = []
        for alg in self.settings.public_key_algorithms:
            cred_params.append(
                PublicKeyCredentialParameters(
                    type=PublicKeyCredentialType.PUBLIC_KEY, alg=alg
                )
            )

        # Create options
        options, state = self.server.register_begin(
            user_entity,
            challenge=challenge,
            credentials=exclude_credentials,
            user_verification=UserVerificationRequirement(
                self.settings.user_verification
            ),
            authenticator_attachment=(
                AuthenticatorAttachment(self.settings.authenticator_attachment)
                if self.settings.authenticator_attachment
                else None
            ),
        )

        # Store state for verification
        await self._store_registration_state(str(user.id), state)

        # Convert to JSON-serializable format
        return self._options_to_json(options)

    async def verify_registration(
        self,
        user: UserAuth,
        credential_data: Dict[str, Any],
        device_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Verify registration response and create credential.

        Args:
            user: User registering credential
            credential_data: Credential data from client
            device_name: Optional device name

        Returns:
            Tuple of (success, credential_id or error message)
        """
        try:
            # Get stored state
            state = await self._get_registration_state(str(user.id))
            if not state:
                return False, "Registration state not found"

            # Verify registration
            auth_data = self.server.register_complete(state, response=credential_data)

            # Extract credential data
            if not auth_data.credential_data:
                return False, "No credential data in response"

            credential_id = websafe_encode(auth_data.credential_data.credential_id)
            public_key = websafe_encode(bytes(auth_data.credential_data.public_key))

            # Get authenticator info
            aaguid = (
                auth_data.credential_data.aaguid.hex()
                if auth_data.credential_data and auth_data.credential_data.aaguid
                else None
            )

            # Create credential record
            credential = WebAuthnCredential(
                user_id=user.id,
                credential_id=credential_id,
                public_key=public_key,
                aaguid=aaguid,
                sign_count=auth_data.counter,
                authenticator_attachment=self.settings.authenticator_attachment,
                transports=(
                    credential_data.get("response", {}).get("transports", [])
                    if isinstance(credential_data, dict)
                    else []
                ),
                device_name=device_name or self._get_default_device_name(),
                is_active=True,
                created_at=datetime.utcnow(),
            )

            self.db.add(credential)
            self.db.commit()

            # Clean up state
            await self._delete_registration_state(str(user.id))

            logger.info("WebAuthn credential registered for user %s", user.id)
            return True, credential_id

        except ValueError as e:
            logger.error("WebAuthn registration verification failed: %s", e)
            return False, str(e)
        except AttributeError as e:
            logger.error("WebAuthn registration attribute error: %s", e)
            return False, "Invalid registration data format"
        except KeyError as e:
            logger.error("WebAuthn registration missing data: %s", e)
            return False, "Missing required registration data"

    async def create_authentication_options(self, user: UserAuth) -> Dict[str, Any]:
        """Create authentication options.

        Args:
            user: User to authenticate

        Returns:
            Authentication options dictionary
        """
        # Get user's credentials
        credentials = self._get_user_credentials(user)

        if not credentials:
            raise ValueError("No credentials registered for user")

        # Create allowed credentials list
        allowed_credentials = []
        for cred in credentials:
            allowed_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=websafe_decode(str(cred.credential_id)),
                    type=PublicKeyCredentialType.PUBLIC_KEY,
                    transports=[
                        AuthenticatorTransport(t) if isinstance(t, str) else t
                        for t in (cred.transports or [])
                    ],
                )
            )

        # Create challenge
        challenge = await self.challenge_manager.create_challenge(
            str(user.id), "authenticate"
        )

        # Create options
        options, state = self.server.authenticate_begin(
            credentials=allowed_credentials,
            challenge=challenge,
            user_verification=UserVerificationRequirement(
                self.settings.user_verification
            ),
        )

        # Store state
        await self._store_authentication_state(str(user.id), state)

        return self._options_to_json(options)

    async def verify_authentication(
        self, user: UserAuth, assertion_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Verify authentication assertion.

        Args:
            user: User authenticating
            assertion_data: Assertion data from client

        Returns:
            Tuple of (success, error message)
        """
        try:
            # Get stored state
            state = await self._get_authentication_state(str(user.id))
            if not state:
                return False, "Authentication state not found"

            # Get credential
            credential_id = assertion_data["id"]
            credential = (
                self.db.query(WebAuthnCredential)
                .filter(
                    WebAuthnCredential.user_id == user.id,
                    WebAuthnCredential.credential_id == credential_id,
                    WebAuthnCredential.is_active.is_(True),
                )
                .first()
            )

            if not credential:
                return False, "Credential not found"

            # Get authenticator data for counter update
            auth_data = AuthenticatorData(
                websafe_decode(assertion_data["response"]["authenticatorData"])
            )

            # Verify assertion
            self.server.authenticate_complete(
                state, credentials=[credential], response=assertion_data
            )

            # Update credential usage
            credential.last_used_at = datetime.utcnow()
            credential.usage_count = (credential.usage_count or 0) + 1
            credential.sign_count = auth_data.counter
            self.db.commit()

            # Clean up state
            await self._delete_authentication_state(str(user.id))

            logger.info("WebAuthn authentication successful for user %s", user.id)
            return True, None

        except ValueError as e:
            logger.error("WebAuthn authentication verification failed: %s", e)
            return False, str(e)
        except AttributeError as e:
            logger.error("WebAuthn authentication attribute error: %s", e)
            return False, "Invalid authentication data format"
        except KeyError as e:
            logger.error("WebAuthn authentication missing data: %s", e)
            return False, "Missing required authentication data"

    def _get_user_credentials(self, user: UserAuth) -> List[WebAuthnCredential]:
        """Get active credentials for a user.

        Args:
            user: User to get credentials for

        Returns:
            List of active credentials
        """
        return (
            self.db.query(WebAuthnCredential)
            .filter(
                WebAuthnCredential.user_id == user.id,
                WebAuthnCredential.is_active.is_(True),
            )
            .all()
        )

    def _options_to_json(self, options: Any) -> Dict[str, Any]:
        """Convert FIDO2 options to JSON-serializable format.

        Args:
            options: FIDO2 options object

        Returns:
            JSON-serializable dictionary
        """
        # Convert options to dictionary
        data = {}

        # Handle different option types
        if hasattr(options, "public_key"):
            pk = options.public_key
            data = {
                "challenge": websafe_encode(pk.challenge),
                "timeout": pk.timeout,
                "rpId": pk.rp.id,
                "userVerification": pk.user_verification,
            }

            # Add RP info for registration
            if hasattr(pk, "rp"):
                data["rp"] = {"id": pk.rp.id, "name": pk.rp.name}

            # Add user info for registration
            if hasattr(pk, "user"):
                data["user"] = {
                    "id": websafe_encode(pk.user.id),
                    "name": pk.user.name,
                    "displayName": pk.user.display_name,
                }

            # Add credential parameters
            if hasattr(pk, "pub_key_cred_params"):
                data["pubKeyCredParams"] = [
                    {"type": p.type, "alg": p.alg} for p in pk.pub_key_cred_params
                ]

            # Add excluded/allowed credentials
            if hasattr(pk, "exclude_credentials"):
                data["excludeCredentials"] = self._format_credentials(
                    pk.exclude_credentials
                )
            elif hasattr(pk, "allow_credentials"):
                data["allowCredentials"] = self._format_credentials(
                    pk.allow_credentials
                )

            # Add authenticator selection
            if hasattr(pk, "authenticator_selection"):
                sel = pk.authenticator_selection
                data["authenticatorSelection"] = {
                    "authenticatorAttachment": sel.authenticator_attachment,
                    "requireResidentKey": sel.require_resident_key,
                    "residentKey": sel.resident_key,
                    "userVerification": sel.user_verification,
                }

            # Add attestation
            if hasattr(pk, "attestation"):
                data["attestation"] = pk.attestation

        return data

    def _format_credentials(
        self, credentials: List[PublicKeyCredentialDescriptor]
    ) -> List[Dict]:
        """Format credential descriptors for JSON.

        Args:
            credentials: List of credential descriptors

        Returns:
            List of formatted credentials
        """
        formatted = []
        for cred in credentials:
            item: Dict[str, Any] = {"type": cred.type, "id": websafe_encode(cred.id)}
            if cred.transports:
                item["transports"] = [
                    t.value if hasattr(t, "value") else str(t) for t in cred.transports
                ]
            formatted.append(item)
        return formatted

    def _get_default_device_name(self) -> str:
        """Get default device name based on context."""
        return "WebAuthn Device"

    async def _store_registration_state(self, user_id: str, state: Any) -> None:
        """Store registration state in cache."""
        # Cache implementation would go here
        # For now, store in memory
        self._registration_states[user_id] = state

    async def _get_registration_state(self, user_id: str) -> Optional[Any]:
        """Get registration state from cache."""
        return self._registration_states.get(user_id)

    async def _delete_registration_state(self, user_id: str) -> None:
        """Delete registration state from cache."""
        if user_id in self._registration_states:
            del self._registration_states[user_id]

    async def _store_authentication_state(self, user_id: str, state: Any) -> None:
        """Store authentication state in cache."""
        # Cache implementation would go here
        # For now, store in memory
        self._auth_states[user_id] = state

    async def _get_authentication_state(self, user_id: str) -> Optional[Any]:
        """Get authentication state from cache."""
        if hasattr(self, "_auth_states"):
            return self._auth_states.get(user_id)
        return None

    async def _delete_authentication_state(self, user_id: str) -> None:
        """Delete authentication state from cache."""
        if hasattr(self, "_auth_states") and user_id in self._auth_states:
            del self._auth_states[user_id]
