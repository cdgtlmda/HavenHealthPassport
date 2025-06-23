# Main Terraform configuration for Haven Health Passport

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration for state management
  backend "s3" {
    # These values should be configured via backend config file or CLI flags
    # bucket         = "haven-health-terraform-state"
    # key            = "terraform.tfstate"
    # region         = "us-east-1"
    # encrypt        = true
    # dynamodb_table = "haven-health-terraform-locks"
  }
}

# AWS Provider Configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "HavenHealthPassport"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Application = "Healthcare"
      Compliance  = "HIPAA"
    }
  }
}

# Additional AWS providers for multi-region support
provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"

  default_tags {
    tags = {
      Project     = "HavenHealthPassport"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Application = "Healthcare"
      Compliance  = "HIPAA"
    }
  }
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"

  default_tags {
    tags = {
      Project     = "HavenHealthPassport"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Application = "Healthcare"
      Compliance  = "HIPAA"
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# Module for Bedrock configuration
module "bedrock" {
  source = "./modules/bedrock"

  environment      = var.environment
  project_name     = var.project_name
  bedrock_regions  = var.bedrock_regions

  # Model access configuration
  requested_models = var.bedrock_models

  # Cost management
  enable_cost_alerts      = var.enable_cost_alerts
  monthly_budget_amount   = var.bedrock_monthly_budget

  # Monitoring
  enable_cloudwatch_logs  = var.enable_cloudwatch_logs
  log_retention_days      = var.log_retention_days
}

# Outputs
output "bedrock_iam_role_arn" {
  description = "ARN of the IAM role for Bedrock access"
  value       = module.bedrock.bedrock_iam_role_arn
}

output "bedrock_policy_arn" {
  description = "ARN of the IAM policy for Bedrock access"
  value       = module.bedrock.bedrock_policy_arn
}

output "bedrock_model_access_status" {
  description = "Status of Bedrock model access requests"
  value       = module.bedrock.model_access_status
}

output "bedrock_monitoring_dashboard_url" {
  description = "URL of the CloudWatch dashboard for Bedrock monitoring"
  value       = module.bedrock.monitoring_dashboard_url
}
