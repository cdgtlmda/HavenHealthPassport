# LangChain Memory Systems

HIPAA-compliant memory for medical conversations with encryption and persistence.

## Quick Start

```python
from langchain.memory import MemoryFactory

# Create and use memory
memory = MemoryFactory.create_conversation_memory("session123", "user456", "buffer")
memory.add_user_message("I have a headache")
memory.add_ai_message("How long has this been going on?")
```

## Memory Types

- **Conversation**: Buffer, Window, Token-based
- **Entity**: Medical entity extraction
- **Summary**: AI-powered summarization
- **Custom**: Hybrid, Medical, Emergency, Multilingual

## Configuration

```bash
export LANGCHAIN_MEMORY_TABLE=haven-health-langchain-memory
export MEMORY_ENCRYPTION_KEY=your-fernet-key
export MEMORY_TTL_DAYS=90
```

## Features

- Fernet encryption at rest
- DynamoDB persistence with TTL
- Medical entity recognition (medications, conditions, symptoms)
- Emergency rapid access
- 50+ language support
- Structured medical summaries

## Setup

```bash
# Create DynamoDB table
python create_dynamodb_table.py

# Test memory systems
python test_memory.py
```

See module docstrings for detailed API documentation.
