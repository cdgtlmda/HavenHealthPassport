# Haven Health Passport Documentation

## Project Overview
Haven Health Passport is a blockchain-verified, AI-powered health record system designed for displaced populations and refugees. The system provides secure, portable, and verifiable health records that can be accessed across borders while maintaining data sovereignty and privacy.

## Documentation Structure

### 📁 [Architecture](./architecture/)
- System architecture and design decisions
- Technical diagrams and data flow
- Integration patterns with AWS services
- Blockchain architecture for verification


### 📁 [API Documentation](./api/)
- REST API specifications
- GraphQL schema definitions
- Authentication and authorization
- Integration endpoints

### 📁 [Setup Guides](./setup/)
- Development environment setup
- AWS services configuration
- Blockchain network setup
- Local development instructions

### 📁 [Security](./security/)
- Security architecture
- HIPAA compliance measures
- Data encryption standards
- Access control policies

### 📁 [Compliance](./compliance/)
- Healthcare compliance documentation
- GDPR and data protection
- Cross-border data regulations
- Audit trails and logging

## Quick Links

- [System Architecture](./architecture/system-architecture.md)
- [Getting Started Guide](./setup/getting-started.md)
- [Security Overview](./security/security-overview.md)
- [API Documentation](./api/api-specification.md)

## Technology Stack

### Backend
- **Primary Language**: Python 3.11+
- **AI/ML Framework**: LangChain, LlamaIndex
- **Blockchain**: AWS Managed Blockchain (Hyperledger Fabric)
- **Voice Processing**: Amazon Transcribe Medical

### Infrastructure
- **IaC**: AWS CDK (TypeScript)
- **Container Orchestration**: Amazon ECS/EKS
- **Serverless**: AWS Lambda
- **API Gateway**: AWS AppSync (GraphQL)

### Frontend
- **Mobile**: React Native
- **Web Admin**: React + TypeScript
- **State Management**: Redux Toolkit
- **Offline Support**: AWS Amplify DataStore

### Data & Storage
- **Health Records**: Amazon HealthLake
- **Document Storage**: Amazon S3
- **Vector Database**: Amazon OpenSearch
- **Cache**: Amazon ElastiCache

## Project Goals

1. **Accessibility**: Provide healthcare access to 100M+ displaced people
2. **Security**: Blockchain-verified, tamper-proof health records
3. **Portability**: Cross-border data accessibility
4. **Privacy**: Patient-controlled data sovereignty
5. **Scalability**: Support for 50+ languages and dialects
