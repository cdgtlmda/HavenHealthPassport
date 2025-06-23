#!/bin/bash

# Haven Health Passport - Install Go Programming Language
# This script installs Go for Hyperledger Fabric chaincode development

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
GO_VERSION="1.21.5"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Go Programming Language Installation${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if Go is already installed
if command -v go &> /dev/null; then
    CURRENT_VERSION=$(go version | cut -d' ' -f3 | sed 's/go//')
    echo -e "\n${GREEN}✓ Go is already installed${NC}"
    echo -e "Current version: $CURRENT_VERSION"
    echo -e "Required version: 1.19+"

    # Compare versions
    if [ "$(printf '%s\n' "1.19" "$CURRENT_VERSION" | sort -V | head -n1)" = "1.19" ]; then
        echo -e "${GREEN}✓ Go version meets requirements${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠️  Go version is below requirements${NC}"
    fi
fi

# Detect OS and architecture
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="darwin"
    if [[ $(uname -m) == 'arm64' ]]; then
        ARCH="arm64"
    else
        ARCH="amd64"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    ARCH="amd64"
else
    echo -e "${RED}Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

echo -e "\n📥 Installing Go ${GO_VERSION} for ${OS}/${ARCH}..."

# Download and install Go
GO_TAR="go${GO_VERSION}.${OS}-${ARCH}.tar.gz"
DOWNLOAD_URL="https://go.dev/dl/${GO_TAR}"

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo -e "Downloading from: $DOWNLOAD_URL"
curl -LO "$DOWNLOAD_URL"

# Remove old installation if exists
if [ -d /usr/local/go ]; then
    echo -e "\n${YELLOW}Removing old Go installation...${NC}"
    sudo rm -rf /usr/local/go
fi

# Extract and install
echo -e "\n📦 Installing Go..."
sudo tar -C /usr/local -xzf "$GO_TAR"

# Configure Go environment
echo -e "\n🔧 Configuring Go environment..."

# Detect shell
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    SHELL_RC="$HOME/.profile"
fi

# Add Go to PATH if not already there
if ! grep -q '/usr/local/go/bin' "$SHELL_RC"; then
    echo -e "\nAdding Go to PATH in $SHELL_RC"
    echo '' >> "$SHELL_RC"
    echo '# Go programming language' >> "$SHELL_RC"
    echo 'export PATH=$PATH:/usr/local/go/bin' >> "$SHELL_RC"
    echo 'export GOPATH=$HOME/go' >> "$SHELL_RC"
    echo 'export PATH=$PATH:$GOPATH/bin' >> "$SHELL_RC"
fi

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Source the shell config
export PATH=$PATH:/usr/local/go/bin
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Verify installation
if /usr/local/go/bin/go version &> /dev/null; then
    echo -e "\n${GREEN}✅ Go installed successfully!${NC}"
    /usr/local/go/bin/go version
    echo -e "\n${YELLOW}Please run: source $SHELL_RC${NC}"
    echo -e "${YELLOW}Or start a new terminal session${NC}"
else
    echo -e "\n${RED}❌ Go installation failed${NC}"
    exit 1
fi
