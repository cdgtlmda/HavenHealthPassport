#!/bin/bash
# Install Node.js for Chaincode Development
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Node.js Installation"
echo "================================================"

# Node.js version required for Hyperledger Fabric chaincode
NODE_VERSION="18"  # LTS version

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

# Detect OS
OS=$(uname -s)
print_info "Detected OS: $OS"

# Check if Node.js is already installed
if command_exists node; then
    CURRENT_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    print_info "Node.js is already installed: $(node -v)"

    if [[ "$CURRENT_VERSION" -ge "$NODE_VERSION" ]]; then
        print_status "Node.js version is sufficient"

        # Check npm
        if command_exists npm; then
            print_status "npm is installed: $(npm -v)"
        else
            print_error "npm is not installed"
            exit 1
        fi

        exit 0
    else
        print_info "Node.js version is too old. Installing Node.js $NODE_VERSION..."
    fi
fi

# Install Node.js using NodeSource repository (recommended for Linux)
if [[ "$OS" == "Linux" ]]; then
    print_info "Installing Node.js via NodeSource repository..."

    # Download and execute NodeSource setup script
    curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | sudo -E bash -

    # Install Node.js
    sudo apt-get install -y nodejs

    # Install build tools for native addons
    sudo apt-get install -y build-essential

elif [[ "$OS" == "Darwin" ]]; then
    # macOS - Use Homebrew or official installer
    print_info "Installing Node.js for macOS..."

    if command_exists brew; then
        # Install via Homebrew
        brew install node@${NODE_VERSION}
        brew link --overwrite node@${NODE_VERSION}
    else
        print_error "Please install Node.js manually from: https://nodejs.org/"
        exit 1
    fi
else
    print_error "Unsupported OS: $OS"
    exit 1
fi

# Verify installation
print_info "Verifying Node.js installation..."

if command_exists node; then
    print_status "Node.js installed successfully: $(node -v)"
else
    print_error "Node.js installation failed"
    exit 1
fi

if command_exists npm; then
    print_status "npm installed successfully: $(npm -v)"
else
    print_error "npm installation failed"
    exit 1
fi

# Install global npm packages useful for Fabric development
print_info "Installing useful npm packages for Fabric development..."

# Install Yeoman (for Fabric generators)
npm install -g yo

# Install Fabric chaincode generator
npm install -g generator-fabric

# Install TypeScript (for TypeScript chaincode)
npm install -g typescript

# Install nodemon for development
npm install -g nodemon

print_status "Global npm packages installed"

# Test Node.js installation
print_info "Testing Node.js installation..."

# Create a simple test file
cat > /tmp/test.js << EOF
console.log('Node.js is working correctly!');
console.log('Version:', process.version);
console.log('Platform:', process.platform);
EOF

if node /tmp/test.js >/dev/null 2>&1; then
    print_status "Node.js test successful"
else
    print_error "Node.js test failed"
fi

rm -f /tmp/test.js

# Display Node.js environment
echo ""
print_info "Node.js Environment:"
echo "  Node.js Version: $(node -v)"
echo "  npm Version: $(npm -v)"
echo "  npm Global Packages Location: $(npm root -g)"

echo ""
print_status "Node.js installation complete!"
echo ""
echo "Next step: Run ./install-fabric.sh to install Hyperledger Fabric"

# Make next script executable
chmod +x install-fabric.sh 2>/dev/null || true
