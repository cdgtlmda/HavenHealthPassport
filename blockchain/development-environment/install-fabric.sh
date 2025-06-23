#!/bin/bash
# Install Hyperledger Fabric Binaries and Samples
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Fabric Installation"
echo "================================================"

# Fabric version
FABRIC_VERSION="2.5.4"
CA_VERSION="1.5.7"

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

# Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please run ./install-docker.sh first"
    exit 1
fi

if ! command_exists go; then
    print_error "Go is not installed. Please run ./install-go.sh first"
    exit 1
fi

if ! command_exists node; then
    print_error "Node.js is not installed. Please run ./install-nodejs.sh first"
    exit 1
fi

print_status "All prerequisites are installed"

# Set up Fabric directory
FABRIC_DIR="$HOME/fabric"
print_info "Setting up Fabric directory at $FABRIC_DIR"
mkdir -p $FABRIC_DIR
cd $FABRIC_DIR

# Clone fabric-samples repository
print_info "Cloning fabric-samples repository..."
if [ -d "fabric-samples" ]; then
    print_info "fabric-samples directory already exists"
    cd fabric-samples
    git pull origin main
    cd ..
else
    git clone https://github.com/hyperledger/fabric-samples.git
fi
print_status "fabric-samples repository cloned"

# Download Fabric binaries and Docker images
print_info "Downloading Fabric binaries version $FABRIC_VERSION..."

# Download bootstrap script
curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/bootstrap.sh -o bootstrap.sh
chmod +x bootstrap.sh

# Execute bootstrap script with specific versions
./bootstrap.sh $FABRIC_VERSION $CA_VERSION

# Verify binary installation
print_info "Verifying Fabric binary installation..."

# Check if binaries exist
FABRIC_BIN_PATH="$FABRIC_DIR/fabric-samples/bin"
if [ -d "$FABRIC_BIN_PATH" ]; then
    print_status "Fabric binaries downloaded to $FABRIC_BIN_PATH"

    # List installed binaries
    print_info "Installed binaries:"
    ls -la $FABRIC_BIN_PATH
else
    print_error "Fabric binaries not found"
    exit 1
fi

# Set up PATH for Fabric tools
print_info "Setting up PATH for Fabric tools..."

# Detect shell
SHELL_NAME=$(basename "$SHELL")
case $SHELL_NAME in
    bash)
        PROFILE="$HOME/.bashrc"
        ;;
    zsh)
        PROFILE="$HOME/.zshrc"
        ;;
    *)
        PROFILE="$HOME/.profile"
        ;;
esac

# Add Fabric bin to PATH if not already present
if ! grep -q "fabric-samples/bin" "$PROFILE" 2>/dev/null; then
    echo "" >> "$PROFILE"
    echo "# Hyperledger Fabric PATH" >> "$PROFILE"
    echo "export PATH=$FABRIC_BIN_PATH:\$PATH" >> "$PROFILE"
    echo "export FABRIC_PATH=$FABRIC_DIR/fabric-samples" >> "$PROFILE"
fi

# Export for current session
export PATH=$FABRIC_BIN_PATH:$PATH
export FABRIC_PATH=$FABRIC_DIR/fabric-samples

# Verify Fabric tool availability
print_info "Verifying Fabric tools..."

# Check each tool
TOOLS=("configtxgen" "configtxlator" "cryptogen" "discover" "fabric-ca-client" "fabric-ca-server" "orderer" "peer")

for tool in "${TOOLS[@]}"; do
    if command_exists $tool; then
        print_status "$tool is available"
    else
        print_error "$tool is not available"
    fi
done

# Test fabric peer version
if command_exists peer; then
    print_info "Peer version:"
    peer version
fi

# Clean up
rm -f bootstrap.sh

# Display summary
echo ""
print_status "Hyperledger Fabric installation complete!"
echo ""
print_info "Installation Summary:"
echo "  Fabric Version: $FABRIC_VERSION"
echo "  Fabric CA Version: $CA_VERSION"
echo "  Fabric Samples: $FABRIC_DIR/fabric-samples"
echo "  Fabric Binaries: $FABRIC_BIN_PATH"
echo ""
print_info "Docker images downloaded:"
docker images | grep hyperledger

echo ""
print_info "IMPORTANT: Run the following command to update your current session:"
echo "  source $PROFILE"
echo ""
echo "Next step: Run ./install-fabric-sdk.sh to install Fabric SDK for Python"

# Make next script executable
chmod +x install-fabric-sdk.sh 2>/dev/null || true

# Create a test network script for verification
cat > $FABRIC_DIR/test-network.sh << 'EOF'
#!/bin/bash
# Test Fabric installation with test-network
cd $FABRIC_PATH/test-network
./network.sh down
./network.sh up
./network.sh down
echo "Fabric test network verification complete!"
EOF

chmod +x $FABRIC_DIR/test-network.sh
print_info "Run $FABRIC_DIR/test-network.sh to test your Fabric installation"
