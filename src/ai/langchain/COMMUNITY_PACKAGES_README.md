# LangChain Community Packages for Haven Health Passport

## Overview
LangChain Community packages provide essential integrations for vector stores, document processing, medical standards, NLP, translation, and infrastructure.

## Installation
```bash
python install_community.py
python verify_community_installation.py
```

## Key Components

**Medical**: FHIR/HL7, DICOM, ScispaCy/MedspaCy clinical NLP
**Documents**: PDF/Word/Excel processing, OCR (Tesseract), table extraction
**Vector Stores**: FAISS, Chroma, OpenSearch for embeddings and search
**Language**: 50+ language translation, spaCy/NLTK, language detection
**Databases**: PostgreSQL, MongoDB, Redis connectors
**Infrastructure**: Async support, Prometheus monitoring, security libs

## Package Categories in requirements-community.txt

1. **Core** - langchain-community base
2. **Vector Stores** - FAISS, Chroma, OpenSearch, Pinecone
3. **Document Loaders** - PDF, Word, Excel, OCR tools
4. **Medical** - FHIR, HL7, DICOM libraries
5. **Embeddings** - Sentence transformers, HuggingFace
6. **Language** - Translation, detection tools
7. **NLP** - spaCy, NLTK, text processing
8. **Audio/Image** - Speech recognition, OpenCV
9. **Databases** - All major DB connectors
10. **Performance** - Caching, parallel processing

## Configuration Notes
- Works with AWS Bedrock models
- HIPAA compliant configurations
- Supports offline functionality
- Medical terminology preservation

## Next Steps
After successful installation:
1. Configure memory systems (checklist item 1.2.4)
2. Set up conversation memory
3. Configure entity memory
4. Implement summary memory

See `/docs/checklists/03-ai-ml-setup.md` for detailed next steps.
