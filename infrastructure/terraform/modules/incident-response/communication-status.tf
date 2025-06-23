# Communication Templates and Status Page Configuration

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

# Status Page Configuration (using AWS Systems Manager)
resource "aws_ssm_parameter" "status_page_config" {
  name  = "/${var.project_name}/incident-response/status-page"
  type  = "SecureString"
  value = jsonencode({
    public_url = var.status_page_url
    components = var.status_page_components
    update_frequency = "5m"
  })

  tags = var.common_tags
}

# Lambda Function for Status Page Updates
resource "aws_lambda_function" "status_updater" {
  filename         = "${path.module}/lambda/status-updater.zip"
  function_name    = "${var.project_name}-status-updater"
  role            = aws_iam_role.status_updater.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 60

  environment {
    variables = {
      STATUS_PAGE_CONFIG = aws_ssm_parameter.status_page_config.name
    }
  }
}
