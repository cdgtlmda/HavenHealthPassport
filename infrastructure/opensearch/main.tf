# AWS OpenSearch Domain for Haven Health Passport

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for OpenSearch domain"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for OpenSearch domain"
  type        = list(string)
}

variable "instance_type" {
  description = "OpenSearch instance type"
  type        = string
  default     = "t3.medium.search"
}

variable "instance_count" {
  description = "Number of instances in the cluster"
  type        = number
  default     = 3
}

variable "master_instance_type" {
  description = "Dedicated master instance type"
  type        = string
  default     = "t3.small.search"
}

variable "master_instance_count" {
  description = "Number of dedicated master instances"
  type        = number
  default     = 3
}

variable "volume_size" {
  description = "EBS volume size in GB"
  type        = number
  default     = 100
}

variable "volume_type" {
  description = "EBS volume type"
  type        = string
  default     = "gp3"
}

# Security group for OpenSearch
resource "aws_security_group" "opensearch" {
  name_prefix = "haven-health-opensearch-${var.environment}-"
  description = "Security group for Haven Health OpenSearch domain"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]  # Adjust based on your VPC CIDR
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "haven-health-opensearch-${var.environment}"
    Environment = var.environment
    Project     = "haven-health-passport"
  }
}

# IAM role for OpenSearch
resource "aws_iam_role" "opensearch" {
  name = "haven-health-opensearch-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "es.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "haven-health-passport"
  }
}

# OpenSearch domain
resource "aws_opensearch_domain" "main" {
  domain_name    = "haven-health-${var.environment}"
  engine_version = "OpenSearch_2.11"

  cluster_config {
    instance_type  = var.instance_type
    instance_count = var.instance_count

    dedicated_master_enabled = true
    dedicated_master_type    = var.master_instance_type
    dedicated_master_count   = var.master_instance_count

    zone_awareness_enabled = true
    zone_awareness_config {
      availability_zone_count = 3
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_type = var.volume_type
    volume_size = var.volume_size
    throughput  = var.volume_type == "gp3" ? 250 : null
  }

  vpc_options {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.opensearch.id]
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = false
    master_user_options {
      master_user_arn = aws_iam_role.opensearch_admin.arn
    }
  }

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action = [
          "es:*"
        ]
        Resource = "arn:aws:es:*:*:domain/haven-health-${var.environment}/*"
      }
    ]
  })

  tags = {
    Name        = "haven-health-${var.environment}"
    Environment = var.environment
    Project     = "haven-health-passport"
  }
}

# IAM role for OpenSearch admin access
resource "aws_iam_role" "opensearch_admin" {
  name = "haven-health-opensearch-admin-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
      }
    ]
  })
}

# IAM policy for application access
resource "aws_iam_policy" "opensearch_access" {
  name        = "haven-health-opensearch-access-${var.environment}"
  description = "Policy for accessing Haven Health OpenSearch domain"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "es:ESHttpGet",
          "es:ESHttpPost",
          "es:ESHttpPut",
          "es:ESHttpDelete",
          "es:ESHttpHead"
        ]
        Resource = "${aws_opensearch_domain.main.arn}/*"
      }
    ]
  })
}

# CloudWatch alarms
resource "aws_cloudwatch_metric_alarm" "cluster_status_red" {
  alarm_name          = "haven-health-opensearch-${var.environment}-cluster-red"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name        = "ClusterStatus.red"
  namespace          = "AWS/ES"
  period             = "60"
  statistic          = "Maximum"
  threshold          = "0"
  alarm_description  = "OpenSearch cluster status is red"

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
  }
}

resource "aws_cloudwatch_metric_alarm" "cluster_index_writes_blocked" {
  alarm_name          = "haven-health-opensearch-${var.environment}-writes-blocked"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name        = "ClusterIndexWritesBlocked"
  namespace          = "AWS/ES"
  period             = "300"
  statistic          = "Maximum"
  threshold          = "0"
  alarm_description  = "OpenSearch cluster is blocking write operations"

  dimensions = {
    DomainName = aws_opensearch_domain.main.domain_name
  }
}

# Data sources
data "aws_caller_identity" "current" {}

# Outputs
output "opensearch_endpoint" {
  value       = aws_opensearch_domain.main.endpoint
  description = "OpenSearch domain endpoint"
}

output "opensearch_arn" {
  value       = aws_opensearch_domain.main.arn
  description = "OpenSearch domain ARN"
}

output "opensearch_domain_id" {
  value       = aws_opensearch_domain.main.domain_id
  description = "OpenSearch domain ID"
}

output "opensearch_access_policy_arn" {
  value       = aws_iam_policy.opensearch_access.arn
  description = "ARN of the IAM policy for OpenSearch access"
}
