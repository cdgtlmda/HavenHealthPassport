#!/bin/bash
# Test Status Report Script for Haven Health Passport

echo "🏥 Haven Health Passport - Test Status Report"
echo "============================================"
echo ""

# Check if jest is available
if ! command -v jest &> /dev/null && ! npx jest --version &> /dev/null; then
    echo "❌ Jest is not installed or not available"
    exit 1
fi

echo "✅ Jest is available"
echo ""

# Count test files
echo "📊 Test File Statistics:"
echo "------------------------"
TEST_FILES=$(find . -name "*.test.*" -o -name "*.spec.*" | grep -v node_modules | wc -l)
echo "Total test files found: $TEST_FILES"

UNIT_TESTS=$(find . -name "*.test.*" -o -name "*.spec.*" | grep -v node_modules | grep -v integration | grep -v e2e | wc -l)
echo "Unit test files: $UNIT_TESTS"

E2E_TESTS=$(find . -name "*.cy.*" -o -name "*.e2e.*" | grep -v node_modules | wc -l)
echo "E2E test files: $E2E_TESTS"

INTEGRATION_TESTS=$(find . -name "*.integration.*" | grep -v node_modules | wc -l)
echo "Integration test files: $INTEGRATION_TESTS"

echo ""
echo "🧪 Running Sample Test:"
echo "----------------------"
cd /Users/cadenceapeiron/Documents/HavenHealthPassport

# Run a specific test with minimal output
npx jest web/src/components/patient/__tests__/PatientRegistration.test.tsx --no-coverage --verbose=false 2>&1 | tail -20

echo ""
echo "📈 Test Infrastructure Status:"
echo "-----------------------------"

# Check for critical directories
if [ -d "test-setup/parallel" ]; then
    echo "✅ Parallel test infrastructure exists"
else
    echo "❌ Parallel test infrastructure missing"
fi

if [ -d "web/src/services/offline" ]; then
    echo "✅ Offline services exist"
else
    echo "❌ Offline services missing"
fi

if [ -d "web/src/utils" ]; then
    echo "✅ Utility functions exist"
else
    echo "❌ Utility functions missing"
fi

echo ""
echo "⚡ Quick Test Run:"
echo "-----------------"
# Try to run tests with a timeout
timeout 30s npx jest --listTests 2>/dev/null | head -10

echo ""
echo "✅ Test status report complete"