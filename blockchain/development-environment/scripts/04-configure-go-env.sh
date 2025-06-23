#!/bin/bash

# Haven Health Passport - Configure Go Environment Variables
# This script configures Go environment for Hyperledger Fabric development

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Go Environment Configuration${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo -e "${RED}❌ Go is not installed${NC}"
    echo -e "${YELLOW}Please run 03-install-go.sh first${NC}"
    exit 1
fi

echo -e "\n${GREEN}✓ Go is installed${NC}"
go version

# Detect shell configuration file
if [ -n "${ZSH_VERSION:-}" ]; then
    SHELL_RC="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [ -n "${BASH_VERSION:-}" ]; then
    SHELL_RC="$HOME/.bashrc"
    SHELL_NAME="bash"
else
    SHELL_RC="$HOME/.profile"
    SHELL_NAME="sh"
fi

echo -e "\n📋 Configuring environment for $SHELL_NAME"

# Create Go workspace directory
GOPATH="${GOPATH:-$HOME/go}"
echo -e "\n📁 Setting up Go workspace at: $GOPATH"

mkdir -p "$GOPATH"/{src,pkg,bin}
mkdir -p "$GOPATH/src/github.com"

# Function to add environment variable
add_env_var() {
    local var_name="$1"
    local var_value="$2"

    if ! grep -q "export $var_name=" "$SHELL_RC"; then
        echo "export $var_name=$var_value" >> "$SHELL_RC"
        echo -e "${GREEN}✓ Added $var_name${NC}"
    else
        echo -e "${YELLOW}✓ $var_name already configured${NC}"
    fi
}

# Configure environment variables
echo -e "\n🔧 Configuring environment variables..."

# Add header comment if not present
if ! grep -q "# Go environment variables" "$SHELL_RC"; then
    echo -e "\n# Go environment variables" >> "$SHELL_RC"
fi

# Set GOPATH
add_env_var "GOPATH" "\$HOME/go"

# Add Go bin to PATH
if ! grep -q 'PATH.*go/bin' "$SHELL_RC"; then
    echo 'export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin' >> "$SHELL_RC"
    echo -e "${GREEN}✓ Added Go binaries to PATH${NC}"
fi

# Set Go module proxy for faster downloads
add_env_var "GOPROXY" "https://proxy.golang.org,direct"

# Set Go private repositories (for future use)
add_env_var "GOPRIVATE" "github.com/HavenHealthPassport/*"

# Create Go environment test file
cat > "$GOPATH/test-env.go" <<'EOF'
package main

import (
    "fmt"
    "os"
    "runtime"
)

func main() {
    fmt.Println("Go Environment Test")
    fmt.Println("==================")
    fmt.Printf("Go Version: %s\n", runtime.Version())
    fmt.Printf("GOPATH: %s\n", os.Getenv("GOPATH"))
    fmt.Printf("GOROOT: %s\n", runtime.GOROOT())
    fmt.Printf("OS/Arch: %s/%s\n", runtime.GOOS, runtime.GOARCH)
}
EOF

echo -e "\n🧪 Testing Go environment..."
cd "$GOPATH"
go run test-env.go

# Create Hyperledger Fabric workspace
echo -e "\n📁 Creating Hyperledger Fabric workspace..."
mkdir -p "$GOPATH/src/github.com/hyperledger"

echo -e "\n${GREEN}✅ Go environment configured successfully!${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "1. Run: ${GREEN}source $SHELL_RC${NC}"
echo -e "2. Verify with: ${GREEN}go env${NC}"
echo -e "3. Continue with Node.js installation"

# Create summary file
cat > "$HOME/.go-env-summary.txt" <<EOF
Go Environment Configuration Summary
===================================
Date: $(date)
GOPATH: $GOPATH
Go Version: $(go version | cut -d' ' -f3)
Shell: $SHELL_NAME
Config File: $SHELL_RC

Workspace Structure:
$GOPATH/
├── src/     # Source code
├── pkg/     # Package objects
└── bin/     # Executable commands

Hyperledger workspace:
$GOPATH/src/github.com/hyperledger/
EOF

echo -e "\n📄 Configuration summary saved to: ~/.go-env-summary.txt"
