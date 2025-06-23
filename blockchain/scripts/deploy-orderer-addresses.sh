#!/bin/bash

# Deploy Orderer Addresses Configuration
# Haven Health Passport - Network Topology Setup

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config/consensus/orderer-addresses.yaml"
AWS_REGION="${AWS_REGION:-us-east-1}"
NETWORK_ID="${HAVEN_BLOCKCHAIN_NETWORK_ID}"
MEMBER_ID="${HAVEN_BLOCKCHAIN_MEMBER_ID}"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_section "Checking Prerequisites"

    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi

    if ! command -v yq &> /dev/null; then
        log_error "yq not found. Please install yq."
        exit 1
    fi

    if [ ! -f "${CONFIG_FILE}" ]; then
        log_error "Configuration file not found: ${CONFIG_FILE}"
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Create Route53 DNS records
create_dns_records() {
    log_section "Creating DNS Records"

    local hosted_zone_id=$(yq eval '.networkTopology.dns.hostedZoneId' "${CONFIG_FILE}")
    local ttl=$(yq eval '.networkTopology.dns.ttl' "${CONFIG_FILE}")

    # Create change batch file
    local change_batch="/tmp/orderer-dns-changes.json"

    cat > "${change_batch}" <<EOF
{
  "Changes": [
EOF

    # Add each DNS record
    local first=true
    yq eval '.networkTopology.dns.records[]' "${CONFIG_FILE}" -o=j | while IFS= read -r record; do
        local type=$(echo "${record}" | jq -r '.type')
        local name=$(echo "${record}" | jq -r '.name')
        local value=$(echo "${record}" | jq -r '.value')

        if [ "${first}" = false ]; then
            echo "," >> "${change_batch}"
        fi
        first=false

        cat >> "${change_batch}" <<EOF
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "${name}",
        "Type": "${type}",
        "TTL": ${ttl},
        "ResourceRecords": [
          {
            "Value": "${value}"
          }
        ]
      }
    }
EOF
    done

    echo -e "\n  ]\n}" >> "${change_batch}"

    # Apply DNS changes
    log_info "Applying DNS changes to Route53"
    aws route53 change-resource-record-sets \
        --hosted-zone-id "${hosted_zone_id}" \
        --change-batch file://"${change_batch}" \
        --region "${AWS_REGION}" \
        --output json > /tmp/dns-change-result.json

    local change_id=$(jq -r '.ChangeInfo.Id' /tmp/dns-change-result.json)
    log_info "DNS change initiated: ${change_id}"

    # Wait for DNS propagation
    log_info "Waiting for DNS propagation..."
    aws route53 wait resource-record-sets-changed \
        --id "${change_id}" \
        --region "${AWS_REGION}"

    log_info "DNS records created successfully"
    rm -f "${change_batch}"
}

