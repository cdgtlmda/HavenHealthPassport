# Incident Response Plan Configuration

# S3 Bucket for Incident Response Documents
resource "aws_s3_bucket" "incident_response" {
  bucket = "${var.project_name}-incident-response-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-incident-response"
    }
  )
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "incident_response" {
  bucket = aws_s3_bucket.incident_response.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "incident_response" {
  bucket = aws_s3_bucket.incident_response.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
# Upload Incident Response Plan
resource "aws_s3_object" "incident_response_plan" {
  bucket = aws_s3_bucket.incident_response.id
  key    = "plans/incident-response-plan.json"

  content = jsonencode({
    version = "1.0"
    updated_at = timestamp()
    severity_levels = var.incident_severity_levels
    escalation_matrix = var.escalation_matrix
    contact_lists = var.incident_contacts
    playbooks = var.incident_playbooks
  })

  content_type = "application/json"
  tags = var.common_tags
}

# Upload Incident Response Playbooks
resource "aws_s3_object" "playbooks" {
  for_each = var.incident_playbooks

  bucket = aws_s3_bucket.incident_response.id
  key    = "playbooks/${each.key}.json"

  content = jsonencode(each.value)
  content_type = "application/json"
  tags = var.common_tags
}
