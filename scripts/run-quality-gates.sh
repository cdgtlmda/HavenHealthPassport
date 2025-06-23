#!/bin/bash
# Haven Health Passport - Run All Quality Gates Locally
# This script runs all quality gate checks before pushing code

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}🏥 Haven Health Passport - Quality Gates${NC}"
echo "=================================================="
echo ""

# Track failures
FAILED_GATES=()

# Function to run a quality gate
run_gate() {
    local gate_name=$1
    local command=$2
    
    echo -e "${BLUE}Running: ${gate_name}${NC}"
    
    if eval "$command"; then
        echo -e "${GREEN}✅ ${gate_name} passed${NC}\n"
    else
        echo -e "${RED}❌ ${gate_name} failed${NC}\n"
        FAILED_GATES+=("$gate_name")
    fi
}

# 1. Code Quality Gates
echo -e "${YELLOW}1. CODE QUALITY GATES${NC}"
echo "----------------------"

# JavaScript/React linting
if [ -d "web" ]; then
    run_gate "JavaScript/React ESLint" "cd web && npm run lint"
fi

# Python linting
if [ -f "requirements.txt" ]; then
    run_gate "Python PyLint" "pylint src/ --exit-zero --reports=y"
fi

# Code complexity
run_gate "Code Complexity" "python scripts/validate-complexity.py --max-complexity=10"

# Healthcare standards
if [ -f "pylint-report.json" ]; then
    run_gate "Healthcare Standards" "python scripts/check-healthcare-standards.py pylint-report.json"
fi

# 2. Security Gates
echo -e "${YELLOW}2. SECURITY GATES${NC}"
echo "-----------------"

# Python security
run_gate "Bandit Security Scan" "bandit -r src/ -f json -o bandit-report.json --exit-zero"

# Dependency vulnerabilities
run_gate "Python Dependencies" "safety check --json > safety-report.json || true"

if [ -d "web" ]; then
    run_gate "NPM Dependencies" "cd web && npm audit --json > npm-audit.json || true"
fi

# Check vulnerabilities
run_gate "Vulnerability Check" "python scripts/check-vulnerabilities.py --max-critical=0 --max-high=0"

# PHI encryption
run_gate "PHI Encryption Coverage" "python scripts/verify-encryption-coverage.py"

# 3. Test Coverage Gates
echo -e "${YELLOW}3. TEST COVERAGE GATES${NC}"
echo "----------------------"

# Python tests
run_gate "Python Tests" "python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80"

# JavaScript tests
if [ -d "web" ]; then
    run_gate "JavaScript Tests" "cd web && npm test -- --coverage --watchAll=false"
fi

# 4. Performance Gates
echo -e "${YELLOW}4. PERFORMANCE GATES${NC}"
echo "--------------------"

# Build size check
if [ -d "web" ]; then
    run_gate "Bundle Size Check" "cd web && npm run build && du -sh build/"
fi

# 5. Compliance Gates
echo -e "${YELLOW}5. COMPLIANCE GATES${NC}"
echo "-------------------"

# HIPAA compliance
run_gate "HIPAA Compliance" "python scripts/hipaa-compliance-check.py"

# 6. Documentation Gates
echo -e "${YELLOW}6. DOCUMENTATION GATES${NC}"
echo "----------------------"

# Check for required documentation files
REQUIRED_DOCS=(
    "README.md"
    "SECURITY.md"
    "docs/api.md"
    "docs/deployment.md"
)

for doc in "${REQUIRED_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "${GREEN}✅ Found: $doc${NC}"
    else
        echo -e "${RED}❌ Missing: $doc${NC}"
        FAILED_GATES+=("Documentation: $doc")
    fi
done

# Summary
echo ""
echo -e "${BLUE}=================================================="
echo -e "QUALITY GATES SUMMARY"
echo -e "==================================================${NC}"

if [ ${#FAILED_GATES[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All quality gates passed!${NC}"
    echo -e "${GREEN}Safe to commit and push your changes.${NC}"
    exit 0
else
    echo -e "${RED}❌ Failed quality gates:${NC}"
    for gate in "${FAILED_GATES[@]}"; do
        echo -e "${RED}   - $gate${NC}"
    done
    echo ""
    echo -e "${YELLOW}⚠️  Fix these issues before pushing code!${NC}"
    echo -e "${YELLOW}   Run individual checks for detailed error messages.${NC}"
    exit 1
fi