# Create Network Load Balancer
create_load_balancer() {
    log_section "Creating Network Load Balancer"

    local lb_name=$(yq eval '.networkTopology.loadBalancer.name' "${CONFIG_FILE}")
    local scheme=$(yq eval '.networkTopology.loadBalancer.scheme' "${CONFIG_FILE}")

    # Get subnet IDs
    local subnet_ids=$(aws ec2 describe-subnets \
        --filters "Name=tag:Name,Values=haven-health-public-*" \
        --region "${AWS_REGION}" \
        --query 'Subnets[*].SubnetId' \
        --output json | jq -r '.[]' | paste -sd, -)

    # Create load balancer
    log_info "Creating Network Load Balancer: ${lb_name}"
    local lb_arn=$(aws elbv2 create-load-balancer \
        --name "${lb_name}" \
        --type network \
        --scheme "${scheme}" \
        --subnets ${subnet_ids//,/ } \
        --tags Key=Environment,Value=production Key=Service,Value=blockchain \
        --region "${AWS_REGION}" \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text 2>/dev/null || \
        aws elbv2 describe-load-balancers \
            --names "${lb_name}" \
            --region "${AWS_REGION}" \
            --query 'LoadBalancers[0].LoadBalancerArn' \
            --output text)

    log_info "Load balancer created/found: ${lb_arn}"

    # Create target groups
    yq eval '.networkTopology.loadBalancer.targetGroups[]' "${CONFIG_FILE}" -o=j | while IFS= read -r tg; do
        local tg_name=$(echo "${tg}" | jq -r '.name')
        local protocol=$(echo "${tg}" | jq -r '.protocol')
        local port=$(echo "${tg}" | jq -r '.port')

        log_info "Creating target group: ${tg_name}"

        # Get VPC ID
        local vpc_id=$(aws ec2 describe-vpcs \
            --filters "Name=tag:Name,Values=haven-health-vpc" \
            --region "${AWS_REGION}" \
            --query 'Vpcs[0].VpcId' \
            --output text)

        # Create target group
        local tg_arn=$(aws elbv2 create-target-group \
            --name "${tg_name}" \
            --protocol "${protocol}" \
            --port "${port}" \
            --vpc-id "${vpc_id}" \
            --target-type instance \
            --health-check-enabled \
            --health-check-protocol "${protocol}" \
            --health-check-interval-seconds 10 \
            --region "${AWS_REGION}" \
            --query 'TargetGroups[0].TargetGroupArn' \
            --output text 2>/dev/null || \
            aws elbv2 describe-target-groups \
                --names "${tg_name}" \
                --region "${AWS_REGION}" \
                --query 'TargetGroups[0].TargetGroupArn' \
                --output text)

        log_info "Target group created/found: ${tg_arn}"
    done

    # Create listeners
    yq eval '.networkTopology.loadBalancer.listeners[]' "${CONFIG_FILE}" -o=j | while IFS= read -r listener; do
        local protocol=$(echo "${listener}" | jq -r '.protocol')
        local port=$(echo "${listener}" | jq -r '.port')
        local target_port=$(echo "${listener}" | jq -r '.targetPort')

        # Get target group ARN
        local tg_arn=$(aws elbv2 describe-target-groups \
            --region "${AWS_REGION}" \
            --query "TargetGroups[?Port==\`${target_port}\`].TargetGroupArn" \
            --output text | head -1)

        log_info "Creating listener for port ${port}"

        aws elbv2 create-listener \
            --load-balancer-arn "${lb_arn}" \
            --protocol "${protocol}" \
            --port "${port}" \
            --default-actions Type=forward,TargetGroupArn="${tg_arn}" \
            --region "${AWS_REGION}" 2>/dev/null || true
    done
}

# Create Security Groups
create_security_groups() {
    log_section "Creating Security Groups"

    # Get VPC ID
    local vpc_id=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=haven-health-vpc" \
        --region "${AWS_REGION}" \
        --query 'Vpcs[0].VpcId' \
        --output text)

    yq eval '.networkTopology.securityGroups[]' "${CONFIG_FILE}" -o=j | while IFS= read -r sg; do
        local sg_name=$(echo "${sg}" | jq -r '.name')
        local sg_description=$(echo "${sg}" | jq -r '.description')

        log_info "Creating security group: ${sg_name}"

        # Create security group
        local sg_id=$(aws ec2 create-security-group \
            --group-name "${sg_name}" \
            --description "${sg_description}" \
            --vpc-id "${vpc_id}" \
            --region "${AWS_REGION}" \
            --query 'GroupId' \
            --output text 2>/dev/null || \
            aws ec2 describe-security-groups \
                --filters "Name=group-name,Values=${sg_name}" \
                --region "${AWS_REGION}" \
                --query 'SecurityGroups[0].GroupId' \
                --output text)

        log_info "Security group created/found: ${sg_id}"

        # Add ingress rules
        echo "${sg}" | jq -r '.ingressRules[]' | jq -s '.' | jq -c '.[]' | while IFS= read -r rule; do
            local protocol=$(echo "${rule}" | jq -r '.protocol')
            local port=$(echo "${rule}" | jq -r '.port')
            local source=$(echo "${rule}" | jq -r '.source')
            local description=$(echo "${rule}" | jq -r '.description')

            if [[ "${source}" == sg-* ]]; then
                # Self-referencing security group
                source="${sg_id}"
            fi

            log_info "Adding ingress rule: ${description}"

            aws ec2 authorize-security-group-ingress \
                --group-id "${sg_id}" \
                --protocol "${protocol}" \
                --port "${port}" \
                --source-group "${source}" \
                --region "${AWS_REGION}" 2>/dev/null || true
        done
    done
}

# Configure AWS Cloud Map
configure_service_discovery() {
    log_section "Configuring Service Discovery"

    if [ "$(yq eval '.serviceDiscovery.cloudMap.enabled' "${CONFIG_FILE}")" != "true" ]; then
        log_info "Cloud Map service discovery is disabled"
        return
    fi

    local namespace=$(yq eval '.serviceDiscovery.cloudMap.namespace' "${CONFIG_FILE}")
    local service=$(yq eval '.serviceDiscovery.cloudMap.service' "${CONFIG_FILE}")

    # Create namespace
    log_info "Creating Cloud Map namespace: ${namespace}"
    local namespace_id=$(aws servicediscovery create-private-dns-namespace \
        --name "${namespace}" \
        --vpc "$(aws ec2 describe-vpcs \
            --filters "Name=tag:Name,Values=haven-health-vpc" \
            --region "${AWS_REGION}" \
            --query 'Vpcs[0].VpcId' \
            --output text)" \
        --region "${AWS_REGION}" \
        --query 'OperationId' \
        --output text 2>/dev/null || \
        aws servicediscovery list-namespaces \
            --region "${AWS_REGION}" \
            --query "Namespaces[?Name==\`${namespace}\`].Id" \
            --output text)

    # Create service
    log_info "Creating Cloud Map service: ${service}"
    local service_id=$(aws servicediscovery create-service \
        --name "${service}" \
        --namespace-id "${namespace_id}" \
        --dns-config "NamespaceId=${namespace_id},DnsRecords=[{Type=A,TTL=60}]" \
        --region "${AWS_REGION}" \
        --query 'Service.Id' \
        --output text 2>/dev/null || \
        aws servicediscovery list-services \
            --region "${AWS_REGION}" \
            --query "Services[?Name==\`${service}\`].Id" \
            --output text)

    # Register instances
    yq eval '.serviceDiscovery.cloudMap.instances[]' "${CONFIG_FILE}" -o=j | while IFS= read -r instance; do
        local instance_id=$(echo "${instance}" | jq -r '.id')
        local attributes=$(echo "${instance}" | jq -r '.attributes')

        log_info "Registering instance: ${instance_id}"

        aws servicediscovery register-instance \
            --service-id "${service_id}" \
            --instance-id "${instance_id}" \
            --attributes "${attributes}" \
            --region "${AWS_REGION}" 2>/dev/null || true
    done
}

# Update orderer configuration
update_orderer_configuration() {
    log_section "Updating Orderer Configuration"

    # Generate orderer configuration updates
    local config_update_dir="${SCRIPT_DIR}/../config/consensus/orderer-updates"
    mkdir -p "${config_update_dir}"

    # For each orderer, generate configuration
    yq eval '.ordererAddresses.production[]' "${CONFIG_FILE}" -o=j | while IFS= read -r orderer; do
        # Extract orderer details
        local orderer_id=$(echo "${orderer}" | jq -r 'keys[0]')
        local orderer_data=$(echo "${orderer}" | jq -r ".[\"${orderer_id}\"]")

        local internal_host=$(echo "${orderer_data}" | jq -r '.addresses.internal.host')
        local external_host=$(echo "${orderer_data}" | jq -r '.addresses.external.host')
        local port=$(echo "${orderer_data}" | jq -r '.addresses.internal.port')

        log_info "Generating configuration for ${orderer_id}"

        # Create orderer configuration file
        cat > "${config_update_dir}/${orderer_id}-config.yaml" <<EOF
# Orderer Configuration for ${orderer_id}
# Generated by deploy-orderer-addresses.sh

General:
  ListenAddress: 0.0.0.0
  ListenPort: ${port}

  # TLS Settings
  TLS:
    Enabled: true
    PrivateKey: /var/hyperledger/orderer/tls/server.key
    Certificate: /var/hyperledger/orderer/tls/server.crt
    RootCAs:
      - /var/hyperledger/orderer/tls/ca.crt
    ClientAuthRequired: true
    ClientRootCAs:
      - /var/hyperledger/orderer/tls/ca.crt

  # Cluster configuration
  Cluster:
    ListenAddress: 0.0.0.0
    ListenPort: 7051
    ServerCertificate: /var/hyperledger/orderer/tls/server.crt
    ServerPrivateKey: /var/hyperledger/orderer/tls/server.key
    ClientCertificate: /var/hyperledger/orderer/tls/server.crt
    ClientPrivateKey: /var/hyperledger/orderer/tls/server.key
    RootCAs:
      - /var/hyperledger/orderer/tls/ca.crt

  # Operations endpoint
  Operations:
    ListenAddress: 0.0.0.0:8443
    TLS:
      Enabled: true
      Certificate: /var/hyperledger/orderer/tls/server.crt
      PrivateKey: /var/hyperledger/orderer/tls/server.key

  # Admin endpoint
  Admin:
    ListenAddress: 0.0.0.0:9443
    TLS:
      Enabled: true
      Certificate: /var/hyperledger/orderer/tls/server.crt
      PrivateKey: /var/hyperledger/orderer/tls/server.key

# Consensus Configuration
Consensus:
  # Addresses of all orderers
  Consenters:
EOF

        # Add all orderer addresses to consenter list
        yq eval '.ordererAddresses.production[]' "${CONFIG_FILE}" -o=j | while IFS= read -r cons_orderer; do
            local cons_id=$(echo "${cons_orderer}" | jq -r 'keys[0]')
            local cons_data=$(echo "${cons_orderer}" | jq -r ".[\"${cons_id}\"]")
            local cons_host=$(echo "${cons_data}" | jq -r '.addresses.internal.host')
            local cons_port=$(echo "${cons_data}" | jq -r '.addresses.internal.port')

            cat >> "${config_update_dir}/${orderer_id}-config.yaml" <<EOF
    - Host: ${cons_host}
      Port: ${cons_port}
      ClientTLSCert: /var/hyperledger/orderer/tls/${cons_id}-cert.pem
      ServerTLSCert: /var/hyperledger/orderer/tls/${cons_id}-cert.pem
EOF
        done

        log_info "Configuration generated for ${orderer_id}"
    done
}

# Generate deployment report
generate_report() {
    log_section "Generating Deployment Report"

    local report_file="${SCRIPT_DIR}/../config/consensus/orderer-addresses-deployment-$(date +%Y%m%d-%H%M%S).txt"

    cat > "${report_file}" <<EOF
Haven Health Passport - Orderer Addresses Deployment Report
==========================================================

Deployment Date: $(date)
Configuration File: ${CONFIG_FILE}
AWS Region: ${AWS_REGION}

Orderer Nodes Configured:
------------------------
EOF

    # List all orderers
    yq eval '.ordererAddresses.production[]' "${CONFIG_FILE}" -o=j | while IFS= read -r orderer; do
        local orderer_id=$(echo "${orderer}" | jq -r 'keys[0]')
        local orderer_data=$(echo "${orderer}" | jq -r ".[\"${orderer_id}\"]")

        cat >> "${report_file}" <<EOF

${orderer_id}:
  External Address: $(echo "${orderer_data}" | jq -r '.addresses.external.host'):$(echo "${orderer_data}" | jq -r '.addresses.external.port')
  Internal Address: $(echo "${orderer_data}" | jq -r '.addresses.internal.host'):$(echo "${orderer_data}" | jq -r '.addresses.internal.port')
  Availability Zone: $(echo "${orderer_data}" | jq -r '.aws.availabilityZone')
  Instance ID: $(echo "${orderer_data}" | jq -r '.aws.instanceId')
EOF
    done

    cat >> "${report_file}" <<EOF

Network Configuration:
---------------------
Load Balancer: $(yq eval '.networkTopology.loadBalancer.name' "${CONFIG_FILE}")
DNS Zone: $(yq eval '.networkTopology.dns.hostedZoneId' "${CONFIG_FILE}")
Service Discovery: $(yq eval '.serviceDiscovery.cloudMap.namespace' "${CONFIG_FILE}")

Next Steps:
-----------
1. Verify DNS resolution for all orderer addresses
2. Test connectivity between orderer nodes
3. Validate load balancer health checks
4. Configure monitoring for all endpoints
5. Update client connection profiles

EOF

    log_info "Deployment report generated: ${report_file}"
}

# Main execution
main() {
    log_info "Starting orderer addresses deployment"

    check_prerequisites
    create_security_groups
    create_load_balancer
    create_dns_records
    configure_service_discovery
    update_orderer_configuration
    generate_report

    log_info "Orderer addresses deployment completed successfully!"
}

# Run main function
main "$@"
