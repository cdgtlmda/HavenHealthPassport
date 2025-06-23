#!/bin/bash

# Deploy Snapshot Configuration to AWS Managed Blockchain
# Haven Health Passport - Snapshot Configuration Deployment Script

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_DIR="${SCRIPT_DIR}/../config/consensus"
SNAPSHOT_CONFIG="${CONFIG_DIR}/snapshot-config.yaml"
AWS_REGION="${AWS_REGION:-us-east-1}"
NETWORK_ID="${HAVEN_BLOCKCHAIN_NETWORK_ID}"
MEMBER_ID="${HAVEN_BLOCKCHAIN_MEMBER_ID}"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq."
        exit 1
    fi

    # Check yq
    if ! command -v yq &> /dev/null; then
        log_error "yq not found. Please install yq."
        exit 1
    fi

    # Check environment variables
    if [ -z "${NETWORK_ID}" ]; then
        log_error "HAVEN_BLOCKCHAIN_NETWORK_ID not set"
        exit 1
    fi

    if [ -z "${MEMBER_ID}" ]; then
        log_error "HAVEN_BLOCKCHAIN_MEMBER_ID not set"
        exit 1
    fi

    # Check config file exists
    if [ ! -f "${SNAPSHOT_CONFIG}" ]; then
        log_error "Snapshot configuration file not found: ${SNAPSHOT_CONFIG}"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Validate configuration
validate_configuration() {
    log_info "Validating snapshot configuration..."

    # Validate YAML syntax
    if ! yq eval '.' "${SNAPSHOT_CONFIG}" > /dev/null 2>&1; then
        log_error "Invalid YAML syntax in snapshot configuration"
        exit 1
    fi

    # Extract and validate key settings
    local size_threshold=$(yq eval '.snapshot.triggers.sizeInterval.threshold' "${SNAPSHOT_CONFIG}")
    local block_threshold=$(yq eval '.snapshot.triggers.blockInterval.threshold' "${SNAPSHOT_CONFIG}")
    local time_interval=$(yq eval '.snapshot.triggers.timeInterval.interval' "${SNAPSHOT_CONFIG}")

    if [ "${size_threshold}" -lt 1048576 ]; then
        log_warn "Snapshot size threshold is less than 1MB, this may cause frequent snapshots"
    fi

    if [ "${block_threshold}" -lt 100 ]; then
        log_warn "Block threshold is less than 100, this may cause frequent snapshots"
    fi

    log_info "Configuration validation passed"
}

# Create CloudWatch log group for snapshots
create_log_group() {
    local log_group="/aws/managedblockchain/${NETWORK_ID}/snapshots"

    log_info "Creating CloudWatch log group: ${log_group}"

    if aws logs describe-log-groups --log-group-name-prefix "${log_group}" \
        --region "${AWS_REGION}" | jq -r '.logGroups[].logGroupName' | grep -q "^${log_group}$"; then
        log_info "Log group already exists"
    else
        aws logs create-log-group \
            --log-group-name "${log_group}" \
            --region "${AWS_REGION}"

        # Set retention policy
        aws logs put-retention-policy \
            --log-group-name "${log_group}" \
            --retention-in-days 30 \
            --region "${AWS_REGION}"

        log_info "Log group created successfully"
    fi
}

