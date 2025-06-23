#!/bin/bash
#
# Run a single test file with proper healthcare system configuration
# CRITICAL: Used for debugging specific test failures in medical components
#
# Usage: ./run-single-test.sh <test-file-path>
# Example: ./run-single-test.sh web/src/components/patient/__tests__/PatientRegistration.test.tsx

set -e

if [ -z "$1" ]; then
  echo "❌ Error: Please provide a test file path"
  echo "Usage: $0 <test-file-path>"
  echo "Example: $0 web/src/components/patient/__tests__/PatientRegistration.test.tsx"
  exit 1
fi

TEST_FILE="$1"

if [ ! -f "$TEST_FILE" ]; then
  echo "❌ Error: Test file not found: $TEST_FILE"
  exit 1
fi

echo "🏥 Running single test: $TEST_FILE"
echo "=================================="

# Set healthcare-specific environment variables
export NODE_ENV=test
export REACT_APP_ENVIRONMENT=test
export REACT_APP_ENCRYPTION_KEY="${TEST_ENCRYPTION_KEY:-placeholder-test-key-replace-in-production}"
export TEST_TIMEOUT=30000  # 30s for medical operations

# Run the test with appropriate configuration
npx jest "$TEST_FILE" \
  --no-coverage \
  --verbose \
  --detectOpenHandles \
  --forceExit \
  --runInBand \
  --testTimeout=30000

echo ""
echo "✅ Test run complete"
