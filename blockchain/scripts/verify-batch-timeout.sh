#!/bin/bash

# Verify Batch Timeout Configuration
# Haven Health Passport - Configuration Validation

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/batch-timeout-config.yaml"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

echo "Batch Timeout Configuration Verification"
echo "======================================="
echo ""

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing ${test_name}... "

    if eval "${test_command}"; then
        echo -e "${GREEN}PASSED${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}FAILED${NC}"
        ((TESTS_FAILED++))
    fi
}

# Tests
run_test "Configuration file exists" \
    "[ -f '${CONFIG_FILE}' ]"

run_test "Valid YAML syntax" \
    "yq eval '.' '${CONFIG_FILE}' > /dev/null 2>&1"

run_test "Production timeout defined" \
    "[ -n \"$(yq eval '.batchTimeout.production.default' '${CONFIG_FILE}')\" ]"

run_test "Performance profiles exist" \
    "[ $(yq eval '.performanceProfiles | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Monitoring configured" \
    "[ -n \"$(yq eval '.monitoring.cloudWatch.namespace' '${CONFIG_FILE}')\" ]"

run_test "Dynamic adjustment configured" \
    "[ -n \"$(yq eval '.batchTimeout.production.dynamic.enabled' '${CONFIG_FILE}')\" ]"

run_test "Minimum timeout reasonable (>= 100ms)" \
    "[ $(yq eval '.batchTimeout.production.dynamic.minTimeout' '${CONFIG_FILE}' | sed 's/ms//') -ge 100 ]"

run_test "Maximum timeout reasonable (<= 10s)" \
    "timeout_val=$(yq eval '.batchTimeout.production.dynamic.maxTimeout' '${CONFIG_FILE}' | sed 's/s//'); [ \${timeout_val} -le 10 ]"

# Summary
echo ""
echo "Summary: ${TESTS_PASSED} passed, ${TESTS_FAILED} failed"

exit ${TESTS_FAILED}
