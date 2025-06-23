#!/bin/bash

# Verify Channel Restrictions Configuration
# Haven Health Passport - Configuration Validation

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/channel-restrictions-config.yaml"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
WARNINGS=0

echo "Haven Health Passport - Channel Restrictions Verification"
echo "======================================================"
echo ""

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    local test_type="${3:-required}"

    echo -n "Testing ${test_name}... "

    if eval "${test_command}"; then
        echo -e "${GREEN}PASSED${NC}"
        ((TESTS_PASSED++))
    else
        if [ "${test_type}" = "warning" ]; then
            echo -e "${YELLOW}WARNING${NC}"
            ((WARNINGS++))
        else
            echo -e "${RED}FAILED${NC}"
            ((TESTS_FAILED++))
        fi
    fi
}

# Configuration file tests
echo "1. Configuration File Tests"
echo "=========================="

run_test "Configuration file exists" \
    "[ -f '${CONFIG_FILE}' ]"

run_test "Valid YAML syntax" \
    "yq eval '.' '${CONFIG_FILE}' > /dev/null 2>&1"

run_test "Global settings present" \
    "[ -n \"$(yq eval '.channelRestrictions.global' '${CONFIG_FILE}')\" ]"

# Channel naming tests
echo ""
echo "2. Channel Naming Tests"
echo "======================"

run_test "Naming pattern defined" \
    "[ -n \"$(yq eval '.channelRestrictions.global.naming.pattern' '${CONFIG_FILE}')\" ]"

run_test "Reserved prefixes defined" \
    "[ $(yq eval '.channelRestrictions.global.naming.reservedPrefixes | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Prohibited names defined" \
    "[ $(yq eval '.channelRestrictions.global.naming.prohibited | length' '${CONFIG_FILE}') -gt 0 ]"

# Channel category tests
echo ""
echo "3. Channel Category Tests"
echo "========================"

run_test "Healthcare category defined" \
    "[ -n \"$(yq eval '.channelRestrictions.channelCategories.healthcare' '${CONFIG_FILE}')\" ]"

run_test "Emergency category defined" \
    "[ -n \"$(yq eval '.channelRestrictions.channelCategories.emergency' '${CONFIG_FILE}')\" ]"

run_test "Audit category defined" \
    "[ -n \"$(yq eval '.channelRestrictions.channelCategories.audit' '${CONFIG_FILE}')\" ]"

run_test "System category defined" \
    "[ -n \"$(yq eval '.channelRestrictions.channelCategories.system' '${CONFIG_FILE}')\" ]"

# Orderer restriction tests
echo ""
echo "4. Orderer Restriction Tests"
echo "==========================="

# Check each orderer has assignments
orderer_count=0
yq eval '.channelRestrictions.ordererRestrictions.ordererAssignments | keys | .[]' "${CONFIG_FILE}" 2>/dev/null | while read -r orderer; do
    ((orderer_count++))
    run_test "Orderer ${orderer} has max channels defined" \
        "[ $(yq eval \".channelRestrictions.ordererRestrictions.ordererAssignments['${orderer}'].maxChannels\" '${CONFIG_FILE}') -gt 0 ]"
done

run_test "At least 3 orderers configured" \
    "[ $(yq eval '.channelRestrictions.ordererRestrictions.ordererAssignments | keys | length' '${CONFIG_FILE}') -ge 3 ]"

# Resource allocation tests
echo ""
echo "5. Resource Allocation Tests"
echo "==========================="

run_test "QoS classes defined" \
    "[ $(yq eval '.channelRestrictions.resourceAllocation.qosClasses | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Critical QoS class exists" \
    "[ -n \"$(yq eval '.channelRestrictions.resourceAllocation.qosClasses.critical' '${CONFIG_FILE}')\" ]"

run_test "Dynamic adjustment configured" \
    "[ \"$(yq eval '.channelRestrictions.resourceAllocation.dynamicAdjustment.enabled' '${CONFIG_FILE}')\" = 'true' ]"

# Security tests
echo ""
echo "6. Security Configuration Tests"
echo "=============================="

run_test "Channel isolation configured" \
    "[ -n \"$(yq eval '.channelRestrictions.security.isolation' '${CONFIG_FILE}')\" ]"

run_test "Default deny policy" \
    "[ \"$(yq eval '.channelRestrictions.security.accessControl.defaultPolicy' '${CONFIG_FILE}')\" = 'deny' ]"

run_test "Encryption required" \
    "[ \"$(yq eval '.channelRestrictions.security.dataProtection.encryptionAtRest' '${CONFIG_FILE}')\" = 'required' ]"

# Compliance tests
echo ""
echo "7. Compliance Tests"
echo "=================="

run_test "Healthcare channels have HIPAA compliance" \
    "[ \"$(yq eval '.channelRestrictions.channelCategories.healthcare.restrictions.compliance.encryption' '${CONFIG_FILE}')\" = 'required' ]"

run_test "Audit channels have retention policy" \
    "[ -n \"$(yq eval '.channelRestrictions.channelCategories.audit.restrictions.compliance.dataRetention' '${CONFIG_FILE}')\" ]"

run_test "Audit channels immutable" \
    "[ \"$(yq eval '.channelRestrictions.channelCategories.audit.restrictions.compliance.auditLogging' '${CONFIG_FILE}')\" = 'immutable' ]"

# Monitoring tests
echo ""
echo "8. Monitoring Configuration Tests"
echo "================================"

run_test "Channel metrics defined" \
    "[ $(yq eval '.channelRestrictions.monitoring.channelMetrics | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Alerts configured" \
    "[ $(yq eval '.channelRestrictions.monitoring.alerts | length' '${CONFIG_FILE}') -gt 0 ]"

# Lifecycle tests
echo ""
echo "9. Lifecycle Management Tests"
echo "============================"

run_test "Creation validation steps defined" \
    "[ $(yq eval '.channelRestrictions.lifecycle.creation.validation | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Deletion pre-checks defined" \
    "[ $(yq eval '.channelRestrictions.lifecycle.deletion.preChecks | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Data retention period set" \
    "[ -n \"$(yq eval '.channelRestrictions.lifecycle.deletion.retentionPeriod' '${CONFIG_FILE}')\" ]"

# Summary
echo ""
echo "Verification Summary:"
echo "===================="
echo "Tests Passed: ${TESTS_PASSED}"
echo "Tests Failed: ${TESTS_FAILED}"
echo "Warnings: ${WARNINGS}"
echo ""

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "${GREEN}All channel restriction tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the configuration.${NC}"
    exit 1
fi
