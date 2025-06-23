# Outputs for Incident Response Module

output "incident_response_bucket_id" {
  description = "S3 bucket ID for incident response documents"
  value       = aws_s3_bucket.incident_response.id
}

output "forensics_bucket_id" {
  description = "S3 bucket ID for forensic evidence"
  value       = aws_s3_bucket.forensics.id
}

output "oncall_sns_topic_arn" {
  description = "ARN of the on-call SNS topic"
  value       = aws_sns_topic.oncall.arn
}

output "postmortems_table_name" {
  description = "Name of the DynamoDB table for post-mortems"
  value       = aws_dynamodb_table.postmortems.name
}

output "evidence_collector_function_name" {
  description = "Name of the evidence collector Lambda function"
  value       = aws_lambda_function.evidence_collector.function_name
}

output "oncall_rotation_function_name" {
  description = "Name of the on-call rotation Lambda function"
  value       = aws_lambda_function.oncall_rotation.function_name
}

output "status_updater_function_name" {
  description = "Name of the status page updater Lambda function"
  value       = aws_lambda_function.status_updater.function_name
}

output "postmortem_processor_function_name" {
  description = "Name of the post-mortem processor Lambda function"
  value       = aws_lambda_function.postmortem_processor.function_name
}

output "forensics_access_role_arn" {
  description = "ARN of the forensics access role"
  value       = aws_iam_role.forensics_access.arn
}
