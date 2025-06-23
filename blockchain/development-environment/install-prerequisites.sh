#!/bin/bash
# Install Hyperledger Fabric Prerequisites
# Haven Health Passport - Development Environment Setup

set -e  # Exit on error

echo "================================================"
echo "Haven Health Passport - Hyperledger Fabric Setup"
echo "Installing Prerequisites"
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

# Check prerequisites based on OS
if [[ "$OS" == "Darwin" ]]; then
    # macOS
    print_info "Setting up for macOS..."

    # Check for Homebrew
    if ! command_exists brew; then
        print_error "Homebrew not found. Please install Homebrew first:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    print_status "Homebrew is installed"

elif [[ "$OS" == "Linux" ]]; then
    # Linux
    print_info "Setting up for Linux..."

    # Update package manager
    if command_exists apt-get; then
        print_info "Updating apt packages..."
        sudo apt-get update -y
    elif command_exists yum; then
        print_info "Updating yum packages..."
        sudo yum update -y
    fi
else
    print_error "Unsupported OS: $OS"
    exit 1
fi

# Install cURL
print_info "Checking cURL..."
if ! command_exists curl; then
    if [[ "$OS" == "Darwin" ]]; then
        brew install curl
    else
        sudo apt-get install -y curl || sudo yum install -y curl
    fi
fi
print_status "cURL is installed"

# Install Git
print_info "Checking Git..."
if ! command_exists git; then
    if [[ "$OS" == "Darwin" ]]; then
        brew install git
    else
        sudo apt-get install -y git || sudo yum install -y git
    fi
fi
print_status "Git is installed ($(git --version))"

# Install wget
print_info "Checking wget..."
if ! command_exists wget; then
    if [[ "$OS" == "Darwin" ]]; then
        brew install wget
    else
        sudo apt-get install -y wget || sudo yum install -y wget
    fi
fi
print_status "wget is installed"

# Install jq (JSON processor)
print_info "Checking jq..."
if ! command_exists jq; then
    if [[ "$OS" == "Darwin" ]]; then
        brew install jq
    else
        sudo apt-get install -y jq || sudo yum install -y jq
    fi
fi
print_status "jq is installed"

# Check for required build tools
print_info "Checking build tools..."
if [[ "$OS" == "Linux" ]]; then
    sudo apt-get install -y build-essential || sudo yum groupinstall -y "Development Tools"
fi
print_status "Build tools are available"

echo ""
print_status "All Hyperledger Fabric prerequisites are installed!"
echo ""
echo "Next steps:"
echo "1. Run ./install-docker.sh to install Docker"
echo "2. Run ./install-go.sh to install Go"
echo "3. Run ./install-nodejs.sh to install Node.js"
echo "4. Run ./install-fabric.sh to install Fabric binaries"
