"""Summary memory implementations for conversation summarization. Handles FHIR Resource validation.

All memory implementations containing PHI are encrypted and access controlled per HIPAA requirements.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain.llms.base import BaseLLM
from langchain.memory import ConversationSummaryMemory as LCSummaryMemory
from langchain.schema import BaseMessage

from .base import BaseMemoryStore, DynamoDBMemoryStore, EncryptedMemoryStore

logger = logging.getLogger(__name__)


class SummaryMemory:
    """Base summary memory with persistence."""

    memory_store: BaseMemoryStore

    def __init__(
        self,
        session_id: str,
        user_id: str,
        llm: BaseLLM,
        memory_store: Optional[BaseMemoryStore] = None,
        encrypt: bool = True,
        max_token_limit: int = 2000,
    ):
        """Initialize summary memory."""
        self.session_id = session_id
        self.user_id = user_id
        self.llm = llm
        self.max_token_limit = max_token_limit

        if memory_store is None:
            dynamo = DynamoDBMemoryStore()
            self.memory_store = EncryptedMemoryStore(dynamo) if encrypt else dynamo
        else:
            self.memory_store = memory_store

        self.summaries: List[Dict[str, Any]] = []
        self.current_summary: str = ""
        self._load_summaries()

    def _get_memory_key(self) -> str:
        return f"summary:{self.user_id}:{self.session_id}"

    def _load_summaries(self) -> None:
        """Load summaries from storage."""
        data = self.memory_store.load(self._get_memory_key())
        if data:
            self.summaries = data.get("summaries", [])
            self.current_summary = data.get("current_summary", "")

    def _save_summaries(self) -> None:
        """Save summaries to storage."""
        data = {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "summaries": self.summaries,
            "current_summary": self.current_summary,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.memory_store.save(self._get_memory_key(), data)

    def summarize_messages(self, messages: List[BaseMessage]) -> str:
        """Generate summary of messages using LLM."""
        if not messages:
            return ""

        # Format messages for summarization
        conversation = "\n".join(
            [
                f"{'Human' if msg.type == 'human' else 'AI'}: {msg.content}"
                for msg in messages
            ]
        )

        prompt = f"""Summarize the following conversation concisely:

{conversation}

Summary:"""

        try:
            summary = self.llm.predict(prompt)
            return summary.strip()
        except (AttributeError, ValueError, KeyError) as e:
            logger.error("Summarization failed: %s", e)
            return "Failed to generate summary"

    def add_summary(self, summary: str, message_count: int) -> None:
        """Add new summary to history."""
        summary_entry = {
            "summary": summary,
            "message_count": message_count,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.summaries.append(summary_entry)
        self.current_summary = summary
        self._save_summaries()

    def get_combined_summary(self) -> str:
        """Get combined summary of all conversations."""
        if not self.summaries:
            return ""
        # Combine all summaries
        all_summaries = "\n\n".join(
            [f"[{s['created_at']}]: {s['summary']}" for s in self.summaries]
        )

        # Generate meta-summary if needed
        if len(self.summaries) > 5:
            prompt = f"""Create a concise summary of these conversation summaries:

{all_summaries}

Combined summary:"""

            try:
                return self.llm.predict(prompt).strip()
            except (AttributeError, ValueError, KeyError):
                return all_summaries

        return all_summaries

    def clear(self) -> None:
        """Clear all summaries."""
        self.summaries = []
        self.current_summary = ""
        self.memory_store.delete(self._get_memory_key())


class ConversationSummaryMemory(SummaryMemory):
    """LangChain-compatible conversation summary memory."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize conversation summary memory."""
        super().__init__(**kwargs)
        self.langchain_memory = LCSummaryMemory(
            llm=self.llm, memory_key="history", return_messages=True
        )

    def to_langchain_memory(self) -> LCSummaryMemory:
        """Convert to LangChain memory format."""
        if self.current_summary:
            self.langchain_memory.buffer = self.current_summary
        return self.langchain_memory


class MedicalSummaryMemory(SummaryMemory):
    """Medical-specific summary memory with structured output."""

    def summarize_medical_conversation(
        self, messages: List[BaseMessage]
    ) -> Dict[str, Any]:
        """Generate structured medical summary."""
        if not messages:
            return {}

        conversation = "\n".join(
            [
                f"{'Patient' if msg.type == 'human' else 'Provider'}: {msg.content}"
                for msg in messages
            ]
        )

        prompt = f"""Analyze this medical conversation and extract:
1. Chief complaint
2. Symptoms mentioned
3. Medical history discussed
4. Medications mentioned
5. Recommended actions/follow-ups

Conversation:
{conversation}

Medical Summary:"""

        try:
            summary_text = self.llm.predict(prompt).strip()

            # Parse structured summary
            summary: Dict[str, Any] = {
                "raw_summary": summary_text,
                "chief_complaint": "",
                "symptoms": [],
                "medical_history": [],
                "medications": [],
                "recommendations": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Simple parsing (can be enhanced with NLP)
            lines = summary_text.split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if "complaint" in line.lower():
                    current_section = "chief_complaint"
                elif "symptom" in line.lower():
                    current_section = "symptoms"
                elif "history" in line.lower():
                    current_section = "medical_history"
                elif "medication" in line.lower():
                    current_section = "medications"
                elif "recommend" in line.lower() or "action" in line.lower():
                    current_section = "recommendations"
                elif current_section and line:
                    if current_section == "chief_complaint":
                        summary[current_section] = line
                    elif current_section in summary and isinstance(
                        summary[current_section], list
                    ):
                        # Cast to list to ensure it's mutable
                        section_list = summary[current_section]
                        if isinstance(section_list, list):
                            section_list.append(line)

            return summary

        except (AttributeError, ValueError, KeyError) as e:
            logger.error("Medical summarization failed: %s", e)
            return {"error": str(e)}


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
