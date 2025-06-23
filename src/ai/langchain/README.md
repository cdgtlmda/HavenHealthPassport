# LangChain Core Library for Haven Health Passport

## Overview
Core LangChain integration providing medical AI capabilities with safety features.

## Installation
```bash
cd src/ai/langchain
pip install -r requirements.txt
```

## Quick Start
```python
from haven_health_passport.ai.langchain import initialize_langchain

# Initialize with medical safety features
initialize_langchain(
    config={
        "environment": "development",
        "default_provider": "bedrock",
        "enable_content_filtering": True,
        "enable_pii_detection": True
    },
    debug=True
)
```

## Key Features
- **Medical Safety**: Content filtering and PII detection
- **Multi-Environment**: Dev, staging, production support
- **Type Safety**: Full Pydantic validation
- **Performance Monitoring**: Built-in metrics collection
- **Flexible Config**: Environment variables or code-based

## Configuration Options
- `environment`: development/staging/production
- `default_provider`: bedrock/openai/anthropic
- `enable_cache`: Response caching
- `enable_memory`: Conversation memory
- `max_retries`: API retry attempts

## Project Structure
- `__init__.py`: Core initialization
- `config.py`: Configuration management
- `utils.py`: Helper utilities
- `requirements.txt`: Dependencies
- `setup.py`: Package setup
