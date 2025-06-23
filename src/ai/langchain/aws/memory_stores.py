"""
DynamoDB Memory Store for LangChain.

Provides persistent conversation memory using DynamoDB
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)


class DynamoDBMemoryStore:
    """DynamoDB-backed memory store for conversations."""

    def __init__(
        self,
        table_name: str,
        session_id: str,
        dynamodb_resource: Optional[Any] = None,
        ttl_days: int = 30,
    ):
        """
        Initialize DynamoDB memory store.

        Args:
            table_name: DynamoDB table name
            session_id: Unique session identifier
            dynamodb_resource: Optional DynamoDB resource
            ttl_days: TTL for memory items in days
        """
        self.table_name = table_name
        self.session_id = session_id
        self.ttl_days = ttl_days

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Ensure DynamoDB table exists with proper schema."""
        try:
            self.table.table_status
        except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
            logger.info("Creating DynamoDB table: %s", self.table_name)
            self._create_table()

    def _create_table(self) -> None:
        """Create DynamoDB table for memory storage."""
        self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
            TimeToLiveSpecification={"AttributeName": "ttl", "Enabled": True},
        )

        # Wait for table to be created
        self.table.wait_until_exists()

    def save_message(self, message: BaseMessage) -> None:
        """Save a message to DynamoDB."""
        timestamp = int(time.time() * 1000)
        ttl = int((datetime.now() + timedelta(days=self.ttl_days)).timestamp())

        item = {
            "session_id": self.session_id,
            "timestamp": timestamp,
            "message_type": message.__class__.__name__,
            "content": message.content,
            "additional_kwargs": message.additional_kwargs,
            "ttl": ttl,
        }
        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            logger.error("Failed to save message: %s", str(e))

    def get_messages(self, limit: int = 100) -> List[BaseMessage]:
        """Retrieve messages from DynamoDB."""
        try:
            response = self.table.query(
                KeyConditionExpression=Key("session_id").eq(self.session_id),
                ScanIndexForward=True,  # Sort by timestamp ascending
                Limit=limit,
            )

            messages: List[BaseMessage] = []
            for item in response["Items"]:
                message_type = item["message_type"]
                content = item["content"]

                if message_type == "HumanMessage":
                    messages.append(HumanMessage(content=content))
                elif message_type == "AIMessage":
                    messages.append(AIMessage(content=content))

            return messages

        except ClientError as e:
            logger.error("Failed to retrieve messages: %s", str(e))
            return []

    def clear(self) -> None:
        """Clear all messages for the session."""
        try:
            # Query all items for the session
            response = self.table.query(
                KeyConditionExpression=Key("session_id").eq(self.session_id)
            )

            # Delete each item
            with self.table.batch_writer() as batch:
                for item in response["Items"]:
                    batch.delete_item(
                        Key={
                            "session_id": self.session_id,
                            "timestamp": item["timestamp"],
                        }
                    )

        except ClientError as e:
            logger.error("Failed to clear messages: %s", str(e))
