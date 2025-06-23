# RDS Parameter Group Configuration

resource "aws_db_parameter_group" "haven_postgres" {
  name   = "${var.project_name}-${var.environment}-postgres14"
  family = "postgres14"

  # Connection pooling settings
  parameter {
    name  = "max_connections"
    value = "1000"
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pglogical"
  }

  # Performance tuning
  parameter {
    name  = "shared_buffers"
    value = "{DBInstanceClassMemory/4}"
  }

  parameter {
    name  = "effective_cache_size"
    value = "{DBInstanceClassMemory*3/4}"
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "2097152"  # 2GB in KB
  }

  parameter {
    name  = "work_mem"
    value = "32768"  # 32MB in KB
  }

  # Logging
  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking more than 1 second
  }

  # SSL/TLS enforcement
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-params"
    Environment = var.environment
    Project     = var.project_name
  }
}

# RDS Subnet Group
resource "aws_db_subnet_group" "haven_postgres" {
  name       = "${var.project_name}-${var.environment}-postgres"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-subnet-group"
    Environment = var.environment
    Project     = var.project_name
  }
}
