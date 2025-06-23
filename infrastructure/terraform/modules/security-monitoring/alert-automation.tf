# EventBridge and Alert Configuration

# EventBridge Target for GuardDuty Findings
resource "aws_cloudwatch_event_target" "guardduty_sns" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "SendToSNS"
  arn       = var.sns_alert_topic_arn
}

# Lambda Function for GuardDuty Response Automation
resource "aws_lambda_function" "guardduty_response" {
  filename         = "${path.module}/lambda/guardduty-response.zip"
  function_name    = "${var.project_name}-guardduty-response"
  role            = aws_iam_role.guardduty_response.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512

  environment {
    variables = {
      AUTO_REMEDIATE = var.enable_auto_remediation
      QUARANTINE_SECURITY_GROUP = aws_security_group.quarantine.id
    }
  }

  tags = var.common_tags
}

# EventBridge Target for Lambda
resource "aws_cloudwatch_event_target" "guardduty_lambda" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "InvokeLambda"
  arn       = aws_lambda_function.guardduty_response.arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "guardduty_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.guardduty_response.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.guardduty_findings.arn
}
