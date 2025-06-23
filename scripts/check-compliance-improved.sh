#!/bin/bash

# Comprehensive code compliance checking script for Haven Health Passport
# Checks Python code quality, type safety, security, healthcare standards, and testing

# Set error handling
set -euo pipefail

# Set colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Haven Health Passport Code Compliance Report ===${NC}"
echo -e "${YELLOW}Checking Python code quality, type safety, security, and healthcare compliance...${NC}"

# Define project root and output directory
PROJECT_ROOT="/Users/cadenceapeiron/Documents/HavenHealthPassport"
VENV_PATH="$PROJECT_ROOT/venv"
TEMP_DIR=$(mktemp -d)
COMPLIANCE_DIR="$PROJECT_ROOT/compliance_reports"
ERROR_CHUNKS_DIR="$PROJECT_ROOT/error_chunks"
LINES_PER_CHUNK=500
trap 'rm -rf "$TEMP_DIR"' EXIT

# Ensure we're using the virtual environment
if [ -d "$VENV_PATH" ]; then
  export PATH="$VENV_PATH/bin:$PATH"
  echo -e "${GREEN}Using virtual environment at: $VENV_PATH${NC}"
else
  echo -e "${YELLOW}Warning: Virtual environment not found at $VENV_PATH${NC}"
  echo -e "${YELLOW}Some checks may fail if dependencies are not installed globally${NC}"
fi

# Create output directories
mkdir -p "$COMPLIANCE_DIR"
mkdir -p "$ERROR_CHUNKS_DIR"

# Helper function to clean numeric values
clean_number() {
  echo "$1" | tr -d '\n\r ' | grep -o '^[0-9]*' || echo "0"
}

# Function to check if a command exists
check_command() {
  if ! command -v "$1" &> /dev/null; then
    echo -e "${RED}Error: $1 is not installed or not in PATH${NC}"
    return 1
  fi
  return 0
}

# Validate required tools
echo -e "${BLUE}Checking required tools...${NC}"
MISSING_TOOLS=0
for tool in flake8 pylint mypy pytest bandit black isort radon; do
  if ! check_command "$tool"; then
    ((MISSING_TOOLS++))
  fi
done

if [ "$MISSING_TOOLS" -gt 0 ]; then
  echo -e "${RED}Error: $MISSING_TOOLS required tools are missing${NC}"
  echo -e "${YELLOW}Please activate your virtual environment or install missing tools${NC}"
  exit 1
fi

# Validate source directories exist
if [ ! -d "$PROJECT_ROOT/src" ]; then
  echo -e "${RED}Error: Source directory $PROJECT_ROOT/src not found${NC}"
  exit 1
fi

# Define output files
FLAKE8_OUTPUT="$TEMP_DIR/flake8_output.txt"
PYLINT_OUTPUT="$TEMP_DIR/pylint_output.txt"
MYPY_OUTPUT="$TEMP_DIR/mypy_output.txt"
PYTEST_OUTPUT="$TEMP_DIR/pytest_output.txt"
COVERAGE_OUTPUT="$TEMP_DIR/coverage_output.txt"
BANDIT_OUTPUT="$TEMP_DIR/bandit_output.txt"
BLACK_OUTPUT="$TEMP_DIR/black_output.txt"
ISORT_OUTPUT="$TEMP_DIR/isort_output.txt"
FHIR_OUTPUT="$TEMP_DIR/fhir_output.txt"
HIPAA_OUTPUT="$TEMP_DIR/hipaa_output.txt"
SUMMARY_FILE="$COMPLIANCE_DIR/compliance_summary.txt"

# Find Python files
echo -e "${BLUE}Finding Python files to check...${NC}"
PYTHON_FILES_LIST="$TEMP_DIR/python_files_list.txt"

# Build find command based on what directories exist
FIND_PATHS=""
[ -d "$PROJECT_ROOT/src" ] && FIND_PATHS="$FIND_PATHS $PROJECT_ROOT/src"
[ -d "$PROJECT_ROOT/tests" ] && FIND_PATHS="$FIND_PATHS $PROJECT_ROOT/tests"

if [ -z "$FIND_PATHS" ]; then
  echo -e "${RED}Error: No source or test directories found${NC}"
  exit 1
fi

find $FIND_PATHS -type f -name "*.py" \
  ! -path "*/venv/*" ! -path "*/__pycache__/*" ! -path "*/dist/*" \
  ! -path "*/.mypy_cache/*" ! -path "*/htmlcov/*" ! -path "*/.pytest_cache/*" \
  > "$PYTHON_FILES_LIST"

TOTAL_FILES=$(wc -l < "$PYTHON_FILES_LIST" | tr -d ' ')
echo -e "${BLUE}Found $TOTAL_FILES Python files to check${NC}"

if [ "$TOTAL_FILES" -eq 0 ]; then
  echo -e "${YELLOW}Warning: No Python files found to check${NC}"
  exit 0
fi

# Create summary header with timestamp
{
  echo "# Haven Health Passport Compliance Summary Report"
  echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Total Files Checked: $TOTAL_FILES"
  echo "Project Root: $PROJECT_ROOT"
  echo ""
  echo "This report provides a comprehensive overview of code compliance issues."
  echo "Special attention is given to healthcare standards and security compliance."
  echo ""
} > "$SUMMARY_FILE"

# Function to run flake8 check
run_flake8_check() {
  echo -e "${BLUE}Running flake8 (style guide enforcement)...${NC}"
  cd "$PROJECT_ROOT" && flake8 src/ tests/ \
    --exclude=venv,__pycache__,dist,.mypy_cache,htmlcov,.pytest_cache \
    --max-line-length=88 \
    --extend-ignore=E203,W503,E501 \
    --count \
    --statistics \
    --show-source \
    > "$FLAKE8_OUTPUT" 2>&1 || true

  if [ -s "$FLAKE8_OUTPUT" ]; then
    FLAKE8_E_ERRORS=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: E[0-9]+" "$FLAKE8_OUTPUT" 2>/dev/null || echo "0")
    FLAKE8_W_ERRORS=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: W[0-9]+" "$FLAKE8_OUTPUT" 2>/dev/null || echo "0")
    FLAKE8_F_ERRORS=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: F[0-9]+" "$FLAKE8_OUTPUT" 2>/dev/null || echo "0")
    FLAKE8_C_ERRORS=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: C[0-9]+" "$FLAKE8_OUTPUT" 2>/dev/null || echo "0")
    FLAKE8_N_ERRORS=$(grep -cE "^[^:]+:[0-9]+:[0-9]+: N[0-9]+" "$FLAKE8_OUTPUT" 2>/dev/null || echo "0")
  else
    FLAKE8_E_ERRORS=0
    FLAKE8_W_ERRORS=0
    FLAKE8_F_ERRORS=0
    FLAKE8_C_ERRORS=0
    FLAKE8_N_ERRORS=0
  fi

  FLAKE8_E_ERRORS=$(clean_number "$FLAKE8_E_ERRORS")
  FLAKE8_W_ERRORS=$(clean_number "$FLAKE8_W_ERRORS")
  FLAKE8_F_ERRORS=$(clean_number "$FLAKE8_F_ERRORS")
  FLAKE8_C_ERRORS=$(clean_number "$FLAKE8_C_ERRORS")
  FLAKE8_N_ERRORS=$(clean_number "$FLAKE8_N_ERRORS")

  FLAKE8_TOTAL=$((FLAKE8_E_ERRORS + FLAKE8_W_ERRORS + FLAKE8_F_ERRORS + FLAKE8_C_ERRORS + FLAKE8_N_ERRORS))
  echo "$FLAKE8_TOTAL" > "$TEMP_DIR/flake8_total.txt"

  # Store individual counts for detailed reporting
  echo "$FLAKE8_E_ERRORS" > "$TEMP_DIR/flake8_e_errors.txt"
  echo "$FLAKE8_W_ERRORS" > "$TEMP_DIR/flake8_w_errors.txt"
  echo "$FLAKE8_F_ERRORS" > "$TEMP_DIR/flake8_f_errors.txt"
  echo "$FLAKE8_C_ERRORS" > "$TEMP_DIR/flake8_c_errors.txt"
  echo "$FLAKE8_N_ERRORS" > "$TEMP_DIR/flake8_n_errors.txt"
}

