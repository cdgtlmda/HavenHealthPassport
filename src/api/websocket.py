"""WebSocket connection handling for GraphQL subscriptions.

This module implements WebSocket connection management, authentication,
and lifecycle handling for real-time GraphQL subscriptions.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

import jwt
from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Bearer token security scheme
security = HTTPBearer()

# Module-level dependency variables to avoid B008 errors
security_dependency = Depends(security)


class ConnectionManager:
    """Manages WebSocket connections for GraphQL subscriptions."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self.subscription_connections: Dict[str, Set[str]] = (
            {}
        )  # subscription_id -> connection_ids

    async def connect(
        self, websocket: WebSocket, connection_id: str, user_data: Dict[str, Any]
    ) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()

        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "user_id": user_data.get("user_id"),
            "user_role": user_data.get("role"),
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "subscriptions": set(),
        }

        # Start heartbeat task
        self.heartbeat_tasks[connection_id] = asyncio.create_task(
            self._heartbeat_loop(connection_id)
        )

        logger.info(
            f"WebSocket connection established: {connection_id} for user {user_data.get('user_id')}"
        )

        # Send connection acknowledgment
        await self.send_message(
            connection_id,
            {
                "type": "connection_ack",
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def disconnect(self, connection_id: str) -> None:
        """Disconnect and clean up a WebSocket connection."""
        if connection_id in self.active_connections:
            # Cancel heartbeat task
            if connection_id in self.heartbeat_tasks:
                self.heartbeat_tasks[connection_id].cancel()
                del self.heartbeat_tasks[connection_id]

            # Clean up subscriptions
            metadata = self.connection_metadata.get(connection_id, {})
            for subscription_id in metadata.get("subscriptions", set()):
                if subscription_id in self.subscription_connections:
                    self.subscription_connections[subscription_id].discard(
                        connection_id
                    )
                    if not self.subscription_connections[subscription_id]:
                        del self.subscription_connections[subscription_id]

            # Remove connection
            del self.active_connections[connection_id]
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

            logger.info(f"WebSocket connection closed: {connection_id}")

    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)
                # Update last activity
                if connection_id in self.connection_metadata:
                    self.connection_metadata[connection_id][
                        "last_activity"
                    ] = datetime.utcnow()
            except (ConnectionError, WebSocketDisconnect, AttributeError) as e:
                logger.error(f"Error sending message to {connection_id}: {e}")
                await self.disconnect(connection_id)

    async def broadcast_to_subscription(
        self, subscription_id: str, message: Dict[str, Any]
    ) -> None:
        """Broadcast a message to all connections subscribed to a specific subscription."""
        connection_ids = self.subscription_connections.get(
            subscription_id, set()
        ).copy()
        for connection_id in connection_ids:
            await self.send_message(connection_id, message)

    def add_subscription(self, connection_id: str, subscription_id: str) -> None:
        """Add a subscription to a connection."""
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["subscriptions"].add(
                subscription_id
            )

            if subscription_id not in self.subscription_connections:
                self.subscription_connections[subscription_id] = set()
            self.subscription_connections[subscription_id].add(connection_id)

    def remove_subscription(self, connection_id: str, subscription_id: str) -> None:
        """Remove a subscription from a connection."""
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["subscriptions"].discard(
                subscription_id
            )

            if subscription_id in self.subscription_connections:
                self.subscription_connections[subscription_id].discard(connection_id)
                if not self.subscription_connections[subscription_id]:
                    del self.subscription_connections[subscription_id]

    async def _heartbeat_loop(self, connection_id: str) -> None:
        """Send periodic heartbeat messages to keep connection alive."""
        try:
            while connection_id in self.active_connections:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds

                # Check for stale connection
                metadata = self.connection_metadata.get(connection_id, {})
                last_activity = metadata.get("last_activity")

                if last_activity and (datetime.utcnow() - last_activity) > timedelta(
                    minutes=5
                ):
                    logger.warning(f"Closing stale connection: {connection_id}")
                    await self.disconnect(connection_id)
                    break

                # Send heartbeat
                await self.send_message(
                    connection_id,
                    {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()},
                )

        except (asyncio.CancelledError, asyncio.TimeoutError) as e:
            logger.warning(f"Heartbeat loop cancelled for {connection_id}: {e}")
        except (ConnectionError, WebSocketDisconnect, AttributeError) as e:
            logger.error(f"Error in heartbeat loop for {connection_id}: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security_dependency,
) -> Dict[str, Any]:
    """Validate JWT token and return user data."""
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )

        # Check token expiration
        if payload.get("exp", 0) < datetime.utcnow().timestamp():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )

        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
        }

    except jwt.PyJWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from e


