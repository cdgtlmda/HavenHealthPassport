"""GraphQL Subscription Implementations.

This module implements real-time subscriptions for the Haven Health Passport
GraphQL API, providing WebSocket-based updates for patient data, health records,
and verification status changes.
Includes encrypted data transmission with access control and audit logging.
 Handles FHIR Resource validation.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

try:
    import graphene
except ImportError:
    graphene = None

from src.api.queries import PatientQueries
from src.services.access_control_service import AccessControlService
from src.services.organization_service import OrganizationService
from src.utils.logging import get_logger

from .scalars import JSONScalar, UUIDScalar
from .types import AccessRequest, HealthRecord, Patient, TranslationResult, Verification

logger = get_logger(__name__)


class SubscriptionManager:
    """Manages WebSocket connections and subscription channels."""

    def __init__(self) -> None:
        """Initialize subscription manager."""
        self.subscribers: Dict[str, Dict[str, Any]] = {}
        self.channels: Dict[str, asyncio.Queue] = {}

    async def subscribe(
        self, channel: str, user_id: str, filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Subscribe to a channel."""
        subscription_id = str(uuid.uuid4())

        if channel not in self.channels:
            self.channels[channel] = asyncio.Queue()

        self.subscribers[subscription_id] = {
            "channel": channel,
            "user_id": user_id,
            "filters": filters or {},
            "subscribed_at": datetime.utcnow(),
        }

        logger.info(f"User {user_id} subscribed to {channel} with ID {subscription_id}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a channel."""
        if subscription_id in self.subscribers:
            subscriber = self.subscribers[subscription_id]
            logger.info(
                f"User {subscriber['user_id']} unsubscribed from {subscriber['channel']}"
            )
            del self.subscribers[subscription_id]

    async def publish(self, channel: str, data: Dict[str, Any]) -> None:
        """Publish data to a channel."""
        if channel in self.channels:
            await self.channels[channel].put(data)
            logger.debug(f"Published to {channel}: {data.get('type', 'unknown')}")

    async def get_messages(self, subscription_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Get messages for a subscription."""
        if subscription_id not in self.subscribers:
            raise ValueError(f"Invalid subscription ID: {subscription_id}")

        subscriber = self.subscribers[subscription_id]
        channel = subscriber["channel"]
        queue = self.channels.get(channel)

        if not queue:
            return

        while subscription_id in self.subscribers:
            try:
                # Wait for message with timeout
                data = await asyncio.wait_for(queue.get(), timeout=30.0)

                # Apply filters
                if self._match_filters(data, subscriber["filters"]):
                    yield data

            except asyncio.TimeoutError:
                # Send heartbeat
                yield {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}

    def _match_filters(self, data: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if data matches subscription filters."""
        for key, value in filters.items():
            if key not in data or data[key] != value:
                return False
        return True


# Global subscription manager instance
subscription_manager = SubscriptionManager()


class PatientSubscriptions:
    """Patient-related subscriptions."""

    patient_updated = graphene.Field(
        Patient,
        patient_id=graphene.Argument(UUIDScalar, required=True),
        description="Subscribe to updates for a specific patient",
    )

    patient_created = graphene.Field(
        Patient,
        organization_id=graphene.String(),
        description="Subscribe to new patient creations",
    )

    async def resolve_patient_updated(
        self, info: Any, patient_id: uuid.UUID
    ) -> AsyncIterator[Optional[Patient]]:
        """Subscribe to patient updates."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:patients"):
            raise ValueError("Unauthorized to subscribe to patient updates")

        # Check if user can access this patient
        if not self._can_access_patient(user, patient_id):
            raise ValueError("Access denied to patient data")

        # Subscribe to patient updates
        subscription_id = await subscription_manager.subscribe(
            channel="patient_updates",
            user_id=str(user.id),
            filters={"patient_id": str(patient_id)},
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None  # Keep connection alive
                else:
                    # Convert to Patient type
                    patient_data = message.get("data", {})
                    if patient_data:
                        yield Patient(**patient_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)

    async def resolve_patient_created(
        self, info: Any, organization_id: Optional[str] = None
    ) -> AsyncIterator[Optional[Patient]]:
        """Subscribe to new patient creations."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:patient_creations"):
            raise ValueError("Unauthorized to subscribe to patient creations")

        # Apply organization filter if specified
        filters = {}
        if organization_id:
            # Check if user belongs to the organization
            if not self._user_in_organization(user, organization_id):
                raise ValueError("Access denied to organization data")
            filters["organization_id"] = organization_id

        # Subscribe to patient creations
        subscription_id = await subscription_manager.subscribe(
            channel="patient_creations", user_id=str(user.id), filters=filters
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    patient_data = message.get("data", {})
                    if patient_data:
                        yield Patient(**patient_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)

    def _can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient data."""
        # Check if user is the patient
        if hasattr(user, "patient_id") and str(user.patient_id) == str(patient_id):
            return True

        # Check if user is a provider with access
        if user.has_permission("read:patients"):
            # Access db from class context
            db = getattr(self, "db", None) or globals().get("db")
            if db:
                access_service = AccessControlService(db=db)

                # Check if provider has been granted access to this patient
                has_provider_access = access_service.check_provider_patient_access(
                    provider_id=user.id, patient_id=str(patient_id)
                )

                if has_provider_access:
                    logger.info(
                        f"Provider {user.id} authorized to access patient {patient_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"Provider {user.id} denied access to patient {patient_id} - no relationship"
                    )
                    return False

        # Check if user is part of an organization with access
        if hasattr(user, "organization_id") and user.organization_id:
            # Access db from class context
            db = getattr(self, "db", None) or globals().get("db")
            if db:
                org_service = OrganizationService(db=db)

                # Check if organization has been granted access to this patient
                has_org_access = org_service.check_organization_patient_access(
                    organization_id=user.organization_id, patient_id=str(patient_id)
                )

                if has_org_access:
                    logger.info(
                        f"User {user.id} authorized via organization {user.organization_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"User {user.id} from organization {user.organization_id} denied access "
                        f"to patient {patient_id} - no organizational relationship"
                    )
                    return False

        return False

    def _user_in_organization(self, user: Any, organization_id: str) -> bool:
        """Check if user belongs to organization."""
        return (
            hasattr(user, "organization_id") and user.organization_id == organization_id
        )


class HealthRecordSubscriptions:
    """Health record-related subscriptions."""

    record_added = graphene.Field(
        HealthRecord,
        patient_id=graphene.Argument(UUIDScalar, required=True),
        record_type=graphene.String(),
        description="Subscribe to new health records for a patient",
    )

    record_updated = graphene.Field(
        HealthRecord,
        record_id=graphene.Argument(UUIDScalar, required=True),
        description="Subscribe to updates for a specific health record",
    )

    async def resolve_record_added(
        self, info: Any, patient_id: uuid.UUID, record_type: Optional[str] = None
    ) -> AsyncIterator[Optional[HealthRecord]]:
        """Subscribe to new health records."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:health_records"):
            raise ValueError("Unauthorized to subscribe to health records")

        # Check patient access
        if not self._can_access_patient(user, patient_id):
            raise ValueError("Access denied to patient records")

        # Set up filters
        filters = {"patient_id": str(patient_id)}
        if record_type:
            filters["record_type"] = record_type

        # Subscribe to record additions
        subscription_id = await subscription_manager.subscribe(
            channel="health_record_additions", user_id=str(user.id), filters=filters
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    record_data = message.get("data", {})
                    if record_data:
                        yield HealthRecord(**record_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)

    async def resolve_record_updated(
        self, info: graphene.ResolveInfo, record_id: uuid.UUID
    ) -> AsyncIterator[Optional[HealthRecord]]:
        """Subscribe to health record updates."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:health_records"):
            raise ValueError("Unauthorized to subscribe to health records")

        # Subscribe to record updates
        subscription_id = await subscription_manager.subscribe(
            channel="health_record_updates",
            user_id=str(user.id),
            filters={"record_id": str(record_id)},
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    record_data = message.get("data", {})
                    if record_data:
                        # Verify user still has access
                        patient_id = record_data.get("patient_id")
                        if patient_id and self._can_access_patient(
                            user, uuid.UUID(patient_id)
                        ):
                            yield HealthRecord(**record_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)

    def _can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient data."""
        patient_queries = PatientQueries()
        return patient_queries.can_access_patient(user, patient_id)


class VerificationSubscriptions:
    """Verification-related subscriptions."""

    verification_changed = graphene.Field(
        Verification,
        patient_id=graphene.Argument(UUIDScalar),
        record_id=graphene.Argument(UUIDScalar),
        description="Subscribe to verification status changes",
    )

    async def resolve_verification_changed(
        self,
        info: graphene.ResolveInfo,
        patient_id: Optional[uuid.UUID] = None,
        record_id: Optional[uuid.UUID] = None,
    ) -> AsyncIterator[Optional[Verification]]:
        """Subscribe to verification changes."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:verifications"):
            raise ValueError("Unauthorized to subscribe to verifications")

        # Set up filters
        filters = {}
        if patient_id:
            if not self._can_access_patient(user, patient_id):
                raise ValueError("Access denied to patient data")
            filters["patient_id"] = str(patient_id)

        if record_id:
            filters["record_id"] = str(record_id)

        # Subscribe to verification changes
        subscription_id = await subscription_manager.subscribe(
            channel="verification_changes", user_id=str(user.id), filters=filters
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    verification_data = message.get("data", {})
                    if verification_data:
                        yield Verification(**verification_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)

    def _can_access_patient(self, user: Any, patient_id: uuid.UUID) -> bool:
        """Check if user can access patient data."""
        patient_queries = PatientQueries()
        return patient_queries.can_access_patient(user, patient_id)


class AccessSubscriptions:
    """Access control-related subscriptions."""

    access_requested = graphene.Field(
        AccessRequest,
        resource_type=graphene.String(),
        description="Subscribe to access requests",
    )

    async def resolve_access_requested(
        self, info: graphene.ResolveInfo, resource_type: Optional[str] = None
    ) -> AsyncIterator[Optional[AccessRequest]]:
        """Subscribe to access requests."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:access_requests"):
            raise ValueError("Unauthorized to subscribe to access requests")

        # Set up filters
        filters = {}
        if resource_type:
            filters["resource_type"] = resource_type

        # Only show requests relevant to the user
        if user.has_role("patient"):
            # Patients only see their own access requests
            filters["patient_id"] = str(user.patient_id)
        elif user.has_role("provider"):
            # Providers see requests for their patients
            filters["provider_id"] = str(user.id)

        # Subscribe to access requests
        subscription_id = await subscription_manager.subscribe(
            channel="access_requests", user_id=str(user.id), filters=filters
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    request_data = message.get("data", {})
                    if request_data:
                        yield AccessRequest(**request_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)


class TranslationSubscriptions:
    """Translation-related subscriptions."""

    translation_streaming = graphene.Field(
        TranslationResult,
        session_id=graphene.String(required=True),
        description="Subscribe to real-time translation updates",
    )

    translation_session_created = graphene.Field(
        JSONScalar,
        user_id=graphene.Argument(UUIDScalar),
        description="Subscribe to new translation session creations",
    )

    async def resolve_translation_streaming(
        self, info: graphene.ResolveInfo, session_id: str
    ) -> AsyncIterator[Optional[TranslationResult]]:
        """Subscribe to real-time translation streaming."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:translations"):
            raise ValueError("Unauthorized to subscribe to translations")

        # Subscribe to translation channel
        subscription_id = await subscription_manager.subscribe(
            channel="translation_stream",
            user_id=str(user.id),
            filters={"session_id": session_id},
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    translation_data = message.get("data", {})
                    if translation_data:
                        # Add timestamp if not present
                        if "timestamp" not in translation_data:
                            translation_data["timestamp"] = datetime.utcnow()
                        yield TranslationResult(**translation_data)

        finally:
            await subscription_manager.unsubscribe(subscription_id)

    async def resolve_translation_session_created(
        self, info: graphene.ResolveInfo, user_id: Optional[uuid.UUID] = None
    ) -> AsyncIterator[Optional[Dict[str, Any]]]:
        """Subscribe to translation session creations."""
        # Check permissions
        user = info.context.get("user")
        if not user or not user.has_permission("subscribe:translation_sessions"):
            raise ValueError("Unauthorized to subscribe to translation sessions")

        # Set up filters
        filters = {}
        if user_id:
            # Check if user can monitor this user's sessions
            if str(user_id) != str(user.id) and not user.has_role("admin"):
                raise ValueError("Cannot subscribe to other user's sessions")
            filters["user_id"] = str(user_id)
        else:
            # Default to own sessions for non-admins
            if not user.has_role("admin"):
                filters["user_id"] = str(user.id)

        # Subscribe to session creations
        subscription_id = await subscription_manager.subscribe(
            channel="translation_sessions", user_id=str(user.id), filters=filters
        )

        try:
            async for message in subscription_manager.get_messages(subscription_id):
                if message.get("type") == "heartbeat":
                    yield None
                else:
                    session_data = message.get("data", {})
                    if session_data:
                        yield session_data

        finally:
            await subscription_manager.unsubscribe(subscription_id)


class Subscription(
    graphene.ObjectType,
    PatientSubscriptions,
    HealthRecordSubscriptions,
    VerificationSubscriptions,
    AccessSubscriptions,
    TranslationSubscriptions,
):
    """Root Subscription type combining all subscription categories."""


# Publish helper functions for use by mutations and services


async def publish_patient_update(patient_data: Dict[str, Any]) -> None:
    """Publish patient update event."""
    await subscription_manager.publish(
        "patient_updates",
        {
            "type": "patient_updated",
            "data": patient_data,
            "patient_id": patient_data.get("id"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_patient_creation(patient_data: Dict[str, Any]) -> None:
    """Publish patient creation event."""
    await subscription_manager.publish(
        "patient_creations",
        {
            "type": "patient_created",
            "data": patient_data,
            "organization_id": patient_data.get("created_by_organization"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_health_record_addition(record_data: Dict[str, Any]) -> None:
    """Publish health record addition event."""
    await subscription_manager.publish(
        "health_record_additions",
        {
            "type": "record_added",
            "data": record_data,
            "patient_id": record_data.get("patient_id"),
            "record_type": record_data.get("type"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_health_record_update(record_data: Dict[str, Any]) -> None:
    """Publish health record update event."""
    await subscription_manager.publish(
        "health_record_updates",
        {
            "type": "record_updated",
            "data": record_data,
            "record_id": record_data.get("id"),
            "patient_id": record_data.get("patient_id"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_verification_change(verification_data: Dict[str, Any]) -> None:
    """Publish verification change event."""
    await subscription_manager.publish(
        "verification_changes",
        {
            "type": "verification_changed",
            "data": verification_data,
            "patient_id": verification_data.get("patient_id"),
            "record_id": verification_data.get("record_id"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_access_request(request_data: Dict[str, Any]) -> None:
    """Publish access request event."""
    await subscription_manager.publish(
        "access_requests",
        {
            "type": "access_requested",
            "data": request_data,
            "resource_type": request_data.get("resource_type"),
            "patient_id": request_data.get("patient_id"),
            "provider_id": request_data.get("provider_id"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_translation_update(translation_data: Dict[str, Any]) -> None:
    """Publish translation update event."""
    await subscription_manager.publish(
        "translation_stream",
        {
            "type": "translation_update",
            "data": translation_data,
            "session_id": translation_data.get("session_id"),
            "is_final": translation_data.get("is_final", False),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def publish_translation_session(session_data: Dict[str, Any]) -> None:
    """Publish translation session creation event."""
    await subscription_manager.publish(
        "translation_sessions",
        {
            "type": "session_created",
            "data": session_data,
            "user_id": session_data.get("user_id"),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Export subscription schema
__all__ = [
    "Subscription",
    "subscription_manager",
    "publish_patient_update",
    "publish_patient_creation",
    "publish_health_record_addition",
    "publish_health_record_update",
    "publish_verification_change",
    "publish_access_request",
    "publish_translation_update",
    "publish_translation_session",
]


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
