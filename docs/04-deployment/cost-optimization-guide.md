# Bedrock Cost Optimization Guide

This document describes the cost optimization features implemented for Amazon Bedrock in Haven Health Passport.

## Overview

The cost optimization system includes:
- Real-time cost monitoring and tracking
- Automated budget alerts
- Service quota management
- Cost anomaly detection
- Multi-tier response caching
- Intelligent model routing

## Components

### 1. Cost Monitor

The `BedrockCostMonitor` class provides:

- **Real-time cost tracking**: Tracks costs per user, model, and request
- **CloudWatch integration**: Sends metrics for monitoring and alerting
- **Budget monitoring**: Tracks spending against configured budgets
- **Cost alerts**: Automatic alerts when thresholds are exceeded
- **Anomaly detection**: Identifies unusual spending patterns

Usage:
```python
from haven_health.ai.bedrock import BedrockCostMonitor

monitor = BedrockCostMonitor()

# Track usage
monitor.track_usage(
    user_id="user123",
    model_id="anthropic.claude-v2",
    input_tokens=1000,
    output_tokens=500
)

# Get user costs
costs = monitor.get_user_costs("user123")

# Check budget status
budget_status = monitor.get_budget_status()
```

### 2. Quota Manager

The `ServiceQuotaManager` class provides:

- **Quota monitoring**: Checks current quota usage and limits
- **Automatic increase requests**: Requests quota increases when needed
- **Health monitoring**: Alerts on high quota utilization
- **Historical tracking**: Tracks quota request history

Usage:
```python
from haven_health.ai.bedrock import ServiceQuotaManager

manager = ServiceQuotaManager()

# Check quotas
quotas = manager.check_current_quotas("production")

# Monitor health
alerts = manager.monitor_quota_health()

# Auto-request increases
requests = manager.auto_request_increases(threshold=85.0)
```

### 3. Response Caching

Multi-tier caching system (implemented in infrastructure):

- **Hot cache (Redis)**: Sub-millisecond response for frequent queries
- **Warm cache (S3)**: Cost-effective storage for less frequent queries
- **Cache key generation**: Smart key generation based on request parameters
- **Similarity matching**: Returns cached responses for similar queries

### 4. Model Routing

Intelligent routing based on request complexity:

- **Simple requests**: Routed to Claude Instant (lowest cost)
- **Medium complexity**: Routed to Claude 3 Sonnet
- **Complex requests**: Routed to Claude 3 Opus
- **Fallback logic**: Automatic fallback to alternative models

### 5. Cost Monitoring Setup

Run the setup script to configure all cost monitoring:

Use the provided setup script to configure cost monitoring.

This creates:
- AWS Budgets with multi-threshold alerts
- Cost anomaly detectors
- CloudWatch dashboards
- Cost allocation tags

## Cost Optimization Strategies

### 1. Caching Strategy

- Cache responses with >95% similarity threshold
- TTL based on use case (1hr for general, 24hr for embeddings)
- Automatic cache warming for popular queries

### 2. Model Selection

- Use appropriate models for each task
- Prefer Titan for embeddings (lower cost)
- Use Claude Instant for simple queries
- Reserve Claude 3 Opus for complex medical analysis

### 3. Batch Processing

- Batch embedding requests (up to 25 items)
- Combine similar translation requests
- Use async processing for non-urgent requests

### 4. Request Optimization

- Compress responses to reduce data transfer
- Limit max tokens based on use case
- Use streaming for long responses

## Monitoring and Alerts

### CloudWatch Metrics

The system publishes these metrics:
- `HavenHealth/Bedrock/TokenCost`: Cost per request
- `HavenHealth/Bedrock/InputTokens`: Input token usage
- `HavenHealth/Bedrock/OutputTokens`: Output token usage
- `HavenHealth/Bedrock/Alerts/CostThresholdExceeded`: Cost alerts

### Budget Alerts

Alerts are triggered at:
- 50% (INFO): Informational notice
- 80% (WARNING): Consider optimization
- 90% (CRITICAL): Immediate action needed
- 100% (ALERT): Budget exceeded
- 110% forecast (WARNING): Projected overage

### Quota Alerts

Alerts for service quotas at:
- 90% utilization: WARNING
- 95% utilization: CRITICAL

## Configuration

### Environment Variables

```bash
# Budget alerts
BUDGET_ALERT_EMAIL=alerts@haven-health.org
ANOMALY_ALERT_EMAIL=anomalies@haven-health.org

# Thresholds
COST_WARNING_THRESHOLD=50
COST_ALERT_THRESHOLD=100
COST_CRITICAL_THRESHOLD=200

# Caching
CACHE_ENABLED=true
CACHE_SIMILARITY_THRESHOLD=0.95
```

### Budget Limits by Environment

- Development: $500/month
- Staging: $1,000/month
- Production: $5,000/month

## Best Practices

1. **Tag all resources** with UserId, ModelId, UseCase for cost tracking
2. **Review dashboards daily** to identify optimization opportunities
3. **Set up alerts** for all stakeholders
4. **Regular reviews** of model usage patterns
5. **Implement caching** for repeated queries
6. **Use batch operations** where possible
7. **Monitor quota utilization** to prevent throttling

## Troubleshooting

### High Costs

1. Check CloudWatch dashboard for usage patterns
2. Identify top users/models via Cost Explorer
3. Review cache hit rates
4. Verify model routing rules

### Quota Limits

1. Check current utilization: `manager.check_current_quotas()`
2. Request increase: `manager.request_quota_increase()`
3. Monitor request status in Service Quotas console

### Cache Issues

1. Verify Redis connectivity
2. Check cache hit/miss metrics
3. Review similarity thresholds
4. Monitor cache size and eviction

## Cost Reports

Generate monthly cost reports:

```python
# Get detailed cost breakdown
costs = monitor.get_user_costs(
    user_id="all",
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Export to CSV for analysis
```

## Future Improvements

- Implement predictive cost modeling
- Add cost allocation by department/project
- Create cost optimization recommendations
- Implement automated cost reduction actions
