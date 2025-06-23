#!/bin/bash

# Verify Orderer Addresses Configuration
# Haven Health Passport - Network Topology Verification

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/orderer-addresses.yaml"
REPORT_FILE="${SCRIPT_DIR}/../config/consensus/orderer-addresses-verification-$(date +%Y%m%d-%H%M%S).txt"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

echo "Haven Health Passport - Orderer Addresses Verification" | tee "${REPORT_FILE}"
echo "====================================================" | tee -a "${REPORT_FILE}"
echo "" | tee -a "${REPORT_FILE}"

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing ${test_name}... " | tee -a "${REPORT_FILE}"

    if eval "${test_command}"; then
        echo -e "${GREEN}PASSED${NC}" | tee -a "${REPORT_FILE}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}FAILED${NC}" | tee -a "${REPORT_FILE}"
        ((TESTS_FAILED++))
    fi
}

# Configuration file tests
echo "1. Configuration File Tests" | tee -a "${REPORT_FILE}"
echo "===========================" | tee -a "${REPORT_FILE}"

run_test "Configuration file exists" \
    "[ -f '${CONFIG_FILE}' ]"

run_test "Valid YAML syntax" \
    "yq eval '.' '${CONFIG_FILE}' > /dev/null 2>&1"

run_test "Network name defined" \
    "[ -n \"$(yq eval '.network.name' '${CONFIG_FILE}')\" ]"

# Orderer configuration tests
echo "" | tee -a "${REPORT_FILE}"
echo "2. Orderer Configuration Tests" | tee -a "${REPORT_FILE}"
echo "==============================" | tee -a "${REPORT_FILE}"

run_test "Production orderers defined" \
    "[ $(yq eval '.ordererAddresses.production | length' '${CONFIG_FILE}') -gt 0 ]"

run_test "Minimum 3 orderers for consensus" \
    "[ $(yq eval '.ordererAddresses.production | length' '${CONFIG_FILE}') -ge 3 ]"

run_test "Odd number of orderers (recommended)" \
    "[ $(( $(yq eval '.ordererAddresses.production | length' '${CONFIG_FILE}') % 2 )) -eq 1 ]"

# Address validation tests
echo "" | tee -a "${REPORT_FILE}"
echo "3. Address Validation Tests" | tee -a "${REPORT_FILE}"
echo "===========================" | tee -a "${REPORT_FILE}"

# Check each orderer has required addresses
orderer_count=0
yq eval '.ordererAddresses.production[]' "${CONFIG_FILE}" -o=j | while IFS= read -r orderer; do
    orderer_id=$(echo "${orderer}" | jq -r 'keys[0]')
    ((orderer_count++))

    run_test "Orderer ${orderer_id} has internal address" \
        "[ -n \"$(echo '${orderer}' | jq -r '.[\"${orderer_id}\"].addresses.internal.host')\" ]"

    run_test "Orderer ${orderer_id} has external address" \
        "[ -n \"$(echo '${orderer}' | jq -r '.[\"${orderer_id}\"].addresses.external.host')\" ]"

    run_test "Orderer ${orderer_id} has valid port" \
        "[ $(echo '${orderer}' | jq -r '.[\"${orderer_id}\"].addresses.internal.port') -eq 7050 ]"
done

# Network topology tests
echo "" | tee -a "${REPORT_FILE}"
echo "4. Network Topology Tests" | tee -a "${REPORT_FILE}"
echo "=========================" | tee -a "${REPORT_FILE}"

run_test "DNS configuration present" \
    "[ -n \"$(yq eval '.networkTopology.dns.hostedZoneId' '${CONFIG_FILE}')\" ]"

run_test "Load balancer configured" \
    "[ -n \"$(yq eval '.networkTopology.loadBalancer.name' '${CONFIG_FILE}')\" ]"

run_test "Security groups defined" \
    "[ $(yq eval '.networkTopology.securityGroups | length' '${CONFIG_FILE}') -gt 0 ]"

# High availability tests
echo "" | tee -a "${REPORT_FILE}"
echo "5. High Availability Tests" | tee -a "${REPORT_FILE}"
echo "==========================" | tee -a "${REPORT_FILE}"

# Check AZ distribution
az_distribution=$(yq eval '.ordererAddresses.production[].*.aws.availabilityZone' "${CONFIG_FILE}" | sort | uniq -c | wc -l)
run_test "Multi-AZ distribution" \
    "[ ${az_distribution} -ge 2 ]"

run_test "Service discovery enabled" \
    "[ \"$(yq eval '.serviceDiscovery.cloudMap.enabled' '${CONFIG_FILE}')\" = 'true' ]"

run_test "Connection pooling configured" \
    "[ -n \"$(yq eval '.connectionPool.client.maxConnections' '${CONFIG_FILE}')\" ]"

# Monitoring tests
echo "" | tee -a "${REPORT_FILE}"
echo "6. Monitoring Configuration Tests" | tee -a "${REPORT_FILE}"
echo "=================================" | tee -a "${REPORT_FILE}"

run_test "Prometheus metrics enabled" \
    "[ \"$(yq eval '.monitoring.prometheus.enabled' '${CONFIG_FILE}')\" = 'true' ]"

run_test "Health check endpoints defined" \
    "[ -n \"$(yq eval '.monitoring.healthCheck.liveness.path' '${CONFIG_FILE}')\" ]"

# Summary
echo "" | tee -a "${REPORT_FILE}"
echo "Verification Summary:" | tee -a "${REPORT_FILE}"
echo "====================" | tee -a "${REPORT_FILE}"
echo "Tests Passed: ${TESTS_PASSED}" | tee -a "${REPORT_FILE}"
echo "Tests Failed: ${TESTS_FAILED}" | tee -a "${REPORT_FILE}"

# Additional information
echo "" | tee -a "${REPORT_FILE}"
echo "Orderer Summary:" | tee -a "${REPORT_FILE}"
echo "================" | tee -a "${REPORT_FILE}"
echo "Total Orderers: $(yq eval '.ordererAddresses.production | length' '${CONFIG_FILE}')" | tee -a "${REPORT_FILE}"
echo "Availability Zones: ${az_distribution}" | tee -a "${REPORT_FILE}"

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "\n${GREEN}All orderer address tests passed!${NC}" | tee -a "${REPORT_FILE}"
    exit 0
else
    echo -e "\n${RED}Some tests failed. Please review the configuration.${NC}" | tee -a "${REPORT_FILE}"
    exit 1
fi
