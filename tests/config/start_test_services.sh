#!/bin/bash
# Start Real Test Services for Medical-Compliant Testing
# This script starts all required services for real testing
# NO MOCKS - These are actual service instances

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "=============================================="
echo "Starting Real Test Services for Haven Health"
echo "=============================================="

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose is required but not installed"
    exit 1
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Stop any existing test services
echo "Stopping any existing test services..."
docker-compose -f docker-compose.test.yml down -v

# Start test services
echo "Starting test services..."
docker-compose -f docker-compose.test.yml up -d \
    test-postgres \
    test-redis \
    localstack \
    test-fhir \
    mock-oauth \
    mailhog

# Wait for services to be healthy
echo "Waiting for services to be healthy..."

# Function to check service health
check_service() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f docker-compose.test.yml ps | grep -q "$service.*healthy"; then
            echo "✓ $service is healthy"
            return 0
        elif docker-compose -f docker-compose.test.yml ps | grep -q "$service.*Up"; then
            echo "✓ $service is running (no health check)"
            return 0
        fi
        
        echo "  Waiting for $service... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "✗ $service failed to start"
    return 1
}

# Check each service
services=(
    "test-postgres"
    "test-redis"
    "localstack"
    "test-fhir"
    "mock-oauth"
    "mailhog"
)

all_healthy=true
for service in "${services[@]}"; do
    if ! check_service "$service"; then
        all_healthy=false
    fi
done

if [ "$all_healthy" = false ]; then
    echo "ERROR: Not all services started successfully"
    echo "Check logs with: docker-compose -f docker-compose.test.yml logs"
    exit 1
fi

# Initialize test database
echo ""
echo "Initializing test database with production schema..."
cd "$SCRIPT_DIR"
python initialize_test_db.py

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to initialize test database"
    exit 1
fi

# Initialize LocalStack services
echo ""
echo "Initializing LocalStack AWS services..."

# Create S3 buckets
echo "Creating S3 buckets..."
aws --endpoint-url=http://localhost:4566 s3 mb s3://haven-test-medical-docs 2>/dev/null || true
aws --endpoint-url=http://localhost:4566 s3 mb s3://haven-test-backups 2>/dev/null || true

# Create DynamoDB tables
echo "Creating DynamoDB tables..."
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name haven-test-sessions \
    --attribute-definitions AttributeName=session_id,AttributeType=S \
    --key-schema AttributeName=session_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    2>/dev/null || true

# Create KMS key
echo "Creating KMS master key..."
KEY_ID=$(aws --endpoint-url=http://localhost:4566 kms create-key \
    --description "Haven Health Test Master Key" \
    --query 'KeyMetadata.KeyId' \
    --output text 2>/dev/null || echo "existing")

if [ "$KEY_ID" != "existing" ]; then
    echo "Created KMS key: $KEY_ID"
fi

# Create test blockchain network (if ganache is installed)
if command -v ganache &> /dev/null; then
    echo ""
    echo "Starting test blockchain network..."
    # Kill any existing ganache
    pkill -f ganache || true
    
    # Start ganache in background
    ganache \
        --deterministic \
        --accounts 10 \
        --host 0.0.0.0 \
        --port 8545 \
        --gasLimit 10000000 \
        --quiet &
    
    GANACHE_PID=$!
    echo "Ganache started with PID: $GANACHE_PID"
    
    # Save PID for later cleanup
    echo $GANACHE_PID > "$SCRIPT_DIR/.ganache.pid"
    
    # Wait for ganache to be ready
    sleep 3
fi

echo ""
echo "=============================================="
echo "All Test Services Started Successfully!"
echo "=============================================="
echo ""
echo "Service URLs:"
echo "  PostgreSQL:    postgresql://test:test@localhost:5433/haven_test"
echo "  Redis:         redis://localhost:6380"
echo "  LocalStack:    http://localhost:4566"
echo "  FHIR Server:   http://localhost:8081/fhir"
echo "  OAuth Mock:    http://localhost:9090"
echo "  Mail Server:   http://localhost:8025 (Web UI)"
echo "  SMTP:          localhost:1025"

if command -v ganache &> /dev/null; then
    echo "  Blockchain:    http://localhost:8545"
fi

echo ""
echo "To view logs: docker-compose -f docker-compose.test.yml logs -f"
echo "To stop services: $SCRIPT_DIR/stop_test_services.sh"
echo ""
