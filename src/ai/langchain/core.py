"""Core LangChain initialization and configuration functions."""

from types import SimpleNamespace
from typing import Any, Dict, Optional

from langchain.callbacks.manager import CallbackManager

from .config import Environment, LangChainConfig, ModelProvider


class _LangChainState:
    """Internal state for LangChain configuration."""

    def __init__(self) -> None:
        self.config: Optional[LangChainConfig] = None
        self.callback_manager: Optional[CallbackManager] = None

    def initialize(
        self, config: Optional[Dict[str, Any]] = None, debug: bool = False
    ) -> None:
        """Initialize LangChain with configuration."""
        # Create config from dict or use defaults
        if config:
            env = Environment(config.get("environment", "development"))
            self.config = LangChainConfig(
                environment=env, default_provider=ModelProvider.BEDROCK, debug=debug
            )
        else:
            self.config = LangChainConfig(debug=debug)

        # Initialize callback manager
        self.callback_manager = CallbackManager([])


# Module-level state instance
_state = _LangChainState()


def initialize_langchain(
    config: Optional[Dict[str, Any]] = None, debug: bool = False
) -> None:
    """Initialize LangChain with configuration."""
    _state.initialize(config, debug)


def get_config() -> LangChainConfig:
    """Get current LangChain configuration."""
    if _state.config is None:
        initialize_langchain()
    assert _state.config is not None
    return _state.config


def get_callback_manager() -> CallbackManager:
    """Get callback manager instance."""
    if _state.callback_manager is None:
        initialize_langchain()
    assert _state.callback_manager is not None
    return _state.callback_manager


def get_runnable_config(
    tags: Optional[list] = None, metadata: Optional[Dict[str, Any]] = None
) -> Any:
    """Get runnable configuration for chains."""
    config = get_config()

    # Create a simple namespace to mimic runnable config
    runnable_config = SimpleNamespace(tags=tags or [], metadata=metadata or {})

    # Add default metadata
    runnable_config.metadata["project"] = "haven-health-passport"
    runnable_config.metadata["environment"] = str(config.environment)

    return runnable_config
