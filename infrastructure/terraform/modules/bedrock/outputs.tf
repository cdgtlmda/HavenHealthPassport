# Outputs for Bedrock module

output "bedrock_iam_role_arn" {
  description = "ARN of the IAM role for Bedrock access"
  value       = aws_iam_role.bedrock_role.arn
}

output "bedrock_iam_role_name" {
  description = "Name of the IAM role for Bedrock access"
  value       = aws_iam_role.bedrock_role.name
}

output "bedrock_policy_arn" {
  description = "ARN of the IAM policy for Bedrock access"
  value       = aws_iam_policy.bedrock_policy.arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for Bedrock"
  value       = var.enable_cloudwatch_logs ? aws_cloudwatch_log_group.bedrock_logs[0].name : ""
}

output "monitoring_dashboard_url" {
  description = "URL of the CloudWatch dashboard for Bedrock monitoring"
  value       = "https://${data.aws_region.current.name}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.bedrock_dashboard.dashboard_name}"
}

output "model_access_status" {
  description = "Instructions for checking model access status"
  value       = "Check model access at: https://console.aws.amazon.com/bedrock/home?region=${data.aws_region.current.name}#/modelaccess"
}

output "budget_name" {
  description = "Name of the AWS Budget for Bedrock costs"
  value       = var.enable_cost_alerts ? aws_budgets_budget.bedrock_budget[0].name : ""
}

output "requested_models" {
  description = "List of models requested for access"
  value       = var.requested_models
}
# Cost monitoring outputs
output "cost_monitoring_status" {
  description = "Status of cost monitoring configuration"
  value = {
    budget_name = var.enable_cost_alerts ? aws_budgets_budget.bedrock_budget[0].name : "Not configured"
    budget_amount = var.monthly_budget_amount
    alarm_threshold_80_percent = var.monthly_budget_amount * 0.8
    alarm_threshold_100_percent = var.monthly_budget_amount
    notifications_enabled = length(var.budget_notification_emails) > 0
  }
}

output "cost_tracking_tags" {
  description = "Tags used for cost allocation"
  value = {
    project = var.project_name
    environment = var.environment
    service = "bedrock"
    cost_center = "ai-ml"
  }
}
