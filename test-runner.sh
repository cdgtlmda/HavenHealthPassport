#!/bin/bash
#
# Run tests with proper configuration for Haven Health Passport
# CRITICAL: Healthcare system testing must work reliably
#

set -e

echo "🏥 Haven Health Passport - Test Runner"
echo "====================================="

# Set environment variables
export NODE_ENV=test
export SKIP_DB_SETUP=true
export REACT_APP_ENCRYPTION_KEY=test-encryption-key-32-characters
export REACT_APP_API_URL=http://localhost:3001
export REACT_APP_ENVIRONMENT=test

# Parse command line arguments
TEST_TYPE=${1:-unit}
TEST_PATH=${2:-}

case $TEST_TYPE in
  unit)
    echo "Running unit tests..."
    if [ -n "$TEST_PATH" ]; then
      npx jest "$TEST_PATH" --no-coverage --verbose
    else
      npx jest --testPathPattern="(test|spec)\.(ts|tsx|js|jsx)$" --no-coverage
    fi
    ;;
  
  integration)
    echo "Running integration tests..."
    npx jest --testPathPattern="integration.*\.(test|spec)\.(ts|tsx|js|jsx)$" --no-coverage
    ;;
  
  e2e)
    echo "Running E2E tests..."
    npx cypress run
    ;;
  
  single)
    if [ -z "$TEST_PATH" ]; then
      echo "❌ Error: Please provide a test file path for single test"
      exit 1
    fi
    echo "Running single test: $TEST_PATH"
    npx jest "$TEST_PATH" --no-coverage --verbose --detectOpenHandles
    ;;
  
  fix)
    echo "Running tests with fix attempt..."
    # Skip global setup/teardown that causes issues
    npx jest \
      --no-coverage \
      --verbose \
      --globalSetup=null \
      --globalTeardown=null \
      --testPathPattern="PatientRegistration.test.tsx" \
      --runInBand
    ;;
  
  *)
    echo "Usage: $0 [unit|integration|e2e|single|fix] [test-path]"
    exit 1
    ;;
esac