#!/bin/bash
# Blockchain Compliance Validation Script
# Runs comprehensive compliance checks for all standards

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VALIDATORS_DIR="$SCRIPT_DIR/validators"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Haven Health Passport Blockchain${NC}"
echo -e "${BLUE}Compliance Validation Suite${NC}"
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
# Create reports directory
REPORTS_DIR="$SCRIPT_DIR/reports/$(date +%Y%m%d)"
mkdir -p "$REPORTS_DIR"

# Log file
LOG_FILE="$REPORTS_DIR/compliance_validation_$(date +%H%M%S).log"

echo "Configuration:"
echo "  Network ID: $AMB_NETWORK_ID"
echo "  Member ID: $AMB_MEMBER_ID"
echo "  Reports directory: $REPORTS_DIR"
echo ""

# Function to run individual validator
run_validator() {
    local validator_name=$1
    local validator_script=$2

    echo -e "${YELLOW}Running $validator_name compliance validation...${NC}"

    if [ -f "$VALIDATORS_DIR/$validator_script" ]; then
        if python3 "$VALIDATORS_DIR/$validator_script" >> "$LOG_FILE" 2>&1; then
            echo -e "${GREEN}✓ $validator_name validation completed${NC}"
            return 0
        else
            echo -e "${RED}✗ $validator_name validation failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠ $validator_name validator not found${NC}"
        return 2
    fi
}

# Run comprehensive validation
echo -e "${YELLOW}Running comprehensive compliance validation...${NC}"
echo ""

cd "$VALIDATORS_DIR"
if python3 compliance_orchestrator.py | tee -a "$LOG_FILE"; then
    VALIDATION_RESULT=0
    echo -e "${GREEN}Compliance validation completed successfully${NC}"
else
    VALIDATION_RESULT=1
    echo -e "${RED}Compliance validation failed${NC}"
fi

echo ""
echo "Log file: $LOG_FILE"
echo "Reports saved to: $REPORTS_DIR"

exit $VALIDATION_RESULT
