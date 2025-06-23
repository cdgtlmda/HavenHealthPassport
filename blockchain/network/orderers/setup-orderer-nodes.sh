#!/bin/bash

# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Script to set up orderer nodes for Haven Health Passport blockchain

set -e

echo "=========================================="
echo "Setting up Orderer Nodes for Haven Health Passport"
echo "=========================================="

# Environment variables
export FABRIC_CFG_PATH=${PWD}/../config
export ORDERER_COUNT=5
export DOMAIN="havenhealthpassport.org"
export ORDERER_ORG="OrdererOrg"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Checking prerequisites..."
if ! command_exists cryptogen; then
    print_error "cryptogen not found. Please ensure Fabric binaries are installed and in PATH."
    exit 1
fi

# Create directory structure for orderers
print_step "Creating directory structure for orderer nodes..."

for i in $(seq 1 $ORDERER_COUNT); do
    mkdir -p orderer${i}
    mkdir -p orderer${i}/config
    mkdir -p orderer${i}/data
    mkdir -p orderer${i}/logs
    print_status "Created directories for orderer${i}"
done

# Create crypto-config.yaml for orderer organization
print_step "Creating crypto configuration for orderer organization..."

cat > crypto-config-orderer.yaml << EOF
# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# ---------------------------------------------------------------------------
# Orderer Organizations
# ---------------------------------------------------------------------------
OrdererOrgs:
  - Name: ${ORDERER_ORG}
    Domain: ${DOMAIN}
    EnableNodeOUs: true
    # ---------------------------------------------------------------------------
    # "Specs" - See PeerOrgs below for complete description
    # ---------------------------------------------------------------------------
    Specs:
EOF

# Add orderer specs
for i in $(seq 1 $ORDERER_COUNT); do
    cat >> crypto-config-orderer.yaml << EOF
      - Hostname: orderer${i}
        CommonName: orderer${i}.${DOMAIN}
        SANS:
          - localhost
          - 127.0.0.1
          - orderer${i}.${DOMAIN}
EOF
done

print_status "Crypto configuration created"
# Generate crypto material
print_step "Generating crypto material for orderer nodes..."

cryptogen generate --config=crypto-config-orderer.yaml --output="../crypto-config"

if [ $? -ne 0 ]; then
    print_error "Failed to generate crypto material"
    exit 1
fi

print_status "Crypto material generated successfully"

# Create individual orderer configurations
print_step "Creating individual orderer configurations..."

for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"
    ORDERER_PORT=$((7050 + (i-1)*1000))
    ADMIN_PORT=$((7053 + (i-1)*1000))
    OPERATIONS_PORT=$((9443 + i - 1))

    print_status "Configuring ${ORDERER_NAME} on port ${ORDERER_PORT}"

    # Create orderer-specific configuration
    cat > ${ORDERER_NAME}/orderer.yaml << EOF
# Copyright Haven Health Passport. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

################################################################################
#
#   Orderer Configuration for ${ORDERER_NAME}
#
################################################################################
General:
    ListenAddress: 0.0.0.0
    ListenPort: ${ORDERER_PORT}

    TLS:
        Enabled: true
        PrivateKey: /var/hyperledger/orderer/tls/server.key
        Certificate: /var/hyperledger/orderer/tls/server.crt
        RootCAs:
          - /var/hyperledger/orderer/tls/ca.crt
        ClientAuthRequired: false
        ClientRootCAs:

    Keepalive:
        ServerMinInterval: 60s
        ServerInterval: 7200s
        ServerTimeout: 20s
EOF
done
# Continue orderer configuration with cluster settings
for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"
    ORDERER_PORT=$((7050 + (i-1)*1000))
    ADMIN_PORT=$((7053 + (i-1)*1000))
    OPERATIONS_PORT=$((9443 + i - 1))

    cat >> ${ORDERER_NAME}/orderer.yaml << EOF

    Cluster:
        SendBufferSize: 10
        ClientCertificate: /var/hyperledger/orderer/tls/server.crt
        ClientPrivateKey: /var/hyperledger/orderer/tls/server.key
        ListenPort: ${ORDERER_PORT}
        ListenAddress: 0.0.0.0
        ServerCertificate: /var/hyperledger/orderer/tls/server.crt
        ServerPrivateKey: /var/hyperledger/orderer/tls/server.key

    BootstrapMethod: none
    BootstrapFile:
    LocalMSPDir: /var/hyperledger/orderer/msp
    LocalMSPID: OrdererMSP

    BCCSP:
        Default: SW
        SW:
            Hash: SHA2
            Security: 256
            FileKeyStore:
                KeyStore:

    Authentication:
        TimeWindow: 15m

FileLedger:
    Location: /var/hyperledger/production/orderer

Consensus:
    WALDir: /var/hyperledger/production/orderer/etcdraft/wal
    SnapDir: /var/hyperledger/production/orderer/etcdraft/snapshot

Operations:
    ListenAddress: 0.0.0.0:${OPERATIONS_PORT}
    TLS:
        Enabled: true
        Certificate: /var/hyperledger/orderer/tls/server.crt
        PrivateKey: /var/hyperledger/orderer/tls/server.key
        ClientAuthRequired: false
        ClientRootCAs: []
