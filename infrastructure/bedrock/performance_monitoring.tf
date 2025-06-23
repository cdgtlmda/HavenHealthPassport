# Model Performance Monitoring Configuration
# Comprehensive monitoring for Bedrock model performance and quality

locals {
  # Performance metrics to track
  performance_metrics = {
    latency_metrics = {
      model_invocation_time = {
        unit        = "Milliseconds"
        statistic   = ["Average", "P50", "P90", "P99"]
        dimensions  = ["ModelKey", "UseCase", "Priority"]
      }

      end_to_end_latency = {
        unit        = "Milliseconds"
        statistic   = ["Average", "P50", "P90", "P99"]
        dimensions  = ["UseCase", "CacheHit"]
      }

      token_generation_rate = {
        unit        = "Count/Second"
        statistic   = ["Average", "Maximum"]
        dimensions  = ["ModelKey"]
      }
    }

    quality_metrics = {
      response_quality_score = {
        unit        = "None"
        statistic   = ["Average", "Minimum"]
        dimensions  = ["ModelKey", "UseCase"]
        threshold   = 0.8
      }

      translation_accuracy = {
        unit        = "Percent"
        statistic   = ["Average"]
        dimensions  = ["SourceLanguage", "TargetLanguage"]
        threshold   = 95
      }

      medical_term_accuracy = {
        unit        = "Percent"
        statistic   = ["Average", "Minimum"]
        dimensions  = ["ModelKey", "Domain"]
        threshold   = 98
      }
    }
    cost_metrics = {
      cost_per_request = {
        unit        = "USD"
        statistic   = ["Average", "Sum"]
        dimensions  = ["ModelKey", "UseCase"]
      }

      token_cost = {
        unit        = "USD"
        statistic   = ["Sum"]
        dimensions  = ["ModelKey", "TokenType"]
      }
    }

    reliability_metrics = {
      error_rate = {
        unit        = "Percent"
        statistic   = ["Average", "Maximum"]
        dimensions  = ["ModelKey", "ErrorType"]
        threshold   = 1  # 1% error rate threshold
      }

      fallback_rate = {
        unit        = "Percent"
        statistic   = ["Average"]
        dimensions  = ["UseCase", "FallbackLevel"]
        threshold   = 5
      }

      circuit_breaker_trips = {
        unit        = "Count"
        statistic   = ["Sum"]
        dimensions  = ["ModelKey"]
      }
    }
  }

  # Alert thresholds
  alert_thresholds = {
    critical = {
      error_rate_percent = 5
      latency_p99_ms    = 10000
      quality_score_min  = 0.7
      cost_spike_factor  = 3
    }

    warning = {
      error_rate_percent = 2
      latency_p99_ms    = 5000
      quality_score_min  = 0.8
      cost_spike_factor  = 2
    }
  }
}
# CloudWatch Dashboard for Bedrock monitoring
resource "aws_cloudwatch_dashboard" "bedrock_performance" {
  dashboard_name = "${var.project_name}-bedrock-performance"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["HavenHealthPassport/Bedrock", "ModelInvocationTime", { stat = "Average" }],
            ["...", { stat = "p99" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Model Invocation Latency"
          yAxis = {
            left = {
              label = "Milliseconds"
            }
          }
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["HavenHealthPassport/Bedrock", "ErrorRate", { stat = "Average" }],
            [".", "FallbackRate", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Error and Fallback Rates"
          yAxis = {
            left = {
              label = "Percentage"
              max   = 10
            }
          }
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["HavenHealthPassport/Bedrock", "CacheHit", { stat = "Sum" }],
            [".", "CacheMiss", { stat = "Sum" }]
          ]          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Cache Performance"
          yAxis = {
            left = {
              label = "Requests"
            }
          }
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["HavenHealthPassport/Bedrock", "ResponseQualityScore", { stat = "Average" }],
            [".", "MedicalTermAccuracy", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Quality Metrics"
          yAxis = {
            left = {
              label = "Score/Percentage"
              min   = 0
              max   = 100
            }
          }
        }
      }
    ]
  })
}

