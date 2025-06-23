# Security Group for RDS PostgreSQL

resource "aws_security_group" "rds_postgres" {
  name        = "${var.project_name}-${var.environment}-rds-postgres"
  description = "Security group for RDS PostgreSQL instance"
  vpc_id      = var.vpc_id

  # Allow PostgreSQL traffic from allowed security groups
  dynamic "ingress" {
    for_each = var.allowed_security_group_ids
    content {
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [ingress.value]
      description     = "PostgreSQL access from application"
    }
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-postgres-sg"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Security group rule for SSL/TLS connections
resource "aws_security_group_rule" "rds_postgres_ssl" {
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  security_group_id = aws_security_group.rds_postgres.id
  self              = true
  description       = "PostgreSQL SSL/TLS connections"
}
