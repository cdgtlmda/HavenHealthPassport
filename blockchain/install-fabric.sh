#!/bin/bash
# Install Hyperledger Fabric binaries and docker images

# Set versions
export FABRIC_VERSION=2.5.0
export FABRIC_CA_VERSION=1.5.5

# Create bin directory
mkdir -p bin

# Download install script
curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh -o install-fabric.sh

# Make it executable
chmod +x install-fabric.sh

# Install binaries and docker images
./install-fabric.sh binary docker

echo "Hyperledger Fabric installation complete!"
echo "Add $(pwd)/bin to your PATH:"
echo "export PATH=\$PATH:$(pwd)/bin"