# Lambda function for performance monitoring
resource "aws_lambda_function" "performance_monitor" {
  filename         = data.archive_file.performance_monitor.output_path
  function_name    = "${var.project_name}-bedrock-performance-monitor"
  role            = aws_iam_role.performance_monitor.arn
  handler         = "performance_monitor.handler"
  runtime         = "python3.11"
  timeout         = 300  # 5 minutes for analysis
  memory_size     = 1024

  environment {
    variables = {
      METRICS_CONFIG_JSON = jsonencode(local.performance_metrics)
      THRESHOLD_CONFIG_JSON = jsonencode(local.alert_thresholds)      ANALYSIS_BUCKET = aws_s3_bucket.performance_analysis.id
      SNS_TOPIC_ARN = aws_sns_topic.performance_alerts.arn
      ENVIRONMENT = var.environment
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-performance-monitor"
      Component = "AI-ML"
    }
  )
}

# EventBridge rule for scheduled monitoring
resource "aws_cloudwatch_event_rule" "performance_monitor_schedule" {
  name                = "${var.project_name}-bedrock-performance-schedule"
  description         = "Trigger performance analysis every 5 minutes"
  schedule_expression = "rate(5 minutes)"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-performance-schedule"
    }
  )
}

resource "aws_cloudwatch_event_target" "performance_monitor_target" {
  rule      = aws_cloudwatch_event_rule.performance_monitor_schedule.name
  target_id = "PerformanceMonitorLambda"
  arn       = aws_lambda_function.performance_monitor.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.performance_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.performance_monitor_schedule.arn
}

# S3 bucket for performance analysis storage
resource "aws_s3_bucket" "performance_analysis" {
  bucket = "${var.project_name}-bedrock-performance-analysis"

  tags = merge(
    var.common_tags,
    {      Name      = "${var.project_name}-performance-analysis"
      Component = "AI-ML"
    }
  )
}

# CloudWatch alarms for critical metrics
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.project_name}-bedrock-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ErrorRate"
  namespace           = "HavenHealthPassport/Bedrock"
  period              = "300"
  statistic           = "Average"
  threshold           = local.alert_thresholds.critical.error_rate_percent
  alarm_description   = "Bedrock error rate exceeds critical threshold"

  alarm_actions = [aws_sns_topic.performance_alerts.arn]

  tags = merge(
    var.common_tags,
    {
      Name     = "${var.project_name}-error-rate-alarm"
      Severity = "Critical"
    }
  )
}

resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "${var.project_name}-bedrock-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "ModelInvocationTime"
  namespace           = "HavenHealthPassport/Bedrock"
  period              = "60"
  extended_statistic  = "p99"
  threshold           = local.alert_thresholds.critical.latency_p99_ms
  alarm_description   = "Bedrock P99 latency exceeds critical threshold"

  alarm_actions = [aws_sns_topic.performance_alerts.arn]

  tags = merge(
    var.common_tags,
    {
      Name     = "${var.project_name}-latency-alarm"
      Severity = "Critical"
    }
  )
}
# SNS topic for performance alerts
resource "aws_sns_topic" "performance_alerts" {
  name = "${var.project_name}-bedrock-performance-alerts"

  kms_master_key_id = aws_kms_key.bedrock_config.id

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-performance-alerts"
      Component = "AI-ML"
    }
  )
}

# SNS topic subscription (email)
resource "aws_sns_topic_subscription" "performance_alerts_email" {
  topic_arn = aws_sns_topic.performance_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Outputs
output "dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.bedrock_performance.dashboard_name}"
}

output "performance_monitor_function_arn" {
  description = "ARN of the performance monitor Lambda function"
  value       = aws_lambda_function.performance_monitor.arn
}

output "performance_analysis_bucket" {
  description = "S3 bucket for performance analysis"
  value       = aws_s3_bucket.performance_analysis.id
}

# Variables
variable "alert_email" {
  description = "Email address for performance alerts"
  type        = string
  default     = "alerts@havenhealthpassport.org"
}