# Function to run pylint check
run_pylint_check() {
  echo -e "${BLUE}Running pylint (comprehensive code analysis)...${NC}"
  cd "$PROJECT_ROOT" && pylint src/ tests/ \
    --disable=R,C0114,C0115,C0116,C0103 \
    --output-format=text \
    --reports=n \
    --score=n \
    --msg-template='{path}:{line}:{column}: {msg_id}: {msg} ({symbol})' \
    > "$PYLINT_OUTPUT" 2>&1 || true

  if [ -s "$PYLINT_OUTPUT" ]; then
    PYLINT_E_ERRORS=$(grep -cE ":[0-9]+:[0-9]+: E[0-9]+" "$PYLINT_OUTPUT" 2>/dev/null || echo "0")
    PYLINT_W_ERRORS=$(grep -cE ":[0-9]+:[0-9]+: W[0-9]+" "$PYLINT_OUTPUT" 2>/dev/null || echo "0")
    PYLINT_C_ERRORS=$(grep -cE ":[0-9]+:[0-9]+: C[0-9]+" "$PYLINT_OUTPUT" 2>/dev/null || echo "0")
  else
    PYLINT_E_ERRORS=0
    PYLINT_W_ERRORS=0
    PYLINT_C_ERRORS=0
  fi

  PYLINT_E_ERRORS=$(clean_number "$PYLINT_E_ERRORS")
  PYLINT_W_ERRORS=$(clean_number "$PYLINT_W_ERRORS")
  PYLINT_C_ERRORS=$(clean_number "$PYLINT_C_ERRORS")

  PYLINT_TOTAL=$((PYLINT_E_ERRORS + PYLINT_W_ERRORS + PYLINT_C_ERRORS))
  echo "$PYLINT_TOTAL" > "$TEMP_DIR/pylint_total.txt"
  echo "$PYLINT_E_ERRORS" > "$TEMP_DIR/pylint_e_errors.txt"
  echo "$PYLINT_W_ERRORS" > "$TEMP_DIR/pylint_w_errors.txt"
}

# Function to run mypy check
run_mypy_check() {
  echo -e "${BLUE}Running mypy (type checking)...${NC}"
  cd "$PROJECT_ROOT" && mypy src/ tests/ \
    --ignore-missing-imports \
    --no-implicit-optional \
    --warn-redundant-casts \
    --warn-unused-ignores \
    --strict-equality \
    --disallow-untyped-defs \
    --disallow-incomplete-defs \
    --check-untyped-defs \
    --warn-return-any \
    --warn-unreachable \
    --pretty \
    > "$MYPY_OUTPUT" 2>&1 || true

  if [ -s "$MYPY_OUTPUT" ]; then
    MYPY_ERRORS=$(grep -c " error:" "$MYPY_OUTPUT" 2>/dev/null || echo "0")
    MYPY_WARNINGS=$(grep -c " warning:" "$MYPY_OUTPUT" 2>/dev/null || echo "0")
    MYPY_NOTES=$(grep -c " note:" "$MYPY_OUTPUT" 2>/dev/null || echo "0")
  else
    MYPY_ERRORS=0
    MYPY_WARNINGS=0
    MYPY_NOTES=0
  fi

  MYPY_ERRORS=$(clean_number "$MYPY_ERRORS")
  MYPY_WARNINGS=$(clean_number "$MYPY_WARNINGS")
  MYPY_TOTAL=$((MYPY_ERRORS + MYPY_WARNINGS))
  echo "$MYPY_TOTAL" > "$TEMP_DIR/mypy_total.txt"
  echo "$MYPY_ERRORS" > "$TEMP_DIR/mypy_errors.txt"
  echo "$MYPY_WARNINGS" > "$TEMP_DIR/mypy_warnings.txt"
}

# Function to run pytest with coverage
run_pytest_coverage() {
  echo -e "${BLUE}Running pytest with coverage...${NC}"

  # Check if tests directory exists
  if [ ! -d "$PROJECT_ROOT/tests" ]; then
    echo -e "${YELLOW}Warning: No tests directory found${NC}"
    echo "0" > "$TEMP_DIR/test_failures.txt"
    echo "0" > "$TEMP_DIR/coverage_pct.txt"
    return
  fi

  cd "$PROJECT_ROOT" && python -m pytest tests/ \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-branch \
    --tb=short \
    -v \
    > "$PYTEST_OUTPUT" 2>&1 || true

  # Extract test results
  if [ -s "$PYTEST_OUTPUT" ]; then
    TEST_PASSED=$(grep -oE "[0-9]+ passed" "$PYTEST_OUTPUT" | grep -oE "[0-9]+" | head -1 || echo "0")
    TEST_FAILED=$(grep -oE "[0-9]+ failed" "$PYTEST_OUTPUT" | grep -oE "[0-9]+" | head -1 || echo "0")
    TEST_SKIPPED=$(grep -oE "[0-9]+ skipped" "$PYTEST_OUTPUT" | grep -oE "[0-9]+" | head -1 || echo "0")
    TEST_ERRORS=$(grep -oE "[0-9]+ error" "$PYTEST_OUTPUT" | grep -oE "[0-9]+" | head -1 || echo "0")

    # Extract coverage percentage - look for the TOTAL line
    COVERAGE_PCT=$(grep -E "^TOTAL.*[0-9]+%" "$PYTEST_OUTPUT" | grep -oE "[0-9]+%" | grep -oE "[0-9]+" | tail -1 || echo "0")
  else
    TEST_PASSED=0
    TEST_FAILED=0
    TEST_SKIPPED=0
    TEST_ERRORS=0
    COVERAGE_PCT=0
  fi

  TEST_FAILED=$(clean_number "$TEST_FAILED")
  TEST_ERRORS=$(clean_number "$TEST_ERRORS")
  TOTAL_TEST_ISSUES=$((TEST_FAILED + TEST_ERRORS))

  echo "$TOTAL_TEST_ISSUES" > "$TEMP_DIR/test_failures.txt"
  echo "$COVERAGE_PCT" > "$TEMP_DIR/coverage_pct.txt"
}

