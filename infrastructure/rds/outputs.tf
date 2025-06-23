# Outputs for RDS Infrastructure

output "rds_master_endpoint" {
  description = "RDS master instance endpoint"
  value       = aws_db_instance.haven_postgres_master.endpoint
  sensitive   = false
}

output "rds_master_address" {
  description = "RDS master instance address"
  value       = aws_db_instance.haven_postgres_master.address
  sensitive   = false
}

output "rds_proxy_endpoint" {
  description = "RDS Proxy endpoint for connection pooling"
  value       = aws_db_proxy.haven_postgres.endpoint
  sensitive   = false
}

output "rds_replica_endpoints" {
  description = "RDS read replica endpoints"
  value = {
    replica_1 = aws_db_instance.haven_postgres_replica_1.endpoint
    replica_2 = aws_db_instance.haven_postgres_replica_2.endpoint
  }
  sensitive = false
}

output "rds_security_group_id" {
  description = "Security group ID for RDS instances"
  value       = aws_security_group.rds_postgres.id
}

output "rds_kms_key_id" {
  description = "KMS key ID for RDS encryption"
  value       = aws_kms_key.rds_encryption.id
}

output "rds_backup_bucket" {
  description = "S3 bucket for RDS backups"
  value       = aws_s3_bucket.rds_backups.id
}

output "rds_credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret for RDS credentials"
  value       = aws_secretsmanager_secret.rds_credentials.arn
  sensitive   = true
}
