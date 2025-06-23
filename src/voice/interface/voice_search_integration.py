"""Voice Search Integration Module.

This module provides integration between voice search and the command grammar system
for the Haven Health Passport.

Security Note: All PHI data accessed through voice search integration must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Voice search integration requires proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import logging
from typing import TYPE_CHECKING, List

from src.voice.interface.voice_command_grammar import (
    CommandGrammar,
    CommandParameter,
    CommandPriority,
    CommandType,
    ParameterType,
    ParsedCommand,
)
from src.voice.interface.voice_search import SearchCategory

if TYPE_CHECKING:
    from src.voice.interface.voice_command_grammar import CommandGrammarEngine
    from src.voice.interface.voice_search import (
        SearchResult,
        VoiceSearchEngine,
    )

logger = logging.getLogger(__name__)


class VoiceSearchIntegration:
    """Integration layer for voice search with the command grammar system."""

    def __init__(
        self,
        grammar_engine: "CommandGrammarEngine",
        voice_search_engine: "VoiceSearchEngine",
    ):
        """Initialize the voice search integration.

        Args:
            grammar_engine: Command grammar engine for registering search commands
            voice_search_engine: Voice search engine for executing searches
        """
        self.grammar_engine = grammar_engine
        self.search_engine = voice_search_engine

        # Register search command grammar
        self._register_search_grammar()

    def _register_search_grammar(self) -> None:
        """Register voice search grammar with the command engine."""
        search_grammar = CommandGrammar(
            command_type=CommandType.SEARCH,
            keywords=["search", "find", "look for", "show me", "where is"],
            aliases=["locate", "get", "display", "list"],
            parameters=[
                CommandParameter(
                    name="query",
                    type=ParameterType.TEXT,
                    required=True,
                    examples=["aspirin", "blood test results", "Dr. Smith"],
                ),
                CommandParameter(
                    name="category",
                    type=ParameterType.TEXT,
                    required=False,
                    constraints={
                        "allowed_values": [cat.value for cat in SearchCategory]
                    },
                    examples=["medications", "appointments", "test results"],
                ),
                CommandParameter(
                    name="time_filter",
                    type=ParameterType.TEXT,
                    required=False,
                    examples=["today", "this week", "last month"],
                ),
            ],
            priority=CommandPriority.NORMAL,
            examples=[
                "Search for my medications",
                "Find blood test results from last week",
                "Show me appointments with Dr. Smith",
                "Where is my vaccination record",
                "Look for recent prescriptions",
            ],
            supported_languages={"en", "es", "fr", "ar", "zh", "hi", "ur", "bn"},
            confirmation_required=False,
        )

        self.grammar_engine.add_grammar(search_grammar)

    async def handle_search_command(
        self, parsed_command: ParsedCommand
    ) -> List["SearchResult"]:
        """Handle a parsed search command."""
        if parsed_command.command_type != CommandType.SEARCH:
            raise ValueError("Not a search command")

        # Extract search query from parameters if available
        # Otherwise use the full raw text
        query_text = parsed_command.parameters.get("query", "")

        # Build search query - prefer specific query if available
        search_query = query_text if query_text else parsed_command.raw_text

        # Execute search
        results = await self.search_engine.search_by_voice(
            search_query, parsed_command.language
        )

        return results
