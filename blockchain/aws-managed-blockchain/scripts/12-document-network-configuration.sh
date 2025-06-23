#!/bin/bash

# Haven Health Passport - Document Network Configuration
# This script generates comprehensive network documentation

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
DOCS_DIR="${SCRIPT_DIR}/../docs"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Network Documentation Generation${NC}"
echo -e "${BLUE}================================================${NC}"

# Create documentation directory
mkdir -p "${DOCS_DIR}"

# Function to generate network documentation
generate_network_docs() {
    echo -e "\n📝 Generating network documentation..."

    # Collect all configuration data
    NETWORK_INFO=$(cat "${CONFIG_DIR}/network-info.json" 2>/dev/null || echo "{}")
    VPC_INFO=$(cat "${CONFIG_DIR}/vpc-info.json" 2>/dev/null || echo "{}")
    PEER_INFO=$(cat "${CONFIG_DIR}/peer-node-info.json" 2>/dev/null || echo "{}")

    # Generate comprehensive documentation
    cat > "${DOCS_DIR}/network-deployment-summary.md" <<'EOF'
# Haven Health Passport - Blockchain Network Deployment Summary

## Deployment Date
$(date -u +"%Y-%m-%d %H:%M:%S UTC")

## Network Configuration

### AWS Managed Blockchain Network
- **Network ID**: $(echo $NETWORK_INFO | jq -r '.NetworkId // "Not deployed"')
- **Network Name**: $(echo $NETWORK_INFO | jq -r '.NetworkName // "Not deployed"')
- **Member ID**: $(echo $NETWORK_INFO | jq -r '.MemberId // "Not deployed"')
- **Member Name**: $(echo $NETWORK_INFO | jq -r '.MemberName // "Not deployed"')
- **Framework**: Hyperledger Fabric v2.2
- **Edition**: STANDARD

### Voting Policy
- **Approval Threshold**: 50%
- **Proposal Duration**: 24 hours
- **Threshold Comparator**: GREATER_THAN

### VPC Configuration
- **VPC ID**: $(echo $VPC_INFO | jq -r '.VpcId // "Not configured"')
- **Subnet IDs**: $(echo $VPC_INFO | jq -r '.SubnetIds // "Not configured"')
- **Security Group ID**: $(echo $VPC_INFO | jq -r '.SecurityGroupId // "Not configured"')
- **VPC Endpoint ID**: $(echo $VPC_INFO | jq -r '.VpcEndpointId // "Not configured"')

### Peer Node Configuration
- **Peer Node ID**: $(echo $PEER_INFO | jq -r '.PeerNodeId // "Not deployed"')
- **Availability Zone**: $(echo $PEER_INFO | jq -r '.AvailabilityZone // "Not deployed"')
- **Instance Type**: bc.m5.large
- **Logging**: Enabled (CloudWatch)

### Security Configuration
- **TLS**: Enabled by default
- **Certificate Authority**: AWS managed
- **Security Groups**: Restrictive ingress rules
- **Network ACLs**: Additional layer of security
- **VPC Flow Logs**: Enabled for monitoring

### CloudWatch Logging
- **Log Retention**: 30 days
- **Log Groups**:
  - Certificate Authority logs
  - Peer node logs
  - Chaincode logs

## Access Information

### Endpoints
- **Peer Endpoint**: Available after deployment
- **CA Endpoint**: Managed by AWS
- **Ordering Service**: Managed by AWS

### Connection Requirements
- VPC endpoint must be accessible
- Security group rules must allow traffic
- TLS certificates required for connections

## Next Steps

1. Deploy chaincode to the network
2. Configure application integration
3. Set up monitoring dashboards
4. Test network connectivity
5. Configure backup procedures

## Troubleshooting

### Common Issues
- **Network not accessible**: Check VPC endpoint configuration
- **Authentication failures**: Verify member credentials
- **Transaction failures**: Check peer node logs
- **Performance issues**: Monitor CloudWatch metrics

### Support Resources
- AWS Managed Blockchain documentation
- Hyperledger Fabric documentation
- Haven Health Passport wiki

## Compliance Notes
- All data is encrypted in transit and at rest
- Network complies with HIPAA requirements
- Audit trails are maintained for all operations
- Access controls are enforced at multiple levels
EOF

    # Replace variables in documentation
    TEMP_FILE="${DOCS_DIR}/temp_doc.md"
    envsubst < "${DOCS_DIR}/network-deployment-summary.md" > "${TEMP_FILE}"
    mv "${TEMP_FILE}" "${DOCS_DIR}/network-deployment-summary.md"

    echo -e "${GREEN}✓ Network documentation generated${NC}"
}

# Execute documentation generation
generate_network_docs

echo -e "\n${GREEN}Documentation completed!${NC}"
echo -e "Location: ${DOCS_DIR}/network-deployment-summary.md"
