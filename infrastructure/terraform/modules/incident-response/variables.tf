# Variables for Incident Response Module

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

variable "incident_severity_levels" {
  description = "Incident severity level definitions"
  type = map(object({
    name        = string
    description = string
    sla_minutes = number
  }))
  default = {
    critical = {
      name        = "Critical"
      description = "Complete service outage"
      sla_minutes = 15
    }
    high = {
      name        = "High"
      description = "Major functionality impaired"
      sla_minutes = 60
    }
    medium = {
      name        = "Medium"
      description = "Minor functionality impaired"
      sla_minutes = 240
    }
  }
}
variable "escalation_matrix" {
  description = "Escalation matrix for incident response"
  type        = map(list(string))
  default = {
    critical = ["security-team", "engineering-lead", "cto"]
    high     = ["security-team", "engineering-lead"]
    medium   = ["security-team"]
  }
}

variable "incident_contacts" {
  description = "Contact information for incident response"
  type = map(object({
    email = string
    phone = string
  }))
  default = {}
}

variable "incident_playbooks" {
  description = "Incident response playbooks"
  type        = map(any)
  default     = {}
}

variable "oncall_contacts" {
  description = "On-call team contacts"
  type = map(object({
    email = string
    phone = optional(string)
  }))
  default = {}
}

variable "oncall_rotation_schedule" {
  description = "On-call rotation schedule"
  type        = map(any)
  default     = {}
}

variable "oncall_rotation_cron" {
  description = "Cron expression for on-call rotation"
  type        = string
  default     = "cron(0 9 ? * MON *)"  # Every Monday at 9 AM
}

variable "evidence_retention_days" {
  description = "Number of days to retain forensic evidence"
  type        = number
  default     = 2555  # 7 years
}
