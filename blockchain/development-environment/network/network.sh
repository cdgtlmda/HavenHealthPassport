#!/bin/bash

# Haven Health Passport - Development Network Management Script
# This script manages the local development blockchain network

set -e

# Configuration
COMPOSE_FILE="docker-compose.yaml"
CHANNEL_NAME="havenhealthchannel"

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

# Function to display usage
usage() {
    echo "Usage: $0 {up|down|restart|generate|clean}"
    echo "  up       - Start the network"
    echo "  down     - Stop the network"
    echo "  restart  - Restart the network"
    echo "  generate - Generate crypto material and channel artifacts"
    echo "  clean    - Clean all generated files and docker volumes"
    exit 1
}

# Check if command is provided
if [ $# -eq 0 ]; then
    usagefi

# Parse command
COMMAND=$1

# Function to generate crypto material
generate_crypto() {
    print_header "Generating Crypto Material and Channel Artifacts"

    # Generate crypto material
    print_status "Generating crypto material..."
    cd ../crypto-config
    ./generate-crypto.sh
    cd - > /dev/null

    # Generate channel artifacts
    print_status "Generating channel artifacts..."
    cd ../channel-artifacts
    ./generate-artifacts.sh
    cd - > /dev/null

    print_status "Crypto material and channel artifacts generated successfully"
}

# Function to start the network
network_up() {
    print_header "Starting Haven Health Passport Development Network"

    # Check if crypto material exists
    if [ ! -d "../crypto-config/peerOrganizations" ] || [ ! -d "../crypto-config/ordererOrganizations" ]; then
        print_warning "Crypto material not found. Generating..."
        generate_crypto
    fi

    # Start docker containers
    print_status "Starting docker containers..."
    docker-compose -f $COMPOSE_FILE up -d

    # Wait for containers to be ready
    print_status "Waiting for containers to be ready..."
    sleep 5

    # Show running containers
    print_status "Running containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    print_header "Network Started Successfully"
    print_status "To interact with the network, use: docker exec -it cli bash"
}

# Function to stop the networknetwork_down() {
    print_header "Stopping Haven Health Passport Development Network"

    print_status "Stopping docker containers..."
    docker-compose -f $COMPOSE_FILE down

    print_status "Network stopped successfully"
}

# Function to restart the network
network_restart() {
    print_header "Restarting Haven Health Passport Development Network"

    network_down
    sleep 2
    network_up
}

# Function to clean everything
clean_all() {
    print_header "Cleaning Haven Health Passport Development Network"

    # Stop containers
    print_status "Stopping containers..."
    docker-compose -f $COMPOSE_FILE down -v

    # Remove crypto material
    print_status "Removing crypto material..."
    rm -rf ../crypto-config/peerOrganizations
    rm -rf ../crypto-config/ordererOrganizations
    rm -f ../crypto-config/*.txt

    # Remove channel artifacts
    print_status "Removing channel artifacts..."
    rm -rf ../channel-artifacts/artifacts
    rm -f ../channel-artifacts/*.txt

    # Remove docker volumes
    print_status "Removing docker volumes..."
    docker volume prune -f

    print_status "Cleanup complete"
}

# Execute command
case $COMMAND in
    up)
        network_up
        ;;
    down)
        network_down
        ;;
    restart)        network_restart
        ;;
    generate)
        generate_crypto
        ;;
    clean)
        clean_all
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        usage
        ;;
esac
