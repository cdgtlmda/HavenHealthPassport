"""Base Agent Class for Haven Health Passport.

Provides foundation for all medical AI agents with:
- HIPAA-compliant data handling
- Multi-language support
- Audit logging
- Error recovery
- Performance monitoring

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

# Standard library imports
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

# Third-party imports
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain.callbacks.base import BaseCallbackHandler
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import BaseTool
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from src.ai.langchain.aws.bedrock_llm import get_bedrock_llm

from ..retry import medical_retry
from ..utils import sanitize_pii, validate_medical_content

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentState(str, Enum):
    """Agent lifecycle states."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    TERMINATED = "terminated"


class MedicalContext(BaseModel):
    """Medical context for agent operations."""

    patient_id: Optional[str] = Field(None, description="Anonymized patient identifier")
    language: str = Field("en", description="ISO 639-1 language code")
    urgency_level: int = Field(1, description="1-5 urgency scale")
    privacy_level: str = Field("standard", description="Privacy handling level")
    cultural_context: Optional[Dict[str, Any]] = Field(
        None, description="Cultural considerations"
    )
    medical_history_available: bool = Field(
        False, description="Whether history is accessible"
    )


@dataclass
class AgentConfig:
    """Configuration for health agents."""

    name: str
    description: str
    model_name: Optional[str] = None
    temperature: float = 0.1  # Low temperature for medical accuracy
    max_iterations: int = 10
    max_execution_time: float = 30.0  # seconds
    enable_memory: bool = True
    memory_key: str = "chat_history"
    enable_audit: bool = True
    enable_pii_filter: bool = True
    enable_medical_validation: bool = True
    tools: List[BaseTool] = field(default_factory=list)
    system_prompt: Optional[str] = None
    callbacks: List[BaseCallbackHandler] = field(default_factory=list)