# Function to run bandit security check
run_bandit_check() {
  echo -e "${BLUE}Running bandit (security linter)...${NC}"
  cd "$PROJECT_ROOT" && bandit -r src/ \
    -f txt \
    -ll \
    --exclude='/test_,/tests/' \
    > "$BANDIT_OUTPUT" 2>&1 || true

  if [ -s "$BANDIT_OUTPUT" ]; then
    SECURITY_HIGH=$(grep -c "Severity: High" "$BANDIT_OUTPUT" 2>/dev/null || echo "0")
    SECURITY_MEDIUM=$(grep -c "Severity: Medium" "$BANDIT_OUTPUT" 2>/dev/null || echo "0")
    SECURITY_LOW=$(grep -c "Severity: Low" "$BANDIT_OUTPUT" 2>/dev/null || echo "0")
  else
    SECURITY_HIGH=0
    SECURITY_MEDIUM=0
    SECURITY_LOW=0
  fi

  SECURITY_HIGH=$(clean_number "$SECURITY_HIGH")
  SECURITY_MEDIUM=$(clean_number "$SECURITY_MEDIUM")
  SECURITY_LOW=$(clean_number "$SECURITY_LOW")

  SECURITY_TOTAL=$((SECURITY_HIGH + SECURITY_MEDIUM + SECURITY_LOW))
  echo "$SECURITY_TOTAL" > "$TEMP_DIR/security_total.txt"
  echo "$SECURITY_HIGH" > "$TEMP_DIR/security_high.txt"
  echo "$SECURITY_MEDIUM" > "$TEMP_DIR/security_medium.txt"
  echo "$SECURITY_LOW" > "$TEMP_DIR/security_low.txt"
}

# Function to check formatting
check_formatting() {
  echo -e "${BLUE}Checking code formatting (Black & isort)...${NC}"

  # Check Black formatting
  cd "$PROJECT_ROOT" && black --check --diff src/ tests/ > "$BLACK_OUTPUT" 2>&1 || true
  if [ -s "$BLACK_OUTPUT" ]; then
    BLACK_ISSUES=$(grep -c "would reformat" "$BLACK_OUTPUT" 2>/dev/null || echo "0")
  else
    BLACK_ISSUES=0
  fi

  # Check import sorting
  cd "$PROJECT_ROOT" && isort --check-only --diff src/ tests/ > "$ISORT_OUTPUT" 2>&1 || true
  if [ -s "$ISORT_OUTPUT" ]; then
    ISORT_ISSUES=$(grep -c "ERROR:" "$ISORT_OUTPUT" 2>/dev/null || echo "0")
  else
    ISORT_ISSUES=0
  fi

  BLACK_ISSUES=$(clean_number "$BLACK_ISSUES")
  ISORT_ISSUES=$(clean_number "$ISORT_ISSUES")

  FORMATTING_TOTAL=$((BLACK_ISSUES + ISORT_ISSUES))
  echo "$FORMATTING_TOTAL" > "$TEMP_DIR/formatting_total.txt"
  echo "$BLACK_ISSUES" > "$TEMP_DIR/black_issues.txt"
  echo "$ISORT_ISSUES" > "$TEMP_DIR/isort_issues.txt"
}

# Enhanced function to check healthcare compliance
check_healthcare_compliance() {
  echo -e "${BLUE}Checking healthcare standards compliance...${NC}"

  FHIR_ISSUES=0
  HL7_ISSUES=0
  HIPAA_ISSUES=0
  PHI_UNENCRYPTED=0
  AUDIT_MISSING=0
  ACCESS_CONTROL_MISSING=0

  > "$HIPAA_OUTPUT"
  > "$FHIR_OUTPUT"

  # More comprehensive healthcare compliance checks
  while IFS= read -r file; do
    # Skip test files for some checks
    if [[ "$file" =~ /tests?/ ]]; then
      continue
    fi

    # Check for FHIR resource handling
    if grep -qE "(fhir|hl7|Patient|Observation|Medication|Encounter)" "$file" 2>/dev/null; then
      # Check for proper FHIR validation
      if ! grep -qE "(validate|validator|ValidationError|check.*valid)" "$file" 2>/dev/null; then
        ((FHIR_ISSUES++))
        echo "Missing FHIR validation: $file" >> "$FHIR_OUTPUT"
      fi

      # Check for proper resource typing
      if ! grep -qE "(Resource|DomainResource|Bundle)" "$file" 2>/dev/null; then
        ((FHIR_ISSUES++))
        echo "Missing FHIR resource typing: $file" >> "$FHIR_OUTPUT"
      fi
    fi

    # Check for PHI handling
    if grep -qiE "(patient.*data|medical.*record|health.*information|phi|pii|ssn|dob|diagnosis|medication)" "$file" 2>/dev/null; then
      # Check for encryption
      if ! grep -qE "(encrypt|cipher|crypto|hash|secure.*stor|field_encryption)" "$file" 2>/dev/null; then
        ((PHI_UNENCRYPTED++))
        echo "Potential unencrypted PHI: $file" >> "$HIPAA_OUTPUT"
      fi

      # Check for audit logging
      if grep -qE "(def.*get|def.*read|def.*access|def.*fetch|def.*retrieve).*patient" "$file" 2>/dev/null; then
        if ! grep -qE "(audit|log.*access|track.*access|record.*access)" "$file" 2>/dev/null; then
          ((AUDIT_MISSING++))
          echo "Missing audit logging for PHI access: $file" >> "$HIPAA_OUTPUT"
        fi
      fi

      # Check for access control
      if ! grep -qE "(permission|authorize|auth.*required|@.*protect|role.*based|access.*control)" "$file" 2>/dev/null; then
        ((ACCESS_CONTROL_MISSING++))
        echo "Missing access control for PHI: $file" >> "$HIPAA_OUTPUT"
      fi
    fi

    # Check for data retention policies
    if grep -qE "(delete.*patient|purge.*data|remove.*record)" "$file" 2>/dev/null; then
      if ! grep -qE "(retention.*policy|compliance.*delete|audit.*delete)" "$file" 2>/dev/null; then
        ((HIPAA_ISSUES++))
        echo "Missing data retention compliance: $file" >> "$HIPAA_OUTPUT"
      fi
    fi

    # Check for secure communication
    if grep -qE "(send.*patient|transmit.*health|share.*medical|export.*phi)" "$file" 2>/dev/null; then
      if ! grep -qE "(tls|ssl|https|secure.*channel|encrypt.*transit)" "$file" 2>/dev/null; then
        ((HIPAA_ISSUES++))
        echo "Potential insecure PHI transmission: $file" >> "$HIPAA_OUTPUT"
      fi
    fi
  done < "$PYTHON_FILES_LIST"

  HIPAA_ISSUES=$((HIPAA_ISSUES + PHI_UNENCRYPTED + AUDIT_MISSING + ACCESS_CONTROL_MISSING))
  HEALTHCARE_TOTAL=$((FHIR_ISSUES + HL7_ISSUES + HIPAA_ISSUES))

  echo "$HEALTHCARE_TOTAL" > "$TEMP_DIR/healthcare_total.txt"
  echo "$FHIR_ISSUES" > "$TEMP_DIR/fhir_issues.txt"
  echo "$HIPAA_ISSUES" > "$TEMP_DIR/hipaa_issues.txt"
  echo "$PHI_UNENCRYPTED" > "$TEMP_DIR/phi_unencrypted.txt"
  echo "$AUDIT_MISSING" > "$TEMP_DIR/audit_missing.txt"
  echo "$ACCESS_CONTROL_MISSING" > "$TEMP_DIR/access_control_missing.txt"
}

