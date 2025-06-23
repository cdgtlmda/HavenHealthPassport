# Amazon Bedrock Model Endpoint Configurations
# This file defines all model endpoints for the Haven Health Passport AI/ML services

locals {
  # Model endpoint configurations for different use cases
  bedrock_model_endpoints = {
    # Claude models for medical text processing
    claude_3_opus = {
      model_id          = "anthropic.claude-3-opus-20240229"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-opus-20240229"
      max_tokens        = 4096
      temperature       = 0.3  # Lower temperature for medical accuracy
      top_p             = 0.9
      stop_sequences    = []
      use_case          = "medical_analysis"
      timeout_seconds   = 300
      retry_attempts    = 3
      cache_enabled     = true
      cache_ttl_seconds = 3600
    }

    claude_3_sonnet = {
      model_id          = "anthropic.claude-3-sonnet-20240229"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-sonnet-20240229"
      max_tokens        = 4096
      temperature       = 0.5
      top_p             = 0.95
      stop_sequences    = []
      use_case          = "general_assistance"
      timeout_seconds   = 180
      retry_attempts    = 3
      cache_enabled     = true
      cache_ttl_seconds = 1800
    }

    claude_instant = {
      model_id          = "anthropic.claude-instant-v1"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-instant-v1"
      max_tokens        = 4096
      temperature       = 0.7
      top_p             = 1.0
      stop_sequences    = []
      use_case          = "quick_responses"
      timeout_seconds   = 60
      retry_attempts    = 2
      cache_enabled     = true
      cache_ttl_seconds = 900
    }
    # Titan models for embeddings and text generation
    titan_text_express = {
      model_id          = "amazon.titan-text-express-v1"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-text-express-v1"
      max_tokens        = 8192
      temperature       = 0.5
      top_p             = 0.9
      stop_sequences    = []
      use_case          = "translation"
      timeout_seconds   = 120
      retry_attempts    = 3
      cache_enabled     = true
      cache_ttl_seconds = 7200
    }

    titan_embeddings_v1 = {
      model_id          = "amazon.titan-embed-text-v1"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1"
      dimensions        = 1536
      normalize         = true
      use_case          = "document_embeddings"
      timeout_seconds   = 30
      retry_attempts    = 3
      cache_enabled     = true
      cache_ttl_seconds = 86400  # 24 hours for embeddings
    }

    titan_embeddings_v2 = {
      model_id          = "amazon.titan-embed-text-v2"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2"
      dimensions        = 1024
      normalize         = true
      use_case          = "semantic_search"
      timeout_seconds   = 30
      retry_attempts    = 3
      cache_enabled     = true
      cache_ttl_seconds = 86400
    }
    # Multimodal models
    claude_3_sonnet_multimodal = {
      model_id          = "anthropic.claude-3-sonnet-20240229"
      model_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-sonnet-20240229"
      max_tokens        = 4096
      temperature       = 0.3
      top_p             = 0.9
      stop_sequences    = []
      use_case          = "medical_image_analysis"
      supports_vision   = true
      max_image_size_mb = 20
      supported_formats = ["image/jpeg", "image/png", "image/webp"]
      timeout_seconds   = 600  # Longer timeout for image processing
      retry_attempts    = 2
      cache_enabled     = false  # No caching for image analysis
    }
  }

  # Model selection rules based on use case
  model_selection_rules = {
    medical_translation = {
      primary_model   = "titan_text_express"
      fallback_model  = "claude_3_sonnet"
      quality_check   = "claude_3_opus"
    }

    medical_qa = {
      primary_model   = "claude_3_opus"
      fallback_model  = "claude_3_sonnet"
      quality_check   = null
    }

    document_analysis = {
      primary_model   = "claude_3_sonnet_multimodal"
      fallback_model  = "claude_3_sonnet"
      quality_check   = "claude_3_opus"
    }

    general_chat = {
      primary_model   = "claude_instant"
      fallback_model  = "claude_3_sonnet"
      quality_check   = null
    }

    embeddings = {
      primary_model   = "titan_embeddings_v2"
      fallback_model  = "titan_embeddings_v1"
      quality_check   = null
    }
  }
  # Rate limiting configurations per model
  rate_limits = {
    claude_3_opus = {
      requests_per_minute = 10
      tokens_per_minute   = 40000
      burst_capacity      = 5
    }

    claude_3_sonnet = {
      requests_per_minute = 50
      tokens_per_minute   = 200000
      burst_capacity      = 10
    }

    claude_instant = {
      requests_per_minute = 100
      tokens_per_minute   = 400000
      burst_capacity      = 20
    }

    titan_text_express = {
      requests_per_minute = 100
      tokens_per_minute   = 800000
      burst_capacity      = 20
    }

    titan_embeddings_v1 = {
      requests_per_minute = 500
      tokens_per_minute   = 1000000
      burst_capacity      = 50
    }

    titan_embeddings_v2 = {
      requests_per_minute = 500
      tokens_per_minute   = 1000000
      burst_capacity      = 50
    }
  }
  # Cost optimization rules
  cost_optimization = {
    enable_caching           = true
    cache_similarity_threshold = 0.95
    batch_embedding_requests = true
    batch_size_limit        = 25
    use_spot_inference      = false  # Not available for Bedrock
    compress_responses      = true

    # Model routing based on request complexity
    complexity_routing = {
      simple_requests = "claude_instant"
      medium_requests = "claude_3_sonnet"
      complex_requests = "claude_3_opus"
    }
  }
}

