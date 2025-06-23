# Outputs for Container Security Module

output "ecr_repository_urls" {
  description = "URLs of the ECR repositories"
  value       = { for k, v in aws_ecr_repository.main : k => v.repository_url }
}

output "image_signing_key_id" {
  description = "ID of the KMS key for image signing"
  value       = aws_kms_key.image_signing.id
}

output "signer_profile_name" {
  description = "Name of the signer profile"
  value       = aws_signer_signing_profile.container.name
}

output "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role"
  value       = aws_iam_role.ecs_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "ecs_task_security_group_id" {
  description = "ID of the ECS task security group"
  value       = aws_security_group.ecs_tasks.id
}

output "container_secrets_arns" {
  description = "ARNs of the container secrets"
  value       = { for k, v in aws_secretsmanager_secret.container_secrets : k => v.arn }
}

output "approved_images_bucket" {
  description = "S3 bucket containing approved images list"
  value       = aws_s3_bucket.approved_images.id
}

output "vulnerability_processor_function_name" {
  description = "Name of the vulnerability processor Lambda function"
  value       = aws_lambda_function.vulnerability_processor.function_name
}
