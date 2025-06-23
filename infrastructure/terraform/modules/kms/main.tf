# AWS KMS Configuration for Haven Health Passport
# This module configures AWS Key Management Service for encryption at rest

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# Data source for AWS region
data "aws_region" "current" {}

# Main KMS key for data encryption
resource "aws_kms_key" "main" {
  description             = "Haven Health Passport main encryption key"
  deletion_window_in_days = var.deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.multi_region

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-main-key"
      Purpose     = "data-encryption"
      Environment = var.environment
    }
  )
}

# Alias for the main KMS key
resource "aws_kms_alias" "main" {
  name          = "alias/${var.project_name}-${var.environment}-main"
  target_key_id = aws_kms_key.main.key_id
}

# KMS key policy
resource "aws_kms_key_policy" "main" {
  key_id = aws_kms_key.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${var.project_name}-key-policy"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow administration of the key"
        Effect = "Allow"
        Principal = {
          AWS = var.admin_arns
        }
        Action = [
          "kms:Create*",
          "kms:Describe*",
          "kms:Enable*",
          "kms:List*",
          "kms:Put*",
          "kms:Update*",
          "kms:Revoke*",
          "kms:Disable*",
          "kms:Get*",
          "kms:Delete*",
          "kms:TagResource",
          "kms:UntagResource",
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow use of the key for encryption/decryption"
        Effect = "Allow"
        Principal = {
          AWS = var.user_arns
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "s3.${data.aws_region.current.name}.amazonaws.com",
              "rds.${data.aws_region.current.name}.amazonaws.com",
              "dynamodb.${data.aws_region.current.name}.amazonaws.com",
              "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
            ]
          }
        }
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      }
    ]
  })
}

# KMS key for S3 bucket encryption
resource "aws_kms_key" "s3" {
  description             = "Haven Health Passport S3 encryption key"
  deletion_window_in_days = var.deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.multi_region

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-s3-key"
      Purpose     = "s3-encryption"
      Environment = var.environment
    }
  )
}

# Alias for S3 KMS key
resource "aws_kms_alias" "s3" {
  name          = "alias/${var.project_name}-${var.environment}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# KMS key for RDS encryption
resource "aws_kms_key" "rds" {
  description             = "Haven Health Passport RDS encryption key"
  deletion_window_in_days = var.deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.multi_region

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-rds-key"
      Purpose     = "rds-encryption"
      Environment = var.environment
    }
  )
}

# Alias for RDS KMS key
resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project_name}-${var.environment}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# KMS key for Secrets Manager
resource "aws_kms_key" "secrets" {
  description             = "Haven Health Passport Secrets Manager encryption key"
  deletion_window_in_days = var.deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.multi_region

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-secrets-key"
      Purpose     = "secrets-encryption"
      Environment = var.environment
    }
  )
}

# Alias for Secrets Manager KMS key
resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.project_name}-${var.environment}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# KMS key for application-level encryption
resource "aws_kms_key" "app" {
  description             = "Haven Health Passport application encryption key"
  deletion_window_in_days = var.deletion_window_days
  enable_key_rotation     = true
  multi_region            = var.multi_region

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-app-key"
      Purpose     = "app-encryption"
      Environment = var.environment
    }
  )
}

# Alias for application KMS key
resource "aws_kms_alias" "app" {
  name          = "alias/${var.project_name}-${var.environment}-app"
  target_key_id = aws_kms_key.app.key_id
}

# Cloudwatch Log Group for KMS key usage monitoring
resource "aws_cloudwatch_log_group" "kms_usage" {
  name              = "/aws/kms/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.main.arn

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-kms-logs"
      Environment = var.environment
    }
  )
}

# CloudWatch Metric Alarm for KMS key usage
resource "aws_cloudwatch_metric_alarm" "kms_key_usage" {
  alarm_name          = "${var.project_name}-${var.environment}-kms-key-usage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "NumberOfOperations"
  namespace           = "AWS/KMS"
  period              = "300"
  statistic           = "Sum"
  threshold           = var.kms_usage_threshold
  alarm_description   = "This metric monitors KMS key usage"
  alarm_actions       = var.alarm_actions

  dimensions = {
    KeyId = aws_kms_key.main.key_id
  }

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-kms-usage-alarm"
      Environment = var.environment
    }
  )
}

# IAM Policy for KMS key usage
resource "aws_iam_policy" "kms_usage" {
  name        = "${var.project_name}-${var.environment}-kms-usage"
  path        = "/"
  description = "Policy for using Haven Health Passport KMS keys"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = [
          aws_kms_key.main.arn,
          aws_kms_key.s3.arn,
          aws_kms_key.rds.arn,
          aws_kms_key.secrets.arn,
          aws_kms_key.app.arn
        ]
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-kms-usage-policy"
      Environment = var.environment
    }
  )
}
