# Variables for KMS module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "haven-health-passport"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "deletion_window_days" {
  description = "KMS key deletion window in days"
  type        = number
  default     = 30
}

variable "multi_region" {
  description = "Whether to create multi-region KMS keys"
  type        = bool
  default     = false
}

variable "admin_arns" {
  description = "List of ARNs that can administer the KMS keys"
  type        = list(string)
  default     = []
}

variable "user_arns" {
  description = "List of ARNs that can use the KMS keys"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 90
}

variable "kms_usage_threshold" {
  description = "Threshold for KMS usage alarm"
  type        = number
  default     = 1000
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarm triggers"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
