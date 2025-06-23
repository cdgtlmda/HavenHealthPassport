# Staging Environment Configuration

environment = "staging"

# AWS Configuration
aws_region = "us-east-1"

# Bedrock Configuration
bedrock_regions = ["us-east-1", "us-west-2"]

bedrock_models = [
  "anthropic.claude-v2",
  "anthropic.claude-v2:1",
  "anthropic.claude-instant-v1",
  "anthropic.claude-3-sonnet-20240229-v1:0",
  "amazon.titan-text-express-v1",
  "amazon.titan-text-lite-v1",
  "amazon.titan-embed-text-v1",
  "meta.llama2-13b-chat-v1"
]

# Cost Management
enable_cost_alerts    = true
bedrock_monthly_budget = 1000

# Monitoring
enable_cloudwatch_logs = true
log_retention_days     = 30

# Service Quotas
bedrock_service_quotas = {
  max_requests_per_minute = 60
  max_concurrent_requests = 10
}

# Tags
tags = {
  Environment = "staging"
  Purpose     = "Pre-production testing"
  CostCenter  = "Engineering"
}
