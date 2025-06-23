#!/bin/bash

# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

################################################################################
# Script: integrate-orderer-policies.sh
# Purpose: Integrate orderer policies into the main configtx.yaml configuration
# Usage: ./integrate-orderer-policies.sh
################################################################################

set -e

echo "======================================"
echo "Haven Health Passport"
echo "Orderer Policy Integration Script"
echo "======================================"

# Configuration paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}"
POLICIES_FILE="${CONFIG_DIR}/orderer-policies.yaml"
CONFIGTX_FILE="${CONFIG_DIR}/configtx.yaml"
BACKUP_DIR="${CONFIG_DIR}/backups"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Function to create backup
create_backup() {
    local file=$1
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/$(basename ${file}).${timestamp}.bak"

    echo "Creating backup: ${backup_file}"
    cp "${file}" "${backup_file}"
}

# Function to validate YAML files
validate_yaml() {
    local file=$1
    echo "Validating YAML file: ${file}"

    if command -v yamllint &> /dev/null; then
        yamllint -d relaxed "${file}"
    else
        echo "Warning: yamllint not installed. Skipping YAML validation."
    fi
}

# Function to merge policy configurations
merge_policies() {
    echo "Merging orderer policies into main configuration..."

    # Create a temporary merged configuration
    local temp_config="${CONFIG_DIR}/configtx-merged.yaml"

    # Use yq to merge configurations if available
    if command -v yq &> /dev/null; then
        echo "Using yq to merge configurations..."
        yq eval-all 'select(fileIndex == 0) * select(fileIndex == 1)' \
            "${CONFIGTX_FILE}" "${POLICIES_FILE}" > "${temp_config}"
    else
        echo "Warning: yq not installed. Creating reference in configtx.yaml instead."

        # Add reference to policies file in configtx.yaml
        cat >> "${CONFIGTX_FILE}" << EOF

################################################################################
# Orderer Policies Reference
#
# Additional orderer policies are defined in: orderer-policies.yaml
# These policies provide granular control over:
# - Consensus node management
# - Emergency healthcare access
# - HIPAA compliance operations
# - Cross-border data transfers
# - Monitoring and audit access
################################################################################
EOF
    fi

    # If merge was successful, replace original
    if [ -f "${temp_config}" ]; then
        mv "${temp_config}" "${CONFIGTX_FILE}"
        echo "Policies successfully merged into configtx.yaml"
    fi
}

# Main execution
main() {
    echo "Starting orderer policy integration..."

    # Check if required files exist
    if [ ! -f "${POLICIES_FILE}" ]; then
        echo "Error: Orderer policies file not found: ${POLICIES_FILE}"
        exit 1
    fi

    if [ ! -f "${CONFIGTX_FILE}" ]; then
        echo "Error: configtx.yaml not found: ${CONFIGTX_FILE}"
        exit 1
    fi

    # Create backups
    create_backup "${CONFIGTX_FILE}"

    # Validate YAML files
    validate_yaml "${POLICIES_FILE}"
    validate_yaml "${CONFIGTX_FILE}"

    # Merge policies
    merge_policies

    # Validate merged configuration
    if [ -f "${CONFIGTX_FILE}" ]; then
        validate_yaml "${CONFIGTX_FILE}"
    fi

    echo ""
    echo "======================================"
    echo "Policy integration complete!"
    echo "======================================"
    echo ""
    echo "Next steps:"
    echo "1. Review the updated configtx.yaml"
    echo "2. Generate new genesis block with updated policies"
    echo "3. Update channel configurations as needed"
    echo "4. Test policy enforcement in development environment"
}

# Execute main function
main "$@"
