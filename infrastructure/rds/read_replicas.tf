# RDS Read Replica Configuration

# Read Replica 1 - Same region
resource "aws_db_instance" "haven_postgres_replica_1" {
  identifier = "${var.project_name}-${var.environment}-postgres-replica-1"

  # Replica configuration
  replicate_source_db = aws_db_instance.haven_postgres_master.identifier

  # Instance configuration
  instance_class = "db.r6g.large"  # 2 vCPUs, 16 GB RAM

  # No need to specify these for replicas - inherited from master
  # engine, engine_version, allocated_storage, etc.

  # Performance and monitoring
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Other settings
  auto_minor_version_upgrade = true
  publicly_accessible = false

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-replica-1"
    Environment = var.environment
    Project     = var.project_name
    Type        = "read-replica"
  }
}

# Read Replica 2 - Different AZ for better distribution
resource "aws_db_instance" "haven_postgres_replica_2" {
  identifier = "${var.project_name}-${var.environment}-postgres-replica-2"

  # Replica configuration
  replicate_source_db = aws_db_instance.haven_postgres_master.identifier

  # Instance configuration
  instance_class = "db.r6g.large"  # 2 vCPUs, 16 GB RAM

  # Performance and monitoring
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # Other settings
  auto_minor_version_upgrade = true
  publicly_accessible = false

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-replica-2"
    Environment = var.environment
    Project     = var.project_name
    Type        = "read-replica"
  }
}
