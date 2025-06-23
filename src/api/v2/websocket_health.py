"""Real-time WebSocket endpoints for Haven Health Passport.

This module provides WebSocket connections for real-time updates on health
monitoring, analysis progress, treatment plans, and system status.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.auth.jwt_handler import jwt_handler
from src.auth.rbac import RBACManager
from src.healthcare.fhir.validators import FHIRValidator
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)
rbac_manager = RBACManager()


class EventType(str, Enum):
    """Types of real-time events."""

    # Health monitoring events
    VITAL_SIGN_UPDATE = "vital_sign_update"
    LAB_RESULT_AVAILABLE = "lab_result_available"
    MEDICATION_REMINDER = "medication_reminder"
    HEALTH_ALERT = "health_alert"

    # Analysis events
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_PROGRESS = "analysis_progress"
    ANALYSIS_COMPLETED = "analysis_completed"
    INSIGHT_GENERATED = "insight_generated"

    # Treatment/Remediation events
    TREATMENT_PLAN_UPDATED = "treatment_plan_updated"
    ACTION_REQUIRED = "action_required"
    APPOINTMENT_REMINDER = "appointment_reminder"
    PRESCRIPTION_READY = "prescription_ready"

    # System events
    SYSTEM_NOTIFICATION = "system_notification"
    MAINTENANCE_ALERT = "maintenance_alert"
    SYNC_STATUS = "sync_status"
    VERIFICATION_STATUS = "verification_status"


class EventPriority(str, Enum):
    """Event priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class HealthEvent(BaseModel):
    """Real-time health event model."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    priority: EventPriority = EventPriority.NORMAL
    patient_id: Optional[uuid.UUID] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class SubscriptionRequest(BaseModel):
    """WebSocket subscription request."""

    subscription_type: str = Field(..., description="Type of events to subscribe to")
    filters: Optional[Dict[str, Any]] = Field(None, description="Event filters")
    patient_ids: Optional[List[uuid.UUID]] = Field(
        None, description="Specific patients to monitor"
    )


class HealthConnectionManager:
    """Manages WebSocket connections for health-related real-time updates."""

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.connection_subscriptions: Dict[str, Set[str]] = (
            {}
        )  # connection_id -> subscriptions
        self.subscription_connections: Dict[str, Set[str]] = (
            {}
        )  # subscription -> connection_ids
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.fhir_validator = FHIRValidator()
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

    async def connect(self, websocket: WebSocket, user_id: str) -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())

        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
        }

        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)

        logger.info(f"Health WebSocket connected: {connection_id} for user {user_id}")

        # Send connection acknowledgment
        await self.send_personal_message(
            connection_id,
            {
                "type": "connection_established",
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Disconnect and clean up a WebSocket connection."""
        if connection_id in self.active_connections:
            # Get user_id before cleanup
            user_id = self.connection_metadata.get(connection_id, {}).get("user_id")

            # Remove from active connections
            del self.active_connections[connection_id]

            # Clean up user connections
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            # Clean up subscriptions
            if connection_id in self.connection_subscriptions:
                for subscription in self.connection_subscriptions[connection_id]:
                    if subscription in self.subscription_connections:
                        self.subscription_connections[subscription].discard(
                            connection_id
                        )
                        if not self.subscription_connections[subscription]:
                            del self.subscription_connections[subscription]
                del self.connection_subscriptions[connection_id]

            # Remove metadata
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

            logger.info(f"Health WebSocket disconnected: {connection_id}")

    async def send_personal_message(
        self, connection_id: str, message: Dict[str, Any]
    ) -> None:
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)
                self.connection_metadata[connection_id][
                    "last_activity"
                ] = datetime.utcnow()
            except (WebSocketDisconnect, ConnectionError) as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                await self.disconnect(connection_id)

    async def broadcast_event(self, event: HealthEvent) -> None:
        """Broadcast an event to all relevant subscribers."""
        # Get all connections subscribed to this event type
        connection_ids = self.subscription_connections.get(
            str(event.event_type), set()
        ).copy()

        # Also get connections subscribed to specific patient events
        if event.patient_id:
            patient_subscription = f"patient:{event.patient_id}"
            connection_ids.update(
                self.subscription_connections.get(patient_subscription, set())
            )

        # Send to all relevant connections
        for connection_id in connection_ids:
            await self.send_personal_message(connection_id, event.model_dump())

    def validate_fhir_resource(self, resource: dict) -> bool:
        """Validate FHIR resource structure and requirements."""
        return self.fhir_validator.validate_resource(resource)

    @audit_phi_access("process_phi_data")
    @require_permission(AccessPermission.READ_PHI)
    def process_with_phi_protection(self, data: dict) -> dict:
        """Process data with PHI protection and audit logging."""
        # Encrypt sensitive fields
        sensitive_fields = ["name", "birthDate", "ssn", "address"]
        encrypted_data = data.copy()

        for field in sensitive_fields:
            if field in encrypted_data:
                encrypted_data[field] = self.encryption_service.encrypt(
                    str(encrypted_data[field]).encode("utf-8")
                )

        return encrypted_data

    def subscribe(self, connection_id: str, subscription: str) -> None:
        """Subscribe a connection to specific events."""
        if connection_id not in self.connection_subscriptions:
            self.connection_subscriptions[connection_id] = set()

        self.connection_subscriptions[connection_id].add(subscription)

        if subscription not in self.subscription_connections:
            self.subscription_connections[subscription] = set()
        self.subscription_connections[subscription].add(connection_id)

        logger.info(f"Connection {connection_id} subscribed to {subscription}")

    def unsubscribe(self, connection_id: str, subscription: str) -> None:
        """Unsubscribe a connection from specific events."""
        if connection_id in self.connection_subscriptions:
            self.connection_subscriptions[connection_id].discard(subscription)

        if subscription in self.subscription_connections:
            self.subscription_connections[subscription].discard(connection_id)
            if not self.subscription_connections[subscription]:
                del self.subscription_connections[subscription]


