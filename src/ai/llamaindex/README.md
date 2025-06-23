# LlamaIndex Integration for Haven Health Passport

## Overview

This module provides document indexing and retrieval capabilities optimized for medical documents using LlamaIndex. It includes specialized configurations for healthcare data, HIPAA-compliant processing, and multi-language support.

## Installation

```bash
cd src/ai/llamaindex
pip install -r requirements.txt
```

## Quick Start

```python
from haven_health_passport.ai.llamaindex import (
    initialize_llamaindex,
    MedicalIndexConfig,
    create_medical_index
)

# Initialize with medical optimizations
config = MedicalIndexConfig(
    chunk_size=512,
    chunk_overlap=128,
    enable_medical_ner=True,
    enable_phi_detection=True
)

initialize_llamaindex(config)

# Create index from documents
from llama_index.core import Document

documents = [
    Document(text="Medical report content...", metadata={"type": "clinical_note"}),
    Document(text="Lab results...", metadata={"type": "lab_report"})
]

index = create_medical_index(documents, config)

# Query the index
query_engine = index.as_query_engine()
response = query_engine.query("What were the patient's lab results?")
```

## Features

### Medical Document Optimization
- Chunk sizes optimized for medical terminology
- Preservation of clinical context across chunks
- Medical entity recognition and extraction
- PHI (Protected Health Information) detection

### Supported Document Types
- Clinical notes
- Lab reports
- Prescriptions
- Imaging reports
- Discharge summaries
- Medical research papers
- Insurance documents

### Configuration Options

```python
config = MedicalIndexConfig(
    # Chunking settings
    chunk_size=512,  # Optimal for medical docs
    chunk_overlap=128,  # Context preservation

    # Medical features
    enable_medical_ner=True,  # Named entity recognition
    enable_phi_detection=True,  # PHI detection
    enable_metadata_extraction=True,  # Extract doc metadata

    # Storage
    storage_path="./storage/llamaindex",  # Index storage location

    # Embedding settings
    embed_model="amazon.titan-embed-text-v1",  # Bedrock embedding
)
```

## Document Processing

### Loading Medical Documents

```python
from llama_index.core import SimpleDirectoryReader

# Load from directory
reader = SimpleDirectoryReader(
    input_dir="./medical_documents",
    recursive=True,
    required_exts=[".pdf", ".txt", ".docx"]
)

documents = reader.load_data()

# Apply medical preprocessing
for doc in documents:
    doc.metadata["processed_date"] = datetime.now()
    doc.metadata["phi_detected"] = detect_phi(doc.text)
```

### Creating Specialized Indexes

```python
# Clinical notes index
clinical_index = create_medical_index(
    clinical_documents,
    config=MedicalIndexConfig(
        chunk_size=512,
        enable_medical_ner=True
    )
)

# Lab reports index with smaller chunks
lab_index = create_medical_index(
    lab_documents,
    config=MedicalIndexConfig(
        chunk_size=256,  # Smaller for structured data
        chunk_overlap=64
    )
)
```

## Integration with AWS Bedrock

```python
from llama_index.llms.bedrock import Bedrock
from llama_index.embeddings.bedrock import BedrockEmbedding

# Configure Bedrock LLM
llm = Bedrock(
    model="anthropic.claude-3-sonnet-20240229-v1:0",
    aws_region="us-east-1",
    temperature=0.1
)

# Configure Bedrock embeddings
embed_model = BedrockEmbedding(
    model_name="amazon.titan-embed-text-v1",
    aws_region="us-east-1"
)

# Initialize with Bedrock
initialize_llamaindex(
    config=MedicalIndexConfig(),
    llm=llm,
    embed_model=embed_model
)
```

## Medical Query Examples

```python
# Search for specific conditions
response = query_engine.query(
    "What medications is the patient currently taking?"
)

# Extract lab values
response = query_engine.query(
    "What was the patient's last HbA1c value?"
)

# Summarize clinical history
response = query_engine.query(
    "Summarize the patient's cardiovascular history"
)
```

## Privacy and Security

- **PHI Detection**: Automatic detection and flagging of protected health information
- **Encryption**: All indexes can be encrypted at rest
- **Access Control**: Integration with Haven's permission system
- **Audit Logging**: All queries and index operations are logged

## Performance Optimization

- **Batch Processing**: Process multiple documents in parallel
- **Caching**: Query results cached for improved performance
- **Incremental Indexing**: Add new documents without rebuilding
- **Vector Store Options**: Support for OpenSearch, Pinecone, Weaviate

## Configuration Management

Environment variables:
```bash
export LLAMAINDEX_STORAGE_PATH=/path/to/storage
export LLAMAINDEX_CHUNK_SIZE=512
export LLAMAINDEX_EMBEDDING_PROVIDER=bedrock
export LLAMAINDEX_LLM_PROVIDER=bedrock
```

## Monitoring and Metrics

- Index size and document count
- Query latency and throughput
- Embedding generation time
- Cache hit rates
- Error rates and types

## Troubleshooting

### Verification
```bash
python verify_installation.py
```

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Storage Errors**: Check permissions on storage directory
3. **Memory Issues**: Adjust batch_size for large documents
4. **Slow Queries**: Consider enabling caching or using GPU

## Next Steps

1. Configure vector store integration (OpenSearch)
2. Set up document loaders for medical formats
3. Implement custom embedding models
4. Create retrieval pipelines
