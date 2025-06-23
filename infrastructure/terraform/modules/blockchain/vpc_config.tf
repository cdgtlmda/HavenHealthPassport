# VPC Configuration for AWS Managed Blockchain
# Haven Health Passport - Blockchain Infrastructure

# Data source to get the VPC information
data "aws_vpc" "main" {
  id = var.vpc_id
}

# Create VPC endpoint for the Managed Blockchain network
resource "aws_vpc_endpoint" "blockchain" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.managedblockchain.${aws_managedblockchain_network.haven_health_network.framework_version}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.blockchain_endpoint.id]

  private_dns_enabled = true

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.environment}-blockchain-vpc-endpoint"
      Environment = var.environment
      Type        = "managed-blockchain"
    }
  )
}

# Security group for blockchain VPC endpoint
resource "aws_security_group" "blockchain_endpoint" {
  name        = "${var.environment}-blockchain-endpoint-sg"
  description = "Security group for Managed Blockchain VPC endpoint"
  vpc_id      = var.vpc_id

  # Ingress rules
  ingress {
    description     = "HTTPS from VPC"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    cidr_blocks     = [data.aws_vpc.main.cidr_block]
  }

  ingress {
    description     = "Peer communication"
    from_port       = 30001
    to_port         = 30004
    protocol        = "tcp"
    cidr_blocks     = [data.aws_vpc.main.cidr_block]
  }

  # Egress rules
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.environment}-blockchain-endpoint-sg"
      Environment = var.environment
    }
  )
}

# Network ACL configuration
resource "aws_network_acl_rule" "blockchain_ingress" {
  network_acl_id = var.network_acl_id
  rule_number    = 100
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = data.aws_vpc.main.cidr_block
  from_port      = 443
  to_port        = 443
}

resource "aws_network_acl_rule" "blockchain_peer_ingress" {
  network_acl_id = var.network_acl_id
  rule_number    = 110
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = data.aws_vpc.main.cidr_block
  from_port      = 30001
  to_port        = 30004
}

# VPC Flow Logs
resource "aws_flow_log" "blockchain" {
  iam_role_arn    = aws_iam_role.flow_log.arn
  log_destination = aws_cloudwatch_log_group.flow_log.arn
  traffic_type    = "ALL"
  vpc_id          = var.vpc_id

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.environment}-blockchain-flow-logs"
      Environment = var.environment
    }
  )
}

resource "aws_cloudwatch_log_group" "flow_log" {
  name              = "/aws/vpc/${var.environment}/blockchain-flow-logs"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.common_tags,
    {
      Name = "${var.environment}-blockchain-vpc-flow-logs"
    }
  )
}

resource "aws_iam_role" "flow_log" {
  name = "${var.environment}-blockchain-flow-log-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy" "flow_log" {
  name = "${var.environment}-blockchain-flow-log-policy"
  role = aws_iam_role.flow_log.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Effect = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Outputs
output "vpc_endpoint_id" {
  description = "ID of the VPC endpoint"
  value       = aws_vpc_endpoint.blockchain.id
}

output "security_group_id" {
  description = "ID of the blockchain security group"
  value       = aws_security_group.blockchain_endpoint.id
}
