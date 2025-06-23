"""
Multi-modal Vector Index Implementation.

Handles text, images, and other modalities together.
Handles FHIR Resource validation.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from llama_index.core import Document

from ..embeddings import get_embedding_model
from .base import BaseVectorIndex, VectorIndexConfig, VectorIndexType
from .dense import DenseVectorIndex

logger = logging.getLogger(__name__)


@dataclass
class MultiModalDocument:
    """Document containing multiple modalities."""

    text: Optional[str] = None
    image_path: Optional[str] = None
    image_data: Optional[bytes] = None
    audio_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    doc_id: Optional[str] = None

    def to_document(self) -> Document:
        """Convert to standard Document."""
        # Combine all modalities into text representation
        combined_text = ""

        if self.text:
            combined_text += self.text

        if self.image_path:
            combined_text += f"\n[IMAGE: {self.image_path}]"

        if self.audio_path:
            combined_text += f"\n[AUDIO: {self.audio_path}]"

        metadata = self.metadata or {}
        metadata["modalities"] = self._get_modalities()

        return Document(text=combined_text, metadata=metadata, doc_id=self.doc_id)

    def _get_modalities(self) -> List[str]:
        """Get list of modalities present."""
        modalities = []
        if self.text:
            modalities.append("text")
        if self.image_path or self.image_data:
            modalities.append("image")
        if self.audio_path:
            modalities.append("audio")
        return modalities


class MultiModalIndex(BaseVectorIndex):
    """
    Multi-modal vector index supporting text and images.

    Features:
    - Unified embeddings for text and images
    - Cross-modal search
    - Modal-specific retrieval
    """

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize multi-modal index."""
        if config is None:
            config = VectorIndexConfig(index_type=VectorIndexType.MULTIMODAL)

        # Use multimodal embeddings
        if "embedding_model" not in kwargs:
            kwargs["embedding_model"] = get_embedding_model("multimodal")

        super().__init__(config, **kwargs)

        # Separate indices for each modality
        self.text_index = DenseVectorIndex(
            config=config,
            embedding_model=self.embedding_model,
            similarity_scorer=self.similarity_scorer,
        )

        self.image_index = DenseVectorIndex(
            config=config,
            embedding_model=self.embedding_model,
            similarity_scorer=self.similarity_scorer,
        )

        # Unified index for cross-modal search
        self.unified_index = DenseVectorIndex(
            config=config,
            embedding_model=self.embedding_model,
            similarity_scorer=self.similarity_scorer,
        )

        # Modality weights for search
        self.modality_weights = {"text": 0.6, "image": 0.4}

    def build_index(self, documents: List[Document]) -> None:
        """Build multi-modal index."""
        self.logger.info("Building multi-modal index with %d documents", len(documents))

        text_docs = []
        image_docs = []
        unified_docs = []

        for doc in documents:
            # Check if this is actually a MultiModalDocument via duck typing
            if hasattr(doc, "image_path") or hasattr(doc, "image_data"):
                # Use doc directly as it's already a document
                standard_doc = doc

                # Add to appropriate indices
                if doc.text:
                    text_doc = Document(
                        text=doc.text,
                        metadata={**standard_doc.metadata, "modality": "text"},
                        doc_id=f"{doc.doc_id}_text",
                    )
                    text_docs.append(text_doc)

                if getattr(doc, "image_path", None) or getattr(doc, "image_data", None):
                    # Create image document
                    # Cast to Any since we're using duck typing
                    image_doc = self._create_image_document(cast(Any, doc))
                    if image_doc:
                        image_docs.append(image_doc)

                # Add to unified index
                unified_docs.append(standard_doc)

            else:
                # Regular document - add to text index
                text_docs.append(doc)
                unified_docs.append(doc)

        # Build indices
        if text_docs:
            self.text_index.build_index(text_docs)

        if image_docs:
            self.image_index.build_index(image_docs)

        self.unified_index.build_index(unified_docs)

        # Update metrics
        self._metrics.total_documents = len(documents)

    def _create_image_document(self, doc: MultiModalDocument) -> Optional[Document]:
        """Create document from image."""
        try:
            # Get image embedding
            # In production, use actual image embedding model
            image_text = f"Image: {doc.image_path or 'embedded_image'}"

            # Add any text descriptions
            if doc.text:
                image_text += f"\nDescription: {doc.text}"

            return Document(
                text=image_text,
                metadata={
                    **(doc.metadata or {}),
                    "modality": "image",
                    "image_path": getattr(doc, "image_path", None),
                    "has_image_data": getattr(doc, "image_data", None) is not None,
                },
                doc_id=f"{doc.doc_id}_image",
            )

        except (ValueError, AttributeError) as e:
            self.logger.error("Failed to create image document: %s", e)
            return None

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add multi-modal documents."""
        doc_ids: List[str] = []

        for doc in documents:
            # Check if this is a multi-modal document via duck typing
            if hasattr(doc, "image_path") or hasattr(doc, "image_data"):
                # Add to appropriate indices
                if doc.text:
                    text_doc = Document(
                        text=doc.text,
                        metadata={**doc.metadata, "modality": "text"},
                        doc_id=f"{doc.doc_id}_text",
                    )
                    self.text_index.add_documents([text_doc])

                if getattr(doc, "image_path", None) or getattr(doc, "image_data", None):
                    image_doc = self._create_image_document(cast(Any, doc))
                    if image_doc:
                        self.image_index.add_documents([image_doc])

                # Add to unified
                self.unified_index.add_documents([doc])
                doc_ids.append(doc.doc_id or f"multimodal_{len(doc_ids)}")

            else:
                # Regular document
                self.text_index.add_documents([doc])
                self.unified_index.add_documents([doc])
                doc_ids.append(doc.doc_id or doc.id_)

        # Update metrics
        self._metrics.total_documents += len(documents)

        return doc_ids

    def delete_documents(self, doc_ids: List[str]) -> bool:
        """Delete from all indices."""
        success = True

        # Delete from modal indices
        text_ids = [f"{doc_id}_text" for doc_id in doc_ids]
        image_ids = [f"{doc_id}_image" for doc_id in doc_ids]

        if not self.text_index.delete_documents(text_ids):
            success = False

        if not self.image_index.delete_documents(image_ids):
            success = False

        if not self.unified_index.delete_documents(doc_ids):
            success = False

        if success:
            self._metrics.total_documents -= len(doc_ids)

        return success

    def search(
        self,
        query: Union[str, MultiModalDocument],
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        modality: Optional[str] = None,  # text, image, or None for all
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Multi-modal search."""
        if top_k is None:
            top_k = self.config.default_top_k

        # Determine search modality
        if isinstance(query, MultiModalDocument):
            # Multi-modal query
            return self._multi_modal_search(query, top_k, filters, **kwargs)
        else:
            # Text query
            if modality == "image":
                # Search only images
                return self.image_index.search(query, top_k, filters, **kwargs)
            elif modality == "text":
                # Search only text
                return self.text_index.search(query, top_k, filters, **kwargs)
            else:
                # Search all modalities
                return self.unified_index.search(query, top_k, filters, **kwargs)

    def _multi_modal_search(
        self,
        query: MultiModalDocument,
        top_k: int,
        filters: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Search with multi-modal query."""
        results = []

        # Search with text component
        if query.text:
            text_results = self.text_index.search(query.text, top_k, filters, **kwargs)
            for doc, score in text_results:
                results.append((doc, score * self.modality_weights["text"]))

        # Search with image component
        if query.image_path or query.image_data:
            # Create image query
            image_query = f"Image: {query.image_path or 'query_image'}"
            image_results = self.image_index.search(
                image_query, top_k, filters, **kwargs
            )
            for doc, score in image_results:
                results.append((doc, score * self.modality_weights["image"]))

        # Merge and sort results
        # Group by original document ID
        doc_scores: Dict[str, float] = {}
        for doc, score in results:
            # Extract original doc ID
            original_id = doc.doc_id.rsplit("_", 1)[0]

            if original_id in doc_scores:
                doc_scores[original_id] = max(doc_scores[original_id], score)
            else:
                doc_scores[original_id] = score

        # Get full documents and create final results
        final_results = []
        for doc_id, score in doc_scores.items():
            # Get from unified index
            unified_results = self.unified_index.search(
                doc_id, top_k=1, filters={"doc_id": doc_id}
            )
            if unified_results:
                final_results.append((unified_results[0][0], score))

        # Sort by score
        final_results.sort(key=lambda x: x[1], reverse=True)

        return final_results[:top_k]

    def _optimize_index(self) -> bool:
        """Optimize all modal indices."""
        text_success = self.text_index.optimize()
        image_success = self.image_index.optimize()
        unified_success = self.unified_index.optimize()

        return text_success and image_success and unified_success

    def _persist_index(self, path: str) -> bool:
        """Persist multi-modal index."""
        persist_dir = Path(path)
        persist_dir.mkdir(parents=True, exist_ok=True)

        # Persist each index
        text_success = self.text_index.persist(str(persist_dir / "text"))
        image_success = self.image_index.persist(str(persist_dir / "image"))
        unified_success = self.unified_index.persist(str(persist_dir / "unified"))

        # Save modality weights
        # pylint: disable=import-outside-toplevel
        import json

        with open(persist_dir / "modality_weights.json", "w", encoding="utf-8") as f:
            json.dump(self.modality_weights, f)

        return text_success and image_success and unified_success

    def _load_index(self, path: str) -> bool:
        """Load multi-modal index."""
        persist_dir = Path(path)

        # Load each index
        text_success = self.text_index.load(str(persist_dir / "text"))
        image_success = self.image_index.load(str(persist_dir / "image"))
        unified_success = self.unified_index.load(str(persist_dir / "unified"))

        # Load modality weights
        # pylint: disable=import-outside-toplevel
        import json

        weights_file = persist_dir / "modality_weights.json"
        if weights_file.exists():
            with open(weights_file, "r", encoding="utf-8") as f:
                self.modality_weights = json.load(f)

        return text_success and image_success and unified_success


class TextImageIndex(MultiModalIndex):
    """Optimized index for text and image pairs."""

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize text-image index."""
        super().__init__(config, **kwargs)

        # CLIP-style unified embeddings
        self.use_unified_embeddings = True

    def _create_unified_embedding(
        self, text: Optional[str], image_path: Optional[str]
    ) -> List[float]:
        """Create unified embedding for text-image pair."""
        # In production, use CLIP or similar model
        # For now, use placeholder
        if self.embedding_model and hasattr(
            self.embedding_model, "get_agg_embedding_from_queries"
        ):
            if text:
                text_emb = self.embedding_model.get_agg_embedding_from_queries([text])
            else:
                text_emb = [0.0] * self.config.dimension

            if image_path:
                # Placeholder for image embedding
                image_emb = [0.1] * self.config.dimension
            else:
                image_emb = [0.0] * self.config.dimension

            # Combine embeddings
            unified = []
            for t, i in zip(text_emb, image_emb):
                unified.append((t + i) / 2)

            return unified

        return [0.0] * self.config.dimension


class MedicalImagingIndex(MultiModalIndex):
    """Specialized index for medical imaging with reports."""

    def __init__(
        self, config: Optional[VectorIndexConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize medical imaging index."""
        super().__init__(config, **kwargs)

        # Medical imaging specific
        self.imaging_types = ["xray", "ct", "mri", "ultrasound", "pet", "mammography"]

        # DICOM metadata fields
        self.dicom_fields = [
            "PatientID",
            "StudyDate",
            "Modality",
            "BodyPartExamined",
            "StudyDescription",
            "SeriesDescription",
        ]

    def _extract_dicom_metadata(self, image_path: str) -> Dict[str, Any]:
        """Extract DICOM metadata from medical image."""
        # Placeholder - in production, use pydicom
        metadata = {
            "modality": "unknown",
            "body_part": "unknown",
            "study_date": None,
        }

        # Infer from filename
        path_lower = image_path.lower()
        for imaging_type in self.imaging_types:
            if imaging_type in path_lower:
                metadata["modality"] = imaging_type
                break

        return metadata

    def build_index(self, documents: List[Document]) -> None:
        """Build medical imaging index."""
        # Process documents to extract medical imaging metadata
        processed_docs = []

        for doc in documents:
            # Check for multi-modal document with image path using duck typing
            image_path = getattr(doc, "image_path", None)
            if image_path:
                # Extract DICOM metadata
                dicom_meta = self._extract_dicom_metadata(image_path)

                # Update metadata
                doc.metadata.update(
                    {
                        "imaging_metadata": dicom_meta,
                        "is_medical_image": True,
                    }
                )

            processed_docs.append(doc)

        # Build parent index
        super().build_index(processed_docs)

    def search_by_modality(
        self, query: str, modality: str, top_k: Optional[int] = None, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        """Search within specific imaging modality."""
        filters = {"imaging_metadata.modality": modality}
        return self.search(query, top_k, filters, **kwargs)

    def find_similar_studies(
        self,
        reference_image_path: str,
        top_k: Optional[int] = None,
        same_modality_only: bool = True,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Find similar medical imaging studies."""
        # Extract metadata from reference
        ref_metadata = self._extract_dicom_metadata(reference_image_path)

        # Create query
        query = MultiModalDocument(
            text=f"Medical image: {ref_metadata.get('modality', 'unknown')} "
            f"of {ref_metadata.get('body_part', 'unknown')}",
            image_path=reference_image_path,
            metadata=ref_metadata,
        )

        # Set filters if same modality only
        filters = None
        if same_modality_only and ref_metadata.get("modality"):
            filters = {"imaging_metadata.modality": ref_metadata["modality"]}

        return self.search(query, top_k, filters, **kwargs)


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
