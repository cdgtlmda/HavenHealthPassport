# Amazon Bedrock Model Endpoint Configuration

This module implements dynamic model endpoint configuration for Amazon Bedrock in the Haven Health Passport project.

## Overview

The endpoint configuration system provides:
- Dynamic model selection based on use case and availability
- Rate limiting to prevent API throttling
- Health monitoring with automatic failover
- Cost optimization through intelligent routing

## Architecture Components

1. **model_endpoints.tf**: Terraform configuration for all model endpoints
2. **lambda/index.py**: Runtime endpoint selection logic
3. **iam.tf**: Security and permissions configuration
4. **variables.tf**: Configurable parameters

## Usage

Deploy with Terraform:
```bash
terraform init
terraform plan -var="environment=dev"
terraform apply
```

## Model Selection Rules

- **medical_translation**: Titan Text Express → Claude 3 Sonnet (fallback)
- **medical_qa**: Claude 3 Opus → Claude 3 Sonnet (fallback)
- **document_analysis**: Claude 3 Sonnet Multimodal → Claude 3 Sonnet
- **general_chat**: Claude Instant → Claude 3 Sonnet
- **embeddings**: Titan Embeddings V2 → V1 (fallback)

## Monitoring

CloudWatch metrics track:
- Model selection patterns
- Rate limit violations
- Endpoint health status
- Cost optimization effectiveness

## Security

- All configurations encrypted with KMS
- Lambda runs in private VPC
- Minimal IAM permissions
- HIPAA-compliant logging
