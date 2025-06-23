# Variables for Haven Health Passport infrastructure

variable "aws_region" {
  description = "Primary AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production"
  }
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "haven-health-passport"
}

# Bedrock-specific variables
variable "bedrock_regions" {
  description = "AWS regions where Bedrock should be configured"
  type        = list(string)
  default     = ["us-east-1", "us-west-2", "eu-west-1"]
}

variable "bedrock_models" {
  description = "List of Bedrock models to request access for"
  type        = list(string)
  default = [
    "anthropic.claude-v2",
    "anthropic.claude-v2:1",
    "anthropic.claude-instant-v1",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "amazon.titan-text-express-v1",
    "amazon.titan-text-lite-v1",
    "amazon.titan-embed-text-v1",
    "meta.llama2-70b-chat-v1",
    "meta.llama2-13b-chat-v1",
    "ai21.j2-ultra-v1",
    "ai21.j2-mid-v1"
  ]
}

variable "enable_cost_alerts" {
  description = "Enable cost alerts for Bedrock usage"
  type        = bool
  default     = true
}

variable "bedrock_monthly_budget" {
  description = "Monthly budget for Bedrock usage in USD"
  type        = number
  default     = 1000
}

variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch logs for Bedrock requests"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 30
}

# Service quotas
variable "bedrock_service_quotas" {
  description = "Service quota configurations for Bedrock"
  type = object({
    max_requests_per_minute = number
    max_concurrent_requests = number
  })
  default = {
    max_requests_per_minute = 60
    max_concurrent_requests = 10
  }
}

# Tags
variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
