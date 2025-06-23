#!/bin/bash

echo "========================================"
echo "Haven Health Passport Environment Check"
echo "========================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check function
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $2: $3"
        return 0
    else
        echo -e "${RED}✗${NC} $2 not found"
        return 1
    fi
}

# Initialize counters
total_checks=0
passed_checks=0

# Python
((total_checks++))
if check_command python3 "Python" "$(python3 --version 2>&1)"; then
    ((passed_checks++))
fi

# pip
((total_checks++))
if check_command pip3 "pip" "$(pip3 --version 2>&1 | head -1)"; then
    ((passed_checks++))
fi

# Node.js
((total_checks++))
if check_command node "Node.js" "$(node --version)"; then
    ((passed_checks++))
fi

# npm
((total_checks++))
if check_command npm "npm" "$(npm --version)"; then
    ((passed_checks++))
fi

# Git
((total_checks++))
if check_command git "Git" "$(git --version)"; then
    ((passed_checks++))
fi

# Docker
((total_checks++))
if check_command docker "Docker" "$(docker --version 2>&1)"; then
    ((passed_checks++))
else
    echo -e "  ${YELLOW}→ Install with: brew install --cask docker${NC}"
fi

# Docker Compose
((total_checks++))
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker Compose: $(docker compose version)"
    ((passed_checks++))
else
    echo -e "${RED}✗${NC} Docker Compose not found"
fi

# Go
((total_checks++))
if check_command go "Go" "$(go version 2>&1 | head -1)"; then
    ((passed_checks++))
else
    echo -e "  ${YELLOW}→ Install with: brew install go${NC}"
fi

# AWS CLI
((total_checks++))
if check_command aws "AWS CLI" "$(aws --version 2>&1)"; then
    ((passed_checks++))
fi

# AWS CDK
((total_checks++))
if check_command cdk "AWS CDK" "$(cdk --version 2>&1)"; then
    ((passed_checks++))
fi

# Check VS Code
((total_checks++))
if [ -d "/Applications/Visual Studio Code.app" ]; then
    echo -e "${GREEN}✓${NC} VS Code: Installed"
    ((passed_checks++))
else
    echo -e "${RED}✗${NC} VS Code not found"
    echo -e "  ${YELLOW}→ Download from: https://code.visualstudio.com/${NC}"
fi

echo ""
echo "========================================"
echo "Summary: $passed_checks/$total_checks checks passed"
echo "========================================"

# Check Python virtual environment
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Python virtual environment exists"
    if [ -n "$VIRTUAL_ENV" ]; then
        echo -e "${GREEN}✓${NC} Virtual environment is activated"
    else
        echo -e "${YELLOW}!${NC} Virtual environment exists but not activated"
        echo -e "  ${YELLOW}→ Run: source venv/bin/activate${NC}"
    fi
else
    echo -e "${YELLOW}!${NC} No virtual environment found"
    echo -e "  ${YELLOW}→ Run: python3 -m venv venv${NC}"
fi

echo ""

# Exit with error if not all checks passed
if [ $passed_checks -ne $total_checks ]; then
    exit 1
fi