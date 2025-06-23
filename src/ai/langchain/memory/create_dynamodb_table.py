#!/usr/bin/env python3
"""Create DynamoDB table for LangChain memory storage."""

import sys

import boto3
from botocore.exceptions import ClientError


def create_memory_table(
    table_name: str = "haven-health-langchain-memory", region: str = "us-east-1"
) -> None:
    """Create DynamoDB table for memory storage."""
    dynamodb = boto3.client("dynamodb", region_name=region)

    table_config = {
        "TableName": table_name,
        "KeySchema": [
            {"AttributeName": "memory_key", "KeyType": "HASH"},
            {"AttributeName": "version", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "memory_key", "AttributeType": "S"},
            {"AttributeName": "version", "AttributeType": "N"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "N"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user_id_index",
                "Keys": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        "BillingMode": "PAY_PER_REQUEST",
        "StreamSpecification": {
            "StreamEnabled": True,
            "StreamViewType": "NEW_AND_OLD_IMAGES",
        },
    }

    try:
        dynamodb.create_table(**table_config)
        print(f"✅ Creating table: {table_name}")

        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=table_name)

        # Enable TTL
        dynamodb.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
        print("✅ Table created with TTL enabled")

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Table {table_name} already exists")
        else:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    create_memory_table()
