# CloudWatch Alarms for RDS Monitoring

# CPU Utilization Alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"
  alarm_actions       = [aws_sns_topic.rds_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.haven_postgres_master.id
  }
}

# Database Connection Alarm
resource "aws_cloudwatch_metric_alarm" "rds_connection_high" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "800"  # 80% of max_connections (1000)
  alarm_description   = "This metric monitors RDS connection count"
  alarm_actions       = [aws_sns_topic.rds_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.haven_postgres_master.id
  }
}

# Free Storage Space Alarm
resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "53687091200"  # 50 GB in bytes
  alarm_description   = "This metric monitors RDS free storage"
  alarm_actions       = [aws_sns_topic.rds_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.haven_postgres_master.id
  }
}

# Read Replica Lag Alarm
resource "aws_cloudwatch_metric_alarm" "rds_replica_lag" {
  count               = 2  # For both replicas
  alarm_name          = "${var.project_name}-${var.environment}-rds-replica-${count.index + 1}-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReplicaLag"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "60"  # 60 seconds
  alarm_description   = "This metric monitors RDS replica lag"
  alarm_actions       = [aws_sns_topic.rds_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = count.index == 0 ? aws_db_instance.haven_postgres_replica_1.id : aws_db_instance.haven_postgres_replica_2.id
  }
}

# SNS Topic for RDS Alerts
resource "aws_sns_topic" "rds_alerts" {
  name = "${var.project_name}-${var.environment}-rds-alerts"

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-alerts"
    Environment = var.environment
    Project     = var.project_name
  }
}

# SNS Topic Subscription
resource "aws_sns_topic_subscription" "rds_alerts_email" {
  topic_arn = aws_sns_topic.rds_alerts.arn
  protocol  = "email"
  endpoint  = "devops@havenhealthpassport.org"
}
