#!/bin/bash

# Test Environment Validation Script

echo "======================================"
echo "Certification Environment Validation"
echo "======================================"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Validation results
PASSED=0
FAILED=0

# Function to check service
check_service() {
    local service_name=$1
    local url=$2
    local expected_code=$3

    echo -n "Checking $service_name... "

    response=$(curl -s -o /dev/null -w "%{http_code}" $url)

    if [ "$response" == "$expected_code" ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $response)"
        ((FAILED++))
    fi
}

# Check FHIR Server
check_service "FHIR Server" "http://localhost:8080/fhir/metadata" "200"

# Check Terminology Service
check_service "Terminology Service" "http://localhost:8090/health" "200"

# Check Database connectivity
echo -n "Checking PostgreSQL... "
if PGPASSWORD=$POSTGRES_CERT_PASSWORD psql -h localhost -p 5433 -U haven_cert_user -d haven_cert -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Check HL7 Interface
echo -n "Checking HL7 Interface... "
if nc -z localhost 2575 2>/dev/null; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Check Prometheus
check_service "Prometheus Monitoring" "http://localhost:9091/-/ready" "200"

# Summary
echo ""
echo "======================================"
echo "Validation Summary"
echo "======================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Environment is ready for certification testing.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please resolve issues before proceeding.${NC}"
    exit 1
fi
