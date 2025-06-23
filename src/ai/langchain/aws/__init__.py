"""LangChain AWS Integration for Haven Health Passport.

Provides AWS-specific implementations and Bedrock integration
"""

import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.config import Config
from langchain_aws import BedrockEmbeddings, BedrockLLM, ChatBedrock
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_community.chat_models import BedrockChat as CommunityBedrockChat
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..config import LangChainConfig, ModelProvider
from .aws_callbacks import AWSCallbackHandler
from .bedrock_models import BedrockModelFactory
from .document_stores import S3DocumentStore
from .memory_stores import DynamoDBMemoryStore

# Configure logging
logger = logging.getLogger(__name__)

# Global AWS clients
_aws_clients: Dict[str, Any] = {}


def initialize_aws_integration(
    region_name: str = "us-east-1",
    aws_profile: Optional[str] = None,
    config: Optional[LangChainConfig] = None,
) -> None:
    """Initialize AWS integration for LangChain.

    Args:
        region_name: AWS region
        aws_profile: AWS profile name
        config: LangChain configuration
    """
    _ = config  # Mark as intentionally unused for now

    # Configure boto3
    boto_config = Config(
        region_name=region_name,
        signature_version="v4",
        retries={"max_attempts": 3, "mode": "adaptive"},
    )
    # Initialize session
    if aws_profile:
        session = boto3.Session(profile_name=aws_profile)
    else:
        session = boto3.Session()

    # Initialize AWS clients
    _aws_clients["bedrock"] = session.client("bedrock-runtime", config=boto_config)
    _aws_clients["bedrock_client"] = session.client("bedrock", config=boto_config)
    _aws_clients["s3"] = session.client("s3", config=boto_config)
    _aws_clients["dynamodb"] = session.resource("dynamodb", config=boto_config)
    _aws_clients["secretsmanager"] = session.client(
        "secretsmanager", config=boto_config
    )
    _aws_clients["cloudwatch"] = session.client("cloudwatch", config=boto_config)
    _aws_clients["lambda"] = session.client("lambda", config=boto_config)

    logger.info("AWS integration initialized for region: %s", region_name)


def get_bedrock_llm(
    model_id: str = "anthropic.claude-3-sonnet-20240229", **kwargs: Any
) -> ChatBedrock:
    """Get a Bedrock LLM instance.

    Args:
        model_id: Bedrock model ID
        **kwargs: Additional model parameters

    Returns:
        ChatBedrock instance
    """
    if "bedrock" not in _aws_clients:
        raise RuntimeError(
            "AWS integration not initialized. Call initialize_aws_integration() first."
        )

    # Get model configuration from factory
    factory = BedrockModelFactory()
    model_config = factory.get_model_config(model_id)

    # Merge configurations
    final_config = {**model_config, **kwargs}

    # Create and return model
    return ChatBedrock(
        client=_aws_clients["bedrock"],
        model=model_id,
        model_kwargs=final_config,
        callbacks=[AWSCallbackHandler()],
    )


def get_bedrock_embeddings(
    model_id: str = "amazon.titan-embed-text-v2", **kwargs: Any
) -> BedrockEmbeddings:
    """Get a Bedrock embeddings model.

    Args:
        model_id: Bedrock embeddings model ID
        **kwargs: Additional parameters

    Returns:
        BedrockEmbeddings instance
    """
    if "bedrock" not in _aws_clients:
        raise RuntimeError(
            "AWS integration not initialized. Call initialize_aws_integration() first."
        )

    return BedrockEmbeddings(
        client=_aws_clients["bedrock"], model_id=model_id, **kwargs
    )


def get_aws_client(service_name: str) -> Any:
    """Get an initialized AWS client.

    Args:
        service_name: AWS service name

    Returns:
        AWS client instance
    """
    if service_name not in _aws_clients:
        raise ValueError(f"AWS client '{service_name}' not initialized")

    return _aws_clients[service_name]


def create_bedrock_chain(
    prompt_template: str,
    model_id: str = "anthropic.claude-3-sonnet-20240229",
    output_parser: Optional[Any] = None,
    **model_kwargs: Any,
) -> Any:
    """Create a complete Bedrock chain with prompt, model, and parser."""
    # Create prompt
    prompt = ChatPromptTemplate.from_template(prompt_template)

    # Get model
    model = get_bedrock_llm(model_id=model_id, **model_kwargs)

    # Use default parser if none provided
    if output_parser is None:
        output_parser = StrOutputParser()

    # Create and return chain
    return prompt | model | output_parser


# Public API
__all__ = [
    "initialize_aws_integration",
    "get_bedrock_llm",
    "get_bedrock_embeddings",
    "get_aws_client",
    "create_bedrock_chain",
    "BedrockModelFactory",
    "AWSCallbackHandler",
    "DynamoDBMemoryStore",
    "S3DocumentStore",
]
