# Backup Infrastructure for Haven Health Passport

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# S3 bucket for encrypted backups
resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-${var.environment}-backups"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-backups"
      Environment = var.environment
      Purpose     = "encrypted-backups"
    }
  )
}

# Enable versioning for backup protection
resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Configure server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_id
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}
# Block all public access
resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle configuration for backup retention
resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "patient-data-retention"
    status = "Enabled"

    filter {
      prefix = "patient-data/"
    }

    expiration {
      days = 2555  # 7 years for HIPAA
    }
  }

  rule {
    id     = "audit-logs-retention"
    status = "Enabled"

    filter {
      prefix = "audit-logs/"
    }

    expiration {
      days = 365  # 1 year
    }
  }

  rule {
    id     = "system-config-retention"
    status = "Enabled"

    filter {
      prefix = "system-config/"
    }

    expiration {
      days = 90
    }
  }
}
# Bucket policy for backup security
resource "aws_s3_bucket_policy" "backups" {
  bucket = aws_s3_bucket.backups.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.backups.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      }
    ]
  })
}

# AWS Backup vault for additional protection
resource "aws_backup_vault" "main" {
  name        = "${var.project_name}-${var.environment}-vault"
  kms_key_arn = var.kms_key_arn

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-backup-vault"
      Environment = var.environment
    }
  )
}

# Backup plan for RDS
resource "aws_backup_plan" "database" {
  name = "${var.project_name}-${var.environment}-db-backup"

  rule {
    rule_name         = "daily_backups"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 2 * * ? *)"  # 2 AM daily

    lifecycle {
      delete_after = 2555  # 7 years for HIPAA
    }
  }
}
