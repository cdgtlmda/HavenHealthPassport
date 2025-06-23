#!/bin/bash

# Haven Health Passport - Certification Test Environment Setup Script

set -e

echo "=================================================="
echo "Haven Health Passport Certification Environment Setup"
echo "=================================================="

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "ERROR: Docker Compose is not installed"
        exit 1
    fi

    # Check required ports
    for port in 8080 5433 2575 8090 9091; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
            echo "ERROR: Port $port is already in use"
            exit 1
        fi
    done

    echo "✓ Prerequisites check passed"
}

# Create required directories
create_directories() {
    echo "Creating required directories..."

    mkdir -p fhir-config
    mkdir -p hl7-engine
    mkdir -p terminology
    mkdir -p test-tools
    mkdir -p monitoring
    mkdir -p init-scripts
    mkdir -p test-data
    mkdir -p logs/certification

    echo "✓ Directories created"
}

# Generate environment variables
generate_env_file() {
    echo "Generating environment configuration..."

    if [ ! -f .env.cert ]; then
        cat > .env.cert << EOF
# Certification Environment Variables
POSTGRES_CERT_PASSWORD=$(openssl rand -base64 32)
FHIR_ADMIN_PASSWORD=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 64)
AUDIT_LOG_PATH=./logs/certification
ENABLE_DEBUG=false
ENABLE_AUDIT=true
COMPLIANCE_MODE=true
EOF
        echo "✓ Environment file created"
    else
        echo "✓ Environment file already exists"
    fi
}

# Initialize database
init_database() {
    echo "Initializing certification database..."

    cat > init-scripts/01-init-cert-db.sql << 'EOF'
-- Create audit schema
CREATE SCHEMA IF NOT EXISTS audit;

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit.access_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(255),
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    action VARCHAR(20),
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN,
    error_message TEXT
);

-- Create indexes for performance
CREATE INDEX idx_audit_timestamp ON audit.access_log(timestamp);
CREATE INDEX idx_audit_user ON audit.access_log(user_id);
CREATE INDEX idx_audit_resource ON audit.access_log(resource_type, resource_id);
EOF

    echo "✓ Database initialization script created"
}

# Start services
start_services() {
    echo "Starting certification environment..."

    # Load environment variables
    export $(cat .env.cert | xargs)

    # Start services
    docker-compose -f docker-compose.cert.yml up -d

    echo "✓ Services started"
    echo ""
    echo "Waiting for services to be healthy..."
    sleep 30

    # Check service health
    docker-compose -f docker-compose.cert.yml ps
}

# Main execution
main() {
    check_prerequisites
    create_directories
    generate_env_file
    init_database
    start_services

    echo ""
    echo "=================================================="
    echo "Certification Environment Setup Complete!"
    echo "=================================================="
    echo ""
    echo "Services:"
    echo "  - FHIR Server: http://localhost:8080/fhir"
    echo "  - PostgreSQL: localhost:5433"
    echo "  - HL7 Interface: localhost:2575"
    echo "  - Terminology Service: http://localhost:8090"
    echo "  - Prometheus: http://localhost:9091"
    echo ""
    echo "Next steps:"
    echo "  1. Run certification test suite"
    echo "  2. Monitor test execution"
    echo "  3. Collect evidence for certification"
    echo ""
}

# Run main function
main
