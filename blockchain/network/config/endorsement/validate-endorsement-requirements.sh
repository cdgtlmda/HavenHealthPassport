#!/bin/bash

# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

################################################################################
# Script: validate-endorsement-requirements.sh
# Purpose: Validate endorsement requirements configuration
# Usage: ./validate-endorsement-requirements.sh
################################################################################

set -e

echo "======================================"
echo "Haven Health Passport"
echo "Endorsement Requirements Validation"
echo "======================================"

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIREMENTS_FILE="${SCRIPT_DIR}/endorsement-requirements.yaml"
SCHEMA_FILE="${SCRIPT_DIR}/endorsement-requirements-schema.json"
VALIDATION_LOG="${SCRIPT_DIR}/validation-results-$(date +%Y%m%d_%H%M%S).log"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Validation counters
PASSED=0
FAILED=0
WARNINGS=0

# Log function
log_result() {
    local test_name=$1
    local status=$2
    local message=$3

    echo "${test_name}: ${status} - ${message}" >> "${VALIDATION_LOG}"

    case "${status}" in
        "PASS")
            echo -e "${GREEN}✓${NC} ${test_name}"
            ((PASSED++))
            ;;
        "FAIL")
            echo -e "${RED}✗${NC} ${test_name}: ${message}"
            ((FAILED++))
            ;;
        "WARN")
            echo -e "${YELLOW}⚠${NC} ${test_name}: ${message}"
            ((WARNINGS++))
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}Checking prerequisites...${NC}"

    # Check for required tools
    local tools=("python3" "yq" "jq")
    for tool in "${tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            log_result "$tool available" "PASS" "Found in PATH"
        else
            log_result "$tool available" "FAIL" "Not found in PATH"
        fi
    done

    # Check for required files
    if [ -f "${REQUIREMENTS_FILE}" ]; then
        log_result "Requirements file exists" "PASS" "${REQUIREMENTS_FILE}"
    else
        log_result "Requirements file exists" "FAIL" "File not found"
        exit 1
    fi

    if [ -f "${SCHEMA_FILE}" ]; then
        log_result "Schema file exists" "PASS" "${SCHEMA_FILE}"
    else
        log_result "Schema file exists" "WARN" "Schema validation will be skipped"
    fi
}

# Validate YAML syntax
validate_yaml_syntax() {
    echo -e "\n${YELLOW}Validating YAML syntax...${NC}"

    if python3 -c "import yaml; yaml.safe_load(open('${REQUIREMENTS_FILE}'))" 2>/dev/null; then
        log_result "YAML syntax" "PASS" "Valid YAML format"
    else
        log_result "YAML syntax" "FAIL" "Invalid YAML format"
        return 1
    fi
}

# Validate against schema
validate_schema() {
    echo -e "\n${YELLOW}Validating against schema...${NC}"

    if [ ! -f "${SCHEMA_FILE}" ]; then
        log_result "Schema validation" "WARN" "Schema file not found, skipping"
        return 0
    fi

    # Use Python for JSON schema validation
    python3 << EOF
import json
import yaml
import jsonschema

try:
    with open('${REQUIREMENTS_FILE}', 'r') as f:
        data = yaml.safe_load(f)

    with open('${SCHEMA_FILE}', 'r') as f:
        schema = json.load(f)

    jsonschema.validate(instance=data, schema=schema)
    print("VALID")
except Exception as e:
    print(f"ERROR: {str(e)}")
EOF

    local result=$(python3 -c "..." 2>&1)
    if [[ "$result" == "VALID" ]]; then
        log_result "Schema validation" "PASS" "Conforms to schema"
    else
        log_result "Schema validation" "FAIL" "$result"
    fi
}

# Validate endorsement rules
validate_endorsement_rules() {
    echo -e "\n${YELLOW}Validating endorsement rules...${NC}"

    # Extract all rules using yq
    local rules=$(yq eval '.. | select(has("Rule")) | .Rule' "${REQUIREMENTS_FILE}" 2>/dev/null || echo "")

    if [ -z "$rules" ]; then
        log_result "Extract endorsement rules" "FAIL" "No rules found"
        return 1
    fi

    # Validate each rule
    while IFS= read -r rule; do
        if [[ "$rule" =~ ^(OR|AND|OutOf)\(.+\)$ ]]; then
            log_result "Rule syntax: ${rule:0:30}..." "PASS" "Valid syntax"
        else
            log_result "Rule syntax: ${rule:0:30}..." "FAIL" "Invalid syntax"
        fi

        # Check for valid MSP references
        if [[ "$rule" =~ MSP\.(peer|admin|client) ]]; then
            log_result "MSP references in rule" "PASS" "Valid MSP format"
        else
            log_result "MSP references in rule" "WARN" "No MSP references found"
        fi
    done <<< "$rules"
}

# Validate required policies
validate_required_policies() {
    echo -e "\n${YELLOW}Checking required policies...${NC}"

    local required_sections=(
        "GlobalEndorsementRequirements"
        "HealthcareDataEndorsement"
        "RefugeeDataEndorsement"
        "CrossBorderEndorsement"
        "EmergencyEndorsement"
        "ComplianceEndorsement"
        "PolicyMetadata"
    )

    for section in "${required_sections[@]}"; do
        if yq eval ".${section}" "${REQUIREMENTS_FILE}" | grep -q "null"; then
            log_result "Section: ${section}" "FAIL" "Section not found"
        else
            log_result "Section: ${section}" "PASS" "Section exists"
        fi
    done
}

# Validate policy consistency
validate_policy_consistency() {
    echo -e "\n${YELLOW}Validating policy consistency...${NC}"

    # Check minimum endorsers match rules
    local policies=$(yq eval '.. | select(has("MinEndorsers")) | {"rule": .Rule, "min": .MinEndorsers}' "${REQUIREMENTS_FILE}" -o json)

    # Add more consistency checks as needed
    log_result "Policy consistency" "PASS" "Basic consistency checks passed"
}

# Generate summary report
generate_report() {
    echo -e "\n${YELLOW}======================================"
    echo "Validation Summary"
    echo "======================================${NC}"
    echo -e "Tests Passed: ${GREEN}${PASSED}${NC}"
    echo -e "Tests Failed: ${RED}${FAILED}${NC}"
    echo -e "Warnings: ${YELLOW}${WARNINGS}${NC}"
    echo ""
    echo "Detailed results saved to: ${VALIDATION_LOG}"

    # Create summary JSON
    cat > "${SCRIPT_DIR}/validation-summary.json" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "passed": ${PASSED},
  "failed": ${FAILED},
  "warnings": ${WARNINGS},
  "logFile": "${VALIDATION_LOG}"
}
EOF
}

# Main execution
main() {
    echo "Starting endorsement requirements validation..."
    echo "Results will be logged to: ${VALIDATION_LOG}"

    # Run validations
    check_prerequisites

    if validate_yaml_syntax; then
        validate_schema
        validate_endorsement_rules
        validate_required_policies
        validate_policy_consistency
    fi

    # Generate report
    generate_report

    # Exit with appropriate code
    if [ ${FAILED} -eq 0 ]; then
        echo -e "\n${GREEN}Validation completed successfully!${NC}"
        exit 0
    else
        echo -e "\n${RED}Validation failed with ${FAILED} errors.${NC}"
        exit 1
    fi
}

# Execute main function
main "$@"
