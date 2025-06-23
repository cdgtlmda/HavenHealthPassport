#!/bin/bash

# Verify Preferred Reader Configuration
set -euo pipefail

echo "Preferred Reader Configuration Verification"
echo "=========================================="

CONFIG_FILE="$(dirname "$0")/../config/consensus/preferred-reader-config.yaml"
PASSED=0
FAILED=0

# Test function
test_item() {
    if eval "$2"; then
        echo "✓ $1"
        ((PASSED++))
    else
        echo "✗ $1"
        ((FAILED++))
    fi
}

# Run tests
test_item "Configuration exists" "[ -f '$CONFIG_FILE' ]"
test_item "Valid YAML syntax" "yq eval '.' '$CONFIG_FILE' > /dev/null 2>&1"
test_item "Global settings defined" "yq eval '.preferredReader.global.enabled' '$CONFIG_FILE' > /dev/null"
test_item "Consistency level set" "[ -n \"$(yq eval '.preferredReader.global.consistencyLevel' '$CONFIG_FILE')\" ]"
test_item "Monitoring configured" "[ $(yq eval '.preferredReader.monitoring.metrics | length' '$CONFIG_FILE') -gt 0 ]"

echo ""
echo "Results: $PASSED passed, $FAILED failed"
exit $FAILED
