#!/bin/bash

# TLS Setup Verification Script
# Haven Health Passport - Verify TLS Configuration

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
TLS_CONFIG="${SCRIPT_DIR}/../config/tls/tls-certificate-config.yaml"
VERIFICATION_REPORT="${SCRIPT_DIR}/../config/tls/tls-verification-$(date +%Y%m%d-%H%M%S).txt"

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

echo "Haven Health Passport - TLS Setup Verification" | tee "${VERIFICATION_REPORT}"
echo "=============================================" | tee -a "${VERIFICATION_REPORT}"
echo "" | tee -a "${VERIFICATION_REPORT}"

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing ${test_name}... " | tee -a "${VERIFICATION_REPORT}"

    if eval "${test_command}"; then
        echo -e "${GREEN}PASSED${NC}" | tee -a "${VERIFICATION_REPORT}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}FAILED${NC}" | tee -a "${VERIFICATION_REPORT}"
        ((TESTS_FAILED++))
    fi
}

# Tests
echo "1. Configuration File Tests" | tee -a "${VERIFICATION_REPORT}"
echo "===========================" | tee -a "${VERIFICATION_REPORT}"

run_test "TLS configuration file exists" \
    "[ -f '${TLS_CONFIG}' ]"

run_test "Valid YAML syntax" \
    "yq eval '.' '${TLS_CONFIG}' > /dev/null 2>&1"

run_test "Root CA configuration present" \
    "[ $(yq eval '.certificateAuthority.rootCA.commonName' '${TLS_CONFIG}' | wc -c) -gt 0 ]"

run_test "Key algorithm is ECDSA" \
    "[ $(yq eval '.certificateAuthority.rootCA.keyAlgorithm' '${TLS_CONFIG}') = 'ECDSA' ]"

run_test "TLS 1.2 minimum version set" \
    "[ $(yq eval '.tlsConfiguration.orderer.server.minVersion' '${TLS_CONFIG}') = '1.2' ]"

echo "" | tee -a "${VERIFICATION_REPORT}"
echo "2. Script Tests" | tee -a "${VERIFICATION_REPORT}"
echo "===============" | tee -a "${VERIFICATION_REPORT}"

run_test "Certificate generation script exists" \
    "[ -f '${SCRIPT_DIR}/generate-tls-certificates.sh' ]"

run_test "Certificate generation script is executable" \
    "[ -x '${SCRIPT_DIR}/generate-tls-certificates.sh' ]"

run_test "Certificate management script exists" \
    "[ -f '${SCRIPT_DIR}/manage-tls-certificates.sh' ]"

run_test "Certificate management script is executable" \
    "[ -x '${SCRIPT_DIR}/manage-tls-certificates.sh' ]"

echo "" | tee -a "${VERIFICATION_REPORT}"
echo "3. Security Configuration Tests" | tee -a "${VERIFICATION_REPORT}"
echo "===============================" | tee -a "${VERIFICATION_REPORT}"

run_test "Mutual TLS enabled for orderer" \
    "[ $(yq eval '.tlsConfiguration.orderer.server.clientAuthRequired' '${TLS_CONFIG}') = 'true' ]"

run_test "Strong cipher suites configured" \
    "[ $(yq eval '.tlsConfiguration.orderer.server.cipherSuites | length' '${TLS_CONFIG}') -gt 0 ]"

run_test "Certificate rotation enabled" \
    "[ $(yq eval '.certificateManagement.autoRenewal.enabled' '${TLS_CONFIG}') = 'true' ]"

run_test "CRL enabled" \
    "[ $(yq eval '.certificateManagement.revocation.crl.enabled' '${TLS_CONFIG}') = 'true' ]"

run_test "OCSP enabled" \
    "[ $(yq eval '.certificateManagement.revocation.ocsp.enabled' '${TLS_CONFIG}') = 'true' ]"

echo "" | tee -a "${VERIFICATION_REPORT}"
echo "4. AWS Integration Tests" | tee -a "${VERIFICATION_REPORT}"
echo "========================" | tee -a "${VERIFICATION_REPORT}"

run_test "ACM integration enabled" \
    "[ $(yq eval '.awsIntegration.acm.enabled' '${TLS_CONFIG}') = 'true' ]"

run_test "Secrets Manager enabled" \
    "[ $(yq eval '.awsIntegration.secretsManager.enabled' '${TLS_CONFIG}') = 'true' ]"

run_test "Parameter Store enabled" \
    "[ $(yq eval '.awsIntegration.parameterStore.enabled' '${TLS_CONFIG}') = 'true' ]"

echo "" | tee -a "${VERIFICATION_REPORT}"
echo "5. Compliance Tests" | tee -a "${VERIFICATION_REPORT}"
echo "===================" | tee -a "${VERIFICATION_REPORT}"

run_test "FIPS compliance enabled" \
    "[ $(yq eval '.compliance.fips.enabled' '${TLS_CONFIG}') = 'true' ]"

run_test "Audit logging enabled" \
    "[ $(yq eval '.compliance.auditLogging.enabled' '${TLS_CONFIG}') = 'true' ]"

run_test "HIPAA encryption enforced" \
    "[ $(yq eval '.compliance.regulatory.hipaa.enforceEncryption' '${TLS_CONFIG}') = 'true' ]"

# Summary
echo "" | tee -a "${VERIFICATION_REPORT}"
echo "Verification Summary:" | tee -a "${VERIFICATION_REPORT}"
echo "====================" | tee -a "${VERIFICATION_REPORT}"
echo "Tests Passed: ${TESTS_PASSED}" | tee -a "${VERIFICATION_REPORT}"
echo "Tests Failed: ${TESTS_FAILED}" | tee -a "${VERIFICATION_REPORT}"

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "${GREEN}All TLS setup tests passed!${NC}" | tee -a "${VERIFICATION_REPORT}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review the configuration.${NC}" | tee -a "${VERIFICATION_REPORT}"
    exit 1
fi
