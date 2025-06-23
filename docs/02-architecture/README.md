# Haven Health Passport Architecture Documentation

This directory contains architectural documentation for the Haven Health Passport project, a blockchain-verified, AI-powered health record management system designed for displaced populations and refugees, with heavy emphasis on AWS GenAI services for intelligent processing.

## Overview

Haven Health Passport leverages AWS's comprehensive GenAI service suite including Amazon Bedrock, Amazon Comprehend Medical, Amazon Transcribe Medical, and Amazon Translate to provide culturally-aware, multilingual healthcare record management. The architecture consists of multiple services working together to provide secure, portable, and verifiable health records that can be accessed across borders with AI-powered translation and understanding.

## Directory Contents

- [system-architecture.md](./system-architecture.md) - Detailed description of the system architecture with AWS GenAI integration
- [data-flow.md](./data-flow.md) - Documentation of data flows through AI/ML pipelines
- [deployment.md](./deployment.md) - Infrastructure and deployment architecture with GenAI service configurations
- [development-timeline.md](./development-timeline.md) - Project timeline and milestones
- [diagrams/](./diagrams/) - Enhanced Mermaid diagram files with AWS service annotations

## Architecture Diagrams

The following architecture diagrams are available with detailed AWS service integration:

1. **High-Level Architecture** - Shows the overall system architecture including:
   - AWS AppSync for GraphQL API management
   - Amazon Bedrock for foundation model access
   - Amazon Comprehend Medical for medical entity extraction
   - Amazon Transcribe Medical for voice-to-text processing
   - Amazon Translate for multilingual support
   - Amazon SageMaker for custom model training
   - Amazon HealthLake for FHIR-compliant storage

2. **Core Components** - Details the internal components with AWS service mappings:
   - Health Records: HealthLake, Comprehend Medical
   - Authentication: Cognito with custom authorizers
   - Translation: Bedrock Claude 3 for medical accuracy
   - Voice Processing: Transcribe Medical with custom vocabularies
   - Verification: Managed Blockchain integration

3. **Data Flow** - Illustrates AI-powered data processing:
   - LangChain orchestration with Bedrock
   - RAG pipeline using Amazon OpenSearch Serverless
   - Medical knowledge graphs with Neptune
   - Real-time inference with SageMaker endpoints

4. **Patient Verification Sequence** - AWS service interactions:
   - Step Functions for orchestration
   - Lambda for serverless processing
   - Textract for document extraction
   - Rekognition for identity verification

5. **Blockchain Integration** - AWS Managed Blockchain architecture:
   - Hyperledger Fabric network setup
   - Cross-region peer nodes
   - Smart contract deployment pipeline
   - CloudHSM for key management

6. **Deployment Architecture** - Multi-region AWS deployment:
   - ECS Fargate for containerized services
   - API Gateway with WAF protection
   - CloudFront for global content delivery
   - Route 53 for traffic management

## Key AWS GenAI Components

### Amazon Bedrock Integration
- **Claude 3 Opus**: Primary model for medical translation and cultural adaptation
- **Titan Embeddings**: Semantic search for medical records
- **Stable Diffusion**: Visual communication for low-literacy users
- **Guardrails**: Medical accuracy and safety checks

### Amazon Comprehend Medical
- Automated medical entity extraction from unstructured text
- ICD-10, RxNorm, and SNOMED CT coding
- PHI detection and redaction
- Medical relationship extraction

### Amazon Transcribe Medical
- Multi-language medical speech recognition
- Custom medical vocabularies for 50+ languages
- Real-time streaming transcription
- Speaker diarization for consultations

### Amazon Translate
- Medical terminology preservation
- Custom terminology databases
- Batch translation for document processing
- Real-time translation for conversations

### Amazon SageMaker
- Custom model training for refugee health patterns
- Multi-model endpoints for cost optimization
- Model registry for version control
- Edge deployment for offline inference

### Amazon HealthLake
- FHIR R4 compliant data store
- Automated medical NLP
- Population health analytics
- Integrated with Comprehend Medical

## Architecture Principles with AWS GenAI

1. **AI-First Design** - Every interaction enhanced by GenAI services
2. **Serverless Priority** - Leverage managed services for scalability
3. **Multi-Model Approach** - Use best model for each task
4. **Cost Optimization** - Intelligent caching and batch processing
5. **Privacy-Preserving AI** - On-premises inference options
6. **Continuous Learning** - A/B testing and model improvement

## Security and Compliance

- **HIPAA Compliance**: All AWS services are HIPAA eligible
- **Data Residency**: Regional deployment for data sovereignty
- **Encryption**: AWS KMS for key management
- **Access Control**: IAM roles with least privilege
- **Audit Trail**: CloudTrail for comprehensive logging

## Performance Metrics

| Component | AWS Service | Target SLA |
|-----------|------------|------------|
| Translation | Bedrock Claude 3 | < 2s per request |
| Medical Entity Extraction | Comprehend Medical | < 500ms |
| Voice Transcription | Transcribe Medical | Real-time streaming |
| Document Processing | Textract | < 5s per page |
| Semantic Search | OpenSearch Serverless | < 100ms |
| Model Inference | SageMaker | < 200ms p95 |

For detailed implementation guides, refer to the specific documentation files listed above.