#!/bin/bash
# Ensure LocalStack is running and configured for tests
# This script must be run before executing AWS-dependent tests

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "========================================"
echo "Checking LocalStack for AWS Testing"
echo "========================================"

# Function to check if LocalStack is running
check_localstack() {
    if curl -s http://localhost:4566/_localstack/health | grep -q "running"; then
        return 0
    else
        return 1
    fi
}

# Check if LocalStack is already running
if check_localstack; then
    echo "✓ LocalStack is already running"
else
    echo "LocalStack is not running. Starting it now..."
    
    # Check if LocalStack is installed
    if ! command -v localstack &> /dev/null; then
        echo "ERROR: LocalStack is not installed"
        echo "Install with: pip install localstack"
        exit 1
    fi
    
    # Start LocalStack
    export SERVICES="s3,kms,dynamodb,sqs,sns,secretsmanager,lambda,cloudwatch,events"
    export DEFAULT_REGION="us-east-1"
    export EDGE_PORT=4566
    export LAMBDA_EXECUTOR=local
    export DISABLE_CORS_CHECKS=1
    export DISABLE_CUSTOM_CORS_S3=1
    export EXTRA_CORS_ALLOWED_ORIGINS=https://app.havenhealth.org
    export PERSISTENCE=1
    export LOCALSTACK_VOLUME_DIR=/tmp/localstack/volume
    
    # Create volume directory
    mkdir -p $LOCALSTACK_VOLUME_DIR
    
    # Start LocalStack in background
    localstack start -d
    
    echo "Waiting for LocalStack to be ready..."
    
    # Wait for LocalStack to be healthy
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if check_localstack; then
            echo "✓ LocalStack is ready!"
            break
        fi
        
        echo "  Waiting... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        echo "ERROR: LocalStack failed to start"
        exit 1
    fi
fi

# Initialize AWS services
echo ""
echo "Initializing AWS services in LocalStack..."

cd "$SCRIPT_DIR"

# Run the initialization script
python -c "
import sys
sys.path.insert(0, '.')
from localstack_aws_setup import LocalStackAWSServices

print('Setting up AWS services...')
services = LocalStackAWSServices()
results = services.initialize_all_services()

print('\nServices initialized:')
for service, result in results.items():
    if service != 'summary' and service != 'error':
        count = result.get('total', 0)
        print(f'  ✓ {service}: {count} resources')

if 'summary' in results:
    print(f'\nTotal resources created: {results[\"summary\"][\"total_resources\"]}')

# Verify services
print('\nVerifying services...')
verifications = services.verify_services()
all_good = True
for service, status in verifications.items():
    icon = '✓' if status else '✗'
    print(f'  {icon} {service}: {\"Running\" if status else \"Failed\"}')
    if not status:
        all_good = False

if not all_good:
    print('\nERROR: Some services failed verification')
    sys.exit(1)

print('\n✅ All AWS services ready for testing!')
"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to initialize AWS services"
    exit 1
fi

# Create test data
echo ""
echo "Creating test data..."

# Upload a test document
aws --endpoint-url=http://localhost:4566 s3 cp \
    "$SCRIPT_DIR/README.md" \
    s3://haven-health-medical-documents/test/sample-document.txt \
    --metadata patient-id=test-001,document-type=test \
    2>/dev/null || true

# Create a test secret
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
    --name haven-health/test/api-key \
    --secret-string "test-api-key-12345" \
    2>/dev/null || true

echo ""
echo "========================================"
echo "✅ LocalStack is ready for testing!"
echo "========================================"
echo ""
echo "AWS Endpoint: http://localhost:4566"
echo "Services: S3, KMS, DynamoDB, SQS, SNS, Lambda, Secrets Manager"
echo ""
echo "To run AWS tests:"
echo "  pytest tests/integration/test_localstack_aws_services.py -v"
echo ""
echo "To stop LocalStack:"
echo "  localstack stop"
echo ""
