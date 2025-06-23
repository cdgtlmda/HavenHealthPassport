# Production Environment Configuration

environment = "production"

# AWS Configuration
aws_region = "us-east-1"

# Bedrock Configuration - Multi-region for HA
bedrock_regions = ["us-east-1", "us-west-2", "eu-west-1"]

bedrock_models = [
  "anthropic.claude-v2",
  "anthropic.claude-v2:1",
  "anthropic.claude-instant-v1",
  "anthropic.claude-3-sonnet-20240229-v1:0",
  "anthropic.claude-3-haiku-20240307-v1:0",
  "amazon.titan-text-express-v1",
  "amazon.titan-text-lite-v1",
  "amazon.titan-embed-text-v1",
  "meta.llama2-70b-chat-v1",
  "meta.llama2-13b-chat-v1",
  "ai21.j2-ultra-v1",
  "ai21.j2-mid-v1"
]

# Cost Management
enable_cost_alerts    = true
bedrock_monthly_budget = 5000

# Monitoring
enable_cloudwatch_logs = true
log_retention_days     = 90

# Service Quotas
bedrock_service_quotas = {
  max_requests_per_minute = 120
  max_concurrent_requests = 20
}

# Tags
tags = {
  Environment = "production"
  Purpose     = "Production healthcare services"
  CostCenter  = "Operations"
  Compliance  = "HIPAA"
  DataClass   = "PHI"
}
