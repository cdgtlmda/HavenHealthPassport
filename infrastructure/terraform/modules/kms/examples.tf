# Example usage of KMS module in main Terraform configuration

module "kms" {
  source = "./modules/kms"

  environment          = var.environment
  project_name        = var.project_name
  deletion_window_days = 30
  multi_region        = var.environment == "production" ? true : false

  # Admin ARNs - typically would include DevOps team roles
  admin_arns = [
    aws_iam_role.devops_admin.arn,
    aws_iam_role.security_admin.arn
  ]

  # User ARNs - application roles that need to use the keys
  user_arns = [
    aws_iam_role.ecs_task_role.arn,
    aws_iam_role.lambda_execution_role.arn,
    aws_iam_role.ec2_instance_role.arn
  ]

  # SNS topic for security alerts
  alarm_actions = [
    aws_sns_topic.security_alerts.arn
  ]

  tags = local.common_tags
}

# Example of using KMS keys with S3 bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = module.kms.s3_key_id
      sse_algorithm     = "aws:kms"
    }
  }
}

# Example of using KMS key with RDS instance
resource "aws_db_instance" "main" {
  # ... other configuration ...

  storage_encrypted = true
  kms_key_id       = module.kms.rds_key_arn
}
