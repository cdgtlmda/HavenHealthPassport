# Forensics Tools Configuration

# S3 Bucket for Forensic Evidence
resource "aws_s3_bucket" "forensics" {
  bucket = "${var.project_name}-forensics-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-forensics"
      Compliance = "evidence-retention"
    }
  )
}

# S3 Bucket Object Lock for Chain of Custody
resource "aws_s3_bucket_object_lock_configuration" "forensics" {
  bucket = aws_s3_bucket.forensics.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.evidence_retention_days
    }
  }
}

# S3 Bucket Versioning (required for Object Lock)
resource "aws_s3_bucket_versioning" "forensics" {
  bucket = aws_s3_bucket.forensics.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "forensics" {
  bucket = aws_s3_bucket.forensics.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

# IAM Role for Forensics Access
resource "aws_iam_role" "forensics_access" {
  name = "${var.project_name}-forensics-access-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = var.forensics_team_arns
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.forensics_external_id
          }
        }
      }
    ]
  })

  tags = var.common_tags
}

# IAM Policy for Forensics Access
resource "aws_iam_role_policy" "forensics_access" {
  name = "${var.project_name}-forensics-access-policy"
  role = aws_iam_role.forensics_access.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket",
          "s3:ListBucketVersions",
          "s3:PutObject",
          "s3:PutObjectLegalHold",
          "s3:PutObjectRetention"
        ]
        Resource = [
          aws_s3_bucket.forensics.arn,
          "${aws_s3_bucket.forensics.arn}/*"
        ]
      }
    ]
  })
}
