# Main RDS PostgreSQL Instance Configuration

# RDS Master Instance
resource "aws_db_instance" "haven_postgres_master" {
  identifier = "${var.project_name}-${var.environment}-postgres-master"

  # Engine configuration
  engine               = "postgres"
  engine_version       = "14.10"
  instance_class       = "db.r6g.xlarge"  # 4 vCPUs, 32 GB RAM
  allocated_storage    = 500
  storage_type         = "gp3"
  storage_encrypted    = true
  kms_key_id          = aws_kms_key.rds_encryption.arn
  iops                = 12000

  # Database configuration
  db_name  = var.database_name
  username = var.database_username
  password = var.database_password
  port     = 5432

  # Multi-AZ deployment for high availability
  multi_az               = true
  availability_zone      = null  # Let AWS choose for Multi-AZ
  db_subnet_group_name   = aws_db_subnet_group.haven_postgres.name
  vpc_security_group_ids = [aws_security_group.rds_postgres.id]

  # Parameter and option groups
  parameter_group_name = aws_db_parameter_group.haven_postgres.name

  # Backup configuration
  backup_retention_period   = 35  # 35 days retention
  backup_window            = "03:00-04:00"  # UTC
  maintenance_window       = "sun:04:00-sun:05:00"  # UTC
  skip_final_snapshot      = false
  final_snapshot_identifier = "${var.project_name}-${var.environment}-postgres-final-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = true
  performance_insights_retention_period = 7  # days
  monitoring_interval            = 60
  monitoring_role_arn           = aws_iam_role.rds_monitoring.arn

  # Other settings
  auto_minor_version_upgrade = true
  deletion_protection       = true
  copy_tags_to_snapshot    = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-master"
    Environment = var.environment
    Project     = var.project_name
    Type        = "master"
  }
}
