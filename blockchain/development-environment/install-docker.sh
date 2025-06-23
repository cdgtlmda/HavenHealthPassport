#!/bin/bash
# Install Docker and Docker Compose
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Docker Installation"
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

# Detect OS
OS=$(uname -s)
print_info "Detected OS: $OS"

# Check if Docker is already installed
if command_exists docker; then
    print_info "Docker is already installed: $(docker --version)"
    read -p "Do you want to continue with the installation? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping Docker installation"
        exit 0
    fi
fi

# Install Docker based on OS
if [[ "$OS" == "Darwin" ]]; then
    # macOS - Install Docker Desktop
    print_info "Installing Docker Desktop for Mac..."

    if command_exists brew; then
        brew install --cask docker
        print_status "Docker Desktop installed via Homebrew"
        print_info "Please start Docker Desktop from Applications"
    else
        print_error "Please install Docker Desktop manually from:"
        echo "  https://www.docker.com/products/docker-desktop"
        exit 1
    fi

elif [[ "$OS" == "Linux" ]]; then
    # Linux - Install Docker Engine
    print_info "Installing Docker Engine for Linux..."

    # Remove old versions
    print_info "Removing old Docker versions..."
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Install prerequisites
    print_info "Installing prerequisites..."
    sudo apt-get update
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Add Docker's official GPG key
    print_info "Adding Docker GPG key..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    # Set up stable repository
    print_info "Setting up Docker repository..."
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine
    print_info "Installing Docker Engine..."
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Add current user to docker group
    print_info "Adding user to docker group..."
    sudo usermod -aG docker $USER

    print_status "Docker Engine installed successfully"

    # Start and enable Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    print_status "Docker service started and enabled"

else
    print_error "Unsupported OS: $OS"
    exit 1
fi

# Install Docker Compose standalone (for compatibility)
print_info "Installing Docker Compose..."

# Docker Compose is included with Docker Desktop on Mac
if [[ "$OS" == "Linux" ]]; then
    # Download Docker Compose
    COMPOSE_VERSION="v2.23.0"
    sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    # Create symbolic link
    sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
fi

# Verify installations
print_info "Verifying installations..."

if command_exists docker; then
    print_status "Docker installed: $(docker --version)"
else
    print_error "Docker installation failed"
    exit 1
fi

if command_exists docker-compose; then
    print_status "Docker Compose installed: $(docker-compose --version)"
else
    print_error "Docker Compose installation failed"
    exit 1
fi

# Test Docker installation
print_info "Testing Docker installation..."
if [[ "$OS" == "Linux" ]]; then
    # Need to use sudo for first run or logout/login for group changes
    sudo docker run --rm hello-world >/dev/null 2>&1 && print_status "Docker test successful" || print_error "Docker test failed"
else
    # On macOS, check if Docker is running
    if docker info >/dev/null 2>&1; then
        docker run --rm hello-world >/dev/null 2>&1 && print_status "Docker test successful" || print_error "Docker test failed"
    else
        print_info "Please ensure Docker Desktop is running"
    fi
fi

echo ""
print_status "Docker and Docker Compose installation complete!"
echo ""

if [[ "$OS" == "Linux" ]]; then
    print_info "IMPORTANT: Log out and log back in for docker group changes to take effect"
    print_info "Or run: newgrp docker"
fi

echo "Next step: Run ./install-go.sh to install Go programming language"

# Make script executable
chmod +x install-go.sh 2>/dev/null || true