# Create S3 bucket for snapshot backups
create_s3_bucket() {
    local bucket_name=$(yq eval '.snapshot.storage.backup.s3.bucket' "${SNAPSHOT_CONFIG}")

    log_info "Creating S3 bucket for snapshot backups: ${bucket_name}"

    # Check if bucket exists
    if aws s3api head-bucket --bucket "${bucket_name}" 2>/dev/null; then
        log_info "S3 bucket already exists"
    else
        # Create bucket
        if [ "${AWS_REGION}" = "us-east-1" ]; then
            aws s3api create-bucket \
                --bucket "${bucket_name}" \
                --region "${AWS_REGION}"
        else
            aws s3api create-bucket \
                --bucket "${bucket_name}" \
                --region "${AWS_REGION}" \
                --create-bucket-configuration LocationConstraint="${AWS_REGION}"
        fi

        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "${bucket_name}" \
            --versioning-configuration Status=Enabled

        # Enable encryption
        aws s3api put-bucket-encryption \
            --bucket "${bucket_name}" \
            --server-side-encryption-configuration '{
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "aws:kms",
                        "KMSMasterKeyID": "alias/haven-health-blockchain-backup"
                    }
                }]
            }'

        # Set lifecycle policy
        aws s3api put-bucket-lifecycle-configuration \
            --bucket "${bucket_name}" \
            --lifecycle-configuration '{
                "Rules": [{
                    "Id": "SnapshotArchival",
                    "Status": "Enabled",
                    "Prefix": "orderer-snapshots/",
                    "Transitions": [{
                        "Days": 30,
                        "StorageClass": "GLACIER"
                    }],
                    "Expiration": {
                        "Days": 365
                    }
                }]
            }'

        log_info "S3 bucket created and configured successfully"
    fi
}

# Configure peer nodes with snapshot settings
configure_peer_nodes() {
    log_info "Configuring peer nodes with snapshot settings..."

    # Get peer node IDs
    local peer_nodes=$(aws managedblockchain list-nodes \
        --network-id "${NETWORK_ID}" \
        --member-id "${MEMBER_ID}" \
        --region "${AWS_REGION}" \
        --query 'Nodes[?Status==`AVAILABLE`].Id' \
        --output json)

    # Convert snapshot config to environment variables
    local snapshot_env_vars=$(cat <<EOF
CORE_LEDGER_SNAPSHOTS_ROOTDIR=/var/hyperledger/production/orderer/snapshots
ORDERER_CONSENSUS_SNAPINTERVAL_SIZE=$(yq eval '.snapshot.triggers.sizeInterval.threshold' "${SNAPSHOT_CONFIG}")
ORDERER_CONSENSUS_SNAPSHOT_BLOCKINTERVAL=$(yq eval '.snapshot.triggers.blockInterval.threshold' "${SNAPSHOT_CONFIG}")
ORDERER_CONSENSUS_SNAPSHOT_CATCHUP_ENTRIES=100
ORDERER_FILESYSTEMPATH=/var/hyperledger/production/orderer
EOF
)

    # Update each peer node
    echo "${peer_nodes}" | jq -r '.[]' | while read -r node_id; do
        log_info "Updating node: ${node_id}"

        # Note: AWS Managed Blockchain doesn't directly support updating node configuration
        # This would typically be done through the AWS console or by recreating nodes
        # Here we document what would need to be configured

        cat > "${CONFIG_DIR}/node-${node_id}-snapshot-config.txt" <<EOF
# Snapshot configuration for node ${node_id}
# Apply these settings through AWS Managed Blockchain console or node recreation

${snapshot_env_vars}

# Additional settings from snapshot-config.yaml
SNAPSHOT_COMPRESSION_ENABLED=$(yq eval '.snapshot.creation.compression.enabled' "${SNAPSHOT_CONFIG}")
SNAPSHOT_COMPRESSION_ALGORITHM=$(yq eval '.snapshot.creation.compression.algorithm' "${SNAPSHOT_CONFIG}")
SNAPSHOT_RETENTION_LOCAL=$(yq eval '.snapshot.storage.retention.localSnapshots' "${SNAPSHOT_CONFIG}")
SNAPSHOT_RETENTION_BACKUP=$(yq eval '.snapshot.storage.retention.backupSnapshots' "${SNAPSHOT_CONFIG}")
EOF

        log_info "Configuration documented for node ${node_id}"
    done
}

