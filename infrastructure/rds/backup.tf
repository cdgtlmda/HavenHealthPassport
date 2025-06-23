# Automated Backup Configuration

# S3 Bucket for Database Exports
resource "aws_s3_bucket" "rds_backups" {
  bucket = "${var.project_name}-${var.environment}-rds-backups-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-backups"
    Environment = var.environment
    Project     = var.project_name
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "rds_backups" {
  bucket = aws_s3_bucket.rds_backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "rds_backups" {
  bucket = aws_s3_bucket.rds_backups.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.rds_encryption.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# S3 Bucket Lifecycle
resource "aws_s3_bucket_lifecycle_configuration" "rds_backups" {
  bucket = aws_s3_bucket.rds_backups.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "GLACIER"
    }

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2555  # 7 years
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
