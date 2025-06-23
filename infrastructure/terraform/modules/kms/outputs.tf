# Outputs for KMS module

output "main_key_id" {
  description = "ID of the main KMS key"
  value       = aws_kms_key.main.id
}

output "main_key_arn" {
  description = "ARN of the main KMS key"
  value       = aws_kms_key.main.arn
}

output "main_key_alias" {
  description = "Alias of the main KMS key"
  value       = aws_kms_alias.main.name
}

output "s3_key_id" {
  description = "ID of the S3 KMS key"
  value       = aws_kms_key.s3.id
}

output "s3_key_arn" {
  description = "ARN of the S3 KMS key"
  value       = aws_kms_key.s3.arn
}

output "s3_key_alias" {
  description = "Alias of the S3 KMS key"
  value       = aws_kms_alias.s3.name
}

output "rds_key_id" {
  description = "ID of the RDS KMS key"
  value       = aws_kms_key.rds.id
}

output "rds_key_arn" {
  description = "ARN of the RDS KMS key"
  value       = aws_kms_key.rds.arn
}

output "rds_key_alias" {
  description = "Alias of the RDS KMS key"
  value       = aws_kms_alias.rds.name
}

output "secrets_key_id" {
  description = "ID of the Secrets Manager KMS key"
  value       = aws_kms_key.secrets.id
}

output "secrets_key_arn" {
  description = "ARN of the Secrets Manager KMS key"
  value       = aws_kms_key.secrets.arn
}

output "secrets_key_alias" {
  description = "Alias of the Secrets Manager KMS key"
  value       = aws_kms_alias.secrets.name
}

output "app_key_id" {
  description = "ID of the application KMS key"
  value       = aws_kms_key.app.id
}

output "app_key_arn" {
  description = "ARN of the application KMS key"
  value       = aws_kms_key.app.arn
}

output "app_key_alias" {
  description = "Alias of the application KMS key"
  value       = aws_kms_alias.app.name
}

output "kms_usage_policy_arn" {
  description = "ARN of the IAM policy for KMS usage"
  value       = aws_iam_policy.kms_usage.arn
}

output "all_key_arns" {
  description = "List of all KMS key ARNs"
  value = [
    aws_kms_key.main.arn,
    aws_kms_key.s3.arn,
    aws_kms_key.rds.arn,
    aws_kms_key.secrets.arn,
    aws_kms_key.app.arn
  ]
}