# Create global instance
health_connection_manager = HealthConnectionManager()


async def authenticate_websocket(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    """Authenticate WebSocket connection using token from query params or headers."""
    # Try to get token from query parameters
    token = websocket.query_params.get("token")

    if not token:
        # Try to get from headers
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    try:
        payload = jwt_handler.verify_token(token)
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "organization": payload.get("organization"),
        }
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        return None


@router.websocket("/ws/health")
async def health_websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connections for real-time health updates."""
    connection_id = None

    try:
        # Authenticate the connection
        user_data = await authenticate_websocket(websocket)

        if not user_data:
            await websocket.close(code=4001, reason="Authentication required")
            return

        # Connect
        connection_id = await health_connection_manager.connect(
            websocket, user_data["user_id"]
        )

        # Handle messages
        while True:
            try:
                data = await websocket.receive_json()
                await handle_health_websocket_message(connection_id, data, user_data)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await health_connection_manager.send_personal_message(
                    connection_id, {"type": "error", "message": "Invalid JSON format"}
                )
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await health_connection_manager.send_personal_message(
                    connection_id, {"type": "error", "message": "Internal server error"}
                )

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        if connection_id:
            await health_connection_manager.disconnect(connection_id)


async def handle_health_websocket_message(
    connection_id: str, message: Dict[str, Any], user_data: Dict[str, Any]
) -> None:
    """Handle incoming WebSocket messages for health updates."""
    message_type = message.get("type")

    if message_type == "subscribe":
        # Handle subscription request
        subscription_data = message.get("data", {})
        event_types = subscription_data.get("event_types", [])
        patient_ids = subscription_data.get("patient_ids", [])

        # Check permissions for requested subscriptions
        for event_type in event_types:
            # Verify user has permission to subscribe to this event type
            if await check_subscription_permission(user_data, event_type, patient_ids):
                health_connection_manager.subscribe(connection_id, event_type)

                # Subscribe to specific patient events if requested
                for patient_id in patient_ids:
                    health_connection_manager.subscribe(
                        connection_id, f"patient:{patient_id}"
                    )

        await health_connection_manager.send_personal_message(
            connection_id,
            {
                "type": "subscription_confirmed",
                "subscriptions": list(
                    health_connection_manager.connection_subscriptions.get(
                        connection_id, set()
                    )
                ),
            },
        )

    elif message_type == "unsubscribe":
        # Handle unsubscribe request
        subscription_data = message.get("data", {})
        event_types = subscription_data.get("event_types", [])

        for event_type in event_types:
            health_connection_manager.unsubscribe(connection_id, event_type)

        await health_connection_manager.send_personal_message(
            connection_id,
            {"type": "unsubscribe_confirmed", "unsubscribed": event_types},
        )

    elif message_type == "ping":
        # Respond to ping
        await health_connection_manager.send_personal_message(
            connection_id, {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
        )

    else:
        # Unknown message type
        await health_connection_manager.send_personal_message(
            connection_id,
            {"type": "error", "message": f"Unknown message type: {message_type}"},
        )


async def check_subscription_permission(
    user_data: Dict[str, Any], event_type: str, patient_ids: List[str]
) -> bool:
    """Check if user has permission to subscribe to specific events."""
    # Healthcare providers can subscribe to their patients' events
    if user_data.get("role") in ["doctor", "nurse", "healthcare_provider"]:
        return True

    # Patients can only subscribe to their own events
    if user_data.get("role") == "patient":
        user_patient_id = user_data.get("patient_id")
        if patient_ids and str(user_patient_id) not in [
            str(pid) for pid in patient_ids
        ]:
            return False
        return True

    # Admins can subscribe to system events
    if user_data.get("role") == "admin" and event_type.startswith("SYSTEM_"):
        return True

    return False


# Event emission functions for use by other services
async def emit_health_event(event: HealthEvent) -> None:
    """Emit a health event to all relevant subscribers."""
    await health_connection_manager.broadcast_event(event)


async def emit_vital_sign_update(
    patient_id: uuid.UUID, vital_data: Dict[str, Any]
) -> None:
    """Emit a vital sign update event."""
    event = HealthEvent(
        event_type=EventType.VITAL_SIGN_UPDATE,
        priority=EventPriority.NORMAL,
        patient_id=patient_id,
        data=vital_data,
    )
    await emit_health_event(event)


async def emit_analysis_progress(
    patient_id: uuid.UUID, analysis_id: str, progress: int, status: str
) -> None:
    """Emit an analysis progress update."""
    event = HealthEvent(
        event_type=EventType.ANALYSIS_PROGRESS,
        priority=EventPriority.NORMAL,
        patient_id=patient_id,
        data={"analysis_id": analysis_id, "progress": progress, "status": status},
    )
    await emit_health_event(event)


async def emit_health_alert(
    patient_id: uuid.UUID, alert_type: str, severity: str, message: str
) -> None:
    """Emit a health alert event."""
    priority_map = {
        "low": EventPriority.LOW,
        "medium": EventPriority.NORMAL,
        "high": EventPriority.HIGH,
        "critical": EventPriority.CRITICAL,
    }

    event = HealthEvent(
        event_type=EventType.HEALTH_ALERT,
        priority=priority_map.get(severity, EventPriority.HIGH),
        patient_id=patient_id,
        data={"alert_type": alert_type, "severity": severity, "message": message},
    )
    await emit_health_event(event)
