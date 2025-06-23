#!/bin/bash

# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

################################################################################
# Script: test-orderer-policies.sh
# Purpose: Test orderer policies implementation
# Usage: ./test-orderer-policies.sh
################################################################################

set -e

echo "======================================"
echo "Haven Health Passport"
echo "Orderer Policy Testing Script"
echo "======================================"

# Test configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/configtx.yaml"
POLICIES_FILE="${SCRIPT_DIR}/orderer-policies.yaml"
TEST_RESULTS="${SCRIPT_DIR}/test-results-$(date +%Y%m%d_%H%M%S).log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test result counters
TESTS_PASSED=0
TESTS_FAILED=0

# Function to log test results
log_test() {
    local test_name=$1
    local result=$2
    local message=$3

    echo "Test: ${test_name}" >> "${TEST_RESULTS}"
    echo "Result: ${result}" >> "${TEST_RESULTS}"
    echo "Message: ${message}" >> "${TEST_RESULTS}"
    echo "---" >> "${TEST_RESULTS}"

    if [ "${result}" == "PASS" ]; then
        echo -e "${GREEN}✓${NC} ${test_name}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗${NC} ${test_name}: ${message}"
        ((TESTS_FAILED++))
    fi
}

# Test 1: Verify policy files exist
test_policy_files() {
    echo -e "\n${YELLOW}Testing policy file existence...${NC}"

    if [ -f "${CONFIG_FILE}" ]; then
        log_test "configtx.yaml exists" "PASS" "File found"
    else
        log_test "configtx.yaml exists" "FAIL" "File not found"
    fi

    if [ -f "${POLICIES_FILE}" ]; then
        log_test "orderer-policies.yaml exists" "PASS" "File found"
    else
        log_test "orderer-policies.yaml exists" "FAIL" "File not found"
    fi
}

# Test 2: Validate YAML syntax
test_yaml_syntax() {
    echo -e "\n${YELLOW}Testing YAML syntax...${NC}"

    if command -v python3 &> /dev/null; then
        # Test configtx.yaml
        python3 -c "import yaml; yaml.safe_load(open('${CONFIG_FILE}'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            log_test "configtx.yaml syntax" "PASS" "Valid YAML"
        else
            log_test "configtx.yaml syntax" "FAIL" "Invalid YAML syntax"
        fi

        # Test orderer-policies.yaml
        python3 -c "import yaml; yaml.safe_load(open('${POLICIES_FILE}'))" 2>/dev/null
        if [ $? -eq 0 ]; then
            log_test "orderer-policies.yaml syntax" "PASS" "Valid YAML"
        else
            log_test "orderer-policies.yaml syntax" "FAIL" "Invalid YAML syntax"
        fi
    else
        log_test "YAML syntax validation" "FAIL" "Python3 not available"
    fi
}

# Test 3: Check required policy fields
test_required_policies() {
    echo -e "\n${YELLOW}Testing required policy fields...${NC}"

    # List of required policies
    local required_policies=(
        "OrdererReaders"
        "OrdererWriters"
        "OrdererAdmins"
        "OrdererBlockValidation"
        "EmergencyOverride"
        "HIPAAComplianceOperations"
    )

    for policy in "${required_policies[@]}"; do
        if grep -q "${policy}:" "${POLICIES_FILE}"; then
            log_test "Policy ${policy} defined" "PASS" "Found in configuration"
        else
            log_test "Policy ${policy} defined" "FAIL" "Not found in configuration"
        fi
    done
}

# Test 4: Validate policy rules
test_policy_rules() {
    echo -e "\n${YELLOW}Testing policy rule validity...${NC}"

    # Check for valid rule types
    if grep -E "Type: (Signature|ImplicitMeta)" "${POLICIES_FILE}" > /dev/null; then
        log_test "Policy rule types" "PASS" "Valid rule types found"
    else
        log_test "Policy rule types" "FAIL" "Invalid or missing rule types"
    fi

    # Check for MSP references
    if grep -E "MSP\.(admin|member|client|peer)" "${POLICIES_FILE}" > /dev/null; then
        log_test "MSP references" "PASS" "Valid MSP references found"
    else
        log_test "MSP references" "FAIL" "No valid MSP references found"
    fi
}

# Test 5: Verify emergency policy constraints
test_emergency_policies() {
    echo -e "\n${YELLOW}Testing emergency policy constraints...${NC}"

    # Check for time limits in emergency policies
    if grep -A5 "EmergencyOverride:" "${POLICIES_FILE}" | grep -q "TimeLimit:"; then
        log_test "Emergency time limits" "PASS" "Time constraints defined"
    else
        log_test "Emergency time limits" "FAIL" "No time constraints for emergency access"
    fi

    # Check for audit requirements
    if grep -A5 "EmergencyOverride:" "${POLICIES_FILE}" | grep -q "AuditRequired: true"; then
        log_test "Emergency audit requirement" "PASS" "Audit required for emergency access"
    else
        log_test "Emergency audit requirement" "FAIL" "No audit requirement found"
    fi
}

# Main test execution
echo "Starting orderer policy tests..."
echo "Test results will be saved to: ${TEST_RESULTS}"

# Run all tests
test_policy_files
test_yaml_syntax
test_required_policies
test_policy_rules
test_emergency_policies

# Summary
echo -e "\n${YELLOW}======================================"
echo "Test Summary"
echo "======================================${NC}"
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo "Detailed results: ${TEST_RESULTS}"

# Exit with appropriate code
if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}Some tests failed. Please review and fix.${NC}"
    exit 1
fi
