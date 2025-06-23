# Haven Health Passport

⚠️ **SECURITY NOTICE**: This repository has been sanitized for public use. All credentials, private keys, and sensitive information have been removed. Please see [SECURITY_SETUP.md](SECURITY_SETUP.md) for instructions on configuring required credentials.

## ⚠️ Notice

This project, Haven Health Passport, was developed by Cadence Apeiron (cdgtlmda) and submitted to the AWS Breaking Barriers Hackathon 2025. Public availability is required for judging purposes. Unauthorized resubmission, redistribution, or misrepresentation as original work by third parties is prohibited and may result in legal action.

## 🎯 Project Overview

Haven Health Passport provides secure, portable, and verifiable health records that can be accessed across borders while maintaining data sovereignty and privacy. The system addresses the critical healthcare needs of over 100 million displaced people worldwide.

### Key Features

- 🔐 **Blockchain Verification**: Tamper-proof health records using AWS Managed Blockchain
- 🌍 **Multi-language Support**: 50+ languages with cultural adaptation
- 🤖 **AI-Powered Translation**: Context-aware medical translation using LangChain and Amazon Bedrock
- 📱 **Offline-First Mobile**: Works without internet connectivity
- 🏥 **Cross-Border Access**: Secure verification at border checkpoints
- 🔒 **Privacy-First Design**: Patient-controlled data sovereignty

## 📊 Project Status

**Current Status**: 🔄 **ACTIVE DEVELOPMENT** - Core Features Implemented

> **Note:** The current UI implementation is a temporary demonstration version created specifically for the AWS Breaking Barriers Hackathon submission. The complete solution continues to be developed as a dual-platform architecture with both a comprehensive web portal and mobile application, as outlined in the architecture section below.

- Comprehensive testing in staging environment
- Medical professional review and validation
- Security audit and penetration testing

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop
- AWS Account with appropriate permissions

### Installation

**📋 For complete setup instructions, see [REQUIREMENTS.md](REQUIREMENTS.md)**

**Quick Start:**

```bash
# Clone the repository
git clone https://github.com/cdgtlmda/HavenHealthPassport.git
cd HavenHealthPassport

# Python setup
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Node.js setup for demo UI
npm install

# Start demo UI development server (Vite)
npm run dev  # Demo UI runs on http://localhost:5173
```

**For full functionality with AWS services:**

```bash
# Configure AWS credentials (see REQUIREMENTS.md)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1

# Start backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## 📚 Documentation

- [Getting Started Guide](docs/setup/getting-started.md)
- [System Architecture](docs/architecture/system-architecture.md)
- [API Documentation](docs/api/api-specification.md)
- [Security Overview](docs/security/security-overview.md)
- [Compliance Documentation](docs/compliance/healthcare-compliance.md)

## 🏗️ Architecture

### Technology Stack

- **Backend**: Python 3.11+, FastAPI, LangChain, LlamaIndex
- **Frontend**: React Native (Mobile), React (Web)
- **AI/ML**: Amazon Bedrock, Amazon Transcribe Medical, SageMaker
- **Blockchain**: AWS Managed Blockchain (Hyperledger Fabric)
- **Database**: Amazon HealthLake, DynamoDB, OpenSearch
- **Infrastructure**: AWS CDK, Docker, Kubernetes

### High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Mobile App    │     │   Web Portal    │     │  Provider Portal│
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                        │
         └───────────────────────┴────────────────────────┘
                                │
                        ┌───────┴────────┐
                        │   API Gateway  │
                        └───────┬────────┘
                                │
                ┌───────────────┴───────────────┐
                │       Application Layer       │
                ├───────────────┬───────────────┤
                │  AI Services  │  Blockchain   │
                └───────────────┴───────────────┘
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test suites
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with coverage
pytest --cov=src --cov-report=html
```

## 🚢 Deployment

```bash
# Deploy to development
make deploy-dev

# Deploy to production
make deploy-prod
```

## 🤝 Contributing

Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting PRs.

## 📄 License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- AWS Breaking Barriers Challenge
- UNHCR for refugee healthcare insights
- Healthcare professionals providing domain expertise
