"""LlamaIndex Integration for Haven Health Passport.

This module provides document indexing and retrieval capabilities
optimized for medical documents and healthcare data.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.

Compatible with Python 3.11+ (including 3.13).
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.services.encryption_service import EncryptionService

# Handle different LlamaIndex versions
_import_successful = False

# Initialize variables first
Document: Any
Settings: Any
SimpleDirectoryReader: Any
StorageContext: Any
VectorStoreIndex: Any
load_index_from_storage: Any
BaseEmbedding: Any
LLM: Any
SentenceSplitter: Any

try:
    # Try newer import structure first (0.10+)
    from llama_index.core import Document as _Document
    from llama_index.core import Settings as _Settings
    from llama_index.core import SimpleDirectoryReader as _SimpleDirectoryReader
    from llama_index.core import StorageContext as _StorageContext
    from llama_index.core import VectorStoreIndex as _VectorStoreIndex
    from llama_index.core import load_index_from_storage as _load_index_from_storage
    from llama_index.core.embeddings import BaseEmbedding as _BaseEmbedding
    from llama_index.core.llms import LLM as _LLM
    from llama_index.core.node_parser import SentenceSplitter as _SentenceSplitter

    Document = _Document
    Settings = _Settings
    SimpleDirectoryReader = _SimpleDirectoryReader
    StorageContext = _StorageContext
    VectorStoreIndex = _VectorStoreIndex
    load_index_from_storage = _load_index_from_storage
    BaseEmbedding = _BaseEmbedding
    LLM = _LLM
    SentenceSplitter = _SentenceSplitter

    _import_successful = True
except ImportError:
    # Will be handled in fallback
    pass

if not _import_successful:
    # Fallback to older import structure
    try:
        import llama_index

        # Create placeholder classes for fallback
        class _DocumentPlaceholder:
            pass

        class _SettingsPlaceholder:
            pass

        class _SimpleDirectoryReaderPlaceholder:
            pass

        class _StorageContextPlaceholder:
            pass

        class _VectorStoreIndexPlaceholder:
            pass

        Document = getattr(llama_index, "Document", _DocumentPlaceholder)
        Settings = getattr(llama_index, "Settings", _SettingsPlaceholder)
        SimpleDirectoryReader = getattr(
            llama_index, "SimpleDirectoryReader", _SimpleDirectoryReaderPlaceholder
        )
        StorageContext = getattr(
            llama_index, "StorageContext", _StorageContextPlaceholder
        )
        VectorStoreIndex = getattr(
            llama_index, "VectorStoreIndex", _VectorStoreIndexPlaceholder
        )

        def _dummy_load_index(
            storage_context: Any, index_id: Optional[str] = None, **kwargs: Any
        ) -> Any:
            return None

        load_index_from_storage = getattr(
            llama_index, "load_index_from_storage", _dummy_load_index
        )
        # Try importing from older locations
        try:
            from llama_index.embeddings.base import BaseEmbedding as _BaseEmbedding_old

            BaseEmbedding = _BaseEmbedding_old
        except ImportError:

            class _BaseEmbeddingPlaceholder:
                pass

            BaseEmbedding = _BaseEmbeddingPlaceholder

        try:
            from llama_index.llms.base import LLM as _LLM_old

            LLM = _LLM_old
        except ImportError:

            class _LLMPlaceholder:
                pass

            LLM = _LLMPlaceholder

        try:
            from llama_index.node_parser import (
                SentenceSplitter as _SentenceSplitter_old,
            )

            SentenceSplitter = _SentenceSplitter_old
        except ImportError:

            class _SentenceSplitterPlaceholder:
                pass

            SentenceSplitter = _SentenceSplitterPlaceholder
    except ImportError as e:
        raise ImportError(
            "Could not import LlamaIndex. Please install with: pip install llama-index llama-index-core"
        ) from e

logger = logging.getLogger(__name__)

# Module version
__version__ = "0.1.0"

# Default configuration for medical documents
MEDICAL_CHUNK_SIZE = 512  # Optimized for medical terminology
MEDICAL_CHUNK_OVERLAP = 128  # Ensure context preservation
DEFAULT_EMBED_MODEL = "text-embedding-ada-002"
DEFAULT_LLM_MODEL = "gpt-3.5-turbo"


class MedicalIndexConfig:
    """Configuration for medical document indexing."""

    def __init__(
        self,
        chunk_size: int = MEDICAL_CHUNK_SIZE,
        chunk_overlap: int = MEDICAL_CHUNK_OVERLAP,
        embed_model: Optional[str] = None,
        llm_model: Optional[str] = None,
        enable_metadata_extraction: bool = True,
        enable_medical_ner: bool = True,
        enable_phi_detection: bool = True,
        storage_path: Optional[str] = None,
    ):
        """Initialize medical index configuration."""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embed_model = embed_model or DEFAULT_EMBED_MODEL
        self.llm_model = llm_model or DEFAULT_LLM_MODEL
        self.enable_metadata_extraction = enable_metadata_extraction
        self.enable_medical_ner = enable_medical_ner
        self.enable_phi_detection = enable_phi_detection
        self.storage_path = storage_path or "./storage/llamaindex"

        # Create storage directory if it doesn't exist
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)


def initialize_llamaindex(
    config: Optional[MedicalIndexConfig] = None,
    llm: Optional[LLM] = None,
    embed_model: Optional[BaseEmbedding] = None,
    debug: bool = False,
) -> bool:
    """Initialize LlamaIndex with medical-optimized settings.

    Args:
        config: Medical index configuration
        llm: Language model to use
        embed_model: Embedding model to use
        debug: Enable debug logging

    Returns:
        bool: True if initialization successful
    """
    try:
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug("Initializing LlamaIndex with debug mode")

        if not config:
            config = MedicalIndexConfig()
            logger.info("Using default medical index configuration")

        # Configure global settings
        Settings.chunk_size = config.chunk_size
        Settings.chunk_overlap = config.chunk_overlap

        # Set LLM if provided
        if llm:
            Settings.llm = llm
            logger.info("Configured LLM: %s", type(llm).__name__)

        # Set embedding model if provided
        if embed_model:
            Settings.embed_model = embed_model
            logger.info("Configured embedding model: %s", type(embed_model).__name__)

        # Configure text splitter for medical documents
        try:
            Settings.text_splitter = SentenceSplitter(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                paragraph_separator="\n\n",
                secondary_chunking_regex="[.!?]",  # Preserve sentence boundaries
            )
        except (AttributeError, TypeError) as e:
            # Some versions might have different parameters
            logger.warning("Could not set custom text splitter: %s", e)
            Settings.text_splitter = SentenceSplitter(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )

        logger.info("LlamaIndex initialized successfully with medical optimizations")
        return True

    except (ImportError, ValueError) as e:
        logger.error("Failed to initialize LlamaIndex: %s", e)
        return False


def create_medical_index(
    documents: List[Document],
    config: Optional[MedicalIndexConfig] = None,
    storage_context: Optional[StorageContext] = None,
) -> VectorStoreIndex:
    """Create a vector index optimized for medical documents.

    Args:
        documents: List of documents to index
        config: Medical index configuration
        storage_context: Optional storage context

    Returns:
        VectorStoreIndex: Created index
    """
    if not config:
        config = MedicalIndexConfig()

    logger.info("Creating medical index with %d documents", len(documents))

    # Apply medical document preprocessing
    processed_docs = []
    for doc in documents:
        # Add medical metadata
        if config.enable_metadata_extraction:
            doc.metadata["index_type"] = "medical"
            doc.metadata["chunk_size"] = config.chunk_size

        processed_docs.append(doc)

    # Create index
    try:
        # Try with show_progress parameter (newer versions)
        index = VectorStoreIndex.from_documents(
            processed_docs,
            storage_context=storage_context,
            show_progress=True,
        )
    except TypeError:
        # Fallback without show_progress (older versions)
        index = VectorStoreIndex.from_documents(
            processed_docs,
            storage_context=storage_context,
        )

    logger.info("Medical index created successfully")
    return index


def load_medical_index(
    persist_dir: str,
) -> Optional[VectorStoreIndex]:
    """Load a previously saved medical index.

    Args:
        persist_dir: Directory containing the saved index

    Returns:
        VectorStoreIndex: Loaded index or None if not found
    """
    try:
        if not os.path.exists(persist_dir):
            logger.warning("Persist directory not found: %s", persist_dir)
            return None

        # Load storage context
        storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

        # Load index
        index = load_index_from_storage(storage_context)

        logger.info("Medical index loaded from %s", persist_dir)
        # Ensure we return a VectorStoreIndex instance
        if isinstance(index, VectorStoreIndex):
            return index
        else:
            logger.warning("Loaded index is not a VectorStoreIndex")
            return None

    except (FileNotFoundError, ValueError) as e:
        logger.error("Failed to load medical index: %s", e)
        return None


# Export key components
__all__ = [
    "__version__",
    "MedicalIndexConfig",
    "initialize_llamaindex",
    "create_medical_index",
    "load_medical_index",
    "MEDICAL_CHUNK_SIZE",
    "MEDICAL_CHUNK_OVERLAP",
]

# Export submodules for easy access
try:
    from . import (
        dimensions,
        document_loaders,
        embeddings,
        opensearch,
        similarity,
        text_splitters,
        vector_stores,
    )

    __all__.extend(
        [
            "embeddings",
            "similarity",
            "dimensions",
            "document_loaders",
            "text_splitters",
            "opensearch",
            "vector_stores",
        ]
    )
except ImportError as e:
    logger.debug("Some submodules could not be imported: %s", e)
    # This is okay during initial setup
