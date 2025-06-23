# Communication Templates Configuration

# S3 Bucket for Communication Templates
resource "aws_s3_bucket" "templates" {
  bucket = "${var.project_name}-incident-templates-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-incident-templates"
    }
  )
}

# Upload Communication Templates
resource "aws_s3_object" "communication_templates" {
  for_each = var.communication_templates

  bucket       = aws_s3_bucket.templates.id
  key          = "templates/${each.key}.html"
  content      = each.value
  content_type = "text/html"

  tags = var.common_tags
}

# Upload Stakeholder Notification Templates
resource "aws_s3_object" "stakeholder_templates" {
  for_each = var.stakeholder_templates

  bucket       = aws_s3_bucket.templates.id
  key          = "stakeholder/${each.key}.html"
  content      = each.value
  content_type = "text/html"

  tags = var.common_tags
}