class MedicalAuditHandler(BaseCallbackHandler):
    """Callback handler for medical audit logging."""

    def __init__(self, agent_name: str):
        """Initialize MedicalAuditCallbackHandler.

        Args:
            agent_name: Name of the agent for audit logging
        """
        self.agent_name = agent_name
        self.start_time: Optional[datetime] = None

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Log agent execution start."""
        self.start_time = datetime.utcnow()
        logger.info(
            "Agent %s started processing",
            self.agent_name,
            extra={
                "agent": self.agent_name,
                "action": "start",
                "timestamp": self.start_time.isoformat() if self.start_time else "",
            },
        )

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log agent execution completion."""
        end_time = datetime.utcnow()
        duration = (
            (end_time - self.start_time).total_seconds() if self.start_time else 0
        )
        logger.info(
            "Agent %s completed processing",
            self.agent_name,
            extra={
                "agent": self.agent_name,
                "action": "complete",
                "duration": duration,
                "timestamp": end_time.isoformat(),
            },
        )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        """Log agent errors."""
        logger.error(
            "Agent %s encountered error: %s",
            self.agent_name,
            error,
            extra={
                "agent": self.agent_name,
                "action": "error",
                "error_type": type(error).__name__,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


class BaseHealthAgent(ABC, Generic[T]):
    """Base class for all Haven Health Passport agents."""

    def __init__(self, config: AgentConfig, llm: Optional[BaseLanguageModel] = None):
        """Initialize BaseHealthAgent.

        Args:
            config: Agent configuration
            llm: Optional language model, creates default if not provided
        """
        self.config = config
        self.state = AgentState.INITIALIZING
        self._llm = llm
        self._executor: Optional[AgentExecutor] = None
        self._memory: Optional[ConversationBufferMemory] = None
        self._setup_agent()

    def _setup_agent(self) -> None:
        """Initialize agent components."""
        try:
            # Set up memory if enabled
            if self.config.enable_memory:
                self._memory = ConversationBufferMemory(
                    memory_key=self.config.memory_key, return_messages=True
                )

            # Add audit handler if enabled
            if self.config.enable_audit:
                self.config.callbacks.append(MedicalAuditHandler(self.config.name))

            # Use callbacks directly
            callbacks = self.config.callbacks  # LLM integration is now available

            # Get LLM if not provided
            if not self._llm:
                # LLM integration with Bedrock
                self._llm = get_bedrock_llm(
                    model_name=self.config.model_name
                    or "anthropic.claude-3-opus-20240229-v1:0",
                    temperature=self.config.temperature,
                    medical_mode=True,  # Always use medical mode for Haven Health
                    callbacks=callbacks,
                )

            # Create the agent
            self._create_executor()

            self.state = AgentState.READY
            logger.info("Agent %s initialized successfully", self.config.name)

        except Exception as e:
            self.state = AgentState.ERROR
            logger.error("Failed to initialize agent %s: %s", self.config.name, e)
            raise

    def _create_executor(self) -> None:
        """Create the agent executor."""
        # Create prompt template
        prompt = self._create_prompt_template()

        # Create the agent
        if not self._llm:
            raise ValueError("LLM not initialized")
        agent = create_structured_chat_agent(
            llm=self._llm, tools=self.config.tools, prompt=prompt
        )

        # Create executor
        self._executor = AgentExecutor(
            agent=agent,
            tools=self.config.tools,
            memory=self._memory,
            max_iterations=self.config.max_iterations,
            max_execution_time=self.config.max_execution_time,
            early_stopping_method="generate",
            handle_parsing_errors=True,
            verbose=logger.isEnabledFor(logging.DEBUG),
        )

    def _create_prompt_template(self) -> ChatPromptTemplate:
        """Create the prompt template for the agent."""
        system_prompt = self.config.system_prompt or self._get_default_system_prompt()

        messages: List[Any] = [
            ("system", system_prompt),
        ]

        if self.config.enable_memory:
            messages.append(MessagesPlaceholder(variable_name=self.config.memory_key))

        messages.extend(
            [
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        return ChatPromptTemplate.from_messages(messages)

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for the agent."""

    @abstractmethod
    def _validate_input(self, input_data: T, context: MedicalContext) -> T:
        """Validate and sanitize input data."""

    @abstractmethod
    def _post_process_output(
        self, output: Dict[str, Any], context: MedicalContext
    ) -> Dict[str, Any]:
        """Post-process agent output."""

    async def process(self, input_data: T, context: MedicalContext) -> Dict[str, Any]:
        """Process input through the agent."""
        if self.state != AgentState.READY:
            raise RuntimeError(
                f"Agent {self.config.name} is not ready. Current state: {self.state}"
            )

        self.state = AgentState.PROCESSING

        try:
            # Validate input
            validated_input = self._validate_input(input_data, context)

            # Apply PII filter if enabled
            if self.config.enable_pii_filter:
                input_str = json.dumps(validated_input.dict())
                input_str = sanitize_pii(input_str)
                validated_input = validated_input.parse_raw(input_str)

            # Prepare agent input
            agent_input = {"input": validated_input.dict(), "context": context.dict()}

            # Apply retry logic based on urgency level
            @medical_retry(
                urgency_level=context.urgency_level,
                operation_type="agent_execution",
                audit=self.config.enable_audit,
            )
            async def execute_with_retry() -> Any:
                if not self._executor:
                    raise ValueError("Agent executor not initialized")
                return await self._executor.ainvoke(agent_input)

            # Execute agent with retry
            result = await execute_with_retry()

            # Post-process output
            processed_output = self._post_process_output(result, context)

            # Apply medical validation if enabled
            if self.config.enable_medical_validation:
                validate_medical_content(processed_output)

            self.state = AgentState.READY
            return processed_output

        except Exception as e:
            self.state = AgentState.ERROR
            logger.error("Agent %s processing error: %s", self.config.name, e)
            raise
        finally:
            if self.state == AgentState.PROCESSING:
                self.state = AgentState.READY

    def get_memory_summary(self) -> Optional[str]:
        """Get summary of conversation memory."""
        if not self._memory:
            return None

        chat_memory = self._memory.chat_memory
        messages = getattr(chat_memory, "messages", [])
        if not messages:
            return None

        # Create a concise summary
        summary_parts = []
        for msg in messages[-5:]:  # Last 5 messages
            role = "Human" if msg.type == "human" else "Assistant"
            content = (
                msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            )
            summary_parts.append(f"{role}: {content}")

        return "\n".join(summary_parts)

    def clear_memory(self) -> None:
        """Clear conversation memory."""
        if self._memory:
            self._memory.clear()
            logger.info("Memory cleared for agent %s", self.config.name)

    def terminate(self) -> None:
        """Gracefully terminate the agent."""
        self.state = AgentState.TERMINATED
        self.clear_memory()
        logger.info("Agent %s terminated", self.config.name)
