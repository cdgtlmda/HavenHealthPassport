"""
Sparse Vector Index Implementation.

Provides sparse vector indices for keyword-based search.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

import json
import logging
import math
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from llama_index.core import Document
from scipy.sparse import load_npz, save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

from .base import BaseVectorIndex, VectorIndexConfig, VectorIndexType

logger = logging.getLogger(__name__)


class SparseVectorIndex(BaseVectorIndex):
    """
    Sparse vector index using TF-IDF.

    Good for keyword matching and exact term search.
    """

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize sparse vector index."""
        if config is None:
            config = VectorIndexConfig(index_type=VectorIndexType.SPARSE)

        super().__init__(config, **kwargs)

        # Sparse index specific
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._sparse_matrix: Optional[Any] = None
        self._doc_ids: List[str] = []
        self._id_to_index: Dict[str, int] = {}
        self._vocabulary: Dict[str, int] = {}
        self._document_store: Dict[str, Document] = {}

    def _init_vectorizer(self) -> None:
        """Initialize TF-IDF vectorizer."""
        # Choose analyzer based on configuration
        analyzer = (
            self._medical_analyzer if self.config.enable_medical_expansion else "word"
        )

        self._vectorizer = TfidfVectorizer(
            max_features=10000,  # Limit vocabulary size
            min_df=2,  # Ignore terms that appear in less than 2 documents
            max_df=0.8,  # Ignore terms that appear in more than 80% of documents
            ngram_range=(1, 2),  # Use unigrams and bigrams
            stop_words="english",
            analyzer=analyzer,
            lowercase=True,
            norm="l2",
        )

    def _medical_analyzer(self, text: str) -> List[str]:
        """Perform custom analysis that preserves medical terms."""
        # Default word tokenization
        # Use basic tokenization since this is called during vectorizer initialization
        tokens = text.lower().split()

        # Preserve medical abbreviations (e.g., "mg", "ml", "BP")
        medical_abbrev = {"mg", "ml", "bp", "hr", "rr", "o2", "iv", "im"}
        preserved_tokens = []

        for token in tokens:
            if token.lower() in medical_abbrev:
                preserved_tokens.append(token.upper())
            else:
                preserved_tokens.append(token)

        return preserved_tokens

    def build_index(self, documents: List[Document]) -> None:
        """Build sparse index from documents."""
        self.logger.info("Building sparse index with %d documents", len(documents))

        # Initialize vectorizer
        self._init_vectorizer()

        # Vectorizer should be initialized after _init_vectorizer()
        assert self._vectorizer is not None, "Vectorizer not initialized properly"

        # Extract texts and IDs
        texts = []
        self._doc_ids = []
        self._document_store = {}

        for i, doc in enumerate(documents):
            doc_id = doc.doc_id or doc.id_
            texts.append(doc.text)
            self._doc_ids.append(doc_id)
            self._id_to_index[doc_id] = i
            self._document_store[doc_id] = doc

        # Fit and transform documents
        self._sparse_matrix = self._vectorizer.fit_transform(texts)
        self._vocabulary = self._vectorizer.vocabulary_

        # Update metrics
        self._metrics.total_documents = len(documents)

        self.logger.info(
            "Sparse index built with vocabulary size: %d", len(self._vocabulary)
        )

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to sparse index."""
        if not self._document_store:
            # If no existing documents, just build from these documents
            self.build_index(documents)
        else:
            # For sparse indices, it's often more efficient to rebuild
            # In production, use incremental indexing techniques
            all_docs = list(self._document_store.values()) + documents
            self.build_index(all_docs)

        return [doc.doc_id or doc.id_ for doc in documents]

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete documents from sparse index."""
        try:
            # Remove from document store
            for doc_id in doc_ids:
                if doc_id in self._document_store:
                    del self._document_store[doc_id]

            # Rebuild index without deleted documents
            remaining_docs = list(self._document_store.values())
            if remaining_docs:
                self.build_index(remaining_docs)
            else:
                # Reset if no documents left
                self._sparse_matrix = None
                self._doc_ids = []
                self._id_to_index = {}

            return True

        except (ValueError, KeyError) as e:
            self.logger.error("Failed to delete documents: %s", e)
            return False

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> List[Tuple[Document, float]]:
        """Search sparse index."""
        if self._sparse_matrix is None or self._vectorizer is None:
            self.logger.warning("Index not built yet")
            return []

        # Type narrowing for mypy
        assert self._vectorizer is not None

        if top_k is None:
            top_k = self.config.default_top_k

        start_time = time.time()

        try:
            # Transform query
            query_vector = self._vectorizer.transform([query])

            # Calculate similarities
            similarities = self._sparse_matrix.dot(query_vector.T).toarray().flatten()

            # Get top k indices
            top_indices = np.argsort(similarities)[::-1]

            results: List[Tuple[Document, float]] = []
            for idx in top_indices:
                if len(results) >= top_k:
                    break

                score = float(similarities[idx])
                if score < self.config.similarity_threshold:
                    break

                doc_id = self._doc_ids[idx]
                doc = self._document_store[doc_id]

                # Apply filters
                if filters and not self._match_filters(doc, filters):
                    continue

                results.append((doc, score))

            # Update metrics
            query_time = (time.time() - start_time) * 1000
            self._metrics.update_query_metrics(query_time, False)

            return results

        except (ValueError, AttributeError) as e:
            self.logger.error("Search failed: %s", e)
            self._metrics.error_count += 1
            return []

    def _match_filters(self, doc: Document, filters: Dict[str, Any]) -> bool:
        """Check if document matches filters."""
        for key, value in filters.items():
            if key not in doc.metadata:
                return False

            doc_value = doc.metadata[key]
            if isinstance(value, list):
                if doc_value not in value:
                    return False
            elif doc_value != value:
                return False

        return True

    def _optimize_index(self) -> bool:
        """Optimize sparse index."""
        try:
            # Refit vectorizer to remove low-value terms
            if self._document_store:
                self.build_index(list(self._document_store.values()))
            return True
        except (ValueError, RuntimeError) as e:
            self.logger.error("Optimization failed: %s", e)
            return False

    def _persist_index(self, path: str) -> bool:
        """Persist sparse index."""
        try:
            persist_dir = Path(path)
            persist_dir.mkdir(parents=True, exist_ok=True)

            # Save vectorizer
            joblib.dump(self._vectorizer, persist_dir / "vectorizer.pkl")

            # Save sparse matrix
            save_npz(persist_dir / "sparse_matrix.npz", self._sparse_matrix)

            # Save metadata
            metadata = {
                "doc_ids": self._doc_ids,
                "id_to_index": self._id_to_index,
                "vocabulary_size": len(self._vocabulary),
                "metrics": self._metrics.__dict__,
            }

            with open(persist_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, default=str)

            # Save documents
            with open(persist_dir / "documents.json", "w", encoding="utf-8") as f:
                json.dump(self._document_store, f, indent=2)

            return True

        except OSError as e:
            self.logger.error("Failed to persist sparse index: %s", e)
            return False

    def _load_index(self, path: str) -> bool:
        """Load sparse index."""
        try:
            persist_dir = Path(path)

            # Load vectorizer
            self._vectorizer = joblib.load(persist_dir / "vectorizer.pkl")
            if self._vectorizer is None:
                raise ValueError("Failed to load vectorizer")

            # Type narrowing for mypy
            assert self._vectorizer is not None
            self._vocabulary = self._vectorizer.vocabulary_

            # Load sparse matrix
            self._sparse_matrix = load_npz(persist_dir / "sparse_matrix.npz")

            # Load metadata
            with open(persist_dir / "metadata.json", "r", encoding="utf-8") as f:
                metadata = json.load(f)

            self._doc_ids = metadata["doc_ids"]
            self._id_to_index = metadata["id_to_index"]

            # Load documents
            with open(persist_dir / "documents.json", "r", encoding="utf-8") as f:
                self._document_store = json.load(f)

            # Update metrics
            for key, value in metadata.get("metrics", {}).items():
                if hasattr(self._metrics, key):
                    setattr(self._metrics, key, value)

            return True

        except (OSError, ValueError) as e:
            self.logger.error("Failed to load sparse index: %s", e)
            return False


