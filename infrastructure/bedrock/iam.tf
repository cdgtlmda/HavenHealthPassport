# Data source for Lambda deployment package
data "archive_file" "endpoint_selector" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_endpoint_selector.zip"
}

# IAM role for Lambda function
resource "aws_iam_role" "endpoint_selector" {
  name = "${var.project_name}-bedrock-endpoint-selector-role"

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

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-endpoint-selector-role"
      Component = "AI-ML"
    }
  )
}

# IAM policy for Lambda function
resource "aws_iam_role_policy" "endpoint_selector" {
  name = "${var.project_name}-bedrock-endpoint-selector-policy"
  role = aws_iam_role.endpoint_selector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.bedrock_endpoint_config.arn,
          "${aws_dynamodb_table.bedrock_endpoint_config.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}
# Security group for Lambda function
resource "aws_security_group" "lambda_sg" {
  name        = "${var.project_name}-bedrock-lambda-sg"
  description = "Security group for Bedrock endpoint selector Lambda"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS to AWS services"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "DNS"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "DNS"
  }

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-bedrock-lambda-sg"
      Component = "AI-ML"
    }
  )
}

# Add VPC ID variable
variable "vpc_id" {
  description = "VPC ID for Lambda deployment"
  type        = string
}
# Data source for parameter selector Lambda
data "archive_file" "parameter_selector" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_parameter_selector.zip"

  excludes = [
    "index.py",
    "requirements.txt"
  ]
}

# IAM role for parameter selector Lambda
resource "aws_iam_role" "parameter_selector" {
  name = "${var.project_name}-bedrock-parameter-selector-role"

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

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-parameter-selector-role"
      Component = "AI-ML"
    }
  )
}

# IAM policy for parameter selector
resource "aws_iam_role_policy" "parameter_selector" {
  name = "${var.project_name}-bedrock-parameter-selector-policy"
  role = aws_iam_role.parameter_selector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/haven-health-passport/bedrock/inference/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}
# Data source for version manager Lambda
data "archive_file" "version_manager" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_version_manager.zip"

  excludes = [
    "index.py",
    "parameter_selector.py",
    "requirements.txt"
  ]
}

# IAM role for version manager Lambda
resource "aws_iam_role" "version_manager" {
  name = "${var.project_name}-bedrock-version-manager-role"

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

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-version-manager-role"
      Component = "AI-ML"
    }
  )
}

# IAM policy for version manager
resource "aws_iam_role_policy" "version_manager" {
  name = "${var.project_name}-bedrock-version-manager-policy"
  role = aws_iam_role.version_manager.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:PutItem"
        ]        Resource = [
          aws_dynamodb_table.model_version_history.arn,
          "${aws_dynamodb_table.model_version_history.arn}/index/*",
          aws_dynamodb_table.bedrock_endpoint_config.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/haven-health-passport/bedrock/ab-testing/*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}
# Data source for fallback orchestrator Lambda
data "archive_file" "fallback_orchestrator" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_fallback_orchestrator.zip"

  excludes = [
    "index.py",
    "parameter_selector.py",
    "version_manager.py",
    "requirements.txt"
  ]
}

# IAM role for fallback orchestrator
resource "aws_iam_role" "fallback_orchestrator" {
  name = "${var.project_name}-bedrock-fallback-orchestrator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-fallback-orchestrator-role"
      Component = "AI-ML"
    }
  )
}

# IAM policy for fallback orchestrator
resource "aws_iam_role_policy" "fallback_orchestrator" {
  name = "${var.project_name}-bedrock-fallback-orchestrator-policy"
  role = aws_iam_role.fallback_orchestrator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.fallback_state.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = var.cache_bucket_name != "" ? "arn:aws:s3:::${var.cache_bucket_name}/bedrock-cache/*" : "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}
# Data source for model selector Lambda
data "archive_file" "model_selector" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_model_selector.zip"

  excludes = [
    "index.py",
    "parameter_selector.py",
    "version_manager.py",
    "fallback_orchestrator.py",
    "requirements.txt"
  ]
}

# IAM role for model selector
resource "aws_iam_role" "model_selector" {
  name = "${var.project_name}-bedrock-model-selector-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(var.common_tags, {
    Name      = "${var.project_name}-model-selector-role"
    Component = "AI-ML"
  })
}

# IAM policy for model selector
resource "aws_iam_role_policy" "model_selector" {
  name = "${var.project_name}-bedrock-model-selector-policy"
  role = aws_iam_role.model_selector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.endpoint_selector.arn,
          aws_lambda_function.parameter_selector.arn,
          aws_lambda_function.version_manager.arn,
          aws_lambda_function.fallback_orchestrator.arn
        ]
      },
      {
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}
# Data source for cache manager Lambda
data "archive_file" "cache_manager" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_cache_manager.zip"

  excludes = [
    "index.py",
    "parameter_selector.py",
    "version_manager.py",
    "fallback_orchestrator.py",
    "model_selector.py"
  ]
}

# IAM role for cache manager
resource "aws_iam_role" "cache_manager" {
  name = "${var.project_name}-bedrock-cache-manager-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(var.common_tags, {
    Name      = "${var.project_name}-cache-manager-role"
    Component = "AI-ML"
  })
}

# IAM policy for cache manager
resource "aws_iam_role_policy" "cache_manager" {
  name = "${var.project_name}-bedrock-cache-manager-policy"
  role = aws_iam_role.cache_manager.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "elasticache:DescribeCacheClusters",
          "elasticache:DescribeReplicationGroups"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.bedrock_cache.arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.cache_auth_token.arn
      },
      {
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}
# Data source for performance monitor Lambda
data "archive_file" "performance_monitor" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_performance_monitor.zip"

  excludes = [
    "index.py",
    "parameter_selector.py",
    "version_manager.py",
    "fallback_orchestrator.py",
    "model_selector.py",
    "cache_manager.py"
  ]
}

# IAM role for performance monitor
resource "aws_iam_role" "performance_monitor" {
  name = "${var.project_name}-bedrock-performance-monitor-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(var.common_tags, {
    Name      = "${var.project_name}-performance-monitor-role"
    Component = "AI-ML"
  })
}

# IAM policy for performance monitor
resource "aws_iam_role_policy" "performance_monitor" {
  name = "${var.project_name}-bedrock-performance-monitor-policy"
  role = aws_iam_role.performance_monitor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "cloudwatch:PutMetricData"
        ]        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.performance_analysis.arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = aws_sns_topic.performance_alerts.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.bedrock_config.arn
      }
    ]
  })
}

# CloudWatch Log Group for performance monitor
resource "aws_cloudwatch_log_group" "performance_monitor" {
  name              = "/aws/lambda/${aws_lambda_function.performance_monitor.function_name}"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.bedrock_config.arn

  tags = merge(
    var.common_tags,
    {
      Name      = "${var.project_name}-performance-monitor-logs"
      Component = "AI-ML"
    }
  )
}
