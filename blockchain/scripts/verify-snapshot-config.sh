#!/bin/bash

# Verify Snapshot Configuration
# Haven Health Passport - Snapshot Configuration Verification Script

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/snapshot-config.yaml"
VERIFICATION_REPORT="${SCRIPT_DIR}/../config/consensus/snapshot-verification-$(date +%Y%m%d-%H%M%S).txt"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

echo "Haven Health Passport - Snapshot Configuration Verification" | tee "${VERIFICATION_REPORT}"
echo "=========================================================" | tee -a "${VERIFICATION_REPORT}"
echo "" | tee -a "${VERIFICATION_REPORT}"

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"

    echo -n "Testing ${test_name}... " | tee -a "${VERIFICATION_REPORT}"

    if eval "${test_command}"; then
        echo -e "${GREEN}PASSED${NC}" | tee -a "${VERIFICATION_REPORT}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}FAILED${NC}" | tee -a "${VERIFICATION_REPORT}"
        echo "  Expected: ${expected_result}" | tee -a "${VERIFICATION_REPORT}"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Verify configuration file exists
run_test "Configuration file exists" \
    "[ -f '${CONFIG_FILE}' ]" \
    "File ${CONFIG_FILE} should exist"

# Test 2: Validate YAML syntax
run_test "Valid YAML syntax" \
    "yq eval '.' '${CONFIG_FILE}' > /dev/null 2>&1" \
    "YAML file should have valid syntax"

# Test 3: Check size threshold is reasonable
run_test "Size threshold validation" \
    "[ $(yq eval '.snapshot.triggers.sizeInterval.threshold' '${CONFIG_FILE}') -ge 1048576 ]" \
    "Size threshold should be at least 1MB"

# Test 4: Check block interval is set
run_test "Block interval validation" \
    "[ $(yq eval '.snapshot.triggers.blockInterval.threshold' '${CONFIG_FILE}') -gt 0 ]" \
    "Block interval should be greater than 0"

# Test 5: Verify compression is enabled
run_test "Compression enabled" \
    "[ $(yq eval '.snapshot.creation.compression.enabled' '${CONFIG_FILE}') = 'true' ]" \
    "Compression should be enabled for efficiency"

# Test 6: Check retention policy
run_test "Retention policy set" \
    "[ $(yq eval '.snapshot.storage.retention.localSnapshots' '${CONFIG_FILE}') -gt 0 ]" \
    "Local snapshot retention should be configured"

# Test 7: Verify backup configuration
run_test "Backup storage configured" \
    "[ $(yq eval '.snapshot.storage.backup.enabled' '${CONFIG_FILE}') = 'true' ]" \
    "Backup storage should be enabled"

# Test 8: Check monitoring configuration
run_test "Monitoring enabled" \
    "[ $(yq eval '.snapshot.monitoring.metrics.enabled' '${CONFIG_FILE}') = 'true' ]" \
    "Monitoring should be enabled"

# Test 9: Verify alerts are configured
run_test "Alerts configured" \
    "[ $(yq eval '.snapshot.monitoring.alerts | length' '${CONFIG_FILE}') -gt 0 ]" \
    "At least one alert should be configured"

# Test 10: Check recovery settings
run_test "Automatic recovery enabled" \
    "[ $(yq eval '.snapshot.recovery.automatic' '${CONFIG_FILE}') = 'true' ]" \
    "Automatic recovery should be enabled"

# Summary
echo "" | tee -a "${VERIFICATION_REPORT}"
echo "Verification Summary:" | tee -a "${VERIFICATION_REPORT}"
echo "===================" | tee -a "${VERIFICATION_REPORT}"
echo "Tests Passed: ${TESTS_PASSED}" | tee -a "${VERIFICATION_REPORT}"
echo "Tests Failed: ${TESTS_FAILED}" | tee -a "${VERIFICATION_REPORT}"

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}" | tee -a "${VERIFICATION_REPORT}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the configuration.${NC}" | tee -a "${VERIFICATION_REPORT}"
    exit 1
fi
