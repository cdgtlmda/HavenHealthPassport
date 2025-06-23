#!/bin/bash
# Install Go Programming Language
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Go Installation"
echo "================================================"

# Go version required for Hyperledger Fabric
GO_VERSION="1.21.5"

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

# Detect OS and Architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

# Convert architecture names
case $ARCH in
    x86_64)
        ARCH="amd64"
        ;;
    aarch64)
        ARCH="arm64"
        ;;
    armv6l)
        ARCH="armv6l"
        ;;
    *)
        print_error "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

print_info "Detected OS: $OS"
print_info "Detected Architecture: $ARCH"
print_info "Go version to install: $GO_VERSION"

# Check if Go is already installed
if command_exists go; then
    CURRENT_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
    print_info "Go is already installed: version $CURRENT_VERSION"

    # Compare versions
    if [[ "$CURRENT_VERSION" == "$GO_VERSION" ]]; then
        print_status "Go $GO_VERSION is already installed"
        exit 0
    else
        print_info "Different version detected. Proceeding with installation of Go $GO_VERSION"
    fi
fi

# Download URL
DOWNLOAD_URL="https://go.dev/dl/go${GO_VERSION}.${OS}-${ARCH}.tar.gz"
print_info "Download URL: $DOWNLOAD_URL"

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Download Go
print_info "Downloading Go $GO_VERSION..."
curl -LO $DOWNLOAD_URL || wget $DOWNLOAD_URL

# Remove old installation
if [ -d "/usr/local/go" ]; then
    print_info "Removing old Go installation..."
    sudo rm -rf /usr/local/go
fi

# Extract new version
print_info "Extracting Go..."
sudo tar -C /usr/local -xzf go${GO_VERSION}.${OS}-${ARCH}.tar.gz

# Clean up
cd -
rm -rf $TEMP_DIR

# Configure Go environment variables
print_info "Configuring Go environment..."

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

# Add Go to PATH if not already present
if ! grep -q "export PATH=.*\/usr\/local\/go\/bin" "$PROFILE" 2>/dev/null; then
    echo "" >> "$PROFILE"
    echo "# Go environment variables" >> "$PROFILE"
    echo "export PATH=/usr/local/go/bin:\$PATH" >> "$PROFILE"
fi

# Set GOPATH and GOBIN
if ! grep -q "export GOPATH=" "$PROFILE" 2>/dev/null; then
    echo "export GOPATH=\$HOME/go" >> "$PROFILE"
    echo "export GOBIN=\$GOPATH/bin" >> "$PROFILE"
    echo "export PATH=\$GOBIN:\$PATH" >> "$PROFILE"
fi

# Create Go workspace directories
print_info "Creating Go workspace directories..."
mkdir -p $HOME/go/{bin,src,pkg}

# Source the profile to update current session
export PATH=/usr/local/go/bin:$PATH
export GOPATH=$HOME/go
export GOBIN=$GOPATH/bin
export PATH=$GOBIN:$PATH

# Verify installation
print_info "Verifying Go installation..."

if command_exists go; then
    print_status "Go installed successfully!"
    go version
else
    print_error "Go installation failed"
    exit 1
fi

# Test Go installation
print_info "Testing Go installation..."
cat > /tmp/hello.go << EOF
package main
import "fmt"
func main() {
    fmt.Println("Go is working correctly!")
}
EOF

if go run /tmp/hello.go >/dev/null 2>&1; then
    print_status "Go test successful"
else
    print_error "Go test failed"
fi

rm -f /tmp/hello.go

# Display Go environment
echo ""
print_info "Go Environment:"
echo "  GOPATH: $GOPATH"
echo "  GOBIN: $GOBIN"
echo "  Go Version: $(go version)"

echo ""
print_status "Go installation complete!"
echo ""
print_info "IMPORTANT: Run the following command to update your current session:"
echo "  source $PROFILE"
echo ""
echo "Next step: Run ./install-nodejs.sh to install Node.js"

# Make next script executable
chmod +x install-nodejs.sh 2>/dev/null || true
