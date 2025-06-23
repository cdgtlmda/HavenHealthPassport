#!/bin/bash

# Verify Block Size Limits Configuration
set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/block-size-limits-config.yaml"

echo "Block Size Limits Verification"
echo "=============================="

# Test function
test_config() {
    if eval "$2"; then
        echo -e "$1: ${GREEN}PASS${NC}"
        return 0
    else
        echo -e "$1: ${RED}FAIL${NC}"
        return 1
    fi
}

# Run tests
FAILED=0

test_config "Config file exists" "[ -f '${CONFIG_FILE}' ]" || ((FAILED++))
test_config "Valid YAML" "yq eval '.' '${CONFIG_FILE}' > /dev/null 2>&1" || ((FAILED++))
test_config "Absolute max defined" "[ -n \"$(yq eval '.blockSizeLimits.production.absoluteMaxBytes' '${CONFIG_FILE}')\" ]" || ((FAILED++))
test_config "Preferred max defined" "[ -n \"$(yq eval '.blockSizeLimits.production.preferredMaxBytes' '${CONFIG_FILE}')\" ]" || ((FAILED++))
test_config "Absolute > Preferred" "[ $(yq eval '.blockSizeLimits.production.absoluteMaxBytes' '${CONFIG_FILE}') -gt $(yq eval '.blockSizeLimits.production.preferredMaxBytes' '${CONFIG_FILE}') ]" || ((FAILED++))

echo ""
echo "Tests completed. Failed: ${FAILED}"
exit ${FAILED}