EOF
done
# Complete orderer configuration
for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"
    ADMIN_PORT=$((7053 + (i-1)*1000))

    cat >> ${ORDERER_NAME}/orderer.yaml << EOF

Metrics:
    Provider: prometheus

Admin:
    ListenAddress: 0.0.0.0:${ADMIN_PORT}
    TLS:
        Enabled: true
        Certificate: /var/hyperledger/orderer/tls/server.crt
        PrivateKey: /var/hyperledger/orderer/tls/server.key
        RootCAs: [/var/hyperledger/orderer/tls/ca.crt]
        ClientAuthRequired: true
        ClientRootCAs: [/var/hyperledger/orderer/tls/ca.crt]

ChannelParticipation:
    Enabled: true
    MaxRequestBodySize: 1 MB

Debug:
    BroadcastTraceDir:
    DeliverTraceDir:
EOF

    print_status "Configuration created for ${ORDERER_NAME}"
done

# Create systemd service files for each orderer
print_step "Creating systemd service files..."

for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"

    cat > ${ORDERER_NAME}/${ORDERER_NAME}.service << EOF
[Unit]
Description=Hyperledger Fabric Orderer - ${ORDERER_NAME}
Documentation=https://hyperledger-fabric.readthedocs.io/
After=network.target

[Service]
Type=simple
User=fabric
Group=fabric
WorkingDirectory=/opt/havenhealthpassport/orderers/${ORDERER_NAME}
ExecStart=/usr/local/bin/orderer start
Restart=on-failure
RestartSec=5s
EOF
done
# Complete systemd service files
for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"

    cat >> ${ORDERER_NAME}/${ORDERER_NAME}.service << EOF
Environment="ORDERER_CFG_PATH=/opt/havenhealthpassport/orderers/${ORDERER_NAME}/config"
Environment="FABRIC_CFG_PATH=/opt/havenhealthpassport/orderers/${ORDERER_NAME}/config"
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${ORDERER_NAME}

[Install]
WantedBy=multi-user.target
EOF

    print_status "Service file created for ${ORDERER_NAME}"
done

# Create startup script for each orderer
print_step "Creating individual startup scripts..."

for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"
    ORDERER_PORT=$((7050 + (i-1)*1000))

    cat > ${ORDERER_NAME}/start-${ORDERER_NAME}.sh << 'EOF'
#!/bin/bash

# Start script for ORDERER_NAME_PLACEHOLDER

set -e

ORDERER_NAME=ORDERER_NAME_PLACEHOLDER
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting ${ORDERER_NAME}..."

# Check if running in Docker or standalone
if [ -f /.dockerenv ]; then
    echo "Running in Docker container"
    export ORDERER_CFG_PATH=/etc/hyperledger/fabric
else
    echo "Running standalone"
    export ORDERER_CFG_PATH=${SCRIPT_DIR}/config
fi

# Ensure directories exist
mkdir -p ${SCRIPT_DIR}/data
mkdir -p ${SCRIPT_DIR}/logs

# Start orderer
exec orderer start 2>&1 | tee ${SCRIPT_DIR}/logs/${ORDERER_NAME}.log
EOF

    # Replace placeholder with actual orderer name
    sed -i "s/ORDERER_NAME_PLACEHOLDER/${ORDERER_NAME}/g" ${ORDERER_NAME}/start-${ORDERER_NAME}.sh
    chmod +x ${ORDERER_NAME}/start-${ORDERER_NAME}.sh
done
# Create Docker environment files
print_step "Creating Docker environment files..."

for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_NAME="orderer${i}"
    ORDERER_PORT=$((7050 + (i-1)*1000))
    ADMIN_PORT=$((7053 + (i-1)*1000))
    OPERATIONS_PORT=$((9443 + i - 1))

    cat > ${ORDERER_NAME}/.env << EOF
# Environment variables for ${ORDERER_NAME}
ORDERER_NAME=${ORDERER_NAME}
ORDERER_PORT=${ORDERER_PORT}
ADMIN_PORT=${ADMIN_PORT}
OPERATIONS_PORT=${OPERATIONS_PORT}
ORDERER_GENERAL_LISTENADDRESS=0.0.0.0
ORDERER_GENERAL_LISTENPORT=${ORDERER_PORT}
ORDERER_GENERAL_LOCALMSPID=OrdererMSP
ORDERER_GENERAL_LOCALMSPDIR=/var/hyperledger/orderer/msp
ORDERER_GENERAL_TLS_ENABLED=true
ORDERER_GENERAL_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key
ORDERER_GENERAL_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt
ORDERER_GENERAL_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
ORDERER_GENERAL_CLUSTER_CLIENTCERTIFICATE=/var/hyperledger/orderer/tls/server.crt
ORDERER_GENERAL_CLUSTER_CLIENTPRIVATEKEY=/var/hyperledger/orderer/tls/server.key
ORDERER_GENERAL_CLUSTER_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
ORDERER_GENERAL_BOOTSTRAPMETHOD=none
ORDERER_CHANNELPARTICIPATION_ENABLED=true
ORDERER_ADMIN_TLS_ENABLED=true
ORDERER_ADMIN_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt
ORDERER_ADMIN_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key
ORDERER_ADMIN_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
ORDERER_ADMIN_TLS_CLIENTROOTCAS=[/var/hyperledger/orderer/tls/ca.crt]
ORDERER_ADMIN_LISTENADDRESS=0.0.0.0:${ADMIN_PORT}
ORDERER_OPERATIONS_LISTENADDRESS=0.0.0.0:${OPERATIONS_PORT}
ORDERER_METRICS_PROVIDER=prometheus
FABRIC_LOGGING_SPEC=INFO
EOF

    print_status "Environment file created for ${ORDERER_NAME}"
