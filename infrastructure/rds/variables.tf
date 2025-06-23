# PostgreSQL RDS Configuration Variables

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "haven-health-passport"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "haven_health_db"
}

variable "database_username" {
  description = "Database master username"
  type        = string
  default     = "haven_admin"
  sensitive   = true
}

variable "database_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "vpc_id" {
  description = "VPC ID for RDS deployment"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for RDS deployment (must be in at least 2 AZs)"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to connect to RDS"
  type        = list(string)
}
