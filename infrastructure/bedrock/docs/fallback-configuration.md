# Fallback Model Configuration

## Overview
Resilient AI service with automatic failover, circuit breaking, and caching.

## Fallback Chains

**Medical Analysis**: Claude Opus → Claude Sonnet → Claude Instant → Cached
**Medical Translation**: Titan Express → Claude Sonnet → Claude Instant
**Document Analysis**: Claude Multimodal → Claude Sonnet
**Embeddings**: Titan V2 → Titan V1

## Circuit Breaker
- **Failure Threshold**: 5 failures opens circuit
- **Recovery**: 2 successes closes circuit
- **Timeout**: 60s before testing recovery

## Triggers
- API exceptions (throttling, timeouts)
- Latency > 10 seconds
- Error rate > 10%
- Cost anomalies > 2x

## Features
- S3 response caching
- Exponential backoff
- Generic fallback responses
- CloudWatch monitoring

## Usage
```python
response = fallback_orchestrator.invoke({
    "use_case": "medical_analysis",
    "body": {
        "messages": [...],
        "max_tokens": 4096
    }
})
```

The system automatically handles failures and selects the best available model.
