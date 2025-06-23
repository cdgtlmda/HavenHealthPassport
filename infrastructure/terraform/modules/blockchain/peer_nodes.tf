# Peer Node Configuration for AWS Managed Blockchain
# Haven Health Passport - Blockchain Infrastructure

# Create peer nodes for the network member
resource "aws_managedblockchain_node" "peer_node" {
  count = var.peer_node_count

  network_id = aws_managedblockchain_network.haven_health_network.id
  member_id  = aws_managedblockchain_network.haven_health_network.member_attributes[0].member_id

  node_configuration {
    # Instance type for peer nodes
    instance_type = var.peer_instance_type

    # Availability zone configuration
    availability_zone = element(var.availability_zones, count.index)

    # Logging configuration
    log_publishing_configuration {
      fabric_configuration {
        peer_logs {
          cloudwatch {
            enabled = true
          }
        }

        chaincode_logs {
          cloudwatch {
            enabled = true
          }
        }
      }
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.network_name}-peer-${count.index + 1}"
      Environment = var.environment
      NodeType    = "peer"
      NodeIndex   = count.index + 1
    }
  )
}

# CloudWatch Log Groups for peer nodes
resource "aws_cloudwatch_log_group" "peer_logs" {
  count = var.peer_node_count

  name              = "/aws/managedblockchain/${var.environment}/peer-${count.index + 1}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name     = "${var.environment}-blockchain-peer-logs-${count.index + 1}"
      NodeType = "peer"
    }
  )
}

resource "aws_cloudwatch_log_group" "chaincode_logs" {
  count = var.peer_node_count

  name              = "/aws/managedblockchain/${var.environment}/chaincode-${count.index + 1}"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name     = "${var.environment}-blockchain-chaincode-logs-${count.index + 1}"
      NodeType = "chaincode"
    }
  )
}

# Store peer node endpoints in SSM
resource "aws_ssm_parameter" "peer_endpoints" {
  count = var.peer_node_count

  name  = "/${var.environment}/blockchain/peer_endpoint_${count.index + 1}"
  type  = "SecureString"
  value = aws_managedblockchain_node.peer_node[count.index].node_framework_attributes[0].fabric_attributes[0].peer_endpoint

  tags = merge(
    var.common_tags,
    {
      Name = "${var.environment}-peer-endpoint-${count.index + 1}"
    }
  )
}

# Outputs for peer nodes
output "peer_node_ids" {
  description = "IDs of the peer nodes"
  value       = aws_managedblockchain_node.peer_node[*].id
  sensitive   = true
}

output "peer_endpoints" {
  description = "Endpoints of the peer nodes"
  value       = aws_managedblockchain_node.peer_node[*].node_framework_attributes[0].fabric_attributes[0].peer_endpoint
  sensitive   = true
}
