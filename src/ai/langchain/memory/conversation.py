"""Conversation memory implementations for Haven Health Passport."""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

import tiktoken
from langchain.llms.base import BaseLLM
from langchain.memory import ConversationBufferMemory as LCBufferMemory
from langchain.memory import ConversationBufferWindowMemory as LCWindowMemory
from langchain.memory import ConversationTokenBufferMemory as LCTokenMemory
from langchain.schema import AIMessage, BaseMessage, HumanMessage

from .base import BaseMemoryStore, DynamoDBMemoryStore, EncryptedMemoryStore

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Base conversation memory with persistence."""

    memory_store: BaseMemoryStore

    def __init__(
        self,
        session_id: str,
        user_id: str,
        memory_store: Optional[BaseMemoryStore] = None,
        encrypt: bool = True,
        language: str = "en",
        max_token_limit: int = 4000,
    ):
        """Initialize conversation memory."""
        self.session_id = session_id
        self.user_id = user_id
        self.language = language
        self.max_token_limit = max_token_limit

        if memory_store is None:
            dynamo = DynamoDBMemoryStore()
            self.memory_store = EncryptedMemoryStore(dynamo) if encrypt else dynamo
        else:
            self.memory_store = memory_store

        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.messages: List[BaseMessage] = []
        self._load_conversation()

    def _get_memory_key(self) -> str:
        """Generate memory key for this conversation."""
        return f"conversation:{self.user_id}:{self.session_id}"

    def _load_conversation(self) -> None:
        """Load conversation from storage."""
        data = self.memory_store.load(self._get_memory_key())
        if data and "messages" in data:
            self.messages = []
            for msg in data["messages"]:
                if msg["type"] == "human":
                    self.messages.append(HumanMessage(content=msg["content"]))
                elif msg["type"] == "ai":
                    self.messages.append(AIMessage(content=msg["content"]))

    def _save_conversation(self) -> None:
        """Save conversation to storage."""
        data = {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "language": self.language,
            "messages": [
                {
                    "type": "human" if isinstance(msg, HumanMessage) else "ai",
                    "content": msg.content,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                for msg in self.messages
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory_store.save(self._get_memory_key(), data)

    def add_user_message(self, message: str) -> None:
        """Add user message to conversation."""
        self.messages.append(HumanMessage(content=message))
        self._trim_messages()
        self._save_conversation()

    def add_ai_message(self, message: str) -> None:
        """Add AI message to conversation."""
        self.messages.append(AIMessage(content=message))
        self._trim_messages()
        self._save_conversation()

    def _trim_messages(self) -> None:
        """Trim messages to stay within token limit."""

        def get_content_tokens(content: Any) -> int:
            """Get token count for message content."""
            if isinstance(content, str):
                return len(self.encoding.encode(content))
            else:
                # For list content, convert to string representation
                return len(self.encoding.encode(str(content)))

        total_tokens = sum(get_content_tokens(msg.content) for msg in self.messages)

        while total_tokens > self.max_token_limit and len(self.messages) > 2:
            # Remove oldest messages but keep at least 2
            removed = self.messages.pop(0)
            total_tokens -= get_content_tokens(removed.content)

    def clear(self) -> None:
        """Clear conversation history."""
        self.messages = []
        self.memory_store.delete(self._get_memory_key())

    def get_messages(self) -> List[BaseMessage]:
        """Get all messages."""
        return self.messages

    def get_buffer_string(self) -> str:
        """Get conversation as formatted string."""
        buffer = []
        for msg in self.messages:
            if isinstance(msg, HumanMessage):
                buffer.append(f"Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                buffer.append(f"Assistant: {msg.content}")
        return "\n".join(buffer)


class ConversationBufferMemory(ConversationMemory):
    """Buffer memory that stores entire conversation."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize conversation buffer memory."""
        super().__init__(**kwargs)
        self.langchain_memory = LCBufferMemory(
            return_messages=True, memory_key="history"
        )

    def to_langchain_memory(self) -> LCBufferMemory:
        """Convert to LangChain memory format."""
        self.langchain_memory.chat_memory.messages = self.messages
        return self.langchain_memory


class ConversationBufferWindowMemory(ConversationMemory):
    """Window memory that stores last k messages."""

    def __init__(self, window_size: int = 10, **kwargs: Any) -> None:
        """Initialize conversation buffer window memory."""
        super().__init__(**kwargs)
        self.window_size = window_size
        self.langchain_memory = LCWindowMemory(
            return_messages=True, memory_key="history", k=window_size
        )

    def _trim_messages(self) -> None:
        """Trim to window size instead of token limit."""
        if len(self.messages) > self.window_size:
            self.messages = self.messages[-self.window_size :]

    def to_langchain_memory(self) -> LCWindowMemory:
        """Convert to LangChain memory format."""
        self.langchain_memory.chat_memory.messages = self.messages
        return self.langchain_memory


class ConversationTokenBufferMemory(ConversationMemory):
    """Token-based buffer memory with automatic trimming."""

    def __init__(self, max_token_limit: int = 2000, **kwargs: Any) -> None:
        """Initialize conversation token buffer memory."""
        kwargs["max_token_limit"] = max_token_limit
        super().__init__(**kwargs)

        llm = kwargs.get("llm", None)

        if llm and isinstance(llm, BaseLLM):
            self.langchain_memory = LCTokenMemory(
                llm=llm,
                return_messages=True,
                memory_key="history",
                max_token_limit=max_token_limit,
            )
        else:
            # If no LLM is provided, we'll use a simple token counting approach
            # by inheriting the base class behavior
            logger.warning(
                "No LLM provided for ConversationTokenBufferMemory. Token counting may be inaccurate."
            )
            # Just use parent class token counting

    def to_langchain_memory(self) -> LCTokenMemory:
        """Convert to LangChain memory format."""
        if hasattr(self, "langchain_memory"):
            self.langchain_memory.chat_memory.messages = self.messages
            return self.langchain_memory
        else:
            # Return a basic buffer memory if no token memory was created
            fallback = LCBufferMemory(return_messages=True, memory_key="history")
            fallback.chat_memory.messages = self.messages
            return fallback  # type: ignore

    def get_token_count(self) -> int:
        """Get current token count."""

        def get_content_tokens(content: Any) -> int:
            """Get token count for message content."""
            if isinstance(content, str):
                return len(self.encoding.encode(content))
            else:
                # For list content, convert to string representation
                return len(self.encoding.encode(str(content)))

        return sum(get_content_tokens(msg.content) for msg in self.messages)
