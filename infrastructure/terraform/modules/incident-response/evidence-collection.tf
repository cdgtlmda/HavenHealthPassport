# Evidence Collection Configuration

# Lambda Function for Evidence Collection
resource "aws_lambda_function" "evidence_collector" {
  filename         = "${path.module}/lambda/evidence-collector.zip"
  function_name    = "${var.project_name}-evidence-collector"
  role            = aws_iam_role.evidence_collector.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 900  # 15 minutes for large evidence collection
  memory_size     = 3008

  environment {
    variables = {
      FORENSICS_BUCKET = aws_s3_bucket.forensics.id
      KMS_KEY_ID      = var.kms_key_arn
    }
  }

  tags = var.common_tags
}

# IAM Role for Evidence Collector
resource "aws_iam_role" "evidence_collector" {
  name = "${var.project_name}-evidence-collector-role"

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
# IAM Policy for Evidence Collector
resource "aws_iam_role_policy" "evidence_collector" {
  name = "${var.project_name}-evidence-collector-policy"
  role = aws_iam_role.evidence_collector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSnapshot",
          "ec2:DescribeInstances",
          "ec2:DescribeSnapshots",
          "ec2:DescribeVolumes",
          "ec2:CreateTags"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:PutObjectLegalHold",
          "s3:PutObjectRetention"
        ]
        Resource = "${aws_s3_bucket.forensics.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:GetLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}