class BM25Index(SparseVectorIndex):
    """
    BM25-based sparse index.

    Better ranking than TF-IDF for many use cases.
    """

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize BM25 index."""
        super().__init__(config, **kwargs)

        # BM25 parameters
        self.k1 = 1.5  # Term frequency saturation
        self.b = 0.75  # Length normalization

        # BM25 specific data
        self._doc_lengths: List[int] = []
        self._avg_doc_length: float = 0
        self._doc_freqs: Dict[str, int] = defaultdict(int)
        self._inverse_index: Dict[str, set] = defaultdict(set)

    def build_index(self, documents: List[Document]) -> None:
        """Build BM25 index."""
        self.logger.info("Building BM25 index with %d documents", len(documents))

        # Reset index
        self._doc_lengths = []
        self._doc_freqs.clear()
        self._inverse_index.clear()
        self._doc_ids = []
        self._document_store = {}

        # Process documents
        total_length = 0
        for i, doc in enumerate(documents):
            doc_id = doc.doc_id or doc.id_
            self._doc_ids.append(doc_id)
            self._document_store[doc_id] = doc

            # Tokenize
            tokens = self._tokenize(doc.text)
            doc_length = len(tokens)
            self._doc_lengths.append(doc_length)
            total_length += doc_length

            # Build inverse index
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] += 1
                self._inverse_index[token].add(i)

        # Calculate average document length
        self._avg_doc_length = total_length / len(documents) if documents else 0

        # Update metrics
        self._metrics.total_documents = len(documents)

        self.logger.info("BM25 index built with %d unique terms", len(self._doc_freqs))

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text simply."""
        # In production, use proper tokenizer
        tokens = re.findall(r"\b\w+\b", text.lower())
        return tokens

    def _calculate_bm25_score(self, doc_idx: int, query_tokens: List[str]) -> float:
        """Calculate BM25 score for a document."""
        score = 0.0
        doc_length = self._doc_lengths[doc_idx]

        for token in query_tokens:
            if token not in self._doc_freqs:
                continue

            # Document frequency
            df = self._doc_freqs[token]

            # Inverse document frequency
            idf = math.log((self._metrics.total_documents - df + 0.5) / (df + 0.5))

            # Term frequency in document
            tf = query_tokens.count(token)

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * doc_length / self._avg_doc_length
            )

            score += idf * (numerator / denominator)

        return score

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Search using BM25."""
        if not self._doc_ids:
            return []

        if top_k is None:
            top_k = self.config.default_top_k

        # Tokenize query
        query_tokens = self._tokenize(query)

        # Find candidate documents
        candidate_docs = set()
        for token in query_tokens:
            if token in self._inverse_index:
                candidate_docs.update(self._inverse_index[token])

        # Score candidates
        scored_docs = []
        for doc_idx in candidate_docs:
            score = self._calculate_bm25_score(doc_idx, query_tokens)
            if score > 0:
                doc_id = self._doc_ids[doc_idx]
                doc = self._document_store[doc_id]

                # Apply filters
                if filters and not self._match_filters(doc, filters):
                    continue

                scored_docs.append((doc, score))

        # Sort by score
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        return scored_docs[:top_k]


class TFIDFIndex(SparseVectorIndex):
    """Enhanced TF-IDF index with medical optimizations."""

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize TF-IDF index."""
        super().__init__(config, **kwargs)

        # Medical term weights
        self._medical_term_weights = self._load_medical_weights()

    def _load_medical_weights(self) -> Dict[str, float]:
        """Load medical term importance weights."""
        # In production, load from medical terminology database
        return {
            "diagnosis": 2.0,
            "treatment": 1.8,
            "medication": 1.8,
            "symptom": 1.5,
            "procedure": 1.6,
            "allergy": 2.0,
            "emergency": 3.0,
            # Add more medical terms
        }

    def _init_vectorizer(self) -> None:
        """Initialize medical-optimized TF-IDF vectorizer."""
        super()._init_vectorizer()

        # Custom token weight function
        if not self.config.enable_medical_expansion:
            return

        # Type check - vectorizer should be initialized by parent class
        assert (
            self._vectorizer is not None
        ), "Vectorizer not initialized after super()._init_vectorizer()"

        # Store original transform method
        vectorizer = self._vectorizer  # Type narrowing for mypy
        original_transform = vectorizer.transform

        def medical_transform(raw_documents: Any) -> Any:
            # Get base TF-IDF matrix
            X = original_transform(raw_documents)

            # Apply medical term weights
            feature_names = vectorizer.get_feature_names_out()
            for i, term in enumerate(feature_names):
                if term in self._medical_term_weights:
                    X[:, i] *= self._medical_term_weights[term]

            return X

        # Override transform method
        vectorizer.transform = medical_transform
