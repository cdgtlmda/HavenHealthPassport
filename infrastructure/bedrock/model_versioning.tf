# Model Versioning Strategy for Amazon Bedrock
# Implements version control, rollback capabilities, and A/B testing for AI models

locals {
  # Model version mapping with metadata
  model_versions = {
    # Claude model versions
    claude_versions = {
      stable = {
        model_id      = "anthropic.claude-3-opus-20240229"
        version       = "20240229"
        release_date  = "2024-02-29"
        status        = "stable"
        capabilities  = ["text", "analysis", "code"]
        deprecation   = null
      }

      preview = {
        model_id      = "anthropic.claude-3-opus-20240229"  # Same as stable for now
        version       = "20240229"
        release_date  = "2024-02-29"
        status        = "preview"
        capabilities  = ["text", "analysis", "code", "experimental"]
        deprecation   = null
      }

      legacy = {
        model_id      = "anthropic.claude-instant-v1"
        version       = "v1"
        release_date  = "2023-01-01"
        status        = "deprecated"
        capabilities  = ["text"]
        deprecation   = "2024-12-31"
      }
    }

    # Titan model versions
    titan_versions = {
      stable = {
        model_id      = "amazon.titan-text-express-v1"
        version       = "v1"
        release_date  = "2023-09-28"
        status        = "stable"
        capabilities  = ["text", "translation"]
        deprecation   = null
      }
      embeddings_stable = {
        model_id      = "amazon.titan-embed-text-v2"
        version       = "v2"
        release_date  = "2024-01-15"
        status        = "stable"
        capabilities  = ["embeddings"]
        deprecation   = null
      }
    }
  }

  # Version selection strategy
  version_strategy = {
    default_channel = "stable"

    channels = {
      stable = {
        description = "Production-ready models with proven reliability"
        auto_update = false
        min_testing_days = 30
      }

      preview = {
        description = "Preview features and new models for testing"
        auto_update = true
        min_testing_days = 7
      }

      legacy = {
        description = "Deprecated models for backward compatibility"
        auto_update = false
        min_testing_days = 0
      }
    }

    rollback_policy = {
      enabled = true
      retention_days = 90
      max_rollback_versions = 3
    }
  }
}

# DynamoDB table for version history
resource "aws_dynamodb_table" "model_version_history" {
  name           = "${var.project_name}-model-version-history"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "model_family"
  range_key      = "timestamp"
  attribute {
    name = "model_family"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expiration"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.bedrock_config.arn
  }

  tags = merge(
    var.common_tags,
    {
      Name        = "${var.project_name}-model-version-history"
      Component   = "AI-ML"
      Compliance  = "HIPAA"
    }
  )
}

# Lambda function for version management
resource "aws_lambda_function" "version_manager" {
  filename         = data.archive_file.version_manager.output_path
  function_name    = "${var.project_name}-bedrock-version-manager"  role            = aws_iam_role.version_manager.arn
  handler         = "version_manager.handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = 512

  environment {
    variables = {
      VERSION_TABLE_NAME = aws_dynamodb_table.model_version_history.name
      CONFIG_TABLE_NAME  = aws_dynamodb_table.bedrock_endpoint_config.name
      REGION            = var.aws_region
      ENVIRONMENT       = var.environment
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-version-manager"
      Component = "AI-ML"
    }
  )
}

# CloudWatch Log Group for version manager
resource "aws_cloudwatch_log_group" "version_manager" {
  name              = "/aws/lambda/${aws_lambda_function.version_manager.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.bedrock_config.arn

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-version-manager-logs"
      Component = "AI-ML"
    }
  )
}
# A/B Testing Configuration
resource "aws_ssm_parameter" "ab_test_config" {
  name  = "/haven-health-passport/bedrock/ab-testing/config"
  type  = "String"

  value = jsonencode({
    active_tests = []
    default_split = {
      control = 90
      test    = 10
    }
    metrics = [
      "latency",
      "accuracy",
      "user_satisfaction",
      "cost_per_request"
    ]
  })

  description = "A/B testing configuration for model versions"

  tags = merge(
    var.common_tags,
    {
      Name      = "bedrock-ab-test-config"
      Component = "AI-ML"
    }
  )
}

# Outputs
output "model_versions" {
  description = "Available model versions by family"
  value       = local.model_versions
}

output "version_strategy" {
  description = "Model version selection strategy"
  value       = local.version_strategy
}

output "version_history_table" {
  description = "DynamoDB table for version history"
  value       = aws_dynamodb_table.model_version_history.name
}

output "version_manager_function_arn" {
  description = "ARN of the version manager Lambda function"
  value       = aws_lambda_function.version_manager.arn
}
