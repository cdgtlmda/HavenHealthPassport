#!/bin/bash
# Comprehensive Disaster Recovery Test Suite Execution
# Runs all disaster recovery tests in sequence

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Haven Health Passport Blockchain${NC}"
echo -e "${BLUE}Disaster Recovery Test Suite${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

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

# Check Python
if ! python3 --version &>/dev/null; then
    echo -e "${RED}ERROR: Python 3 not found${NC}"
    exit 1
fi

echo -e "${GREEN}Prerequisites check passed${NC}"
echo ""
# Create test session directory
SESSION_ID=$(date +%Y%m%d_%H%M%S)
SESSION_DIR="$BASE_DIR/results/session_$SESSION_ID"
mkdir -p "$SESSION_DIR"

# Summary report file
SUMMARY_FILE="$SESSION_DIR/dr_test_summary.txt"

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
ERROR_TESTS=0

# Function to run a test
run_test() {
    local test_id=$1
    local test_script=$2
    local test_name=$3

    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}Running: $test_id - $test_name${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    # Create test-specific directory
    TEST_DIR="$SESSION_DIR/$test_id"
    mkdir -p "$TEST_DIR"

    # Run the test
    if [ -f "$SCRIPT_DIR/$test_script" ]; then
        if "$SCRIPT_DIR/$test_script" > "$TEST_DIR/output.log" 2>&1; then
            echo -e "${GREEN}✓ $test_id: PASSED${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            echo "$test_id: PASSED" >> "$SUMMARY_FILE"
        else
            echo -e "${RED}✗ $test_id: FAILED${NC}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            echo "$test_id: FAILED" >> "$SUMMARY_FILE"
        fi
    else
        echo -e "${YELLOW}⚠ $test_id: NOT IMPLEMENTED${NC}"
        ERROR_TESTS=$((ERROR_TESTS + 1))
        echo "$test_id: NOT IMPLEMENTED" >> "$SUMMARY_FILE"
    fi

    echo ""
}
# Test execution start
echo "Starting disaster recovery test suite..." | tee "$SUMMARY_FILE"
echo "Session ID: $SESSION_ID" | tee -a "$SUMMARY_FILE"
echo "Start time: $(date)" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

# Execute Node Failure Recovery Tests
echo -e "${YELLOW}=== Node Failure Recovery Tests ===${NC}"
run_test "DR-NODE-001" "run-dr-node-001.sh" "Single Peer Node Failure"
run_test "DR-NODE-002" "run-dr-node-002.sh" "Multiple Peer Node Failure"
run_test "DR-NODE-003" "run-dr-node-003.sh" "Orderer Node Failure"
run_test "DR-NODE-004" "run-dr-node-004.sh" "Certificate Authority Failure"

# Execute Data Recovery Tests
echo -e "${YELLOW}=== Data Recovery Tests ===${NC}"
run_test "DR-DATA-001" "run-dr-data-001.sh" "Ledger Corruption Recovery"
run_test "DR-DATA-002" "run-dr-data-002.sh" "State Database Recovery"
run_test "DR-DATA-003" "run-dr-data-003.sh" "Private Data Collection Recovery"
run_test "DR-DATA-004" "run-dr-data-004.sh" "Smart Contract State Recovery"

# Execute Network Failure Recovery Tests
echo -e "${YELLOW}=== Network Failure Recovery Tests ===${NC}"
run_test "DR-NET-001" "run-dr-net-001.sh" "Complete Network Partition"
run_test "DR-NET-002" "run-dr-net-002.sh" "AWS Region Failure"
run_test "DR-NET-003" "run-dr-net-003.sh" "VPC Connectivity Loss"
run_test "DR-NET-004" "run-dr-net-004.sh" "Load Balancer Failure"

# Execute Security Recovery Tests
echo -e "${YELLOW}=== Security Recovery Tests ===${NC}"
run_test "DR-SEC-001" "run-dr-sec-001.sh" "Compromised Certificate Recovery"
run_test "DR-SEC-002" "run-dr-sec-002.sh" "HSM Failure Recovery"
run_test "DR-SEC-003" "run-dr-sec-003.sh" "Access Control Corruption"
run_test "DR-SEC-004" "run-dr-sec-004.sh" "Encryption Key Recovery"

# Execute Application Integration Recovery Tests
echo -e "${YELLOW}=== Application Integration Recovery Tests ===${NC}"
run_test "DR-APP-001" "run-dr-app-001.sh" "SDK Connection Recovery"
run_test "DR-APP-002" "run-dr-app-002.sh" "Event Hub Recovery"
run_test "DR-APP-003" "run-dr-app-003.sh" "Transaction Queue Recovery"
run_test "DR-APP-004" "run-dr-app-004.sh" "API Gateway Recovery"
# Execute Compliance Recovery Tests
echo -e "${YELLOW}=== Compliance Recovery Tests ===${NC}"
run_test "DR-COMP-001" "run-dr-comp-001.sh" "Audit Trail Recovery"
run_test "DR-COMP-002" "run-dr-comp-002.sh" "HIPAA Compliance Validation"
run_test "DR-COMP-003" "run-dr-comp-003.sh" "GDPR Data Portability"
run_test "DR-COMP-004" "run-dr-comp-004.sh" "Cross-Border Data Sovereignty"

# Test completion
echo "" | tee -a "$SUMMARY_FILE"
echo "End time: $(date)" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

# Generate summary report
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}================================================${NC}"

echo "Total Tests: $TOTAL_TESTS" | tee -a "$SUMMARY_FILE"
echo "Passed: $PASSED_TESTS" | tee -a "$SUMMARY_FILE"
echo "Failed: $FAILED_TESTS" | tee -a "$SUMMARY_FILE"
echo "Not Implemented: $ERROR_TESTS" | tee -a "$SUMMARY_FILE"

# Calculate pass rate
if [ $TOTAL_TESTS -gt 0 ]; then
    IMPLEMENTED_TESTS=$((TOTAL_TESTS - ERROR_TESTS))
    if [ $IMPLEMENTED_TESTS -gt 0 ]; then
        PASS_RATE=$((PASSED_TESTS * 100 / IMPLEMENTED_TESTS))
        echo "Pass Rate: $PASS_RATE% (of implemented tests)" | tee -a "$SUMMARY_FILE"
    fi
fi

echo ""
echo "Detailed results saved to: $SESSION_DIR"
echo "Summary report: $SUMMARY_FILE"

# Exit with appropriate code
if [ $FAILED_TESTS -eq 0 ] && [ $PASSED_TESTS -gt 0 ]; then
    echo -e "${GREEN}All implemented tests PASSED${NC}"
    exit 0
else
    echo -e "${RED}Some tests FAILED${NC}"
    exit 1
fi
