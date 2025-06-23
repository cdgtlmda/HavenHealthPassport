# Status Page Configuration

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

  tags = var.common_tags
}

# IAM Role for Status Updater
resource "aws_iam_role" "status_updater" {
  name = "${var.project_name}-status-updater-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}
