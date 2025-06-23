# Outputs for Compliance and Auditing Module

output "audit_trail_table_name" {
  description = "Name of the DynamoDB audit trail table"
  value       = aws_dynamodb_table.audit_trail.name
}

output "audit_trail_stream_arn" {
  description = "ARN of the audit trail DynamoDB stream"
  value       = aws_dynamodb_table.audit_trail.stream_arn
}

output "audit_archive_bucket_id" {
  description = "S3 bucket ID for audit archives"
  value       = aws_s3_bucket.audit_archive.id
}

output "config_bucket_id" {
  description = "S3 bucket ID for AWS Config"
  value       = aws_s3_bucket.config.id
}

output "audit_reports_bucket_id" {
  description = "S3 bucket ID for audit reports"
  value       = aws_s3_bucket.audit_reports.id
}

output "config_recorder_name" {
  description = "Name of the AWS Config recorder"
  value       = aws_config_configuration_recorder.main.name
}

output "audit_processor_function_name" {
  description = "Name of the audit processor Lambda function"
  value       = aws_lambda_function.audit_processor.function_name
}

output "drift_detector_function_name" {
  description = "Name of the drift detector Lambda function"
  value       = aws_lambda_function.drift_detector.function_name
}

output "audit_reporter_function_name" {
  description = "Name of the audit reporter Lambda function"
  value       = aws_lambda_function.audit_reporter.function_name
}
