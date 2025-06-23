# Model Inference Parameters Configuration
# This file defines detailed inference parameters for each model type

locals {
  # Base inference parameters by model family
  base_inference_params = {
    claude = {
      # Text generation parameters
      max_tokens        = 4096
      temperature       = 0.7
      top_p            = 1.0
      top_k            = 250
      stop_sequences   = []

      # Advanced parameters
      presence_penalty  = 0.0
      frequency_penalty = 0.0
      repetition_penalty = 1.0

      # Streaming configuration
      stream_enabled    = false
      chunk_size        = 100

      # Token usage limits
      max_input_tokens  = 100000
      token_budget_mode = "strict"  # strict, flexible, unlimited
    }

    titan = {
      # Text generation parameters
      maxTokenCount     = 8192
      temperature       = 0.5
      topP             = 0.9
      stopSequences    = []

      # Titan-specific parameters
      tokenSamplingTopK = 50
      lengthPenalty    = 1.0

      # Response formatting
      outputFormat     = "json"  # json, text
      includeMetadata  = true
    }
    embedding = {
      # Embedding parameters
      dimensions       = 1536
      normalize        = true
      outputFormat     = "float32"  # float32, float16

      # Batch processing
      batch_size       = 25
      max_batch_size   = 100
      parallel_requests = 5
    }
  }

  # Medical domain-specific parameter overrides
  medical_inference_params = {
    # High accuracy for medical content
    medical_analysis = {
      temperature       = 0.2  # Very low for accuracy
      top_p            = 0.9
      top_k            = 100
      max_tokens       = 8192  # Longer for detailed analysis

      # Strict safety parameters
      safety_mode      = "maximum"
      fact_checking    = true
      citation_mode    = "required"

      # Medical terminology handling
      preserve_medical_terms = true
      expand_abbreviations  = true
      include_confidence   = true
    }

    # Translation parameters for medical content
    medical_translation = {
      temperature      = 0.3
      top_p           = 0.95

      # Translation-specific
      preserve_formatting = true
      maintain_terminology = true
      glossary_enforcement = "strict"
      back_translation_check = true

      # Quality thresholds
      min_confidence_score = 0.95
      require_human_review = true
    }
    # Voice processing parameters
    voice_transcription = {
      temperature     = 0.4
      max_tokens     = 2048

      # Voice-specific settings
      handle_accents = true
      noise_tolerance = "high"
      medical_vocabulary = true
      confidence_threshold = 0.85
    }

    # Document analysis parameters
    document_extraction = {
      temperature    = 0.1  # Minimal creativity
      max_tokens    = 16384  # Large documents

      # Extraction settings
      preserve_layout = true
      extract_tables = true
      maintain_formatting = true
      ocr_confidence_min = 0.90
    }
  }

  # Dynamic parameter profiles based on context
  parameter_profiles = {
    emergency = {
      priority         = "speed"
      temperature      = 0.5
      max_tokens      = 1024
      timeout_override = 30  # seconds
      cache_first     = true
    }

    detailed_analysis = {
      priority        = "accuracy"
      temperature     = 0.2
      max_tokens     = 8192
      timeout_override = 600
      multi_pass     = true
    }

    cost_optimized = {
      priority       = "cost"
      temperature    = 0.7
      max_tokens    = 2048
      use_cache     = true
      batch_enabled = true
    }
  }}

# Resource for parameter configuration management
resource "aws_ssm_parameter" "inference_params" {
  for_each = local.medical_inference_params

  name  = "/haven-health-passport/bedrock/inference/${each.key}"
  type  = "String"
  value = jsonencode(each.value)

  description = "Inference parameters for ${each.key} use case"

  tags = merge(
    var.common_tags,
    {
      Name      = "inference-params-${each.key}"
      Component = "AI-ML"
      UseCase   = each.key
    }
  )
}

# Lambda function for parameter selection and merging
resource "aws_lambda_function" "parameter_selector" {
  filename         = data.archive_file.parameter_selector.output_path
  function_name    = "${var.project_name}-bedrock-parameter-selector"
  role            = aws_iam_role.parameter_selector.arn
  handler         = "parameter_selector.handler"
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = 256

  environment {
    variables = {
      BASE_PARAMS_JSON     = jsonencode(local.base_inference_params)
      MEDICAL_PARAMS_JSON  = jsonencode(local.medical_inference_params)
      PROFILES_JSON        = jsonencode(local.parameter_profiles)
      ENVIRONMENT          = var.environment
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-parameter-selector"
      Component = "AI-ML"
    }
  )
}
# CloudWatch Log Group for parameter selector
resource "aws_cloudwatch_log_group" "parameter_selector" {
  name              = "/aws/lambda/${aws_lambda_function.parameter_selector.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.bedrock_config.arn

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-parameter-selector-logs"
      Component = "AI-ML"
    }
  )
}

# Outputs
output "base_inference_params" {
  description = "Base inference parameters by model family"
  value       = local.base_inference_params
}

output "medical_inference_params" {
  description = "Medical domain-specific inference parameters"
  value       = local.medical_inference_params
}

output "parameter_profiles" {
  description = "Dynamic parameter profiles for different contexts"
  value       = local.parameter_profiles
}

output "parameter_selector_arn" {
  description = "ARN of the parameter selector Lambda function"
  value       = aws_lambda_function.parameter_selector.arn
}

output "ssm_parameter_names" {
  description = "SSM parameter names for inference configurations"
  value       = { for k, v in aws_ssm_parameter.inference_params : k => v.name }
}