# DynamoDB table for endpoint configuration versioning
resource "aws_dynamodb_table" "bedrock_endpoint_config" {
  name           = "${var.project_name}-bedrock-endpoint-config"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "config_id"
  range_key      = "version"

  attribute {
    name = "config_id"
    type = "S"
  }

  attribute {
    name = "version"
    type = "N"
  }

  attribute {
    name = "active"
    type = "S"
  }

  global_secondary_index {
    name            = "active-configs-index"
    hash_key        = "active"
    projection_type = "ALL"
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
      Name        = "${var.project_name}-bedrock-endpoint-config"
      Component   = "AI-ML"
      Compliance  = "HIPAA"
    }
  )
}

# KMS key for endpoint configuration encryption
resource "aws_kms_key" "bedrock_config" {
  description             = "KMS key for Bedrock endpoint configuration encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-bedrock-config-key"
      Component = "AI-ML"
    }
  )
}

# Lambda function for dynamic endpoint selection
resource "aws_lambda_function" "endpoint_selector" {
  filename         = data.archive_file.endpoint_selector.output_path
  function_name    = "${var.project_name}-bedrock-endpoint-selector"
  role            = aws_iam_role.endpoint_selector.arn
  handler         = "index.handler"
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = 512

  environment {
    variables = {
      CONFIG_TABLE_NAME = aws_dynamodb_table.bedrock_endpoint_config.name
      REGION           = var.aws_region
      ENVIRONMENT      = var.environment
    }
  }
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-endpoint-selector"
      Component = "AI-ML"
    }
  )
}

# CloudWatch Log Group for endpoint metrics
resource "aws_cloudwatch_log_group" "bedrock_endpoints" {
  name              = "/aws/lambda/${aws_lambda_function.endpoint_selector.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.bedrock_config.arn

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-bedrock-endpoint-logs"
      Component = "AI-ML"
    }
  )
}

# Outputs for use by other modules
output "model_endpoints" {
  description = "Map of all configured model endpoints"
  value       = local.bedrock_model_endpoints
  sensitive   = false
}

output "model_selection_rules" {
  description = "Model selection rules for different use cases"
  value       = local.model_selection_rules
}

output "endpoint_selector_function_arn" {
  description = "ARN of the endpoint selector Lambda function"
  value       = aws_lambda_function.endpoint_selector.arn
}

output "config_table_name" {
  description = "Name of the DynamoDB table storing endpoint configurations"
  value       = aws_dynamodb_table.bedrock_endpoint_config.name
}
