# Variables for AWS Managed Blockchain Network Configuration
# Haven Health Passport - Blockchain Infrastructure

variable "network_name" {
  description = "Name for the Managed Blockchain network"
  type        = string
  default     = "haven-health-passport-network"
}

variable "network_description" {
  description = "Description of the Managed Blockchain network"
  type        = string
  default     = "Haven Health Passport blockchain network for secure healthcare data management"
}

variable "framework_version" {
  description = "Version of Hyperledger Fabric framework"
  type        = string
  default     = "2.2"
}

variable "network_edition" {
  description = "Edition of the network (STANDARD or STARTER)"
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "STARTER"], var.network_edition)
    error_message = "Network edition must be either STANDARD or STARTER"
  }
}

variable "fabric_edition" {
  description = "Edition of Hyperledger Fabric"
  type        = string
  default     = "STANDARD"
}

variable "approval_threshold_percentage" {
  description = "Percentage of members required to approve proposals"
  type        = number
  default     = 50

  validation {
    condition     = var.approval_threshold_percentage >= 0 && var.approval_threshold_percentage <= 100
    error_message = "Approval threshold must be between 0 and 100"
  }
}

variable "proposal_duration_hours" {
  description = "Duration in hours for voting on proposals"
  type        = number
  default     = 24
}
variable "member_name" {
  description = "Name for the initial network member"
  type        = string
  default     = "haven-health-primary-member"
}

variable "member_description" {
  description = "Description of the network member"
  type        = string
  default     = "Primary member for Haven Health Passport blockchain network"
}

variable "admin_username" {
  description = "Admin username for the member"
  type        = string
  sensitive   = true
}

variable "admin_password" {
  description = "Admin password for the member"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.admin_password) >= 8
    error_message = "Admin password must be at least 8 characters long"
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }
}

variable "common_tags" {
  description = "Common tags to be applied to all resources"
  type        = map(string)
  default = {
    Project     = "haven-health-passport"
    ManagedBy   = "terraform"
    Component   = "blockchain"
  }
}

# Peer node configuration variables
variable "peer_node_count" {
  description = "Number of peer nodes to create"
  type        = number
  default     = 2

  validation {
    condition     = var.peer_node_count >= 1 && var.peer_node_count <= 5
    error_message = "Peer node count must be between 1 and 5"
  }
}

variable "peer_instance_type" {
  description = "Instance type for peer nodes"
  type        = string
  default     = "bc.t3.small"

  validation {
    condition = contains([
      "bc.t3.small",
      "bc.t3.medium",
      "bc.t3.large",
      "bc.t3.xlarge",
      "bc.m5.large",
      "bc.m5.xlarge",
      "bc.m5.2xlarge",
      "bc.m5.4xlarge"
    ], var.peer_instance_type)
    error_message = "Invalid peer instance type"
  }
}

variable "availability_zones" {
  description = "List of availability zones for peer nodes"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 30

  validation {
    condition = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Invalid log retention period"
  }
}

# VPC Configuration Variables
variable "vpc_id" {
  description = "ID of the VPC where blockchain resources will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for VPC endpoint"
  type        = list(string)
}

variable "network_acl_id" {
  description = "ID of the network ACL"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}
