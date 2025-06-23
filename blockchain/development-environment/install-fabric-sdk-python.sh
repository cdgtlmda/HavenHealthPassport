#!/bin/bash

# Haven Health Passport - Fabric SDK for Python Installation Script
# This script sets up Python environment and installs Fabric SDK

set -e

# Configuration
PYTHON_VERSION="3.9"
VENV_NAME="fabric-venv"
SDK_DIR="$HOME/haven-fabric-sdk"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_header "Installing Fabric SDK for Python"

# Check Python installation
print_status "Checking Python installation..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_INSTALLED=$(python3 --version | awk '{print $2}')
    print_status "Python installed: $PYTHON_INSTALLED"
else
    print_error "Python 3 is not installed"
    exit 1
fi

# Check pip installationif ! command -v pip3 >/dev/null 2>&1; then
    print_warning "pip3 is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        python3 -m ensurepip
    else
        sudo apt-get update && sudo apt-get install -y python3-pip
    fi
fi

# Create SDK directory
print_header "Setting up Fabric SDK Directory"
mkdir -p "$SDK_DIR"
cd "$SDK_DIR"

# Create Python virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv $VENV_NAME

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_NAME/bin/activate"

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install Fabric SDK for Python
print_header "Installing Fabric SDK for Python"
print_status "Installing fabric-sdk-py and dependencies..."

# Create requirements file
cat > requirements.txt <<EOF
# Hyperledger Fabric SDK for Python
fabric-sdk-py==0.9.0
# Additional dependencies for Haven Health Passport
grpcio==1.51.1
grpcio-tools==1.51.1
protobuf==3.20.3
pyyaml==6.0
cryptography==39.0.0
pysha3==1.0.2
# Development tools
ipython==8.10.0
pytest==7.2.1
pytest-asyncio==0.20.3
black==23.1.0
flake8==6.0.0
EOF

# Install requirements
pip install -r requirements.txt
# Verify installation
print_header "Verifying SDK Installation"
python -c "import hfc; print(f'Fabric SDK version: {hfc.__version__}')" || true

# Create example connection profile
print_status "Creating example connection profile..."
cat > connection-profile.yaml <<EOF
---
name: "Haven Health Passport Network"
version: "1.0"
client:
  organization: HavenHealthFoundation
  connection:
    timeout:
      peer:
        endorser: 300
        eventHub: 300
        eventReg: 300
      orderer: 300

organizations:
  HavenHealthFoundation:
    mspid: HavenHealthFoundationMSP
    peers:
      - peer0.havenhealthfoundation.com
    certificateAuthorities:
      - ca.havenhealthfoundation.com

peers:
  peer0.havenhealthfoundation.com:
    url: grpcs://localhost:7051
    tlsCACerts:
      path: \${FABRIC_CFG_PATH}/peerOrganizations/havenhealthfoundation.com/tlsca/tlsca.havenhealthfoundation.com-cert.pem
    grpcOptions:
      ssl-target-name-override: peer0.havenhealthfoundation.com
      grpc-max-send-message-length: -1
      grpc-max-receive-message-length: -1

certificateAuthorities:
  ca.havenhealthfoundation.com:
    url: https://localhost:7054
    caName: ca-havenhealthfoundation
    tlsCACerts:
      path: \${FABRIC_CFG_PATH}/peerOrganizations/havenhealthfoundation.com/tlsca/tlsca.havenhealthfoundation.com-cert.pem
    httpOptions:
      verify: false
EOF

# Create activation script
cat > activate-fabric-env.sh <<'ACTIVATE_EOF'
#!/bin/bash
# Activate Fabric SDK Python environment
echo "Activating Fabric SDK Python environment..."
source "$SDK_DIR/$VENV_NAME/bin/activate"
export FABRIC_SDK_PATH="$SDK_DIR"
echo "Fabric SDK environment activated!"
echo "Python: $(which python)"
echo "SDK Path: $FABRIC_SDK_PATH"
ACTIVATE_EOF

chmod +x activate-fabric-env.sh

# Create installation report
cat > ./fabric-sdk-python-report.txt <<EOF
Fabric SDK for Python Installation Report
Generated: $(date)

Python Version: $PYTHON_INSTALLED
Virtual Environment: $SDK_DIR/$VENV_NAME
SDK Directory: $SDK_DIR

Installed Packages:
$(pip list | grep -E 'fabric-sdk-py|grpcio|protobuf|cryptography')

Connection Profile: $SDK_DIR/connection-profile.yaml
Activation Script: $SDK_DIR/activate-fabric-env.sh

To activate the environment:
source $SDK_DIR/activate-fabric-env.sh
EOF

print_status "Installation report saved to: ./fabric-sdk-python-report.txt"

# Copy activation script to development environment
cp activate-fabric-env.sh ../

# Deactivate virtual environment
deactivate

print_header "Fabric SDK for Python Installation Complete"
print_status "SDK installed at: $SDK_DIR"
print_status "To activate the environment, run:"
print_status "  source $SDK_DIR/activate-fabric-env.sh"
print_warning "Remember to activate the environment before running Python Fabric scripts"
print_status "Next step: Configure connection profiles"
