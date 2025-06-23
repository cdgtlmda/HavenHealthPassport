# Fallback Model Configurations for Amazon Bedrock
# Implements resilient model selection with automatic failover

locals {
  # Fallback chain definitions for each use case
  fallback_chains = {
    medical_analysis = {
      primary = {
        model_key    = "claude_3_opus"
        max_retries  = 3
        timeout_ms   = 300000  # 5 minutes
      }
      secondary = {
        model_key    = "claude_3_sonnet"
        max_retries  = 2
        timeout_ms   = 180000  # 3 minutes
      }
      tertiary = {
        model_key    = "claude_instant"
        max_retries  = 1
        timeout_ms   = 60000   # 1 minute
      }
      final_fallback = {
        model_key    = "cached_response"
        max_retries  = 1
        timeout_ms   = 5000    # 5 seconds
      }
    }

    medical_translation = {
      primary = {
        model_key    = "titan_text_express"
        max_retries  = 3
        timeout_ms   = 120000  # 2 minutes
      }
      secondary = {
        model_key    = "claude_3_sonnet"
        max_retries  = 2
        timeout_ms   = 120000
      }
      tertiary = {
        model_key    = "claude_instant"
        max_retries  = 1
        timeout_ms   = 60000
      }
    }
    document_analysis = {
      primary = {
        model_key    = "claude_3_sonnet_multimodal"
        max_retries  = 2
        timeout_ms   = 600000  # 10 minutes for images
      }
      secondary = {
        model_key    = "claude_3_sonnet"
        max_retries  = 2
        timeout_ms   = 180000
      }
    }

    embeddings = {
      primary = {
        model_key    = "titan_embeddings_v2"
        max_retries  = 3
        timeout_ms   = 30000
      }
      secondary = {
        model_key    = "titan_embeddings_v1"
        max_retries  = 3
        timeout_ms   = 30000
      }
    }
  }

  # Fallback triggers and conditions
  fallback_triggers = {
    error_codes = [
      "ThrottlingException",
      "ServiceUnavailableException",
      "ModelTimeoutException",
      "ResourceNotFoundException"
    ]

    latency_threshold_ms = 10000  # 10 seconds

    error_rate_threshold = 0.1    # 10% error rate

    cost_threshold_multiplier = 2.0  # 2x expected cost
  }

  # Circuit breaker configuration
  circuit_breaker = {
    failure_threshold = 5
    success_threshold = 2
    timeout_seconds   = 60
    half_open_requests = 3
  }
}
# DynamoDB table for fallback state management
resource "aws_dynamodb_table" "fallback_state" {
  name           = "${var.project_name}-bedrock-fallback-state"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "model_key"
  range_key      = "timestamp"

  attribute {
    name = "model_key"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  ttl {
    attribute_name = "expiration"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.bedrock_config.arn
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-fallback-state"
      Component   = "AI-ML"
    }
  )
}

# Lambda function for fallback orchestration
resource "aws_lambda_function" "fallback_orchestrator" {
  filename         = data.archive_file.fallback_orchestrator.output_path
  function_name    = "${var.project_name}-bedrock-fallback-orchestrator"
  role            = aws_iam_role.fallback_orchestrator.arn
  handler         = "fallback_orchestrator.handler"
  runtime         = "python3.11"
  timeout         = 900  # 15 minutes max
  memory_size     = 1024

  environment {
    variables = {
      FALLBACK_CHAINS_JSON = jsonencode(local.fallback_chains)
      FALLBACK_TRIGGERS_JSON = jsonencode(local.fallback_triggers)      CIRCUIT_BREAKER_JSON = jsonencode(local.circuit_breaker)
      FALLBACK_STATE_TABLE = aws_dynamodb_table.fallback_state.name
      CACHE_BUCKET = var.cache_bucket_name
      ENVIRONMENT = var.environment
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-fallback-orchestrator"
      Component = "AI-ML"
    }
  )
}

# CloudWatch alarms for fallback triggers
resource "aws_cloudwatch_metric_alarm" "model_error_rate" {
  for_each            = local.bedrock_model_endpoints
  alarm_name          = "${var.project_name}-bedrock-${each.key}-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ModelErrors"
  namespace           = "HavenHealthPassport/Bedrock"
  period              = "300"
  statistic           = "Average"
  threshold           = local.fallback_triggers.error_rate_threshold * 100
  alarm_description   = "Model error rate exceeds threshold"

  dimensions = {
    ModelKey = each.key
    Environment = var.environment
  }

  alarm_actions = [aws_sns_topic.fallback_alerts.arn]

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-${each.key}-error-alarm"
      Component = "AI-ML"
    }
  )
}
# SNS topic for fallback alerts
resource "aws_sns_topic" "fallback_alerts" {
  name = "${var.project_name}-bedrock-fallback-alerts"

  kms_master_key_id = aws_kms_key.bedrock_config.id

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-fallback-alerts"
      Component = "AI-ML"
    }
  )
}

# Outputs
output "fallback_chains" {
  description = "Fallback chain configurations by use case"
  value       = local.fallback_chains
}

output "fallback_triggers" {
  description = "Conditions that trigger fallback behavior"
  value       = local.fallback_triggers
}

output "circuit_breaker_config" {
  description = "Circuit breaker configuration"
  value       = local.circuit_breaker
}

output "fallback_orchestrator_arn" {
  description = "ARN of the fallback orchestrator Lambda"
  value       = aws_lambda_function.fallback_orchestrator.arn
}

output "fallback_state_table" {
  description = "DynamoDB table for fallback state management"
  value       = aws_dynamodb_table.fallback_state.name
}

# Variable for cache bucket
variable "cache_bucket_name" {
  description = "S3 bucket name for response caching"
  type        = string
  default     = ""
}
