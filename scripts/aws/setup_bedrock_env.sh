#!/bin/bash
# Setup script for Haven Health Passport AI/ML Infrastructure

echo "============================================"
echo "Haven Health Passport - AI/ML Setup"
echo "============================================"
echo ""

# Check for required tools
echo "Checking required tools..."
echo ""

# Check for Python 3
if command -v python3 &> /dev/null; then
    echo "✅ Python 3 found: $(python3 --version)"
else
    echo "❌ Python 3 not found. Please install Python 3.8 or later"
fi

# Check for AWS CLI
if command -v aws &> /dev/null; then
    echo "✅ AWS CLI found: $(aws --version)"
else
    echo "❌ AWS CLI not found. Please install AWS CLI"
    echo "   Visit: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
fi

# Check for Terraform
if command -v terraform &> /dev/null; then
    echo "✅ Terraform found: $(terraform version | head -n 1)"
else
    echo "❌ Terraform not found. Please install Terraform"
    echo "   Visit: https://www.terraform.io/downloads"
fi

# Check for boto3
if python3 -c "import boto3" &> /dev/null; then
    echo "✅ boto3 Python library found"
else
    echo "❌ boto3 not found. Installing..."
    echo "   Run: pip3 install boto3"
fi

echo ""
echo "============================================"
echo "AWS Configuration Status"
echo "============================================"
echo ""

# Check AWS credentials
if [ -f ~/.aws/credentials ]; then
    echo "✅ AWS credentials file found"
    # Check if credentials are placeholders
    if grep -q "YOUR_ACCESS_KEY" ~/.aws/credentials; then
        echo "⚠️  WARNING: AWS credentials appear to be placeholders"
        echo "   Please update ~/.aws/credentials with valid credentials"
    fi
else
    echo "❌ AWS credentials file not found"
    echo "   Run: aws configure"
fi

echo ""
echo "============================================"
echo "Next Steps for Bedrock Setup"
echo "============================================"
echo ""
echo "1. Configure AWS Credentials:"
echo "   aws configure"
echo "   - Enter your AWS Access Key ID"
echo "   - Enter your AWS Secret Access Key"
echo "   - Set default region to: us-east-1"
echo "   - Set output format to: json"
echo ""
echo "2. Install Required Tools (if missing):"
echo "   - Terraform: brew install terraform (macOS) or download from terraform.io"
echo "   - boto3: pip3 install boto3"
echo ""
echo "3. Enable Bedrock in AWS Console:"
echo "   - Sign in to AWS Console"
echo "   - Search for 'Amazon Bedrock'"
echo "   - Click 'Get started' if first time"
echo "   - Navigate to 'Model access'"
echo "   - Request access to required models"
echo ""
echo "4. Initialize Terraform:"
echo "   cd infrastructure/terraform"
echo "   terraform init"
echo ""
echo "5. Deploy Infrastructure:"
echo "   terraform plan -var-file=environments/development.tfvars"
echo "   terraform apply -var-file=environments/development.tfvars"
echo ""

# Create a requirements file for Python dependencies
echo "Creating Python requirements file..."
cat > /tmp/bedrock-requirements.txt << EOF
boto3>=1.28.0
botocore>=1.31.0
EOF

echo "✅ Requirements file created at: /tmp/bedrock-requirements.txt"
echo "   Install with: pip3 install -r /tmp/bedrock-requirements.txt"
echo ""
