# LangChain AWS Integration

## Installation
```bash
cd src/ai/langchain
pip install -r requirements-aws.txt
```

## Quick Start
```python
from haven_health_passport.ai.langchain.aws import (
    initialize_aws_integration,
    get_bedrock_llm,
    create_bedrock_chain
)

# Initialize
initialize_aws_integration(region_name="us-east-1")

# Create LLM
llm = get_bedrock_llm(
    model_id="anthropic.claude-3-sonnet-20240229",
    temperature=0.3
)

# Create chain
chain = create_bedrock_chain(
    prompt_template="Answer: {question}",
    model_id="anthropic.claude-3-sonnet-20240229"
)

# Use it
response = chain.invoke({"question": "What is dehydration?"})
```

## Components
- **BedrockModelFactory**: Model configurations
- **AWSCallbackHandler**: CloudWatch metrics
- **DynamoDBMemoryStore**: Conversation memory
- **S3DocumentStore**: Document storage

## Models
- Claude 3 (Opus, Sonnet, Haiku)
- Titan (Text Express, Embeddings)
- Jamba (Mini, Large, Instruct)

## Features
- Medical-optimized settings
- Cost tracking
- CloudWatch monitoring
