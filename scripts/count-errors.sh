#!/bin/bash

# Quick script to count errors in Haven Health Passport codebase
# Focuses on critical healthcare compliance and security issues

# Set error handling
set -o pipefail

# Set colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Haven Health Error Count Report ===${NC}"
echo -e "${YELLOW}Quick count of Python errors, focusing on healthcare compliance.${NC}"

# Define project root
PROJECT_ROOT="/Users/cadenceapeiron/Documents/HavenHealthPassport"
VENV_PATH="$PROJECT_ROOT/venv"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Ensure we're using the virtual environment if it exists
if [ -d "$VENV_PATH" ]; then
  export PATH="$VENV_PATH/bin:$PATH"
fi

# Find Python files
echo -e "${BLUE}Finding Python files to check...${NC}"
find "$PROJECT_ROOT/src" -type f -name "*.py" \
  ! -path "*/venv/*" ! -path "*/__pycache__/*" ! -path "*/.mypy_cache/*" \
  > "$TEMP_DIR/python_files.txt"

TOTAL_FILES=$(wc -l < "$TEMP_DIR/python_files.txt")
echo -e "${BLUE}Found $TOTAL_FILES Python files to check${NC}"

# Function to run quick mypy check
run_mypy_check() {
  cd "$PROJECT_ROOT" && mypy src/ --no-error-summary 2>&1 | grep "error:" | wc -l > "$TEMP_DIR/mypy_count.txt" || echo "0" > "$TEMP_DIR/mypy_count.txt"
}

# Function to run quick security check
run_security_check() {
  cd "$PROJECT_ROOT" && bandit -r src/ -f txt -ll 2>&1 | grep -E "Severity: (High|Medium)" | wc -l > "$TEMP_DIR/security_count.txt" || echo "0" > "$TEMP_DIR/security_count.txt"
}

# Function to check healthcare compliance
check_healthcare() {
  local count=0
  
  # Check for unencrypted PHI handling
  while IFS= read -r file; do
    if grep -q "patient.*data\|medical.*record\|health.*information\|PHI\|PII" "$file" 2>/dev/null; then
      if ! grep -q "encrypt\|field_encryption\|encrypted" "$file" 2>/dev/null; then
        ((count++))
      fi
    fi
  done < "$TEMP_DIR/python_files.txt"
  
  echo "$count" > "$TEMP_DIR/hipaa_count.txt"
}

# Function to check test failures
check_tests() {
  cd "$PROJECT_ROOT" && python -m pytest tests/ --tb=no -q 2>&1 | grep -E "[0-9]+ failed" | grep -oE "[0-9]+" | head -1 > "$TEMP_DIR/test_count.txt" || echo "0" > "$TEMP_DIR/test_count.txt"
}

# Function to check formatting
check_formatting() {
  cd "$PROJECT_ROOT" && black --check src/ 2>&1 | grep -c "would reformat" > "$TEMP_DIR/black_count.txt" || echo "0" > "$TEMP_DIR/black_count.txt"
}

# Run all checks in parallel
echo -e "${BLUE}Running quick error checks...${NC}"
run_mypy_check &
run_security_check &
check_healthcare &
check_tests &
check_formatting &
wait

# Read results
MYPY_ERRORS=$(cat "$TEMP_DIR/mypy_count.txt" 2>/dev/null || echo "0")
SECURITY_ISSUES=$(cat "$TEMP_DIR/security_count.txt" 2>/dev/null || echo "0")
HIPAA_ISSUES=$(cat "$TEMP_DIR/hipaa_count.txt" 2>/dev/null || echo "0")
TEST_FAILURES=$(cat "$TEMP_DIR/test_count.txt" 2>/dev/null || echo "0")
FORMATTING_ISSUES=$(cat "$TEMP_DIR/black_count.txt" 2>/dev/null || echo "0")

# Calculate totals
CRITICAL_TOTAL=$((SECURITY_ISSUES + HIPAA_ISSUES + TEST_FAILURES))
ALL_TOTAL=$((MYPY_ERRORS + SECURITY_ISSUES + HIPAA_ISSUES + TEST_FAILURES + FORMATTING_ISSUES))

# Print report
echo -e "\n${CYAN}=========================================${NC}"
echo -e "${CYAN}         ERROR COUNT SUMMARY           ${NC}"
echo -e "${CYAN}=========================================${NC}"

echo -e "\n${RED}CRITICAL ISSUES:${NC}"
printf "${YELLOW}  HIPAA Compliance Issues:      ${RED}%7d${NC}\n" $HIPAA_ISSUES
printf "${YELLOW}  Security Issues (High/Med):   ${RED}%7d${NC}\n" $SECURITY_ISSUES
printf "${YELLOW}  Failed Tests:                 ${RED}%7d${NC}\n" $TEST_FAILURES
printf "${PURPLE}Critical Total:                 ${RED}%7d${NC}\n" $CRITICAL_TOTAL

echo -e "\n${YELLOW}OTHER ISSUES:${NC}"
printf "${YELLOW}  Type Errors (mypy):           ${RED}%7d${NC}\n" $MYPY_ERRORS
printf "${YELLOW}  Formatting Issues:            ${RED}%7d${NC}\n" $FORMATTING_ISSUES

echo -e "\n${CYAN}=========================================${NC}"
printf "${PURPLE}GRAND TOTAL:                     ${RED}%7d${NC}\n" $ALL_TOTAL
echo -e "${CYAN}=========================================${NC}"

# Quick fixes available
if [ "$FORMATTING_ISSUES" -gt 0 ]; then
  echo -e "\n${GREEN}Quick fix available:${NC}"
  echo -e "${YELLOW}Run: ${GREEN}black src/ tests/${NC} to fix formatting issues"
fi

if [ "$CRITICAL_TOTAL" -gt 0 ]; then
  echo -e "\n${RED}⚠️  CRITICAL: Healthcare/Security issues require immediate attention!${NC}"
  echo -e "${YELLOW}Run ${GREEN}./scripts/check-compliance.sh${NC} for detailed report"
fi

echo -e "\n${GREEN}Quick count completed.${NC}"

exit 0