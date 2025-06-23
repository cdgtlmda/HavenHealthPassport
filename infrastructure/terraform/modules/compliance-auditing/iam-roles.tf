# IAM Roles for Compliance and Auditing

# IAM Role for Audit Processor Lambda
resource "aws_iam_role" "audit_processor" {
  name = "${var.project_name}-audit-processor-role"

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

# IAM Policy for Audit Processor
resource "aws_iam_role_policy" "audit_processor" {
  name = "${var.project_name}-audit-processor-policy"
  role = aws_iam_role.audit_processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeStream",
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:ListStreams",
          "s3:PutObject",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "sns:Publish",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}
# IAM Role for Config Recorder
resource "aws_iam_role" "config_recorder" {
  name = "${var.project_name}-config-recorder-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

# Attach AWS managed policy for Config
resource "aws_iam_role_policy_attachment" "config_recorder" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/ConfigRole"
  role       = aws_iam_role.config_recorder.name
}

# IAM Role for Drift Detector Lambda
resource "aws_iam_role" "drift_detector" {
  name = "${var.project_name}-drift-detector-role"

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

# IAM Role for Audit Reporter Lambda
resource "aws_iam_role" "audit_reporter" {
  name = "${var.project_name}-audit-reporter-role"

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
