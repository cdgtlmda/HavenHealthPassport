# Development Environment Configuration

environment = "development"

# AWS Configuration
aws_region = "us-east-1"

# Bedrock Configuration
bedrock_regions = ["us-east-1"]

bedrock_models = [
  "anthropic.claude-v2",
  "anthropic.claude-instant-v1",
  "amazon.titan-text-express-v1",
  "amazon.titan-text-lite-v1",
  "amazon.titan-embed-text-v1"
]

# Cost Management
enable_cost_alerts    = true
bedrock_monthly_budget = 500  # Lower budget for development

# Monitoring
enable_cloudwatch_logs = true
log_retention_days     = 7    # Shorter retention for development

# Service Quotas
bedrock_service_quotas = {
  max_requests_per_minute = 30
  max_concurrent_requests = 5
}

# Tags
tags = {
  Environment = "development"
  Purpose     = "Development and testing"
  CostCenter  = "Engineering"
}
