# Variables for Security Monitoring Module

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

variable "sns_alert_topic_arn" {
  description = "ARN of the SNS topic for security alerts"
  type        = string
}

variable "enable_organization_trail" {
  description = "Enable organization-wide CloudTrail"
  type        = bool
  default     = false
}

variable "cloudtrail_log_retention_days" {
  description = "Number of days to retain CloudTrail logs"
  type        = number
  default     = 90
}

variable "event_data_store_retention_days" {
  description = "Number of days to retain event data"
  type        = number
  default     = 90
}
variable "guardduty_finding_frequency" {
  description = "Frequency of GuardDuty findings publication"
  type        = string
  default     = "FIFTEEN_MINUTES"
}

variable "enable_eks_audit_logs" {
  description = "Enable EKS audit log monitoring in GuardDuty"
  type        = bool
  default     = false
}

variable "threat_intel_set_url" {
  description = "URL of custom threat intelligence set"
  type        = string
  default     = ""
}

variable "trusted_ip_list" {
  description = "List of trusted IP addresses"
  type        = list(string)
  default     = []
}

variable "guardduty_severity_threshold" {
  description = "Minimum severity for GuardDuty alerts (1-10)"
  type        = number
  default     = 4
}

variable "enable_auto_remediation" {
  description = "Enable automatic remediation for GuardDuty findings"
  type        = bool
  default     = false
}

variable "correlation_rules" {
  description = "Security event correlation rules"
  type = map(object({
    event_types = list(string)
    threshold   = number
    time_window = number
  }))
  default = {
    brute_force = {
      event_types = ["failed_login"]
      threshold   = 5
      time_window = 300
    }
  }
}

variable "alert_threshold" {
  description = "Threshold for security alerts"
  type        = number
  default     = 3
}
