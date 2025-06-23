# Bedrock Cost Monitoring Setup

## Overview

Comprehensive cost monitoring has been configured for Amazon Bedrock usage in the Haven Health Passport system.

## Cost Monitoring Components

### 1. AWS Budgets
- Monthly budgets per environment:
  - Development: $500/month
  - Staging: $1,000/month
  - Production: $5,000/month
- Alerts at 80% and 100% of budget

### 2. CloudWatch Alarms
- Real-time token usage tracking
- Request rate monitoring
- Cost per model tracking

### 3. Cost Anomaly Detection
- Automatic detection of unusual spending patterns
- Immediate alerts for 20%+ cost increases
- Daily monitoring frequency

### 4. Cost Allocation Tags
All Bedrock resources are tagged with:
- Project: haven-health-passport
- Environment: development/staging/production
- Service: bedrock
- CostCenter: ai-ml

## Model Pricing Reference

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|-------|----------------------|------------------------|
| Claude 3 Haiku | $0.00025 | $0.00125 |
| Claude 3 Sonnet | $0.003 | $0.015 |
| Claude 2 | $0.008 | $0.024 |
| Claude Instant | $0.0008 | $0.0024 |
| Titan Text Lite | $0.0003 | $0.0004 |
| Titan Text Express | $0.0008 | $0.0016 |

## Cost Optimization Strategies

1. **Model Selection**
   - Use Claude Instant or Titan Lite for simple tasks
   - Reserve Claude 3 Sonnet for medical translations
   - Implement automatic model downgrade for non-critical tasks

2. **Token Optimization**
   - Implement prompt caching
   - Use concise prompts
   - Batch similar requests

3. **Rate Limiting**
   - Per-user rate limits based on role
   - Global rate limiting to prevent runaway costs
   - Queue management for burst traffic

## Monitoring Dashboard

Access the cost monitoring dashboard:
1. AWS Console → CloudWatch → Dashboards
2. Select "haven-health-passport-bedrock-{environment}"

## Alert Configuration

Alerts are sent to configured email addresses when:
- Daily spending exceeds normal patterns by 20%
- Monthly budget reaches 80% or 100%
- Token usage spikes above thresholds

## Cost Tracking Scripts

Check current costs:
```bash
python3 scripts/aws/check_bedrock_costs.py
```

This provides a 7-day cost report and usage breakdown by model.