# Function to check documentation
check_documentation() {
  echo -e "${BLUE}Checking documentation...${NC}"

  # Count files missing docstrings
  MISSING_MODULE_DOCS=0
  MISSING_CLASS_DOCS=0
  MISSING_FUNCTION_DOCS=0

  while IFS= read -r file; do
    # Check for module docstring (first non-comment, non-blank line should be docstring)
    if ! head -n 20 "$file" | grep -E '^"""' > /dev/null 2>&1; then
      ((MISSING_MODULE_DOCS++))
    fi

    # Count classes without docstrings
    CLASSES=$(grep -c "^class " "$file" 2>/dev/null || echo "0")
    if [ "$CLASSES" -gt 0 ]; then
      # Check each class for docstring
      while IFS= read -r line_num; do
        # Get next few lines after class definition
        tail -n +$((line_num + 1)) "$file" | head -n 5 | grep -q '"""' || ((MISSING_CLASS_DOCS++))
      done < <(grep -n "^class " "$file" | cut -d: -f1)
    fi

    # Count functions without docstrings
    FUNCTIONS=$(grep -c "^def " "$file" 2>/dev/null || echo "0")
    if [ "$FUNCTIONS" -gt 0 ]; then
      # Check each function for docstring
      while IFS= read -r line_num; do
        # Get next few lines after function definition
        tail -n +$((line_num + 1)) "$file" | head -n 5 | grep -q '"""' || ((MISSING_FUNCTION_DOCS++))
      done < <(grep -n "^def " "$file" | cut -d: -f1)
    fi
  done < "$PYTHON_FILES_LIST"

  DOCS_TOTAL=$((MISSING_MODULE_DOCS + MISSING_CLASS_DOCS + MISSING_FUNCTION_DOCS))
  echo "$DOCS_TOTAL" > "$TEMP_DIR/docs_total.txt"
  echo "$MISSING_MODULE_DOCS" > "$TEMP_DIR/missing_module_docs.txt"
  echo "$MISSING_CLASS_DOCS" > "$TEMP_DIR/missing_class_docs.txt"
  echo "$MISSING_FUNCTION_DOCS" > "$TEMP_DIR/missing_function_docs.txt"
}

# Function to check code complexity
check_complexity() {
  echo -e "${BLUE}Checking code complexity...${NC}"

  # Use radon for cyclomatic complexity
  cd "$PROJECT_ROOT" && radon cc src/ tests/ -s -a \
    > "$TEMP_DIR/complexity_output.txt" 2>&1 || true

  if [ -s "$TEMP_DIR/complexity_output.txt" ]; then
    COMPLEX_A=$(grep -c " - A " "$TEMP_DIR/complexity_output.txt" 2>/dev/null || echo "0")
    COMPLEX_B=$(grep -c " - B " "$TEMP_DIR/complexity_output.txt" 2>/dev/null || echo "0")
    COMPLEX_C=$(grep -c " - C " "$TEMP_DIR/complexity_output.txt" 2>/dev/null || echo "0")
    COMPLEX_D=$(grep -c " - D " "$TEMP_DIR/complexity_output.txt" 2>/dev/null || echo "0")
    COMPLEX_E=$(grep -c " - E " "$TEMP_DIR/complexity_output.txt" 2>/dev/null || echo "0")
    COMPLEX_F=$(grep -c " - F " "$TEMP_DIR/complexity_output.txt" 2>/dev/null || echo "0")
  else
    COMPLEX_A=0
    COMPLEX_B=0
    COMPLEX_C=0
    COMPLEX_D=0
    COMPLEX_E=0
    COMPLEX_F=0
  fi

  # Count only problematic complexity (C and above)
  COMPLEX_C=$(clean_number "$COMPLEX_C")
  COMPLEX_D=$(clean_number "$COMPLEX_D")
  COMPLEX_E=$(clean_number "$COMPLEX_E")
  COMPLEX_F=$(clean_number "$COMPLEX_F")

  COMPLEXITY_ISSUES=$((COMPLEX_C + COMPLEX_D + COMPLEX_E + COMPLEX_F))
  echo "$COMPLEXITY_ISSUES" > "$TEMP_DIR/complexity_total.txt"
}

# Run all checks in parallel with error handling
echo -e "${BLUE}Running all compliance checks in parallel...${NC}"

# Initialize default values in case checks fail
echo "0" > "$TEMP_DIR/flake8_total.txt"
echo "0" > "$TEMP_DIR/pylint_total.txt"
echo "0" > "$TEMP_DIR/mypy_total.txt"
echo "0" > "$TEMP_DIR/test_failures.txt"
echo "0" > "$TEMP_DIR/coverage_pct.txt"
echo "0" > "$TEMP_DIR/security_total.txt"
echo "0" > "$TEMP_DIR/formatting_total.txt"
echo "0" > "$TEMP_DIR/healthcare_total.txt"
echo "0" > "$TEMP_DIR/docs_total.txt"
echo "0" > "$TEMP_DIR/complexity_total.txt"

# Run checks
run_flake8_check &
run_pylint_check &
run_mypy_check &
run_pytest_coverage &
run_bandit_check &
check_formatting &
check_healthcare_compliance &
check_documentation &
check_complexity &
wait

