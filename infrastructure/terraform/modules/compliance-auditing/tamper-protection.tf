# Tamper Protection Configuration

# Lambda Function for Audit Log Processing and Tamper Detection
resource "aws_lambda_function" "audit_processor" {
  filename         = "${path.module}/lambda/audit-processor.zip"
  function_name    = "${var.project_name}-audit-processor"
  role            = aws_iam_role.audit_processor.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 60
  memory_size     = 512

  environment {
    variables = {
      AUDIT_TABLE     = aws_dynamodb_table.audit_trail.name
      HASH_SECRET     = var.audit_hash_secret
      ALERT_TOPIC_ARN = var.sns_alert_topic_arn
    }
  }

  tags = var.common_tags
}

# S3 Bucket for Immutable Audit Log Archives
resource "aws_s3_bucket" "audit_archive" {
  bucket = "${var.project_name}-audit-archive-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-audit-archive"
    }
  )
}

# Enable Object Lock for Tamper Protection
resource "aws_s3_bucket_object_lock_configuration" "audit_archive" {
  bucket = aws_s3_bucket.audit_archive.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.audit_retention_days
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
