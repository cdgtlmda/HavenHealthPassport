#!/bin/bash

# Haven Health Passport - Install Docker and Docker Compose
# This script installs Docker and Docker Compose for Hyperledger Fabric

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Docker and Docker Compose Installation${NC}"
echo -e "${BLUE}================================================${NC}"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        OS="linux"
    fi
else
    echo -e "${RED}Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

echo -e "\n🖥️  Detected OS: ${OS}"

# Function to install Docker on macOS
install_docker_macos() {
    echo -e "\n${BLUE}Installing Docker Desktop for macOS...${NC}"

    if command -v brew &> /dev/null; then
        echo -e "Installing via Homebrew..."
        brew install --cask docker
        echo -e "${GREEN}✓ Docker Desktop installed${NC}"
        echo -e "${YELLOW}Please start Docker Desktop from Applications${NC}"
    else
        echo -e "${YELLOW}Please download Docker Desktop from:${NC}"
        echo -e "https://www.docker.com/products/docker-desktop"
    fi
}

# Function to install Docker on Ubuntu/Debian
install_docker_ubuntu() {
    echo -e "\n${BLUE}Installing Docker on Ubuntu/Debian...${NC}"

    # Update package index
    sudo apt-get update

    # Install prerequisites
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    # Set up stable repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Add user to docker group
    sudo usermod -aG docker $USER

    echo -e "${GREEN}✓ Docker installed successfully${NC}"
    echo -e "${YELLOW}Note: Log out and back in for group changes to take effect${NC}"
}

# Check if Docker is already installed
if command -v docker &> /dev/null; then
    echo -e "\n${GREEN}✓ Docker is already installed${NC}"
    docker --version
else
    echo -e "\n${YELLOW}Docker is not installed${NC}"

    case "$OS" in
        macos)
            install_docker_macos
            ;;
        ubuntu|debian)
            install_docker_ubuntu
            ;;
        *)
            echo -e "${RED}Automatic installation not supported for $OS${NC}"
            echo -e "Please install Docker manually"
            ;;
    esac
fi

# Verify installation
if command -v docker &> /dev/null; then
    echo -e "\n${GREEN}Docker installation verified!${NC}"
fi