# Read results with fallback to 0
FLAKE8_TOTAL=$(clean_number "$(cat "$TEMP_DIR/flake8_total.txt" 2>/dev/null || echo "0")")
PYLINT_TOTAL=$(clean_number "$(cat "$TEMP_DIR/pylint_total.txt" 2>/dev/null || echo "0")")
MYPY_TOTAL=$(clean_number "$(cat "$TEMP_DIR/mypy_total.txt" 2>/dev/null || echo "0")")
TEST_FAILURES=$(clean_number "$(cat "$TEMP_DIR/test_failures.txt" 2>/dev/null || echo "0")")
COVERAGE_PCT=$(clean_number "$(cat "$TEMP_DIR/coverage_pct.txt" 2>/dev/null || echo "0")")
SECURITY_TOTAL=$(clean_number "$(cat "$TEMP_DIR/security_total.txt" 2>/dev/null || echo "0")")
FORMATTING_TOTAL=$(clean_number "$(cat "$TEMP_DIR/formatting_total.txt" 2>/dev/null || echo "0")")
HEALTHCARE_TOTAL=$(clean_number "$(cat "$TEMP_DIR/healthcare_total.txt" 2>/dev/null || echo "0")")
DOCS_TOTAL=$(clean_number "$(cat "$TEMP_DIR/docs_total.txt" 2>/dev/null || echo "0")")
COMPLEXITY_TOTAL=$(clean_number "$(cat "$TEMP_DIR/complexity_total.txt" 2>/dev/null || echo "0")")

# Read detailed counts
FLAKE8_E_ERRORS=$(clean_number "$(cat "$TEMP_DIR/flake8_e_errors.txt" 2>/dev/null || echo "0")")
FLAKE8_W_ERRORS=$(clean_number "$(cat "$TEMP_DIR/flake8_w_errors.txt" 2>/dev/null || echo "0")")
FLAKE8_F_ERRORS=$(clean_number "$(cat "$TEMP_DIR/flake8_f_errors.txt" 2>/dev/null || echo "0")")
FLAKE8_C_ERRORS=$(clean_number "$(cat "$TEMP_DIR/flake8_c_errors.txt" 2>/dev/null || echo "0")")
FLAKE8_N_ERRORS=$(clean_number "$(cat "$TEMP_DIR/flake8_n_errors.txt" 2>/dev/null || echo "0")")

PYLINT_E_ERRORS=$(clean_number "$(cat "$TEMP_DIR/pylint_e_errors.txt" 2>/dev/null || echo "0")")
PYLINT_W_ERRORS=$(clean_number "$(cat "$TEMP_DIR/pylint_w_errors.txt" 2>/dev/null || echo "0")")

MYPY_ERRORS=$(clean_number "$(cat "$TEMP_DIR/mypy_errors.txt" 2>/dev/null || echo "0")")
MYPY_WARNINGS=$(clean_number "$(cat "$TEMP_DIR/mypy_warnings.txt" 2>/dev/null || echo "0")")

SECURITY_HIGH=$(clean_number "$(cat "$TEMP_DIR/security_high.txt" 2>/dev/null || echo "0")")
SECURITY_MEDIUM=$(clean_number "$(cat "$TEMP_DIR/security_medium.txt" 2>/dev/null || echo "0")")
SECURITY_LOW=$(clean_number "$(cat "$TEMP_DIR/security_low.txt" 2>/dev/null || echo "0")")

BLACK_ISSUES=$(clean_number "$(cat "$TEMP_DIR/black_issues.txt" 2>/dev/null || echo "0")")
ISORT_ISSUES=$(clean_number "$(cat "$TEMP_DIR/isort_issues.txt" 2>/dev/null || echo "0")")

FHIR_ISSUES=$(clean_number "$(cat "$TEMP_DIR/fhir_issues.txt" 2>/dev/null || echo "0")")
HIPAA_ISSUES=$(clean_number "$(cat "$TEMP_DIR/hipaa_issues.txt" 2>/dev/null || echo "0")")
PHI_UNENCRYPTED=$(clean_number "$(cat "$TEMP_DIR/phi_unencrypted.txt" 2>/dev/null || echo "0")")
AUDIT_MISSING=$(clean_number "$(cat "$TEMP_DIR/audit_missing.txt" 2>/dev/null || echo "0")")
ACCESS_CONTROL_MISSING=$(clean_number "$(cat "$TEMP_DIR/access_control_missing.txt" 2>/dev/null || echo "0")")

MISSING_MODULE_DOCS=$(clean_number "$(cat "$TEMP_DIR/missing_module_docs.txt" 2>/dev/null || echo "0")")
MISSING_CLASS_DOCS=$(clean_number "$(cat "$TEMP_DIR/missing_class_docs.txt" 2>/dev/null || echo "0")")
MISSING_FUNCTION_DOCS=$(clean_number "$(cat "$TEMP_DIR/missing_function_docs.txt" 2>/dev/null || echo "0")")

# Calculate grand total
GRAND_TOTAL=$((FLAKE8_TOTAL + PYLINT_TOTAL + MYPY_TOTAL + TEST_FAILURES + SECURITY_TOTAL + FORMATTING_TOTAL + HEALTHCARE_TOTAL + DOCS_TOTAL + COMPLEXITY_TOTAL))

