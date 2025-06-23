# VPC Security Module

This Terraform module creates a secure VPC infrastructure for the Haven Health Passport application with proper network segmentation and security controls.

## Features

- **Secure VPC with Flow Logs**: Creates a VPC with Flow Logs enabled for security monitoring
- **Multi-tier Network Architecture**: Implements public, private application, and private database subnets
- **High Availability**: Deploys resources across multiple availability zones
- **NAT Gateways**: One per AZ for redundant outbound internet access from private subnets
- **VPC Endpoints**: Reduces data transfer costs and improves security for AWS service access
- **Encrypted Logs**: All VPC Flow Logs are encrypted using KMS

## Architecture

The module creates a three-tier network architecture:

1. **Public Subnets**: For NAT Gateways and Load Balancers
2. **Private Application Subnets**: For application servers and containers
3. **Private Database Subnets**: For RDS instances and data storage (no internet access)

## Usage

```hcl
module "networking" {
  source = "./modules/networking"

  project_name            = "haven-health-passport"
  vpc_cidr               = "10.0.0.0/16"
  availability_zones     = ["us-east-1a", "us-east-1b", "us-east-1c"]
  aws_region            = "us-east-1"
  flow_log_retention_days = 30
  kms_key_arn           = module.kms.key_arn

  common_tags = {
    Project     = "haven-health-passport"
    Environment = "production"
    Terraform   = "true"
  }
}
```

## Security Features

- VPC Flow Logs for network traffic monitoring
- Network segmentation with separate subnets for different tiers
- No direct internet access for database subnets
- VPC endpoints to avoid internet routing for AWS services
- All logs encrypted with KMS
