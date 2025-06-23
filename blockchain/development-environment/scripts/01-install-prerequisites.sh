#!/bin/bash

# Haven Health Passport - Install Hyperledger Fabric Prerequisites
# This script installs all prerequisites for Hyperledger Fabric development

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_DIR="${SCRIPT_DIR}/../development-environment"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Hyperledger Fabric Prerequisites Installation${NC}"
echo -e "${BLUE}================================================${NC}"

# Create development directory
mkdir -p "${DEV_DIR}"

# Function to check command existence
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓ $1 is installed${NC}"
        return 0
    else
        echo -e "${RED}✗ $1 is not installed${NC}"
        return 1
    fi
}

# Function to check version
check_version() {
    local cmd="$1"
    local version_cmd="$2"
    local min_version="$3"

    if check_command "$cmd"; then
        local version=$(eval "$version_cmd")
        echo -e "  Version: $version (minimum: $min_version)"
    fi
}

echo -e "\n📋 Checking system prerequisites..."
# Check OS
echo -e "\n🖥️  Operating System:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${GREEN}✓ macOS detected${NC}"
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "${GREEN}✓ Linux detected${NC}"
    OS="linux"
else
    echo -e "${RED}✗ Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

# Check Docker
echo -e "\n🐳 Docker:"
check_version "docker" "docker --version | cut -d' ' -f3 | cut -d',' -f1" "20.10.0"

# Check Docker Compose
echo -e "\n🐳 Docker Compose:"
check_version "docker-compose" "docker-compose --version | cut -d' ' -f4 | cut -d',' -f1" "1.29.0"

# Check Go
echo -e "\n🔷 Go Programming Language:"
check_version "go" "go version | cut -d' ' -f3 | sed 's/go//'" "1.19.0"

# Check Node.js
echo -e "\n📦 Node.js:"
check_version "node" "node --version | sed 's/v//'" "16.0.0"

# Check npm
echo -e "\n📦 npm:"
check_version "npm" "npm --version" "8.0.0"

# Check Python
echo -e "\n🐍 Python:"
check_version "python3" "python3 --version | cut -d' ' -f2" "3.8.0"

# Check Git
echo -e "\n📚 Git:"
check_version "git" "git --version | cut -d' ' -f3" "2.0.0"

# Check curl
echo -e "\n🌐 curl:"
check_command "curl"

# Check jq
echo -e "\n🔧 jq:"
check_command "jq"
# Create installation summary
cat > "${DEV_DIR}/prerequisites-check.md" <<EOF
# Hyperledger Fabric Prerequisites Check

Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

## Required Software

| Software | Required Version | Status |
|----------|-----------------|--------|
| Docker | 20.10+ | $(check_command docker && echo "✓ Installed" || echo "✗ Not installed") |
| Docker Compose | 1.29+ | $(check_command docker-compose && echo "✓ Installed" || echo "✗ Not installed") |
| Go | 1.19+ | $(check_command go && echo "✓ Installed" || echo "✗ Not installed") |
| Node.js | 16+ | $(check_command node && echo "✓ Installed" || echo "✗ Not installed") |
| Python | 3.8+ | $(check_command python3 && echo "✓ Installed" || echo "✗ Not installed") |
| Git | 2.0+ | $(check_command git && echo "✓ Installed" || echo "✗ Not installed") |

## Installation Instructions

### macOS
\`\`\`bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install prerequisites
brew install --cask docker
brew install go node python@3.11 git jq
\`\`\`

### Ubuntu/Debian
\`\`\`bash
# Update package list
sudo apt-get update

# Install prerequisites
sudo apt-get install -y docker.io docker-compose golang nodejs npm python3 python3-pip git curl jq

# Add user to docker group
sudo usermod -aG docker $USER
\`\`\`

### CentOS/RHEL
\`\`\`bash
# Install prerequisites
sudo yum install -y docker golang nodejs npm python3 python3-pip git curl jq

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
\`\`\`
EOF
echo -e "\n${GREEN}Prerequisites check complete!${NC}"
echo -e "Report saved to: ${DEV_DIR}/prerequisites-check.md"

# Check if all prerequisites are met
ALL_GOOD=true
for cmd in docker docker-compose go node npm python3 git curl jq; do
    if ! check_command "$cmd" &> /dev/null; then
        ALL_GOOD=false
        break
    fi
done

if [ "$ALL_GOOD" = true ]; then
    echo -e "\n${GREEN}✅ All prerequisites are installed!${NC}"
else
    echo -e "\n${YELLOW}⚠️  Some prerequisites are missing.${NC}"
    echo -e "${YELLOW}Please install missing software before proceeding.${NC}"
    echo -e "${YELLOW}See ${DEV_DIR}/prerequisites-check.md for installation instructions.${NC}"
fi