# Function to create unified error chunks
create_unified_chunks() {
  local output_dir="$ERROR_CHUNKS_DIR"
  local temp_unified="$TEMP_DIR/unified_errors.txt"

  # Clean old chunks
  rm -f "$output_dir"/error_chunk_*.txt

  # Create unified file with header
  {
    echo "# Haven Health Passport Unified Compliance Errors"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo ""
    echo "This file contains all compliance errors found in the codebase."
    echo "Errors are prioritized by criticality for healthcare applications."
    echo "============================================"
    echo ""
  } > "$temp_unified"

  # Add Healthcare Compliance Issues (HIGHEST PRIORITY)
  if [ "$HEALTHCARE_TOTAL" -gt 0 ]; then
    echo "## Healthcare Compliance Issues (CRITICAL)" >> "$temp_unified"
    echo "" >> "$temp_unified"
    echo "### Summary:" >> "$temp_unified"
    echo "- FHIR Validation Issues: $FHIR_ISSUES" >> "$temp_unified"
    echo "- Total HIPAA Compliance Issues: $HIPAA_ISSUES" >> "$temp_unified"
    echo "  - Unencrypted PHI: $PHI_UNENCRYPTED" >> "$temp_unified"
    echo "  - Missing Audit Logs: $AUDIT_MISSING" >> "$temp_unified"
    echo "  - Missing Access Controls: $ACCESS_CONTROL_MISSING" >> "$temp_unified"
    echo "" >> "$temp_unified"

    if [ -s "$FHIR_OUTPUT" ]; then
      echo "### FHIR Compliance Details:" >> "$temp_unified"
      cat "$FHIR_OUTPUT" >> "$temp_unified"
      echo "" >> "$temp_unified"
    fi

    if [ -s "$HIPAA_OUTPUT" ]; then
      echo "### HIPAA Compliance Details:" >> "$temp_unified"
      cat "$HIPAA_OUTPUT" >> "$temp_unified"
      echo "" >> "$temp_unified"
    fi

    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Add Security Issues (bandit)
  if [ "$SECURITY_TOTAL" -gt 0 ] && [ -s "$BANDIT_OUTPUT" ]; then
    echo "## Security Issues (bandit)" >> "$temp_unified"
    echo "" >> "$temp_unified"
    cat "$BANDIT_OUTPUT" >> "$temp_unified"
    echo "" >> "$temp_unified"
    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Add Type Safety Errors (mypy)
  if [ "$MYPY_TOTAL" -gt 0 ] && [ -s "$MYPY_OUTPUT" ]; then
    echo "## Type Safety Errors (mypy)" >> "$temp_unified"
    echo "" >> "$temp_unified"
    cat "$MYPY_OUTPUT" >> "$temp_unified"
    echo "" >> "$temp_unified"
    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Add Test Failures
  if [ "$TEST_FAILURES" -gt 0 ] && [ -s "$PYTEST_OUTPUT" ]; then
    echo "## Test Failures (pytest)" >> "$temp_unified"
    echo "" >> "$temp_unified"
    # Extract only the failure section
    awk '/FAILURES|ERRORS/,/short test summary/' "$PYTEST_OUTPUT" >> "$temp_unified" 2>/dev/null || cat "$PYTEST_OUTPUT" >> "$temp_unified"
    echo "" >> "$temp_unified"
    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Add Code Quality Issues (pylint)
  if [ "$PYLINT_TOTAL" -gt 0 ] && [ -s "$PYLINT_OUTPUT" ]; then
    echo "## Code Quality Issues (pylint)" >> "$temp_unified"
    echo "" >> "$temp_unified"
    cat "$PYLINT_OUTPUT" >> "$temp_unified"
    echo "" >> "$temp_unified"
    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Add Style Issues (flake8)
  if [ "$FLAKE8_TOTAL" -gt 0 ] && [ -s "$FLAKE8_OUTPUT" ]; then
    echo "## Style Guide Violations (flake8)" >> "$temp_unified"
    echo "" >> "$temp_unified"
    cat "$FLAKE8_OUTPUT" >> "$temp_unified"
    echo "" >> "$temp_unified"
    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Add Formatting Issues
  if [ "$FORMATTING_TOTAL" -gt 0 ]; then
    echo "## Formatting Issues" >> "$temp_unified"
    echo "" >> "$temp_unified"
    if [ "$BLACK_ISSUES" -gt 0 ] && [ -s "$BLACK_OUTPUT" ]; then
      echo "### Black formatting issues ($BLACK_ISSUES files):" >> "$temp_unified"
      grep "would reformat" "$BLACK_OUTPUT" >> "$temp_unified" 2>/dev/null || true
      echo "" >> "$temp_unified"
    fi
    if [ "$ISORT_ISSUES" -gt 0 ] && [ -s "$ISORT_OUTPUT" ]; then
      echo "### Import sorting issues ($ISORT_ISSUES files):" >> "$temp_unified"
      grep "ERROR:" "$ISORT_OUTPUT" >> "$temp_unified" 2>/dev/null || true
      echo "" >> "$temp_unified"
    fi
    echo "============================================" >> "$temp_unified"
    echo "" >> "$temp_unified"
  fi

  # Split into chunks
  local total_lines=$(wc -l < "$temp_unified")
  local num_chunks=$(( (total_lines + LINES_PER_CHUNK - 1) / LINES_PER_CHUNK ))

  if [ "$num_chunks" -gt 0 ]; then
    echo -e "${BLUE}Creating $num_chunks error chunks of $LINES_PER_CHUNK lines each...${NC}"

    # Split the file
    tail -n +7 "$temp_unified" | split -l "$LINES_PER_CHUNK" - "$output_dir/error_part_"

    # Add header to each chunk
    local chunk_num=0
    for chunk in "$output_dir"/error_part_*; do
      [ -f "$chunk" ] || continue
      chunk_num=$((chunk_num + 1))
      local final_name="$output_dir/error_chunk_$(printf "%02d" $chunk_num).txt"

      {
        echo "# Haven Health Passport Unified Compliance Errors"
        echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z') (Chunk $chunk_num of $num_chunks)"
        echo ""
        echo "This file contains compliance errors found in the codebase."
        echo "============================================"
        echo ""
        cat "$chunk"
      } > "$final_name"

      rm "$chunk"
    done
  fi
}

# Create unified chunks if there are errors
if [ "$GRAND_TOTAL" -gt 0 ]; then
  echo -e "${BLUE}Creating unified error chunks...${NC}"
  create_unified_chunks
fi