class WebSocketAuthMiddleware:
    """Middleware for WebSocket authentication."""

    @staticmethod
    async def authenticate(websocket: WebSocket) -> Optional[Dict[str, Any]]:
        """Authenticate WebSocket connection."""
        # Try to get token from query parameters
        token = websocket.query_params.get("token")

        if not token:
            # Try to get from first message
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                if message.get("type") == "connection_init":
                    token = message.get("payload", {}).get("token")
            except asyncio.TimeoutError:
                return None

        if not token:
            return None

        # Validate token
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )

            if payload.get("exp", 0) < datetime.utcnow().timestamp():
                return None

            return {
                "user_id": payload.get("sub"),
                "role": payload.get("role"),
                "permissions": payload.get("permissions", []),
            }

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
            logger.error("WebSocket authentication error", exc_info=True)
            return None


async def handle_websocket_connection(websocket: WebSocket) -> None:
    """Handle a WebSocket connection for GraphQL subscriptions."""
    connection_id = str(uuid.uuid4())
    user_data = None

    try:
        # Authenticate connection
        user_data = await WebSocketAuthMiddleware.authenticate(websocket)

        if not user_data:
            await websocket.close(code=4001, reason="Authentication required")
            return

        # Connect
        await connection_manager.connect(websocket, connection_id, user_data)

        # Handle messages
        while True:
            try:
                message = await websocket.receive_json()
                await handle_websocket_message(connection_id, message, user_data)

            except WebSocketDisconnect:
                break
            except (json.JSONDecodeError, ValueError):
                logger.error("Error handling WebSocket message", exc_info=True)
                await connection_manager.send_message(
                    connection_id, {"type": "error", "message": "Internal error"}
                )

    except (ConnectionError, WebSocketDisconnect):
        logger.error("WebSocket connection error", exc_info=True)

    finally:
        await connection_manager.disconnect(connection_id)


async def handle_websocket_message(
    connection_id: str, message: Dict[str, Any], user_data: Optional[Dict[str, Any]]
) -> None:
    """Handle incoming WebSocket messages."""
    # Currently user_data is unused but will be used for authorization checks
    _ = user_data  # Acknowledge unused parameter
    message_type = message.get("type")

    if message_type == "subscribe":
        # Handle subscription request
        # Currently payload is extracted but not used - will be used for GraphQL integration
        payload = message.get("payload", {})
        _ = payload  # Acknowledge unused variable
        subscription_id = message.get("id")
        if not subscription_id:
            return
        # Execute subscription
        # This would integrate with the GraphQL subscription resolver
        try:
            # Add subscription
            connection_manager.add_subscription(connection_id, subscription_id)

            # Send subscription confirmation
            await connection_manager.send_message(
                connection_id,
                {
                    "id": subscription_id,
                    "type": "subscription_ack",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            logger.info(
                f"Subscription {subscription_id} started for connection {connection_id}"
            )

        except (KeyError, ValueError, AttributeError):
            await connection_manager.send_message(
                connection_id,
                {
                    "id": subscription_id,
                    "type": "subscription_error",
                    "payload": {"message": "Subscription error"},
                },
            )

    elif message_type == "unsubscribe":
        # Handle unsubscribe request
        subscription_id = message.get("id")
        if subscription_id:
            connection_manager.remove_subscription(connection_id, subscription_id)

        # Send confirmation
        await connection_manager.send_message(
            connection_id,
            {
                "id": subscription_id,
                "type": "unsubscribe_ack",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            f"Subscription {subscription_id} stopped for connection {connection_id}"
        )

    elif message_type == "ping":
        # Respond to ping
        await connection_manager.send_message(
            connection_id, {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
        )

    else:
        # Unknown message type
        await connection_manager.send_message(
            connection_id,
            {"type": "error", "message": f"Unknown message type: {message_type}"},
        )


# Export for use in FastAPI app
__all__ = ["connection_manager", "handle_websocket_connection", "get_current_user"]
