# Variables for Compliance and Auditing Module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "haven-health-passport"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project = "haven-health-passport"
    Environment = "production"
    Terraform = "true"
  }
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encryption"
  type        = string
}

variable "sns_alert_topic_arn" {
  description = "ARN of the SNS topic for security alerts"
  type        = string
}

variable "audit_hash_secret" {
  description = "Secret for audit log hashing"
  type        = string
  sensitive   = true
}

variable "audit_retention_days" {
  description = "Number of days to retain audit logs"
  type        = number
  default     = 2555
}

variable "audit_report_schedule" {
  description = "Schedule for audit report generation"
  type        = string
  default     = "cron(0 8 1 * ? *)"
}

variable "compliance_rules" {
  description = "Custom compliance rules"
  type        = map(any)
  default     = {}
}
