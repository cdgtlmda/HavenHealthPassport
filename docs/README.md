# Haven Health Passport Documentation

## Overview

Haven Health Passport is a blockchain-verified, AI-powered health record system designed for displaced populations and refugees. The system provides secure, portable, and verifiable health records that can be accessed across borders while maintaining data sovereignty and privacy.

## Documentation Structure

### 📁 [01-getting-started](./01-getting-started/)
Getting started guides, system requirements, and quick start tutorials

### 📁 [02-architecture](./02-architecture/)
System architecture, design patterns, and technical diagrams

### 📁 [03-api](./03-api/)
API documentation, OpenAPI specifications, and SDK guides

### 📁 [04-deployment](./04-deployment/)
Deployment guides, AWS configuration, and infrastructure setup

### 📁 [05-operations](./05-operations/)
Operational guides, troubleshooting, and maintenance procedures

### 📁 [06-development](./06-development/)
Development environment setup, testing, and contribution guidelines

### 📁 [07-reference](./07-reference/)
Healthcare standards, security implementation, and technical reference

## Quick Start

1. **New to Haven Health?** Start with [Getting Started](./01-getting-started/README.md)
2. **Setting up development?** See [Development Environment](./06-development/development-environment.md)
3. **Looking for API docs?** Check [API Documentation](./03-api/api-specification.md)
4. **Deploying the system?** Read [Deployment Guide](./04-deployment/aws-configuration.md)

## Key Features

- **Blockchain Verification**: Tamper-proof health records using Hyperledger Fabric
- **Multi-language Support**: 50+ languages with medical accuracy
- **Offline-First**: Full functionality without internet connectivity
- **FHIR Compliant**: HL7 FHIR R4 standard for healthcare interoperability
- **AI-Powered**: Medical translation, OCR, and entity extraction
- **Security**: End-to-end encryption, HIPAA compliant

## Technology Stack

- **Backend**: Python 3.11+, FastAPI
- **Frontend**: React Native (mobile), React (web)
- **Blockchain**: AWS Managed Blockchain (Hyperledger Fabric)
- **Healthcare**: Amazon HealthLake (FHIR), HL7
- **AI/ML**: Amazon Bedrock, LangChain, LlamaIndex
- **Infrastructure**: AWS CDK, ECS, Lambda