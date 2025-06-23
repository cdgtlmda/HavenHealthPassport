# Outputs for Security Monitoring Module

output "cloudtrail_name" {
  description = "Name of the CloudTrail"
  value       = aws_cloudtrail.main.name
}

output "cloudtrail_s3_bucket_id" {
  description = "S3 bucket ID for CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail.id
}

output "guardduty_detector_id" {
  description = "ID of the GuardDuty detector"
  value       = aws_guardduty_detector.main.id
}

output "kinesis_firehose_name" {
  description = "Name of the Kinesis Firehose delivery stream"
  value       = aws_kinesis_firehose_delivery_stream.security_logs.name
}

output "siem_logs_bucket_id" {
  description = "S3 bucket ID for SIEM logs"
  value       = aws_s3_bucket.siem_logs.id
}

output "guardduty_response_function_name" {
  description = "Name of the GuardDuty response Lambda function"
  value       = aws_lambda_function.guardduty_response.function_name
}

output "log_processor_function_name" {
  description = "Name of the log processor Lambda function"
  value       = aws_lambda_function.log_processor.function_name
}

output "quarantine_security_group_id" {
  description = "ID of the quarantine security group"
  value       = aws_security_group.quarantine.id
}

output "glue_database_name" {
  description = "Name of the Glue database for security logs"
  value       = aws_glue_catalog_database.security_logs.name
}
