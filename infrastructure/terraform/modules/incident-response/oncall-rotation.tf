# On-Call Rotation Configuration

# SNS Topic for On-Call Notifications
resource "aws_sns_topic" "oncall" {
  name = "${var.project_name}-oncall-notifications"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-oncall-notifications"
    }
  )
}

# SNS Topic Subscriptions for On-Call Team
resource "aws_sns_topic_subscription" "oncall_email" {
  for_each = var.oncall_contacts

  topic_arn = aws_sns_topic.oncall.arn
  protocol  = "email"
  endpoint  = each.value.email
}

# SNS Topic Subscriptions for SMS
resource "aws_sns_topic_subscription" "oncall_sms" {
  for_each = { for k, v in var.oncall_contacts : k => v if v.phone != null }

  topic_arn = aws_sns_topic.oncall.arn
  protocol  = "sms"
  endpoint  = each.value.phone
}

# Lambda Function for On-Call Rotation Management
resource "aws_lambda_function" "oncall_rotation" {
  filename         = "${path.module}/lambda/oncall-rotation.zip"
  function_name    = "${var.project_name}-oncall-rotation"
  role            = aws_iam_role.oncall_rotation.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 60

  environment {
    variables = {
      ROTATION_SCHEDULE = jsonencode(var.oncall_rotation_schedule)
      SNS_TOPIC_ARN    = aws_sns_topic.oncall.arn
    }
  }

  tags = var.common_tags
}
# EventBridge Rule for On-Call Rotation
resource "aws_cloudwatch_event_rule" "oncall_rotation" {
  name                = "${var.project_name}-oncall-rotation"
  description         = "Trigger on-call rotation updates"
  schedule_expression = var.oncall_rotation_cron

  tags = var.common_tags
}

# EventBridge Target for Lambda
resource "aws_cloudwatch_event_target" "oncall_lambda" {
  rule      = aws_cloudwatch_event_rule.oncall_rotation.name
  target_id = "OnCallRotationLambda"
  arn       = aws_lambda_function.oncall_rotation.arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "oncall_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.oncall_rotation.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.oncall_rotation.arn
}

# IAM Role for On-Call Rotation Lambda
resource "aws_iam_role" "oncall_rotation" {
  name = "${var.project_name}-oncall-rotation-role"

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

  tags = var.common_tags
}
