#!/bin/bash

# Haven Health Passport - Record Configuration Decisions
# This script documents all configuration decisions made during setup

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
DOCS_DIR="${SCRIPT_DIR}/../docs"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Recording Configuration Decisions${NC}"
echo -e "${BLUE}================================================${NC}"

# Create decision record
cat > "${DOCS_DIR}/configuration-decisions.md" <<'EOF'
# Haven Health Passport - Blockchain Configuration Decisions

## Decision Record
Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

## 1. Platform Selection
**Decision**: AWS Managed Blockchain with Hyperledger Fabric
**Rationale**:
- Managed service reduces operational overhead
- Hyperledger Fabric provides enterprise features
- Healthcare-grade security and compliance
- Built-in high availability

## 2. Network Edition
**Decision**: STANDARD Edition
**Rationale**:
- Supports up to 1000 TPS (vs 100 for Starter)
- Up to 5 peer nodes per member (vs 2)
- Better suited for production healthcare workloads
- Cost justified by performance requirements

## 3. Voting Policy
**Decision**: 50% threshold with GREATER_THAN comparator
**Rationale**:
- Balances security with operational agility
- Prevents single member veto power
- 24-hour proposal window accommodates global operations
- Democratic governance model

## 4. Instance Types
**Decision**: bc.m5.large for peer nodes
**Rationale**:
- 8GB memory handles healthcare data volumes
- Cost-effective for production use
- Scalable to larger instances if needed
- Proven performance for similar workloads

## 5. Security Architecture
**Decision**: Multi-layer security approach
**Rationale**:
- VPC endpoints for private connectivity
- Security groups for application-level control
- Network ACLs for subnet-level protection
- VPC flow logs for compliance auditing

## 6. Logging Strategy
**Decision**: 30-day retention with CloudWatch
**Rationale**:
- Meets HIPAA audit requirements
- Balances cost with compliance needs
- Enables real-time monitoring
- Supports incident investigation

## 7. Certificate Management
**Decision**: AWS-managed CA with HSM protection
**Rationale**:
- Hardware security module protection
- Automatic certificate rotation
- No operational overhead
- Compliance with healthcare standards

## 8. Network Topology
**Decision**: Single-region deployment initially
**Rationale**:
- Simplifies initial deployment
- Reduces latency for regional operations
- Can expand to multi-region later
- Cost-effective starting point

## 9. Access Control
**Decision**: Member-based permissions model
**Rationale**:
- Aligns with consortium governance
- Granular control per organization
- Supports regulatory requirements
- Enables partner onboarding

## 10. Monitoring Approach
**Decision**: CloudWatch + VPC Flow Logs
**Rationale**:
- Native AWS integration
- Comprehensive metrics coverage
- Supports compliance reporting
- Cost-effective monitoring solution

## Review and Approval
- Technical Lead: _________________ Date: _______
- Security Lead: _________________ Date: _______
- Compliance Lead: _______________ Date: _______
EOF

echo -e "\n${GREEN}✓ Configuration decisions recorded${NC}"
echo -e "Location: ${DOCS_DIR}/configuration-decisions.md"

# Create summary of all scripts
echo -e "\n📋 Creating script inventory..."

cat > "${DOCS_DIR}/script-inventory.md" <<EOF
# Blockchain Setup Scripts Inventory

## AWS Managed Blockchain Configuration Scripts

1. **01-create-blockchain-network.sh**
   - Creates AWS Managed Blockchain network
   - Configures network parameters
   - Sets up initial member

2. **02-validate-framework-selection.sh**
   - Validates Hyperledger Fabric selection
   - Verifies framework version

3. **03-configure-network-edition.sh**
   - Documents network edition choice
   - Validates STANDARD edition

4. **04-validate-network-naming.sh**
   - Validates network naming conventions
   - Checks name length limits

5. **05-configure-voting-policy.sh**
   - Sets up voting policy
   - Documents governance rules

6. **06-configure-admin-user.sh**
   - Handles admin user setup
   - Documents security practices

7. **07-configure-certificate-authority.sh**
   - Documents CA configuration
   - Explains AWS-managed CA

8. **08-configure-network-member.sh**
   - Configures member settings
   - Creates member profile

9. **09-configure-peer-node.sh**
   - Deploys peer nodes
   - Selects instance types

10. **10-configure-cloudwatch-logging.sh**
    - Sets up CloudWatch logs
    - Configures retention

11. **11-deploy-vpc-configuration.sh**
    - Deploys VPC components
    - Creates security groups

12. **12-document-network-configuration.sh**
    - Generates network documentation
    - Creates deployment summary

13. **13-create-network-diagram.py**
    - Generates network diagrams
    - Creates visual documentation

14. **14-record-configuration-decisions.sh**
    - Documents all decisions
    - Creates audit trail

## Usage Order
Run scripts in numerical order for complete setup.
EOF

echo -e "${GREEN}✓ Script inventory created${NC}"
echo -e "\n${GREEN}Configuration documentation complete!${NC}"
