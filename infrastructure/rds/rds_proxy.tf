# RDS Proxy for Connection Pooling

resource "aws_db_proxy" "haven_postgres" {
  name                   = "${var.project_name}-${var.environment}-postgres-proxy"
  engine_family         = "POSTGRESQL"
  auth {
    auth_scheme = "SECRETS"
    secret_arn  = aws_secretsmanager_secret.rds_credentials.arn
  }

  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids         = var.subnet_ids

  # Connection pooling settings
  max_connections_percent       = 100
  max_idle_connections_percent  = 50
  connection_borrow_timeout     = 120

  require_tls = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-proxy"
    Environment = var.environment
    Project     = var.project_name
  }
}

# RDS Proxy Target
resource "aws_db_proxy_target" "haven_postgres" {
  db_instance_identifier = aws_db_instance.haven_postgres_master.id
  db_proxy_name         = aws_db_proxy.haven_postgres.name
  target_arn           = aws_db_instance.haven_postgres_master.arn
}

# IAM Role for RDS Proxy
resource "aws_iam_role" "rds_proxy" {
  name = "${var.project_name}-${var.environment}-rds-proxy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for RDS Proxy
resource "aws_iam_role_policy" "rds_proxy" {
  name = "${var.project_name}-${var.environment}-rds-proxy-policy"
  role = aws_iam_role.rds_proxy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.rds_credentials.arn
      }
    ]
  })
}
