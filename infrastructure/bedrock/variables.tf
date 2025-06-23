# Variables for Bedrock Model Endpoint Configuration

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "haven-health-passport"
}

variable "aws_region" {
  description = "AWS region for Bedrock deployment"
  type        = string
  default     = "us-east-1"  # Bedrock is available in select regions
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "Haven Health Passport"
    ManagedBy   = "Terraform"
    CostCenter  = "AI-ML"
    Compliance  = "HIPAA"
  }
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Lambda deployment"
  type        = list(string)
}

variable "enable_endpoint_caching" {
  description = "Enable caching for model endpoints"
  type        = bool
  default     = true
}

variable "cache_ttl_override" {
  description = "Override cache TTL for specific models (in seconds)"
  type        = map(number)
  default     = {}
}
