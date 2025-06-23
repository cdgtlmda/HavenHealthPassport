# Model Performance Monitoring

## Overview
Real-time monitoring and analysis of Bedrock model performance, quality, and costs.

## Key Metrics
- **Latency**: P50/P90/P99, token generation rate
- **Quality**: Response scores, translation accuracy
- **Cost**: Per request, token costs, trends
- **Reliability**: Error rates, fallback usage

## Alert Thresholds
| Metric | Warning | Critical |
|--------|---------|----------|
| Error Rate | 2% | 5% |
| P99 Latency | 5s | 10s |
| Quality Score | 0.8 | 0.7 |
| Cost Spike | 2x | 3x |

## Components
1. **CloudWatch Dashboard**: Real-time metrics
2. **Lambda Monitor**: 5-minute analysis cycles
3. **Alarms**: Automated alerting
4. **S3 Storage**: Historical analysis

## Features
- Automatic trend detection
- Cost optimization recommendations
- Performance insights
- Model comparison
- Alert notifications via SNS

## Access
CloudWatch Console → Dashboards → "haven-health-passport-bedrock-performance"

## Analysis Output
- Hourly performance summaries
- Actionable recommendations
- Alert history
- Cost breakdowns by model/use case
