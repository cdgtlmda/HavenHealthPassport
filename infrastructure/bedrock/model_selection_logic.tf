# Model Selection Logic Configuration

resource "aws_lambda_function" "model_selector" {
  filename         = data.archive_file.model_selector.output_path
  function_name    = "${var.project_name}-bedrock-model-selector"
  role            = aws_iam_role.model_selector.arn
  handler         = "model_selector.handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = 512

  environment {
    variables = {
      ENDPOINT_SELECTOR_ARN     = aws_lambda_function.endpoint_selector.arn
      PARAMETER_SELECTOR_ARN    = aws_lambda_function.parameter_selector.arn
      VERSION_MANAGER_ARN       = aws_lambda_function.version_manager.arn
      FALLBACK_ORCHESTRATOR_ARN = aws_lambda_function.fallback_orchestrator.arn
      ENVIRONMENT              = var.environment
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  tags = merge(var.common_tags, {
    Name      = "${var.project_name}-model-selector"
    Component = "AI-ML"
  })
}

resource "aws_cloudwatch_log_group" "model_selector" {
  name              = "/aws/lambda/${aws_lambda_function.model_selector.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.bedrock_config.arn

  tags = merge(var.common_tags, {
    Name      = "${var.project_name}-model-selector-logs"
    Component = "AI-ML"
  })
}

output "model_selector_function_arn" {
  description = "ARN of the model selector Lambda function"
  value       = aws_lambda_function.model_selector.arn
}
