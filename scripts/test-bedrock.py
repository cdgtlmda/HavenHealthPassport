#!/usr/bin/env python3
"""Test Bedrock access with Claude model."""

import os
import json
import boto3

# Set up credentials from environment variables
# These should be configured in your environment or AWS credentials file
# Do not hardcode credentials in source code!
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_region = os.getenv('AWS_REGION', 'us-east-1')

if not aws_access_key_id or not aws_secret_access_key:
    print("❌ Error: AWS credentials not configured!")
    print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
    print("or configure your AWS credentials file")
    exit(1)

# Create Bedrock client
bedrock = boto3.client(
    service_name='bedrock-runtime',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_region
)

# Test with Claude Haiku
try:
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Say 'Hello from Haven Health Passport!'"
                }
            ]
        })
    )

    result = json.loads(response['body'].read())
    print("✅ Bedrock access working!")
    print(f"Response: {result['content'][0]['text']}")

except Exception as e:
    print(f"❌ Error: {e}")
    print("\nYou may need to:")
    print("1. Go to https://console.aws.amazon.com/bedrock/")
    print("2. Click 'Model access' in the left menu")
    print("3. Request access to 'Claude 3 Haiku' model")
    print("4. Wait for approval (usually instant)")
