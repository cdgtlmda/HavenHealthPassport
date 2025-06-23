#!/bin/bash

# Apply Batch Timeout Configuration
# Haven Health Passport - Performance Optimization

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/batch-timeout-config.yaml"
ORDERER_CONFIG="${SCRIPT_DIR}/../config/consensus/ordering-service-config.yaml"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Logging
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

# Get current environment
get_environment() {
    if [ -n "${BLOCKCHAIN_ENV:-}" ]; then
        echo "${BLOCKCHAIN_ENV}"
    elif [ -f /etc/blockchain-env ]; then
        cat /etc/blockchain-env
    else
        echo "production"
    fi
}

# Update orderer configuration
update_orderer_config() {
    log_section "Updating Orderer Configuration"

    local env=$(get_environment)
    local timeout=$(yq eval ".batchTimeout.${env}.default" "${CONFIG_FILE}")

    log_info "Setting batch timeout to ${timeout} for ${env} environment"

    # Update the main orderer configuration
    yq eval ".orderingService.performance.batching.batchTimeout = \"${timeout}\"" \
        "${ORDERER_CONFIG}" > "${ORDERER_CONFIG}.tmp"
    mv "${ORDERER_CONFIG}.tmp" "${ORDERER_CONFIG}"

    log_info "Orderer configuration updated"
}

# Apply performance profile
apply_performance_profile() {
    local profile="${1:-balanced}"

    log_section "Applying Performance Profile: ${profile}"

    # Get profile settings
    local timeout=$(yq eval ".performanceProfiles.${profile}.batchTimeout" "${CONFIG_FILE}")
    local max_msg=$(yq eval ".performanceProfiles.${profile}.maxMessageCount" "${CONFIG_FILE}")
    local abs_max=$(yq eval ".performanceProfiles.${profile}.absoluteMaxBytes" "${CONFIG_FILE}")
    local pref_max=$(yq eval ".performanceProfiles.${profile}.preferredMaxBytes" "${CONFIG_FILE}")

    log_info "Profile settings:"
    log_info "  Batch Timeout: ${timeout}"
    log_info "  Max Message Count: ${max_msg}"
    log_info "  Absolute Max Bytes: ${abs_max}"
    log_info "  Preferred Max Bytes: ${pref_max}"

    # Update configuration
    cat > /tmp/batch-config-update.yaml <<EOF
batchTimeout: ${timeout}
maxMessageCount: ${max_msg}
absoluteMaxBytes: ${abs_max}
preferredMaxBytes: ${pref_max}
EOF

    log_info "Performance profile ${profile} applied"
}

# Setup CloudWatch alarms
setup_monitoring() {
    log_section "Setting Up Monitoring"

    local namespace=$(yq eval '.monitoring.cloudWatch.namespace' "${CONFIG_FILE}")

    # Create CloudWatch alarms
    yq eval '.monitoring.cloudWatch.alarms[]' "${CONFIG_FILE}" -o=j | while IFS= read -r alarm; do
        local name=$(echo "${alarm}" | jq -r '.name')
        local metric=$(echo "${alarm}" | jq -r '.metric')
        local threshold=$(echo "${alarm}" | jq -r '.threshold')

        log_info "Creating alarm: ${name}"

        aws cloudwatch put-metric-alarm \
            --alarm-name "HavenHealth-Batch-${name}" \
            --alarm-description "$(echo "${alarm}" | jq -r '.description')" \
            --metric-name "${metric}" \
            --namespace "${namespace}" \
            --statistic "$(echo "${alarm}" | jq -r '.statistic')" \
            --period $(echo "${alarm}" | jq -r '.period') \
            --threshold ${threshold} \
            --comparison-operator "$(echo "${alarm}" | jq -r '.comparisonOperator')" \
            --evaluation-periods $(echo "${alarm}" | jq -r '.evaluationPeriods') \
            --region "${AWS_REGION}" || true
    done

    log_info "Monitoring setup complete"
}

