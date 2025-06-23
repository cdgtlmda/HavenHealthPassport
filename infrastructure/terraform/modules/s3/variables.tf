# Variables for S3 module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "haven-health-passport"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "kms_key_id" {
  description = "KMS key ID for S3 encryption"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for S3 encryption"
  type        = string
}

variable "retention_days" {
  description = "Object lock retention period in days"
  type        = number
  default     = 2555  # 7 years for HIPAA compliance
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "enable_replication" {
  description = "Enable cross-region replication"
  type        = bool
  default     = false
}

variable "replication_destination_bucket" {
  description = "ARN of the destination bucket for replication"
  type        = string
  default     = ""
}
