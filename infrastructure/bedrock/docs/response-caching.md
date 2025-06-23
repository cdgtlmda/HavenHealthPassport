# Response Caching

## Overview
Multi-tier caching for Bedrock responses with Redis (hot), S3 (warm), and Glacier (cold) storage.

## Cache Tiers
- **Hot**: Redis, <5ms, 10K items, LRU eviction
- **Warm**: S3, <100ms, 100K items, TTL-based
- **Cold**: Glacier, archive, 1M items, 365-day retention

## Use Case Configurations

| Use Case | TTL | Similarity | Key Components |
|----------|-----|------------|----------------|
| Medical Analysis | 1 hour | 95% | use_case, messages_hash, model_key |
| Medical Translation | 24 hours | 98% | source/target lang, text_hash, model_key |
| Document Analysis | 2 hours | 90% | document_hash, analysis_type, model_key |
| Embeddings | 7 days | 100% | text_hash, model_key, dimensions |

## Features
- Automatic tier promotion/demotion
- Semantic similarity matching
- Encryption at rest and transit
- Multi-AZ high availability
- Cost-optimized lifecycle policies

## Architecture
```
Request → Cache Check → Redis (Hot)
                     ↓ Miss
                     → S3 (Warm)
                     ↓ Miss
                     → Model Invocation
                     ↓
                     → Cache Write (Multi-tier)
```

## Integration
Cache is automatically integrated with model selection pipeline. No application changes required.

## Monitoring
- CloudWatch metrics for hit/miss rates
- Cache tier distribution
- Performance metrics per use case
