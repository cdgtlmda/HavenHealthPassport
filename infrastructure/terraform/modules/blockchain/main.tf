# AWS Managed Blockchain Network Configuration
# Haven Health Passport - Blockchain Infrastructure

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Create AWS Managed Blockchain Network
resource "aws_managedblockchain_network" "haven_health_network" {
  name        = var.network_name
  description = var.network_description
  framework   = "HYPERLEDGER_FABRIC"

  framework_version = var.framework_version

  # Network configuration
  network_configuration {
    edition = var.network_edition # Standard or Starter

    # Framework specific configuration
    framework_configuration {
      network_fabric_configuration {
        edition = var.fabric_edition
      }
    }
  }

  # Voting policy configuration
  voting_policy {
    approval_threshold_policy {
      threshold_percentage = var.approval_threshold_percentage
      proposal_duration_in_hours = var.proposal_duration_hours

      # Threshold comparator
      threshold_comparator = "GREATER_THAN_OR_EQUAL_TO"
    }
  }

  # Member configuration
  member_configuration {
    name        = var.member_name
    description = var.member_description

    # Framework specific member configuration
    member_framework_configuration {
      member_fabric_configuration {
        admin_username = var.admin_username
        admin_password = var.admin_password
      }
    }

    # Log configuration
    log_publishing_configuration {
      ca_logs {
        cloudwatch {
          enabled = true
        }
      }
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name        = var.network_name
      Environment = var.environment
      Component   = "blockchain"
      Framework   = "hyperledger-fabric"
    }
  )
}

# Store network details in SSM Parameter Store
resource "aws_ssm_parameter" "network_id" {
  name  = "/${var.environment}/blockchain/network_id"
  type  = "SecureString"
  value = aws_managedblockchain_network.haven_health_network.id

  tags = merge(
    var.common_tags,
    {
      Name = "${var.environment}-blockchain-network-id"
    }
  )
}

resource "aws_ssm_parameter" "network_endpoint" {
  name  = "/${var.environment}/blockchain/network_endpoint"
  type  = "SecureString"
  value = aws_managedblockchain_network.haven_health_network.member_attributes[0].member_fabric_attributes[0].ca_endpoint

  tags = merge(
    var.common_tags,
    {
      Name = "${var.environment}-blockchain-network-endpoint"
    }
  )
}

# Outputs
output "network_id" {
  description = "The ID of the Managed Blockchain network"
  value       = aws_managedblockchain_network.haven_health_network.id
  sensitive   = true
}

output "network_name" {
  description = "The name of the Managed Blockchain network"
  value       = aws_managedblockchain_network.haven_health_network.name
}

output "member_id" {
  description = "The ID of the network member"
  value       = aws_managedblockchain_network.haven_health_network.member_attributes[0].member_id
  sensitive   = true
}

output "ca_endpoint" {
  description = "The certificate authority endpoint"
  value       = aws_managedblockchain_network.haven_health_network.member_attributes[0].member_fabric_attributes[0].ca_endpoint
  sensitive   = true
}

output "network_arn" {
  description = "The ARN of the Managed Blockchain network"
  value       = aws_managedblockchain_network.haven_health_network.arn
  sensitive   = true
}