# Create CloudWatch alarms
create_cloudwatch_alarms() {
    log_info "Creating CloudWatch alarms for snapshot monitoring..."

    local namespace=$(yq eval '.snapshot.monitoring.metrics.namespace' "${SNAPSHOT_CONFIG}")

    # Create SNS topic for alerts
    local sns_topic_arn=$(aws sns create-topic \
        --name "haven-health-blockchain-snapshot-alerts" \
        --region "${AWS_REGION}" \
        --query 'TopicArn' \
        --output text)

    # Create alarms from configuration
    yq eval '.snapshot.monitoring.alerts[]' "${SNAPSHOT_CONFIG}" -o=j | while IFS= read -r alert; do
        local alert_name=$(echo "${alert}" | jq -r '.name')
        local condition=$(echo "${alert}" | jq -r '.condition')
        local severity=$(echo "${alert}" | jq -r '.severity')

        # Convert condition to CloudWatch alarm format
        case "${alert_name}" in
            "SnapshotCreationFailed")
                aws cloudwatch put-metric-alarm \
                    --alarm-name "HavenHealth-${alert_name}" \
                    --alarm-description "Alert when snapshot creation fails" \
                    --metric-name "SnapshotCreationFailures" \
                    --namespace "${namespace}" \
                    --statistic "Sum" \
                    --period 300 \
                    --threshold 1 \
                    --comparison-operator "GreaterThanOrEqualToThreshold" \
                    --evaluation-periods 1 \
                    --alarm-actions "${sns_topic_arn}" \
                    --region "${AWS_REGION}"
                ;;

            "SnapshotAgeTooOld")
                aws cloudwatch put-metric-alarm \
                    --alarm-name "HavenHealth-${alert_name}" \
                    --alarm-description "Alert when oldest snapshot is too old" \
                    --metric-name "OldestSnapshotAge" \
                    --namespace "${namespace}" \
                    --statistic "Maximum" \
                    --period 3600 \
                    --threshold 48 \
                    --comparison-operator "GreaterThanThreshold" \
                    --evaluation-periods 1 \
                    --unit "Hours" \
                    --alarm-actions "${sns_topic_arn}" \
                    --region "${AWS_REGION}"
                ;;
        esac

        log_info "Created alarm: ${alert_name}"
    done
}

# Generate deployment report
generate_report() {
    local report_file="${CONFIG_DIR}/snapshot-deployment-report-$(date +%Y%m%d-%H%M%S).txt"

    cat > "${report_file}" <<EOF
Haven Health Passport - Snapshot Configuration Deployment Report
================================================================

Deployment Date: $(date)
Network ID: ${NETWORK_ID}
Member ID: ${MEMBER_ID}
Region: ${AWS_REGION}

Configuration Summary:
- Size Threshold: $(yq eval '.snapshot.triggers.sizeInterval.threshold' "${SNAPSHOT_CONFIG}") bytes
- Block Interval: $(yq eval '.snapshot.triggers.blockInterval.threshold' "${SNAPSHOT_CONFIG}") blocks
- Time Interval: $(yq eval '.snapshot.triggers.timeInterval.interval' "${SNAPSHOT_CONFIG}")
- Compression: $(yq eval '.snapshot.creation.compression.algorithm' "${SNAPSHOT_CONFIG}")
- Local Retention: $(yq eval '.snapshot.storage.retention.localSnapshots' "${SNAPSHOT_CONFIG}") snapshots
- Backup Retention: $(yq eval '.snapshot.storage.retention.backupSnapshots' "${SNAPSHOT_CONFIG}") snapshots

Resources Created:
- CloudWatch Log Group: /aws/managedblockchain/${NETWORK_ID}/snapshots
- S3 Bucket: $(yq eval '.snapshot.storage.backup.s3.bucket' "${SNAPSHOT_CONFIG}")
- CloudWatch Alarms: $(yq eval '.snapshot.monitoring.alerts[].name' "${SNAPSHOT_CONFIG}" | wc -l) alarms

Next Steps:
1. Apply node configurations through AWS Managed Blockchain console
2. Verify snapshot creation after configuration
3. Monitor CloudWatch metrics for snapshot health
4. Test snapshot recovery process

EOF

    log_info "Deployment report generated: ${report_file}"
}

# Main execution
main() {
    log_info "Starting snapshot configuration deployment..."

    check_prerequisites
    validate_configuration
    create_log_group
    create_s3_bucket
    configure_peer_nodes
    create_cloudwatch_alarms
    generate_report

    log_info "Snapshot configuration deployment completed successfully!"
    log_info "Please review the deployment report and apply node configurations through AWS console"
}

# Run main function
main "$@"
