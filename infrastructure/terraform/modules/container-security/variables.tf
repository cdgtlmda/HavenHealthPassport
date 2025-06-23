# Variables for Container Security Module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "haven-health-passport"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "haven-health-passport"
    Environment = "production"
    Terraform   = "true"
  }
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encryption"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "ecr_repositories" {
  description = "List of ECR repository names"
  type        = list(string)
  default     = ["web", "api", "worker", "ml-engine"]
}

variable "ecr_pull_principals" {
  description = "AWS principals allowed to pull images"
  type        = list(string)
  default     = []
}

variable "sns_alert_topic_arn" {
  description = "ARN of the SNS topic for security alerts"
  type        = string
}

variable "vulnerability_severity_threshold" {
  description = "Severity threshold for vulnerability alerts"
  type        = string
  default     = "HIGH"
}
variable "approved_base_images" {
  description = "List of approved base images"
  type = list(object({
    repository = string
    tag        = string
    digest     = string
  }))
  default = [
    {
      repository = "public.ecr.aws/docker/library/alpine"
      tag        = "3.18"
      digest     = "sha256:..."
    },
    {
      repository = "public.ecr.aws/docker/library/node"
      tag        = "18-alpine"
      digest     = "sha256:..."
    }
  ]
}

variable "container_port" {
  description = "Port exposed by containers"
  type        = number
  default     = 8080
}

variable "alb_security_group_id" {
  description = "Security group ID of the ALB"
  type        = string
}

variable "rds_security_group_id" {
  description = "Security group ID of RDS"
  type        = string
}

variable "elasticache_security_group_id" {
  description = "Security group ID of ElastiCache"
  type        = string
}

variable "container_secrets_names" {
  description = "Names of secrets to create for containers"
  type        = list(string)
  default     = ["database-url", "api-key", "jwt-secret", "encryption-key"]
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}
