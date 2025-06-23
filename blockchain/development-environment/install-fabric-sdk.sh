#!/bin/bash
# Install Fabric SDK for Python
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Fabric SDK Python Setup"
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python installation
print_info "Checking Python installation..."

if ! command_exists python3; then
    print_error "Python 3 is not installed"

    # Install Python based on OS
    OS=$(uname -s)
    if [[ "$OS" == "Darwin" ]]; then
        if command_exists brew; then
            brew install python@3.11
        else
            print_error "Please install Python 3.11 or later"
            exit 1
        fi
    elif [[ "$OS" == "Linux" ]]; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
    fi
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_status "Python installed: $(python3 --version)"

# Ensure pip is up to date
print_info "Updating pip..."
python3 -m pip install --upgrade pip

# Install virtualenv if not present
if ! python3 -m pip show virtualenv >/dev/null 2>&1; then
    print_info "Installing virtualenv..."
    python3 -m pip install virtualenv
fi

# Create project directory for Fabric SDK
FABRIC_SDK_DIR="$HOME/fabric/fabric-sdk-py"
print_info "Creating Fabric SDK directory at $FABRIC_SDK_DIR"
mkdir -p $FABRIC_SDK_DIR
cd $FABRIC_SDK_DIR

# Configure Python virtual environment
print_info "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip in virtual environment
pip install --upgrade pip

# Install required dependencies
print_info "Installing dependencies..."
pip install wheel setuptools

# Install fabric-sdk-py package
print_info "Installing fabric-sdk-py..."
pip install fabric-sdk-py

# Install additional useful packages
print_info "Installing additional packages for development..."
pip install \
    grpcio \
    grpcio-tools \
    protobuf \
    pyyaml \
    requests \
    ipython \
    jupyter

# Verify SDK installation
print_info "Verifying Fabric SDK installation..."

# Create a verification script
cat > verify_sdk.py << 'EOF'
#!/usr/bin/env python3
import sys
try:
    from hfc.fabric import Client
    from hfc.fabric_network import Gateway
    print("✓ Fabric SDK for Python is installed correctly")
    print(f"✓ SDK components are importable")
    sys.exit(0)
except ImportError as e:
    print(f"✗ Error importing Fabric SDK: {e}")
    sys.exit(1)
EOF

chmod +x verify_sdk.py

# Run verification
if python verify_sdk.py; then
    print_status "Fabric SDK verification passed"
else
    print_error "Fabric SDK verification failed"
    exit 1
fi

# Create a sample connection profile template
print_info "Creating sample connection profile..."
cat > connection-profile-template.yaml << 'EOF'
name: "haven-health-network"
version: "1.0"
description: "Haven Health Passport Network Connection Profile"

organizations:
  HavenHealth:
    mspid: HavenHealthMSP
    peers:
      - peer0.havenheath.com
    certificateAuthorities:
      - ca.havenhealth.com

peers:
  peer0.havenhealth.com:
    url: grpcs://localhost:7051
    tlsCACerts:
      path: ./crypto-config/peerOrganizations/havenhealth.com/peers/peer0.havenhealth.com/tls/ca.crt
    grpcOptions:
      ssl-target-name-override: peer0.havenhealth.com
      hostnameOverride: peer0.havenhealth.com

certificateAuthorities:
  ca.havenhealth.com:
    url: https://localhost:7054
    caName: ca-havenhealth
    tlsCACerts:
      path: ./crypto-config/peerOrganizations/havenhealth.com/ca/ca.havenhealth.com-cert.pem
    httpOptions:
      verify: false

channels:
  healthchannel:
    peers:
      peer0.havenhealth.com:
        endorsingPeer: true
        chaincodeQuery: true
        ledgerQuery: true
        eventSource: true
EOF

print_status "Connection profile template created"

# Create requirements file for the project
cat > requirements.txt << EOF
fabric-sdk-py==1.0.0
grpcio==1.51.1
grpcio-tools==1.51.1
protobuf==4.21.12
pyyaml==6.0
requests==2.28.2
cryptography==39.0.1
EOF

# Display summary
echo ""
print_status "Fabric SDK for Python installation complete!"
echo ""
print_info "Installation Summary:"
echo "  SDK Directory: $FABRIC_SDK_DIR"
echo "  Virtual Environment: $FABRIC_SDK_DIR/venv"
echo "  Connection Profile Template: connection-profile-template.yaml"
echo ""
print_info "To activate the virtual environment in the future:"
echo "  cd $FABRIC_SDK_DIR"
echo "  source venv/bin/activate"
echo ""
echo "Next steps:"
echo "1. Configure connection profiles in ./configure-connection-profiles.sh"
echo "2. Create crypto material in ./create-crypto-material.sh"

# Create activation script
cat > activate.sh << EOF
#!/bin/bash
source $FABRIC_SDK_DIR/venv/bin/activate
echo "Fabric SDK Python environment activated"
EOF
chmod +x activate.sh

# Deactivate virtual environment
deactivate

print_info "Run ./activate.sh to activate the Fabric SDK environment"