done

# Create health check script
print_step "Creating health check script..."

cat > check-orderer-health.sh << 'EOF'
#!/bin/bash

# Health check script for orderer nodes

ORDERERS=5

echo "=========================================="
echo "Orderer Node Health Check"
echo "=========================================="
EOF
# Complete health check script
cat >> check-orderer-health.sh << 'EOF'

for i in $(seq 1 $ORDERERS); do
    ORDERER_NAME="orderer${i}"
    OPERATIONS_PORT=$((9443 + i - 1))

    echo -n "Checking ${ORDERER_NAME} (port ${OPERATIONS_PORT})... "

    if curl -sk https://localhost:${OPERATIONS_PORT}/healthz > /dev/null 2>&1; then
        echo -e "\033[0;32m[HEALTHY]\033[0m"
    else
        echo -e "\033[0;31m[UNHEALTHY]\033[0m"
    fi
done

echo "=========================================="
EOF

chmod +x check-orderer-health.sh

# Create consolidated startup script
print_step "Creating consolidated startup script..."

cat > start-all-orderers.sh << 'EOF'
#!/bin/bash

# Start all orderer nodes

echo "Starting all orderer nodes..."

for i in $(seq 1 5); do
    ORDERER_NAME="orderer${i}"
    echo "Starting ${ORDERER_NAME}..."
    cd ${ORDERER_NAME} && ./start-${ORDERER_NAME}.sh &
    cd ..
done

echo "All orderer nodes started. Check logs for status."
echo "Run ./check-orderer-health.sh to verify health status"
EOF

chmod +x start-all-orderers.sh

# Create stop script
cat > stop-all-orderers.sh << 'EOF'
#!/bin/bash

# Stop all orderer nodes

echo "Stopping all orderer nodes..."

pkill -f "orderer start" || true

echo "All orderer nodes stopped."
EOF

chmod +x stop-all-orderers.sh
# Create verification script
print_step "Creating verification script..."

cat > verify-orderer-setup.sh << 'EOF'
#!/bin/bash

# Verify orderer node setup

echo "=========================================="
echo "Verifying Orderer Node Setup"
echo "=========================================="

ERRORS=0

# Check directories
echo -n "Checking orderer directories... "
for i in $(seq 1 5); do
    if [ ! -d "orderer${i}" ]; then
        echo -e "\033[0;31m[MISSING: orderer${i}]\033[0m"
        ((ERRORS++))
    fi
done
if [ $ERRORS -eq 0 ]; then
    echo -e "\033[0;32m[OK]\033[0m"
fi

# Check configuration files
echo -n "Checking configuration files... "
for i in $(seq 1 5); do
    if [ ! -f "orderer${i}/orderer.yaml" ]; then
        echo -e "\033[0;31m[MISSING: orderer${i}/orderer.yaml]\033[0m"
        ((ERRORS++))
    fi
done
if [ $ERRORS -eq 0 ]; then
    echo -e "\033[0;32m[OK]\033[0m"
fi

# Check crypto material
echo -n "Checking crypto material... "
if [ ! -d "../crypto-config/ordererOrganizations" ]; then
    echo -e "\033[0;31m[MISSING]\033[0m"
    ((ERRORS++))
else
    echo -e "\033[0;32m[OK]\033[0m"
fi

echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "\033[0;32mAll checks passed!\033[0m"
else
    echo -e "\033[0;31mFound $ERRORS errors!\033[0m"
fi
EOF

chmod +x verify-orderer-setup.sh
# Display summary
echo ""
echo "=========================================="
echo "Orderer Node Setup Complete!"
echo "=========================================="
echo ""
echo "Created ${ORDERER_COUNT} orderer nodes:"
for i in $(seq 1 $ORDERER_COUNT); do
    ORDERER_PORT=$((7050 + (i-1)*1000))
    echo "  - orderer${i}: Port ${ORDERER_PORT}"
done
echo ""
echo "Next steps:"
echo "1. Run ./verify-orderer-setup.sh to verify setup"
echo "2. Copy crypto material to appropriate locations"
echo "3. Run ./start-all-orderers.sh to start orderer nodes"
echo "4. Run ./check-orderer-health.sh to check health status"
echo ""
echo "For production deployment:"
echo "- Copy systemd service files to /etc/systemd/system/"
echo "- Run 'systemctl daemon-reload'"
echo "- Start services with 'systemctl start orderer{1..5}'"
echo ""
print_status "Setup script completed successfully!"
