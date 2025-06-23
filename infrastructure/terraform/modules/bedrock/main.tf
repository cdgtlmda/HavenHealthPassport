# Bedrock Module - Main Configuration
# This module sets up Amazon Bedrock with proper IAM roles, policies, and monitoring

locals {
  bedrock_service_principal = "bedrock.amazonaws.com"

  # Model permissions mapping
  model_permissions = {
    "anthropic.claude-v2"                       = "bedrock:InvokeModel"
    "anthropic.claude-v2:1"                     = "bedrock:InvokeModel"
    "anthropic.claude-instant-v1"               = "bedrock:InvokeModel"
    "anthropic.claude-3-sonnet-20240229-v1:0"   = "bedrock:InvokeModel"
    "anthropic.claude-3-haiku-20240307-v1:0"    = "bedrock:InvokeModel"
    "amazon.titan-text-express-v1"              = "bedrock:InvokeModel"
    "amazon.titan-text-lite-v1"                 = "bedrock:InvokeModel"
    "amazon.titan-embed-text-v1"                = "bedrock:InvokeModel"
    "meta.llama2-70b-chat-v1"                   = "bedrock:InvokeModel"
    "meta.llama2-13b-chat-v1"                   = "bedrock:InvokeModel"
    "ai21.j2-ultra-v1"                          = "bedrock:InvokeModel"
    "ai21.j2-mid-v1"                            = "bedrock:InvokeModel"
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# IAM Role for Bedrock Access
resource "aws_iam_role" "bedrock_role" {
  name               = "${var.project_name}-bedrock-role-${var.environment}"
  description        = "IAM role for accessing Amazon Bedrock services"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "ecs-tasks.amazonaws.com",
            "ec2.amazonaws.com"
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# IAM Policy for Bedrock Access
resource "aws_iam_policy" "bedrock_policy" {
  name        = "${var.project_name}-bedrock-policy-${var.environment}"
  description = "IAM policy for accessing Amazon Bedrock models and services"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockModelAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
          "bedrock:ListProvisionedModelThroughputs",
          "bedrock:GetProvisionedModelThroughput"
        ]
        Resource = [
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:model/*",
          "arn:aws:bedrock:*::foundation-model/*"
        ]
      },
      {
        Sid    = "BedrockServiceAccess"
        Effect = "Allow"
        Action = [
          "bedrock:ListFoundationModels",
          "bedrock:GetUseCaseForModelAccess",
          "bedrock:ListCustomModels"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogging"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "bedrock_policy_attachment" {
  role       = aws_iam_role.bedrock_role.name
  policy_arn = aws_iam_policy.bedrock_policy.arn
}

# CloudWatch Log Group for Bedrock
resource "aws_cloudwatch_log_group" "bedrock_logs" {
  count = var.enable_cloudwatch_logs ? 1 : 0

  name              = "/aws/bedrock/${var.project_name}/${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-bedrock-logs"
    Service     = "Bedrock"
    Environment = var.environment
  })
}

# Service Quota Request (Note: This is informational - actual quota increases must be requested via AWS Support)
resource "aws_cloudwatch_metric_alarm" "bedrock_throttling" {
  alarm_name          = "${var.project_name}-bedrock-throttling-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ModelInvocationThrottles"
  namespace           = "AWS/Bedrock"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Alarm when Bedrock throttling exceeds threshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  dimensions = {
    ModelId = "*"
  }
}

# CloudWatch Dashboard for Bedrock Monitoring
resource "aws_cloudwatch_dashboard" "bedrock_dashboard" {
  dashboard_name = "${var.project_name}-bedrock-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Bedrock", "InvocationLatency", { stat = "Average" }],
            ["...", { stat = "p99" }]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.name
          title  = "Bedrock Invocation Latency"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/Bedrock", "InvocationCount", { stat = "Sum" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Bedrock Invocation Count"
        }
      }
    ]
  })
}

# Cost Monitoring with AWS Budgets
resource "aws_budgets_budget" "bedrock_budget" {
  count = var.enable_cost_alerts ? 1 : 0

  name         = "${var.project_name}-bedrock-budget-${var.environment}"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_amount
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name = "Service"
    values = [
      "Amazon Bedrock"
    ]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_notification_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_notification_emails
  }
}

# Model Access Status Check (This is a null resource that documents the process)
resource "null_resource" "model_access_documentation" {
  triggers = {
    models = join(",", var.requested_models)
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "================================================================"
      echo "IMPORTANT: Bedrock Model Access Request"
      echo "================================================================"
      echo "The following models need to be manually requested via AWS Console:"
      echo "${join("\n", var.requested_models)}"
      echo ""
      echo "To request access:"
      echo "1. Go to AWS Console > Amazon Bedrock > Model access"
      echo "2. Click 'Manage model access'"
      echo "3. Select the models listed above"
      echo "4. Submit the access request"
      echo "5. Wait for approval (usually instant for most models)"
      echo "================================================================"
    EOT
  }
}

# Service Quota Monitoring
resource "aws_cloudwatch_metric_alarm" "bedrock_request_rate" {
  alarm_name          = "${var.project_name}-bedrock-request-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ModelInvocationCount"
  namespace           = "AWS/Bedrock"
  period              = "60"
  statistic           = "Sum"
  threshold           = "50"  # 50 requests per minute warning
  alarm_description   = "Alert when Bedrock request rate approaches quota"
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
}

resource "aws_cloudwatch_metric_alarm" "bedrock_token_usage" {
  alarm_name          = "${var.project_name}-bedrock-token-usage-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "InputTokenCount"
  namespace           = "AWS/Bedrock"
  period              = "60"
  statistic           = "Sum"
  threshold           = "50000"  # 50k tokens per minute warning
  alarm_description   = "Alert when token usage approaches quota"
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
}

# Documentation for quota increase process
resource "null_resource" "quota_documentation" {
  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "================================================================"
      echo "Service Quota Configuration for Bedrock"
      echo "================================================================"
      echo "Default Quotas:"
      echo "- Requests per minute: 60"
      echo "- Tokens per minute: 60,000"
      echo "- Concurrent requests: 10"
      echo ""
      echo "To increase quotas:"
      echo "1. AWS Console > Service Quotas > Amazon Bedrock"
      echo "2. Or use AWS CLI: aws service-quotas request-service-quota-increase"
      echo "3. Or contact AWS Support for enterprise limits"
      echo "================================================================"
    EOT
  }
}

# Enhanced Cost Monitoring Metrics
resource "aws_cloudwatch_log_metric_filter" "bedrock_token_usage" {
  count = var.enable_cloudwatch_logs ? 1 : 0

  name           = "${var.project_name}-bedrock-token-usage"
  log_group_name = aws_cloudwatch_log_group.bedrock_logs[0].name
  pattern        = "[timestamp, request_id, model_id, input_tokens, output_tokens, cost]"

  metric_transformation {
    name      = "BedrockTokenUsage"
    namespace = "${var.project_name}/Bedrock"
    value     = "$input_tokens"

    dimensions = {
      ModelId = "$model_id"
    }
  }
}

# Cost anomaly detector
resource "aws_ce_anomaly_monitor" "bedrock_costs" {
  count = var.enable_cost_alerts ? 1 : 0

  name              = "${var.project_name}-bedrock-anomaly-${var.environment}"
  monitor_type      = "CUSTOM"
  monitor_frequency = "DAILY"

  monitor_specification = jsonencode({
    Dimensions = {
      Key    = "SERVICE"
      Values = ["Amazon Bedrock"]
    }
  })
}

resource "aws_ce_anomaly_subscription" "bedrock_alerts" {
  count = var.enable_cost_alerts ? 1 : 0

  name      = "${var.project_name}-bedrock-anomaly-alerts"
  frequency = "IMMEDIATE"

  monitor_arn_list = [
    aws_ce_anomaly_monitor.bedrock_costs[0].arn
  ]

  subscriber {
    type    = "EMAIL"
    address = var.budget_notification_emails[0]
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_PERCENTAGE"
      values        = ["20"]
      match_options = ["GREATER_THAN_OR_EQUAL"]
    }
  }
}
