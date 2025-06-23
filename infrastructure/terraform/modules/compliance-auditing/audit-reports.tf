# Audit Reports Configuration

# Lambda Function for Audit Report Generation
resource "aws_lambda_function" "audit_reporter" {
  filename         = "${path.module}/lambda/audit-reporter.zip"
  function_name    = "${var.project_name}-audit-reporter"
  role            = aws_iam_role.audit_reporter.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 900
  memory_size     = 1024

  environment {
    variables = {
      AUDIT_TABLE    = aws_dynamodb_table.audit_trail.name
      REPORT_BUCKET  = aws_s3_bucket.audit_reports.id
      KMS_KEY_ID     = var.kms_key_arn
    }
  }

  tags = var.common_tags
}

# S3 Bucket for Audit Reports
resource "aws_s3_bucket" "audit_reports" {
  bucket = "${var.project_name}-audit-reports-${data.aws_caller_identity.current.account_id}"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-audit-reports"
    }
  )
}

# EventBridge Rule for Scheduled Reports
resource "aws_cloudwatch_event_rule" "audit_reports" {
  name                = "${var.project_name}-audit-reports"
  description         = "Generate periodic audit reports"
  schedule_expression = var.audit_report_schedule

  tags = var.common_tags
}

# EventBridge Target for Report Generation
resource "aws_cloudwatch_event_target" "audit_reporter" {
  rule      = aws_cloudwatch_event_rule.audit_reports.name
  target_id = "AuditReporterLambda"
  arn       = aws_lambda_function.audit_reporter.arn
}
