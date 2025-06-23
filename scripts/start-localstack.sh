#!/bin/bash

# Start LocalStack for local AWS development
echo "Starting LocalStack for local AWS services..."

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Start LocalStack
docker-compose up -d localstack

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
sleep 10

# LocalStack requires dummy AWS credentials for testing
# These are NOT real AWS credentials - LocalStack ignores actual values
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL=http://localhost:4566

# Create S3 bucket
echo "Creating S3 bucket..."
aws s3 mb s3://haven-health-local --endpoint-url http://localhost:4566

# Create DynamoDB tables
echo "Creating DynamoDB tables..."
aws dynamodb create-table \
    --table-name haven-health-sessions \
    --attribute-definitions AttributeName=session_id,AttributeType=S \
    --key-schema AttributeName=session_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:4566

aws dynamodb create-table \
    --table-name haven-health-audit-logs \
    --attribute-definitions AttributeName=log_id,AttributeType=S \
    --key-schema AttributeName=log_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:4566

echo "LocalStack setup complete!"
echo ""
echo "To use LocalStack in your code, set:"
echo "  AWS_ENDPOINT_URL=http://localhost:4566"
echo "  AWS_ACCESS_KEY_ID=test"
echo "  AWS_SECRET_ACCESS_KEY=test"
