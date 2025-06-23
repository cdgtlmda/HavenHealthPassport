# LangChain Agents for Haven Health Passport

## Overview

This module provides intelligent AI agents for medical tasks using LangChain. Each agent is specialized for specific healthcare operations while maintaining HIPAA compliance and medical accuracy.

## Agent Types

### 1. Medical Information Agent
- **Purpose**: Retrieve and explain medical information
- **Capabilities**:
  - Search medical databases
  - Explain conditions and treatments
  - Check drug interactions
  - Provide health education

### 2. Emergency Response Agent
- **Purpose**: Provide immediate emergency guidance
- **Capabilities**:
  - Emergency protocol guidance
  - First aid instructions
  - Triage assessment
  - Critical action steps

### 3. Medical Translation Agent
- **Purpose**: Translate medical content accurately
- **Capabilities**:
  - Preserve medical terminology
  - Cultural adaptation
  - Multi-language support (50+)
  - Document-specific translation

### 4. Health Record Analysis Agent
- **Purpose**: Analyze patient health records
- **Capabilities**:
  - Identify health trends
  - Detect care gaps
  - Generate summaries
  - Risk assessment

## Quick Start

```python
from haven_health_passport.ai.langchain.agents import AgentFactory, AgentType, MedicalContext

# Create a medical information agent
agent = AgentFactory.create_agent(AgentType.MEDICAL_INFO)

# Set up context
context = MedicalContext(
    language="en",
    urgency_level=2,
    privacy_level="standard"
)

# Process a query
from haven_health_passport.ai.langchain.agents.medical import MedicalQuery

query = MedicalQuery(
    query="What are the symptoms of diabetes?",
    query_type="condition",
    detail_level="standard"
)

result = await agent.process(query, context)
```

## Using the Agent Factory

```python
# Create agent with custom configuration
from haven_health_passport.ai.langchain.agents import AgentConfig

config = AgentConfig(
    name="CustomMedicalAgent",
    description="Specialized medical agent",
    temperature=0.1,
    enable_memory=True,
    enable_audit=True
)

agent = AgentFactory.create_agent(
    AgentType.MEDICAL_INFO,
    config=config,
    agent_id="med_agent_001"  # Optional: store for later retrieval
)

# Retrieve stored agent
agent = AgentFactory.get_agent("med_agent_001")

# List all active agents
active_agents = AgentFactory.list_agents()

# Terminate agent when done
AgentFactory.terminate_agent("med_agent_001")
```

## Context-Based Agent Selection

```python
# High urgency automatically selects emergency agent
emergency_context = MedicalContext(urgency_level=5)
agent = AgentFactory.create_agent_for_context(emergency_context)
# Returns: EmergencyResponseAgent

# Non-English context selects translation agent
spanish_context = MedicalContext(language="es", urgency_level=2)
agent = AgentFactory.create_agent_for_context(spanish_context)
# Returns: MedicalTranslationAgent
```

## Medical Tools

Each agent has access to specialized tools:

```python
from haven_health_passport.ai.langchain.agents.tools import create_medical_tools

# Get all available tools
tools = create_medical_tools()

# Tools include:
# - medical_search: Search medical databases
# - drug_interaction_check: Check medication interactions
# - symptom_analysis: Analyze reported symptoms
# - emergency_protocol: Get emergency procedures
# - medical_translation: Translate medical text
```

## Best Practices

1. **Always provide context**: Include language, urgency, and privacy requirements
2. **Use appropriate agent types**: Match agent to task for best results
3. **Handle errors gracefully**: Agents may fail on network/API issues
4. **Clear memory when needed**: For privacy, clear conversation memory
5. **Monitor performance**: Use audit logs for quality assurance

## Security & Compliance

- **HIPAA Compliant**: All agents follow healthcare privacy standards
- **PII Protection**: Automatic sanitization of personal information
- **Audit Logging**: Complete audit trail for all operations
- **Medical Validation**: Built-in validation for medical content
- **Privacy Controls**: Configurable privacy levels

## Configuration

### Environment Variables
```bash
# LangChain configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_api_key

# AWS Bedrock configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

### Agent Configuration Options
```python
config = AgentConfig(
    name="AgentName",
    description="Agent description",
    model_name="anthropic.claude-3-sonnet",  # Optional: specific model
    temperature=0.1,  # 0.0-1.0, lower = more consistent
    max_iterations=10,  # Max reasoning steps
    max_execution_time=30.0,  # Timeout in seconds
    enable_memory=True,  # Conversation memory
    enable_audit=True,  # Audit logging
    enable_pii_filter=True,  # PII sanitization
    enable_medical_validation=True,  # Medical content validation
    system_prompt="Custom system prompt"  # Optional custom prompt
)
```

## Error Handling

```python
try:
    result = await agent.process(query, context)
except Exception as e:
    # Agents provide detailed error information
    logger.error(f"Agent error: {e}")

    # Check agent state
    if agent.state == AgentState.ERROR:
        # Reset or recreate agent
        agent.terminate()
        agent = AgentFactory.create_agent(AgentType.MEDICAL_INFO)
```

## Testing

Run agent tests:
```bash
pytest src/ai/langchain/agents/tests/
```

## Future Enhancements

- [ ] Multi-agent collaboration
- [ ] Streaming responses
- [ ] Voice input/output integration
- [ ] Image analysis capabilities
- [ ] Real-time language detection
- [ ] Advanced caching strategies
- [ ] Custom tool creation API
