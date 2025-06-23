#!/bin/bash

# Script to verify fixes for individual files
# Usage: ./scripts/verify-fix.sh <file_path>

# Set colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

if [ "$#" -ne 1 ]; then
    echo -e "${RED}Usage: $0 <file_path>${NC}"
    echo -e "${YELLOW}Example: $0 src/auth/oauth2.py${NC}"
    exit 1
fi

FILE_PATH="$1"
PROJECT_ROOT="/Users/cadenceapeiron/Documents/HavenHealthPassport"
VENV_PATH="$PROJECT_ROOT/venv"

# Ensure we're using the virtual environment if it exists
if [ -d "$VENV_PATH" ]; then
  export PATH="$VENV_PATH/bin:$PATH"
fi

# Check if file exists
if [ ! -f "$PROJECT_ROOT/$FILE_PATH" ]; then
    echo -e "${RED}Error: File not found: $FILE_PATH${NC}"
    exit 1
fi

echo -e "${BLUE}=== Verifying fixes for: $FILE_PATH ===${NC}"

# Run all checks for the specific file
ERROR_COUNT=0

# 1. Type checking
echo -e "\n${BLUE}1. Type Checking (mypy):${NC}"
cd "$PROJECT_ROOT" && mypy "$FILE_PATH"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ No type errors${NC}"
else
    echo -e "${RED}✗ Type errors found${NC}"
    ((ERROR_COUNT++))
fi

# 2. Security check
echo -e "\n${BLUE}2. Security Check (bandit):${NC}"
cd "$PROJECT_ROOT" && bandit -r "$FILE_PATH" -f txt -ll
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ No security issues${NC}"
else
    echo -e "${RED}✗ Security issues found${NC}"
    ((ERROR_COUNT++))
fi

# 3. Style check
echo -e "\n${BLUE}3. Style Check (flake8):${NC}"
cd "$PROJECT_ROOT" && flake8 "$FILE_PATH" --max-line-length=88 --extend-ignore=E203,W503
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ No style violations${NC}"
else
    echo -e "${RED}✗ Style violations found${NC}"
    ((ERROR_COUNT++))
fi

# 4. Code quality
echo -e "\n${BLUE}4. Code Quality (pylint):${NC}"
cd "$PROJECT_ROOT" && pylint "$FILE_PATH" --disable=R,C0114,C0115,C0116
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ No quality issues${NC}"
else
    echo -e "${RED}✗ Quality issues found${NC}"
    ((ERROR_COUNT++))
fi

# 5. Formatting check
echo -e "\n${BLUE}5. Formatting Check (black):${NC}"
cd "$PROJECT_ROOT" && black --check "$FILE_PATH"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Properly formatted${NC}"
else
    echo -e "${RED}✗ Formatting issues found${NC}"
    echo -e "${YELLOW}Run: black $FILE_PATH${NC}"
    ((ERROR_COUNT++))
fi

# 6. Import sorting
echo -e "\n${BLUE}6. Import Sorting (isort):${NC}"
cd "$PROJECT_ROOT" && isort --check-only "$FILE_PATH"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Imports properly sorted${NC}"
else
    echo -e "${RED}✗ Import sorting needed${NC}"
    echo -e "${YELLOW}Run: isort $FILE_PATH${NC}"
    ((ERROR_COUNT++))
fi

# 7. Healthcare compliance (if applicable)
if grep -q "patient.*data\|medical.*record\|health.*information\|PHI\|PII" "$PROJECT_ROOT/$FILE_PATH" 2>/dev/null; then
    echo -e "\n${BLUE}7. Healthcare Compliance Check:${NC}"
    
    # Check for encryption
    if grep -q "encrypt\|field_encryption\|encrypted" "$PROJECT_ROOT/$FILE_PATH" 2>/dev/null; then
        echo -e "${GREEN}✓ PHI encryption found${NC}"
    else
        echo -e "${RED}✗ PHI handling without encryption detected${NC}"
        ((ERROR_COUNT++))
    fi
    
    # Check for audit logging
    if grep -q "audit\|log.*access" "$PROJECT_ROOT/$FILE_PATH" 2>/dev/null; then
        echo -e "${GREEN}✓ Audit logging found${NC}"
    else
        echo -e "${YELLOW}⚠  Consider adding audit logging for PHI access${NC}"
    fi
fi

# Summary
echo -e "\n${CYAN}=========================================${NC}"
if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed for $FILE_PATH${NC}"
else
    echo -e "${RED}❌ Found $ERROR_COUNT issue(s) in $FILE_PATH${NC}"
    echo -e "${YELLOW}Fix the issues above and run this script again.${NC}"
fi
echo -e "${CYAN}=========================================${NC}"

exit $ERROR_COUNT