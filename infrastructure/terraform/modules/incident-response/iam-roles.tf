# IAM Roles for Incident Response Module

# IAM Role for Post-Mortem Processor
resource "aws_iam_role" "postmortem_processor" {
  name = "${var.project_name}-postmortem-processor-role"

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

# IAM Policy for Post-Mortem Processor
resource "aws_iam_role_policy" "postmortem_processor" {
  name = "${var.project_name}-postmortem-processor-policy"
  role = aws_iam_role.postmortem_processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}
