# Lambda Function for Log Processing
resource "aws_lambda_function" "log_processor" {
  filename         = "${path.module}/lambda/log-processor.zip"
  function_name    = "${var.project_name}-log-processor"
  role            = aws_iam_role.log_processor.arn
  handler         = "index.handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 1024

  environment {
    variables = {
      CORRELATION_RULES = jsonencode(var.correlation_rules)
      ALERT_THRESHOLD   = var.alert_threshold
    }
  }

  tags = var.common_tags
}

# Quarantine Security Group
resource "aws_security_group" "quarantine" {
  name        = "${var.project_name}-quarantine-sg"
  description = "Security group for quarantined resources"
  vpc_id      = var.vpc_id

  # No ingress rules - complete isolation

  egress {
    description = "Allow DNS"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.project_name}-quarantine-sg"
    }
  )
}
