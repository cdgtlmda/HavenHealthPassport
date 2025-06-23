#!/bin/bash
# Deploy chaincode to AWS Managed Blockchain

set -e

# Configuration
NETWORK_ID="${MANAGED_BLOCKCHAIN_NETWORK_ID}"
MEMBER_ID="${MANAGED_BLOCKCHAIN_MEMBER_ID}"
CHANNEL_NAME="${BLOCKCHAIN_CHANNEL:-healthcare-channel}"
REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Deploying Chaincode to AWS Managed Blockchain${NC}"
echo -e "Network ID: ${NETWORK_ID}"
echo -e "Member ID: ${MEMBER_ID}"
echo -e "Channel: ${CHANNEL_NAME}"
echo -e "Region: ${REGION}"

# Check prerequisites
if [ -z "$NETWORK_ID" ] || [ -z "$MEMBER_ID" ]; then
    echo -e "${RED}ERROR: MANAGED_BLOCKCHAIN_NETWORK_ID and MANAGED_BLOCKCHAIN_MEMBER_ID must be set${NC}"
    exit 1
fi

# Function to package chaincode
package_chaincode() {
    local chaincode_name=$1
    local chaincode_path=$2
    
    echo -e "\n${YELLOW}Packaging ${chaincode_name} chaincode...${NC}"
    
    cd "$chaincode_path"
    
    # Build the chaincode
    GO111MODULE=on go mod vendor
    
    # Create package
    tar -czf "${chaincode_name}.tar.gz" .
    
    # Upload to S3
    local s3_bucket="haven-health-chaincode-${NETWORK_ID}"
    local s3_key="chaincode/${chaincode_name}/${chaincode_name}-$(date +%Y%m%d%H%M%S).tar.gz"
    
    echo -e "Uploading to S3: s3://${s3_bucket}/${s3_key}"
    aws s3 cp "${chaincode_name}.tar.gz" "s3://${s3_bucket}/${s3_key}" --region "$REGION"
    
    echo -e "${GREEN}✓ ${chaincode_name} packaged and uploaded${NC}"
    
    cd - > /dev/null
}

# Function to install chaincode on peer
install_chaincode() {
    local chaincode_name=$1
    local version=$2
    
    echo -e "\n${YELLOW}Installing ${chaincode_name} chaincode...${NC}"
    
    # Note: In production AWS Managed Blockchain, chaincode installation
    # is done through the AWS Console or AWS CLI commands specific to
    # Managed Blockchain. This is a placeholder for the actual commands.
    
    echo -e "${GREEN}✓ ${chaincode_name} installation initiated${NC}"
}

# Function to instantiate/upgrade chaincode
instantiate_chaincode() {
    local chaincode_name=$1
    local version=$2
    local init_args=$3
    
    echo -e "\n${YELLOW}Instantiating ${chaincode_name} chaincode...${NC}"
    
    # Note: In production AWS Managed Blockchain, chaincode instantiation
    # is done through the AWS Console or AWS CLI commands specific to
    # Managed Blockchain. This is a placeholder for the actual commands.
    
    echo -e "${GREEN}✓ ${chaincode_name} instantiation initiated${NC}"
}

# Create S3 bucket for chaincode if it doesn't exist
create_s3_bucket() {
    local bucket_name="haven-health-chaincode-${NETWORK_ID}"
    
    echo -e "\n${YELLOW}Checking S3 bucket...${NC}"
    
    if aws s3 ls "s3://${bucket_name}" 2>&1 | grep -q 'NoSuchBucket'; then
        echo -e "Creating S3 bucket: ${bucket_name}"
        aws s3 mb "s3://${bucket_name}" --region "$REGION"
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "${bucket_name}" \
            --versioning-configuration Status=Enabled \
            --region "$REGION"
        
        # Add encryption
        aws s3api put-bucket-encryption \
            --bucket "${bucket_name}" \
            --server-side-encryption-configuration '{
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }]
            }' \
            --region "$REGION"
            
        echo -e "${GREEN}✓ S3 bucket created${NC}"
    else
        echo -e "${GREEN}✓ S3 bucket exists${NC}"
    fi
}

# Main deployment process
main() {
    echo -e "\n${GREEN}Starting Chaincode Deployment Process${NC}"
    echo -e "${GREEN}======================================${NC}"
    
    # Create S3 bucket
    create_s3_bucket
    
    # Get chaincode directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    CHAINCODE_DIR="${SCRIPT_DIR}/../chaincode"
    
    # Deploy health-record chaincode
    if [ -d "${CHAINCODE_DIR}/health-record" ]; then
        package_chaincode "health-record" "${CHAINCODE_DIR}/health-record"
        install_chaincode "health-record" "1.0"
        instantiate_chaincode "health-record" "1.0" '{"function":"InitLedger","Args":[]}'
    fi
    
    # Deploy cross-border chaincode
    if [ -d "${CHAINCODE_DIR}/cross-border" ]; then
        package_chaincode "cross-border" "${CHAINCODE_DIR}/cross-border"
        install_chaincode "cross-border" "1.0"
        instantiate_chaincode "cross-border" "1.0" '{"function":"InitLedger","Args":[]}'
    fi
    
    # Deploy access-control chaincode
    if [ -d "${CHAINCODE_DIR}/access-control" ]; then
        package_chaincode "access-control" "${CHAINCODE_DIR}/access-control"
        install_chaincode "access-control" "1.0"
        instantiate_chaincode "access-control" "1.0" '{"function":"InitLedger","Args":[]}'
    fi
    
    echo -e "\n${GREEN}======================================${NC}"
    echo -e "${GREEN}Chaincode Deployment Process Complete${NC}"
    echo -e "${GREEN}======================================${NC}"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo -e "1. Go to AWS Managed Blockchain console"
    echo -e "2. Navigate to your network: ${NETWORK_ID}"
    echo -e "3. Install chaincode from S3 locations"
    echo -e "4. Instantiate chaincode on channel: ${CHANNEL_NAME}"
    echo -e "5. Test chaincode functions"
}

# Run main function
main