# Print comprehensive report
{
echo -e "\n${CYAN}=========================================${NC}"
echo -e "${CYAN}  HAVEN HEALTH PASSPORT COMPLIANCE SUMMARY${NC}"
echo -e "${CYAN}=========================================${NC}"

# Healthcare Compliance (CRITICAL for medical software)
echo -e "\n${PURPLE}1. Healthcare Compliance:${NC}"
printf "${YELLOW}   Total Healthcare Issues:     ${RED}%7d${NC}\n" $HEALTHCARE_TOTAL
if [ "$HEALTHCARE_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - FHIR Validation Issues:    ${RED}%7d${NC}\n" $FHIR_ISSUES
  printf "${YELLOW}   - HIPAA Compliance Issues:   ${RED}%7d${NC}\n" $HIPAA_ISSUES
  if [ "$HIPAA_ISSUES" -gt 0 ]; then
    printf "${YELLOW}     • Unencrypted PHI:         ${RED}%7d${NC}\n" $PHI_UNENCRYPTED
    printf "${YELLOW}     • Missing Audit Logs:      ${RED}%7d${NC}\n" $AUDIT_MISSING
    printf "${YELLOW}     • Missing Access Control:  ${RED}%7d${NC}\n" $ACCESS_CONTROL_MISSING
  fi
  echo -e "${RED}   ⚠️  CRITICAL: Healthcare compliance issues must be fixed immediately${NC}"
fi

# Security (Critical)
echo -e "\n${PURPLE}2. Security Issues (bandit):${NC}"
printf "${YELLOW}   Total Security Issues:       ${RED}%7d${NC}\n" $SECURITY_TOTAL
if [ "$SECURITY_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - High Severity:             ${RED}%7d${NC}\n" $SECURITY_HIGH
  printf "${YELLOW}   - Medium Severity:           ${RED}%7d${NC}\n" $SECURITY_MEDIUM
  printf "${YELLOW}   - Low Severity:              ${RED}%7d${NC}\n" $SECURITY_LOW
fi

# Type Safety (High Priority)
echo -e "\n${PURPLE}3. Type Safety (mypy):${NC}"
printf "${YELLOW}   Total Type Errors:           ${RED}%7d${NC}\n" $MYPY_TOTAL
if [ "$MYPY_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - Errors:                    ${RED}%7d${NC}\n" $MYPY_ERRORS
  printf "${YELLOW}   - Warnings:                  ${RED}%7d${NC}\n" $MYPY_WARNINGS
fi

# Test Coverage
echo -e "\n${PURPLE}4. Testing:${NC}"
printf "${YELLOW}   Failed Tests:                ${RED}%7d${NC}\n" $TEST_FAILURES
printf "${YELLOW}   Code Coverage:               ${NC}%6d%%${NC}\n" $COVERAGE_PCT
if [ "$COVERAGE_PCT" -lt 80 ]; then
  echo -e "${RED}   ⚠️  Coverage below 80% threshold (medical software requirement)${NC}"
fi

# Code Quality
echo -e "\n${PURPLE}5. Code Quality (pylint):${NC}"
printf "${YELLOW}   Total Issues:                ${RED}%7d${NC}\n" $PYLINT_TOTAL
if [ "$PYLINT_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - Errors:                    ${RED}%7d${NC}\n" $PYLINT_E_ERRORS
  printf "${YELLOW}   - Warnings:                  ${RED}%7d${NC}\n" $PYLINT_W_ERRORS
fi

# Formatting
echo -e "\n${PURPLE}6. Code Formatting:${NC}"
printf "${YELLOW}   Total Formatting Issues:     ${RED}%7d${NC}\n" $FORMATTING_TOTAL
if [ "$FORMATTING_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - Black Issues:              ${RED}%7d${NC}\n" $BLACK_ISSUES
  printf "${YELLOW}   - Import Sort Issues:        ${RED}%7d${NC}\n" $ISORT_ISSUES
fi

# Style Guide
echo -e "\n${PURPLE}7. Style Guide (flake8):${NC}"
printf "${YELLOW}   Total Violations:            ${RED}%7d${NC}\n" $FLAKE8_TOTAL
if [ "$FLAKE8_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - Error (E):                 ${RED}%7d${NC}\n" $FLAKE8_E_ERRORS
  printf "${YELLOW}   - Warning (W):               ${RED}%7d${NC}\n" $FLAKE8_W_ERRORS
  printf "${YELLOW}   - PyFlakes (F):              ${RED}%7d${NC}\n" $FLAKE8_F_ERRORS
  printf "${YELLOW}   - Complexity (C):            ${RED}%7d${NC}\n" $FLAKE8_C_ERRORS
  printf "${YELLOW}   - Naming (N):                ${RED}%7d${NC}\n" $FLAKE8_N_ERRORS
fi

# Documentation
echo -e "\n${PURPLE}8. Documentation:${NC}"
printf "${YELLOW}   Missing Docstrings:          ${RED}%7d${NC}\n" $DOCS_TOTAL
if [ "$DOCS_TOTAL" -gt 0 ]; then
  printf "${YELLOW}   - Module docstrings:         ${RED}%7d${NC}\n" $MISSING_MODULE_DOCS
  printf "${YELLOW}   - Class docstrings:          ${RED}%7d${NC}\n" $MISSING_CLASS_DOCS
  printf "${YELLOW}   - Function docstrings:       ${RED}%7d${NC}\n" $MISSING_FUNCTION_DOCS
fi

# Complexity
echo -e "\n${PURPLE}9. Code Complexity:${NC}"
printf "${YELLOW}   Complex Functions (C+):      ${RED}%7d${NC}\n" $COMPLEXITY_TOTAL

echo -e "\n${CYAN}=========================================${NC}"
printf "${PURPLE}GRAND TOTAL ISSUES:              ${RED}%7d${NC}\n" $GRAND_TOTAL
echo -e "${CYAN}=========================================${NC}"

# Show status
if [ "$GRAND_TOTAL" -eq 0 ]; then
  echo -e "\n${GREEN}✅ Excellent! No compliance issues found.${NC}"
  echo -e "${GREEN}Your code meets all quality standards for production deployment.${NC}"
else
  echo -e "\n${YELLOW}📋 Error chunks created in:${NC}"
  echo -e "${GREEN}$ERROR_CHUNKS_DIR${NC}"
  ls -1 "$ERROR_CHUNKS_DIR"/error_chunk_*.txt 2>/dev/null | while read -r file; do
    [ -f "$file" ] && echo -e "${GREEN}- $(basename "$file")${NC}"
  done
fi
} | tee -a "$TEMP_DIR/report_output.txt"

# Save detailed summary to file
{
echo "========================================="
echo "  HAVEN HEALTH PASSPORT COMPLIANCE SUMMARY"
echo "========================================="
echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""
echo "1. Healthcare Compliance:"
echo "   Total Healthcare Issues:     $(printf "%7d" $HEALTHCARE_TOTAL)"
if [ "$HEALTHCARE_TOTAL" -gt 0 ]; then
  echo "   - FHIR Validation Issues:    $(printf "%7d" $FHIR_ISSUES)"
  echo "   - HIPAA Compliance Issues:   $(printf "%7d" $HIPAA_ISSUES)"
  echo "     • Unencrypted PHI:         $(printf "%7d" $PHI_UNENCRYPTED)"
  echo "     • Missing Audit Logs:      $(printf "%7d" $AUDIT_MISSING)"
  echo "     • Missing Access Control:  $(printf "%7d" $ACCESS_CONTROL_MISSING)"
fi
echo ""
echo "2. Security Issues (bandit):"
echo "   Total Security Issues:       $(printf "%7d" $SECURITY_TOTAL)"
if [ "$SECURITY_TOTAL" -gt 0 ]; then
  echo "   - High Severity:             $(printf "%7d" $SECURITY_HIGH)"
  echo "   - Medium Severity:           $(printf "%7d" $SECURITY_MEDIUM)"
  echo "   - Low Severity:              $(printf "%7d" $SECURITY_LOW)"
fi
echo ""
echo "3. Type Safety (mypy):"
echo "   Total Type Errors:           $(printf "%7d" $MYPY_TOTAL)"
if [ "$MYPY_TOTAL" -gt 0 ]; then
  echo "   - Errors:                    $(printf "%7d" $MYPY_ERRORS)"
  echo "   - Warnings:                  $(printf "%7d" $MYPY_WARNINGS)"
fi
echo ""
echo "4. Testing:"
echo "   Failed Tests:                $(printf "%7d" $TEST_FAILURES)"
echo "   Code Coverage:               $(printf "%6d" $COVERAGE_PCT)%"
echo ""
echo "5. Code Quality (pylint):"
echo "   Total Issues:                $(printf "%7d" $PYLINT_TOTAL)"
echo ""
echo "6. Code Formatting:"
echo "   Total Formatting Issues:     $(printf "%7d" $FORMATTING_TOTAL)"
if [ "$FORMATTING_TOTAL" -gt 0 ]; then
  echo "   - Black Issues:              $(printf "%7d" $BLACK_ISSUES)"
  echo "   - Import Sort Issues:        $(printf "%7d" $ISORT_ISSUES)"
fi
echo ""
echo "7. Style Guide (flake8):"
echo "   Total Violations:            $(printf "%7d" $FLAKE8_TOTAL)"
echo ""
echo "8. Documentation:"
echo "   Missing Docstrings:          $(printf "%7d" $DOCS_TOTAL)"
echo ""
echo "9. Code Complexity:"
echo "   Complex Functions (C+):      $(printf "%7d" $COMPLEXITY_TOTAL)"
echo ""
echo "========================================="
echo "GRAND TOTAL ISSUES:              $(printf "%7d" $GRAND_TOTAL)"
echo "========================================="
} >> "$SUMMARY_FILE"

# Display resolution priority
echo -e "\n${CYAN}=========================================${NC}"
echo -e "${CYAN}     ISSUE RESOLUTION PRIORITY          ${NC}"
echo -e "${CYAN}=========================================${NC}"
echo -e "${YELLOW}Fix issues in this order (medical software priorities):${NC}"
echo -e "${RED}1. Healthcare Compliance${NC} - FHIR validation and HIPAA compliance"
echo -e "${RED}2. Security Issues${NC} - Fix all bandit findings immediately"
echo -e "${RED}3. Failed Tests${NC} - Ensure all tests pass"
echo -e "${YELLOW}4. Type Safety${NC} - Fix mypy errors for type correctness"
echo -e "${YELLOW}5. Test Coverage${NC} - Achieve 80%+ coverage (medical requirement)"
echo -e "${BLUE}6. Code Quality${NC} - Address pylint errors and warnings"
echo -e "${BLUE}7. Code Formatting${NC} - Run black and isort to fix"
echo -e "${BLUE}8. Code Complexity${NC} - Refactor complex functions"
echo -e "${GREEN}9. Style Guide${NC} - Fix flake8 violations"
echo -e "${GREEN}10. Documentation${NC} - Add missing docstrings"

# Show quick fix commands
echo -e "\n${CYAN}=========================================${NC}"
echo -e "${CYAN}         QUICK FIX COMMANDS            ${NC}"
echo -e "${CYAN}=========================================${NC}"
echo -e "${YELLOW}Auto-fix formatting issues:${NC}"
echo -e "${GREEN}cd $PROJECT_ROOT${NC}"
echo -e "${GREEN}black src/ tests/${NC}"
echo -e "${GREEN}isort src/ tests/${NC}"
echo -e ""
echo -e "${YELLOW}Run individual checks:${NC}"
echo -e "${GREEN}mypy src/${NC} - Type checking"
echo -e "${GREEN}bandit -r src/${NC} - Security scan"
echo -e "${GREEN}pytest tests/ --cov=src --cov-report=term-missing${NC} - Tests & coverage"
echo -e "${GREEN}pylint src/${NC} - Code quality"
echo -e "${GREEN}flake8 src/${NC} - Style guide"

# Healthcare-specific recommendations
if [ "$HEALTHCARE_TOTAL" -gt 0 ] || [ "$HIPAA_ISSUES" -gt 0 ]; then
  echo -e "\n${CYAN}=========================================${NC}"
  echo -e "${CYAN}    HEALTHCARE COMPLIANCE ACTIONS      ${NC}"
  echo -e "${CYAN}=========================================${NC}"
  echo -e "${RED}⚠️  CRITICAL: Healthcare compliance issues detected!${NC}"
  echo -e ""
  echo -e "${YELLOW}Required actions for HIPAA compliance:${NC}"
  echo -e "${YELLOW}1. Encrypt all PHI at rest:${NC}"
  echo -e "   - Use field-level encryption for sensitive data"
  echo -e "   - Implement AES-256 or stronger encryption"
  echo -e ""
  echo -e "${YELLOW}2. Implement comprehensive audit logging:${NC}"
  echo -e "   - Log all PHI access with timestamp and user ID"
  echo -e "   - Include read, write, and delete operations"
  echo -e "   - Store audit logs securely and separately"
  echo -e ""
  echo -e "${YELLOW}3. Add robust access controls:${NC}"
  echo -e "   - Implement role-based access control (RBAC)"
  echo -e "   - Require authentication for all PHI access"
  echo -e "   - Use principle of least privilege"
  echo -e ""
  echo -e "${YELLOW}4. Ensure secure data transmission:${NC}"
  echo -e "   - Use TLS 1.2+ for all data in transit"
  echo -e "   - Validate SSL certificates"
  echo -e "   - Implement secure API endpoints"
  echo -e ""
  echo -e "${YELLOW}5. FHIR compliance:${NC}"
  echo -e "   - Validate all FHIR resources before storage"
  echo -e "   - Use proper FHIR resource types"
  echo -e "   - Implement FHIR REST API standards"
fi

# Create detailed reports
echo -e "\n${BLUE}📊 Detailed reports saved to:${NC}"
echo -e "${GREEN}- Summary: $SUMMARY_FILE${NC}"
echo -e "${GREEN}- Full reports: $COMPLIANCE_DIR/${NC}"

# Save individual reports
[ -s "$FLAKE8_OUTPUT" ] && cp "$FLAKE8_OUTPUT" "$COMPLIANCE_DIR/flake8_report.txt"
[ -s "$PYLINT_OUTPUT" ] && cp "$PYLINT_OUTPUT" "$COMPLIANCE_DIR/pylint_report.txt"
[ -s "$MYPY_OUTPUT" ] && cp "$MYPY_OUTPUT" "$COMPLIANCE_DIR/mypy_report.txt"
[ -s "$PYTEST_OUTPUT" ] && cp "$PYTEST_OUTPUT" "$COMPLIANCE_DIR/pytest_report.txt"
[ -s "$BANDIT_OUTPUT" ] && cp "$BANDIT_OUTPUT" "$COMPLIANCE_DIR/bandit_report.txt"
[ -s "$BLACK_OUTPUT" ] && cp "$BLACK_OUTPUT" "$COMPLIANCE_DIR/black_report.txt"
[ -s "$ISORT_OUTPUT" ] && cp "$ISORT_OUTPUT" "$COMPLIANCE_DIR/isort_report.txt"
[ -s "$HIPAA_OUTPUT" ] && cp "$HIPAA_OUTPUT" "$COMPLIANCE_DIR/hipaa_compliance.txt"
[ -s "$FHIR_OUTPUT" ] && cp "$FHIR_OUTPUT" "$COMPLIANCE_DIR/fhir_compliance.txt"

# Show final status
echo -e "\n${GREEN}✅ Compliance check completed.${NC}"

# Exit with appropriate code
if [ "$GRAND_TOTAL" -gt 0 ]; then
  echo -e "${YELLOW}Found $GRAND_TOTAL total issues that need attention.${NC}"
  exit 1
else
  echo -e "${GREEN}All compliance checks passed!${NC}"
  exit 0
fi
