#!/bin/bash
# Disaster Recovery Test Execution Script
# Test: DR-NODE-001 - Single Peer Node Failure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEST_DIR="$(dirname "$SCRIPT_DIR")/tests"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Disaster Recovery Test: DR-NODE-001${NC}"
echo -e "${GREEN}Single Peer Node Failure Test${NC}"
echo -e "${GREEN}========================================${NC}"

# Check environment variables
if [ -z "$AMB_NETWORK_ID" ] || [ -z "$AMB_MEMBER_ID" ]; then
    echo -e "${RED}ERROR: Required environment variables not set${NC}"
    echo "Please set AMB_NETWORK_ID and AMB_MEMBER_ID"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &>/dev/null; then
    echo -e "${RED}ERROR: AWS credentials not configured${NC}"
    exit 1
fi

echo -e "${YELLOW}Pre-test validation...${NC}"

# Create test results directory
RESULTS_DIR="$SCRIPT_DIR/../results/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

# Log file
LOG_FILE="$RESULTS_DIR/dr-node-001.log"

echo "Test configuration:"
echo "  Network ID: $AMB_NETWORK_ID"
echo "  Member ID: $AMB_MEMBER_ID"
echo "  Results directory: $RESULTS_DIR"
echo ""
# Execute the test
echo -e "${YELLOW}Executing test...${NC}"
cd "$TEST_DIR"
python3 test_dr_node_001_single_peer_failure.py 2>&1 | tee "$LOG_FILE"

# Check test result
TEST_RESULT=$?

# Move test report to results directory
mv dr-node-001-report-*.json "$RESULTS_DIR/" 2>/dev/null || true

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Test PASSED${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Test FAILED${NC}"
    echo -e "${RED}========================================${NC}"
fi

echo ""
echo "Test results saved to: $RESULTS_DIR"
echo "Log file: $LOG_FILE"

# Generate summary
echo ""
echo "Test Summary:"
if [ -f "$RESULTS_DIR"/dr-node-001-report-*.json ]; then
    cat "$RESULTS_DIR"/dr-node-001-report-*.json | python3 -m json.tool
fi

exit $TEST_RESULT
