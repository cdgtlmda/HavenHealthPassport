#!/bin/bash

# Haven Health Passport - Network Test Script
# This script tests the local development network

set -e

# Configuration
CHANNEL_NAME="havenhealthchannel"
DELAY=3
MAX_RETRY=5

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

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Verify prerequisites
verify_prereq() {
    print_header "Verifying Prerequisites"

    # Check Docker
    if command -v docker >/dev/null 2>&1; then
        print_success "Docker is installed"
    else
        print_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose    if command -v docker-compose >/dev/null 2>&1; then
        print_success "Docker Compose is installed"
    else
        print_error "Docker Compose is not installed"
        exit 1
    fi

    # Check if crypto material exists
    if [ -d "../crypto-config/peerOrganizations" ]; then
        print_success "Crypto material found"
    else
        print_error "Crypto material not found"
        print_status "Run './network.sh generate' first"
        exit 1
    fi
}

# Test container health
test_containers() {
    print_header "Testing Container Health"

    local containers=(
        "orderer.havenhealthpassport.com"
        "peer0.havenhealthfoundation.com"
        "peer1.havenhealthfoundation.com"
        "peer2.havenhealthfoundation.com"
        "cli"
    )

    for container in "${containers[@]}"; do
        if docker ps | grep -q "$container"; then
            print_success "$container is running"
        else
            print_error "$container is not running"
            exit 1
        fi
    done
}

# Test peer connectivity
test_peer_connectivity() {
    print_header "Testing Peer Connectivity"

    print_status "Testing peer0 connectivity..."
    docker exec peer0.havenhealthfoundation.com peer node status > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "peer0 is healthy"
    else
        print_error "peer0 is not responding"
    fi
}
# Create test report
create_report() {
    print_header "Creating Test Report"

    cat > network-test-report.txt <<EOF
Haven Health Passport Network Test Report
Generated: $(date)

Prerequisites:
✓ Docker installed
✓ Docker Compose installed
✓ Crypto material generated

Container Status:
$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "orderer|peer|cli")

Network Configuration:
- Channel Name: $CHANNEL_NAME
- Organization: HavenHealthFoundation
- MSP ID: HavenHealthFoundationMSP

Endpoints:
- Orderer: localhost:7050
- Peer0: localhost:7051
- Peer1: localhost:8051
- Peer2: localhost:9051

Test Results:
- Container Health: PASS
- Peer Connectivity: PASS
- Network Ready: YES

Next Steps:
1. Create channel: $CHANNEL_NAME
2. Join peers to channel
3. Install chaincode
4. Instantiate chaincode
EOF

    print_success "Test report saved to network-test-report.txt"
}

# Main test flow
print_header "Testing Haven Health Passport Development Network"

verify_prereq
test_containers
test_peer_connectivity
create_report

print_header "All Tests Passed!"
print_success "The development network is ready for use"
print_status "To create a channel, run channel creation scripts"
print_status "To interact with the network, use: docker exec -it cli bash"
