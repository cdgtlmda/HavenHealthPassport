# Haven Health Passport - Getting Started Guide

## Quick Start

This guide will help you set up the Haven Health Passport development environment and run your first local instance.

## Prerequisites

### Required Software

- Python 3.11 or higher
- Node.js 18+ and npm
- Docker Desktop
- AWS CLI v2
- Git

### AWS Account Requirements

- AWS account with appropriate permissions
- Access to:
  - Amazon Bedrock
  - Amazon HealthLake
  - AWS Managed Blockchain
  - Amazon Cognito
  - Amazon S3

## Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/haven-health-passport.git
cd haven-health-passport
```

## Step 2: Environment Setup

### Create Python Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies
npm install

# AWS CDK
npm install -g aws-cdk
```

## Step 3: AWS Configuration

### Configure AWS CLI

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output format: json
```

### Create Environment File

Create a `.env.local` file in the project root:

```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=default

# Application Settings
APP_ENV=development
API_PORT=8000
FRONTEND_PORT=3000

# Service Endpoints
BEDROCK_ENDPOINT=https://bedrock-runtime.us-east-1.amazonaws.com
HEALTHLAKE_DATASTORE_ID=your-datastore-id
BLOCKCHAIN_NETWORK_ID=your-network-id

# Security
JWT_SECRET=your-development-secret
ENCRYPTION_KEY=your-encryption-key
```

## Step 4: Local Services Setup

### Start Docker Services

```bash
# Create Docker network
docker network create haven-health-network

# Start LocalStack for AWS services (includes DynamoDB)
docker run -d \
  --name localstack \
  --network haven-health-network \
  -p 4566:4566 \
  -e SERVICES=s3,dynamodb,kms,secretsmanager \
  localstack/localstack

# Start local S3 (MinIO)
docker run -d \
  --name minio \
  --network haven-health-network \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Start Redis for caching
docker run -d \
  --name redis \
  --network haven-health-network \
  -p 6379:6379 \
  redis:alpine
```

## Step 5: Initialize Local Database

Run the following setup commands:
- Database migrations
- Test data seeding
- Blockchain network initialization

## Step 6: Start Development Servers

### Backend API Server

```bash
# Terminal 1
cd backend
uvicorn main:app --reload --port 8000
```

### Frontend Development Server

```bash
# Terminal 2
cd frontend/web
npm run dev
```

### Mobile App (React Native)

```bash
# Terminal 3
cd frontend/mobile
npm run ios  # or npm run android
```

## Step 7: Verify Installation

### Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "1.0.0"}
```

### Run Tests

```bash
# Backend tests
pytest tests/

# Frontend tests
npm test

# E2E tests
npm run test:e2e
```

## Common Issues and Solutions

### Issue: AWS credentials not found

**Solution**: Ensure AWS CLI is configured correctly and the profile exists

### Issue: Docker containers not starting

**Solution**: Check Docker Desktop is running and ports are not in use

### Issue: Python dependencies fail to install

**Solution**: Ensure you're using Python 3.11+ and virtual environment is activated

## Next Steps

1. Review the [Architecture Documentation](../architecture/system-architecture.md)
2. Explore the [API Documentation](../api/api-specification.md)
3. Check the [Development Workflow](./development-workflow.md)
4. Join our Slack channel for support

## Useful Commands

```bash
# View logs
docker logs -f [container-name]

# Reset local database
python scripts/reset_db.py

# Generate API documentation
python scripts/generate_api_docs.py

# Run linting
make lint

# Format code
make format
```