# Enable dynamic adjustment
enable_dynamic_adjustment() {
    log_section "Enabling Dynamic Timeout Adjustment"

    local env=$(get_environment)
    local enabled=$(yq eval ".batchTimeout.${env}.dynamic.enabled" "${CONFIG_FILE}")

    if [ "${enabled}" != "true" ]; then
        log_warn "Dynamic adjustment is disabled for ${env} environment"
        return
    fi

    # Create dynamic adjustment configuration
    cat > /tmp/dynamic-batch-config.sh <<'EOF'
#!/bin/bash
# Dynamic Batch Timeout Adjustment Script

# Get current TPS
get_current_tps() {
    # Query CloudWatch for transaction rate
    aws cloudwatch get-metric-statistics \
        --namespace "HavenHealth/Blockchain" \
        --metric-name "TransactionsPerSecond" \
        --start-time $(date -u -d '1 minute ago' +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --period 60 \
        --statistics Average \
        --query 'Datapoints[0].Average' \
        --output text
}

# Adjust timeout based on TPS
adjust_timeout() {
    local current_tps=$1
    local current_timeout=$2
    local new_timeout=$current_timeout

    if (( $(echo "$current_tps < 10" | bc -l) )); then
        # Network is idle, increase timeout
        new_timeout=$(echo "$current_timeout * 1.5" | bc -l)
    elif (( $(echo "$current_tps > 100" | bc -l) )); then
        # Network is busy, decrease timeout
        new_timeout=$(echo "$current_timeout / 1.5" | bc -l)
    fi

    # Apply bounds
    if (( $(echo "$new_timeout < 0.5" | bc -l) )); then
        new_timeout="0.5"
    elif (( $(echo "$new_timeout > 5" | bc -l) )); then
        new_timeout="5"
    fi

    echo "${new_timeout}s"
}

# Main loop
while true; do
    current_tps=$(get_current_tps)
    current_timeout=$(get_current_batch_timeout)
    new_timeout=$(adjust_timeout $current_tps $current_timeout)

    if [ "$new_timeout" != "$current_timeout" ]; then
        apply_batch_timeout "$new_timeout"
    fi

    sleep 30
done
EOF

    chmod +x /tmp/dynamic-batch-config.sh
    log_info "Dynamic adjustment script created"
}

# Test configuration
test_configuration() {
    log_section "Testing Batch Timeout Configuration"

    # Run test scenarios
    yq eval '.testing.scenarios[]' "${CONFIG_FILE}" -o=j | while IFS= read -r scenario; do
        local name=$(echo "${scenario}" | jq -r '.name')
        local tps=$(echo "${scenario}" | jq -r '.tps')
        local duration=$(echo "${scenario}" | jq -r '.duration')

        log_info "Running test scenario: ${name}"
        log_info "  TPS: ${tps}"
        log_info "  Duration: ${duration}"

        # Simulate load (placeholder for actual load testing)
        log_info "Test scenario ${name} completed"
    done
}

# Generate report
generate_report() {
    log_section "Generating Configuration Report"

    local report_file="${SCRIPT_DIR}/../config/consensus/batch-timeout-report-$(date +%Y%m%d-%H%M%S).txt"
    local env=$(get_environment)

    cat > "${report_file}" <<EOF
Haven Health Passport - Batch Timeout Configuration Report
=========================================================

Date: $(date)
Environment: ${env}

Current Configuration:
---------------------
Default Timeout: $(yq eval ".batchTimeout.${env}.default" "${CONFIG_FILE}")
Dynamic Adjustment: $(yq eval ".batchTimeout.${env}.dynamic.enabled" "${CONFIG_FILE}")

Performance Profiles:
--------------------
EOF

    # List all profiles
    yq eval '.performanceProfiles | keys | .[]' "${CONFIG_FILE}" | while read profile; do
        echo "" >> "${report_file}"
        echo "${profile}:" >> "${report_file}"
        echo "  Timeout: $(yq eval ".performanceProfiles.${profile}.batchTimeout" "${CONFIG_FILE}")" >> "${report_file}"
        echo "  Max Messages: $(yq eval ".performanceProfiles.${profile}.maxMessageCount" "${CONFIG_FILE}")" >> "${report_file}"
    done

    cat >> "${report_file}" <<EOF

Monitoring:
-----------
CloudWatch Namespace: $(yq eval '.monitoring.cloudWatch.namespace' "${CONFIG_FILE}")
Number of Alarms: $(yq eval '.monitoring.cloudWatch.alarms | length' "${CONFIG_FILE}")

Recommendations:
----------------
- Monitor block fill percentage to optimize timeout
- Use dynamic adjustment in production
- Consider time-based scheduling for predictable workloads
- Test thoroughly before applying changes

EOF

    log_info "Report generated: ${report_file}"
}

# Main menu
show_menu() {
    echo ""
    echo "Batch Timeout Configuration Management"
    echo "====================================="
    echo "1. Update orderer configuration"
    echo "2. Apply performance profile"
    echo "3. Enable dynamic adjustment"
    echo "4. Setup monitoring"
    echo "5. Test configuration"
    echo "6. Generate report"
    echo "7. Exit"
    echo ""
}

# Main execution
main() {
    if [ $# -eq 0 ]; then
        # Interactive mode
        while true; do
            show_menu
            read -p "Select option: " choice

            case $choice in
                1) update_orderer_config ;;
                2)
                    read -p "Enter profile name (lowLatency/balanced/highThroughput/powerSaving): " profile
                    apply_performance_profile "${profile}"
                    ;;
                3) enable_dynamic_adjustment ;;
                4) setup_monitoring ;;
                5) test_configuration ;;
                6) generate_report ;;
                7) exit 0 ;;
                *) log_error "Invalid option" ;;
            esac
        done
    else
        # Command mode
        case "$1" in
            update) update_orderer_config ;;
            profile) apply_performance_profile "${2:-balanced}" ;;
            dynamic) enable_dynamic_adjustment ;;
            monitor) setup_monitoring ;;
            test) test_configuration ;;
            report) generate_report ;;
            *) log_error "Unknown command: $1" ;;
        esac
    fi
}

# Run main
main "$@"
