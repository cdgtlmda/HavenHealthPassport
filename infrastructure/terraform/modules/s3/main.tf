# S3 Bucket Configuration with Encryption for Haven Health Passport

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

# Main storage bucket for patient documents
resource "aws_s3_bucket" "patient_documents" {
  bucket = "${var.project_name}-${var.environment}-patient-documents"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-patient-documents"
      Environment = var.environment
      Purpose     = "patient-document-storage"
      Encryption  = "KMS"
    }
  )
}

# Enable versioning for data protection
resource "aws_s3_bucket_versioning" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Configure server-side encryption with KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_id
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable lifecycle configuration for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  rule {
    id     = "archive-old-documents"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER_FLEXIBLE_RETRIEVAL"
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# S3 bucket for access logs
resource "aws_s3_bucket" "logs" {
  bucket = "${var.project_name}-${var.environment}-logs"

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-logs"
      Environment = var.environment
      Purpose     = "access-logs"
    }
  )
}

# Configure encryption for logs bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_id
      sse_algorithm     = "aws:kms"
    }
  }
}

# Block public access for logs bucket
resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Configure logging for patient documents bucket
resource "aws_s3_bucket_logging" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "patient-documents/"
}

# Enable object lock for compliance
resource "aws_s3_bucket_object_lock_configuration" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.retention_days
    }
  }
}

# Bucket policy for patient documents
resource "aws_s3_bucket_policy" "patient_documents" {
  bucket = aws_s3_bucket.patient_documents.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyInsecureConnections"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.patient_documents.arn,
          "${aws_s3_bucket.patient_documents.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.patient_documents.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      {
        Sid    = "RequireKMSKey"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.patient_documents.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.kms_key_arn
          }
        }
      }
    ]
  })
}
