# OpenSearch Connector for Haven Health Passport

## Overview

This module provides a production-ready OpenSearch connector specifically optimized for medical document indexing and retrieval. It includes HIPAA-compliant configurations, medical text analyzers, and comprehensive health monitoring.

## Features

### 1. Medical-Optimized Text Analysis
- **Medical Synonyms**: Automatically expands medical terms (e.g., "MI" → "myocardial infarction")
- **Abbreviation Expansion**: Converts medical abbreviations to full forms
- **ICD-10/SNOMED Support**: Recognition of medical coding standards
- **Multi-language Support**: Handles medical content in 50+ languages

### 2. HIPAA-Compliant Security
- AWS IAM authentication
- Encryption at rest and in transit
- PHI (Protected Health Information) filtering
- Comprehensive audit logging

### 3. Production-Ready Features
- Connection pooling and retry logic
- Bulk indexing with error handling
- Health monitoring and alerting
- Performance optimization

## Quick Start

```python
from haven_health_passport.ai.llamaindex.opensearch import (
    OpenSearchConnector,
    OpenSearchConnectionConfig,
    OpenSearchEnvironment,
    MedicalIndexManager
)

# Create configuration
config = OpenSearchConnectionConfig.from_environment(
    OpenSearchEnvironment.PRODUCTION
)

# Initialize connector
connector = OpenSearchConnector(config)
connector.connect()

# Create medical indices
index_manager = MedicalIndexManager(connector)
index_manager.initialize_all_indices()

# Index documents
from llama_index.core import Document

documents = [
    Document(
        text="Patient presents with chest pain and shortness of breath...",
        metadata={
            "document_type": "clinical_note",
            "specialty": "cardiology",
            "language": "en"
        }
    )
]

connector.bulk_index_documents(
    documents,
    "haven-health-medical-documents"
)

# Search documents
results = connector.search(
    "haven-health-medical-documents",
    "chest pain MI",
    size=10,
    filters={"metadata.specialty": "cardiology"}
)
```

## Configuration

### Environment-Based Configuration

The connector supports multiple environments:

```python
# Production
config = OpenSearchConnectionConfig.from_environment(
    OpenSearchEnvironment.PRODUCTION
)

# Staging
config = OpenSearchConnectionConfig.from_environment(
    OpenSearchEnvironment.STAGING
)

# Development
config = OpenSearchConnectionConfig.from_environment(
    OpenSearchEnvironment.DEVELOPMENT
)

# Local
config = OpenSearchConnectionConfig.from_environment(
    OpenSearchEnvironment.LOCAL
)
```

### Environment Variables

Set these environment variables for each environment:

```bash
# Production
export OPENSEARCH_PROD_ENDPOINT="search-haven-health-prod.us-east-1.es.amazonaws.com"

# Staging
export OPENSEARCH_STAGING_ENDPOINT="search-haven-health-staging.us-east-1.es.amazonaws.com"

# Development
export OPENSEARCH_DEV_ENDPOINT="search-haven-health-dev.us-east-1.es.amazonaws.com"

# AWS Configuration
export AWS_REGION="us-east-1"
export AWS_PROFILE="haven-health-prod"  # Optional
```

## Index Management

### Predefined Medical Indices

1. **Medical Documents Index**
   - Optimized for clinical notes, reports, and medical literature
   - Enhanced medical analyzers
   - Vector similarity search support

2. **Patient Records Index**
   - High security with encryption support
   - Audit logging enabled
   - Optimized for patient data

3. **Translation Cache Index**
   - Multi-language support
   - Fast retrieval for cached translations
   - Lower resource requirements

### Creating Custom Indices

```python
from haven_health_passport.ai.llamaindex.opensearch import IndexConfig

# Create custom index configuration
custom_config = IndexConfig(
    name="my-medical-index",
    shards=3,
    replicas=2,
    enable_medical_analyzers=True,
    vector_dimension=1536,
    supported_languages=["en", "es", "fr"]
)

# Create the index
connector.create_index(custom_config)
```

## Medical Analyzers

### Available Analyzers

1. **medical_standard**: General medical text analysis
2. **medical_code**: ICD-10, SNOMED CT code recognition
3. **drug_name**: Pharmaceutical name normalization
4. **multilingual_medical**: Multi-language medical content

### Customizing Analyzers

```python
from haven_health_passport.ai.llamaindex.opensearch import MedicalAnalyzerConfig

# Create custom analyzer configuration
analyzer_config = MedicalAnalyzerConfig()

# Add custom medical synonyms
analyzer_config.medical_synonyms["cardiac_arrest"] = [
    "heart stopped",
    "cardiac standstill",
    "asystole"
]

# Add custom abbreviations
analyzer_config.medical_abbreviations["CHF"] = "congestive heart failure"

# Apply to connector
connector._analyzer_config = analyzer_config
```

## Health Monitoring

### Comprehensive Health Check

```python
from haven_health_passport.ai.llamaindex.opensearch import OpenSearchHealthCheck

# Create health checker
health_check = OpenSearchHealthCheck(connector)

# Run comprehensive check
report = health_check.run_comprehensive_health_check()

# Check specific index
index_health = health_check.check_index_performance("haven-health-medical-documents")
```

### Health Metrics

- Cluster status (green/yellow/red)
- Node resource usage (CPU, memory, disk)
- Index performance (query latency, indexing rate)
- Shard allocation status

## Best Practices

### 1. Connection Management
```python
# Use context manager for automatic cleanup
class OpenSearchContext:
    def __enter__(self):
        self.connector = OpenSearchConnector(config)
        self.connector.connect()
        return self.connector

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connector.close()

# Usage
with OpenSearchContext() as connector:
    # Perform operations
    pass
```

### 2. Bulk Indexing
```python
# Index large document sets efficiently
connector.bulk_index_documents(
    documents,
    index_name="haven-health-medical-documents",
    batch_size=500  # Adjust based on document size
)
```

### 3. Error Handling
```python
try:
    results = connector.search(index_name, query)
except Exception as e:
    logger.error(f"Search failed: {e}")
    # Implement fallback logic
```

## Troubleshooting

### Connection Issues
```python
# Check connectivity
import requests
response = requests.get(f"https://{config.endpoint}")
print(f"Status: {response.status_code}")

# Verify AWS credentials
import boto3
sts = boto3.client('sts')
print(sts.get_caller_identity())
```

### Performance Issues
1. Check cluster health: `health_check.check_cluster_health()`
2. Review node stats: `health_check.check_node_stats()`
3. Optimize indices: `index_manager.optimize_indices()`

### Search Quality Issues
1. Verify analyzer configuration
2. Check medical synonym expansion
3. Review query construction
4. Test with different analyzer types

## Terraform Infrastructure

See `/infrastructure/opensearch/` for Terraform configurations to deploy:
- AWS OpenSearch domain
- IAM roles and policies
- VPC and security groups
- Monitoring and alerting

## Future Enhancements

- [ ] Real-time index monitoring dashboard
- [ ] Automatic index optimization
- [ ] Machine learning-based query expansion
- [ ] Cross-region replication
- [ ] Advanced medical entity recognition
