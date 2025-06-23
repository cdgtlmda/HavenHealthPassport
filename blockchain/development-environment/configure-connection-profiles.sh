#!/bin/bash
# Configure Connection Profiles for AWS Managed Blockchain
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Connection Profiles Setup"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check for required environment variables
if [ -z "$AWS_REGION" ]; then
    export AWS_REGION="us-east-1"
    print_info "AWS_REGION not set, using default: $AWS_REGION"
fi

# Configuration directory
CONFIG_DIR="$HOME/fabric/haven-health-config"
mkdir -p $CONFIG_DIR
cd $CONFIG_DIR

print_info "Creating connection profile configuration..."

# Create directory structure
mkdir -p {connection-profiles,crypto-config,channel-artifacts}

# Create AWS Managed Blockchain connection profile generator
cat > generate-connection-profile.sh << 'EOF'
#!/bin/bash
# Generate connection profile for AWS Managed Blockchain

# Check parameters
if [ $# -ne 4 ]; then
    echo "Usage: $0 <network-id> <member-id> <peer-node-id> <environment>"
    exit 1
fi

NETWORK_ID=$1
MEMBER_ID=$2
PEER_NODE_ID=$3
ENVIRONMENT=$4

# Get network details from AWS
echo "Fetching network details from AWS..."

# AWS CLI commands to get network details
NETWORK_INFO=$(aws managedblockchain get-network --network-id $NETWORK_ID --region $AWS_REGION)
MEMBER_INFO=$(aws managedblockchain get-member --network-id $NETWORK_ID --member-id $MEMBER_ID --region $AWS_REGION)
NODE_INFO=$(aws managedblockchain get-node --network-id $NETWORK_ID --member-id $MEMBER_ID --node-id $PEER_NODE_ID --region $AWS_REGION)

# Extract endpoints
CA_ENDPOINT=$(echo $MEMBER_INFO | jq -r '.Member.FrameworkAttributes.Fabric.CaEndpoint')
PEER_ENDPOINT=$(echo $NODE_INFO | jq -r '.Node.FrameworkAttributes.Fabric.PeerEndpoint')
PEER_EVENT_ENDPOINT=$(echo $NODE_INFO | jq -r '.Node.FrameworkAttributes.Fabric.PeerEventEndpoint')

# Generate connection profile
cat > connection-profiles/${ENVIRONMENT}-connection-profile.json << EOL
{
  "name": "haven-health-${ENVIRONMENT}",
  "version": "1.0.0",
  "client": {
    "organization": "HavenHealthOrg",
    "connection": {
      "timeout": {
        "peer": {
          "endorser": "300"
        },
        "orderer": "300"
      }
    }
  },
  "organizations": {
    "HavenHealthOrg": {
      "mspid": "m-${MEMBER_ID}",
      "peers": ["peer-${PEER_NODE_ID}"],
      "certificateAuthorities": ["ca-${MEMBER_ID}"]
    }
  },
  "peers": {
    "peer-${PEER_NODE_ID}": {
      "url": "grpcs://${PEER_ENDPOINT}",
      "tlsCACerts": {
        "path": "crypto-config/peerOrganizations/${MEMBER_ID}/peers/peer-${PEER_NODE_ID}/tls/ca.crt"
      },
      "grpcOptions": {
        "ssl-target-name-override": "peer-${PEER_NODE_ID}",
        "hostnameOverride": "peer-${PEER_NODE_ID}"
      }
    }
  },
  "certificateAuthorities": {
    "ca-${MEMBER_ID}": {
      "url": "https://${CA_ENDPOINT}",
      "caName": "ca-${MEMBER_ID}",
      "tlsCACerts": {
        "path": "crypto-config/peerOrganizations/${MEMBER_ID}/ca/ca.${MEMBER_ID}-cert.pem"
      },
      "httpOptions": {
        "verify": false
      }
    }
  }
}
EOL

echo "Connection profile generated: connection-profiles/${ENVIRONMENT}-connection-profile.json"
EOF

chmod +x generate-connection-profile.sh
print_status "Connection profile generator created"

# Create environment-specific connection profile templates
print_info "Creating environment-specific templates..."

# Development environment connection profile
cat > connection-profiles/dev-template.yaml << 'EOF'
name: haven-health-dev
version: 1.0.0
description: Haven Health Development Network

client:
  organization: HavenHealthOrg
  credentialStore:
    path: ./credential-store
    cryptoStore:
      path: ./crypto-store
  logging:
    level: info

  connection:
    timeout:
      peer:
        endorser: 300
        eventHub: 300
        eventReg: 300
      orderer: 300

channels:
  healthchannel:
    peers:
      peer0.havenhealth.dev:
        endorsingPeer: true
        chaincodeQuery: true
        ledgerQuery: true
        eventSource: true

    policies:
      queryChannelConfig:
        minResponses: 1
        maxTargets: 1
        retryOpts:
          attempts: 5
          initialBackoff: 500ms
          maxBackoff: 5s
          backoffFactor: 2.0

organizations:
  HavenHealthOrg:
    mspid: HavenHealthMSP
    cryptoPath: crypto-config/peerOrganizations/havenhealth.dev/users/{username}@havenhealth.dev/msp
    peers:
      - peer0.havenhealth.dev
    certificateAuthorities:
      - ca.havenhealth.dev

peers:
  peer0.havenhealth.dev:
    url: grpcs://localhost:7051
    tlsCACerts:
      path: crypto-config/peerOrganizations/havenhealth.dev/tlsca/tlsca.havenhealth.dev-cert.pem
    grpcOptions:
      ssl-target-name-override: peer0.havenhealth.dev
      hostnameOverride: peer0.havenhealth.dev
      grpc-max-send-message-length: -1
      grpc.keepalive_time_ms: 600000

certificateAuthorities:
  ca.havenhealth.dev:
    url: https://localhost:7054
    caName: ca-havenhealth
    tlsCACerts:
      path: crypto-config/peerOrganizations/havenhealth.dev/ca/ca.havenhealth.dev-cert.pem
    registrar:
      enrollId: admin
      enrollSecret: adminpw
    httpOptions:
      verify: false
EOF

print_status "Development template created"

# Create staging template
sed 's/dev/staging/g' connection-profiles/dev-template.yaml > connection-profiles/staging-template.yaml
sed -i 's/7051/7052/g' connection-profiles/staging-template.yaml 2>/dev/null || sed -i '' 's/7051/7052/g' connection-profiles/staging-template.yaml
print_status "Staging template created"

# Create production template
sed 's/dev/prod/g' connection-profiles/dev-template.yaml > connection-profiles/prod-template.yaml
sed -i 's/localhost/peer0.havenhealth.com/g' connection-profiles/prod-template.yaml 2>/dev/null || sed -i '' 's/localhost/peer0.havenhealth.com/g' connection-profiles/prod-template.yaml
print_status "Production template created"

# Create validation script
cat > validate-connection.sh << 'EOF'
#!/bin/bash
# Validate connection profile

PROFILE=$1
if [ -z "$PROFILE" ]; then
    echo "Usage: $0 <connection-profile>"
    exit 1
fi

echo "Validating connection profile: $PROFILE"

# Check if file exists
if [ ! -f "$PROFILE" ]; then
    echo "Error: Profile file not found"
    exit 1
fi

# Validate YAML/JSON syntax
if [[ $PROFILE == *.yaml ]] || [[ $PROFILE == *.yml ]]; then
    python3 -c "import yaml; yaml.safe_load(open('$PROFILE'))" && echo "✓ Valid YAML syntax" || echo "✗ Invalid YAML syntax"
elif [[ $PROFILE == *.json ]]; then
    jq . "$PROFILE" > /dev/null && echo "✓ Valid JSON syntax" || echo "✗ Invalid JSON syntax"
fi

# Check required fields
echo "Checking required fields..."
python3 << EOPY
import yaml
import json
import sys

with open('$PROFILE', 'r') as f:
    if '$PROFILE'.endswith('.json'):
        config = json.load(f)
    else:
        config = yaml.safe_load(f)

required_fields = ['name', 'version', 'organizations', 'peers', 'certificateAuthorities']
for field in required_fields:
    if field in config:
        print(f"✓ {field} present")
    else:
        print(f"✗ {field} missing")
        sys.exit(1)
EOPY
EOF

chmod +x validate-connection.sh
print_status "Connection validation script created"

# Summary
echo ""
print_status "Connection profile configuration complete!"
echo ""
print_info "Created files:"
echo "  - Connection profile generator: generate-connection-profile.sh"
echo "  - Development template: connection-profiles/dev-template.yaml"
echo "  - Staging template: connection-profiles/staging-template.yaml"
echo "  - Production template: connection-profiles/prod-template.yaml"
echo "  - Validation script: validate-connection.sh"
echo ""
echo "Next step: Run ./create-crypto-material.sh to generate certificates"

# Make next script executable
chmod +x create-crypto-material.sh 2>/dev/null || true
