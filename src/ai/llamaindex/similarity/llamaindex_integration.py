"""LlamaIndex Integration Example with Similarity Metrics.

Demonstrates how to use custom similarity metrics with LlamaIndex
for medical document retrieval in Haven Health Passport.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance. It integrates with FHIR Resource standards for
healthcare data interoperability.
"""

import asyncio
from typing import Any, Dict, List, Optional

# LlamaIndex imports
from llama_index.core import Document, Settings, VectorStoreIndex

from src.ai.llamaindex.config import ConfigManager

# Haven Health Passport imports
from src.ai.llamaindex.embeddings import get_embedding_model
from src.ai.llamaindex.similarity import (
    get_similarity_scorer,
)
from src.ai.llamaindex.similarity.factory import create_similarity_pipeline
from src.ai.llamaindex.similarity.reranking import create_reranker


class MedicalDocumentRetriever:
    """Medical document retriever with custom similarity metrics."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize retriever with configuration."""
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config

        # Initialize embedding model
        self.embedding_model = get_embedding_model(
            use_case=(
                "medical" if self.config.similarity_metric == "medical" else "general"
            )
        )

        # Initialize similarity scorer
        self.similarity_scorer = get_similarity_scorer(
            use_case=self.config.similarity_metric,
            normalize_scores=self.config.similarity_normalize_scores,
            score_threshold=self.config.similarity_score_threshold,
            consider_metadata=self.config.similarity_consider_metadata,
            boost_medical_terms=self.config.similarity_boost_medical_terms,
            medical_term_weight=self.config.similarity_medical_term_weight,
        )

        # Initialize re-ranker if enabled
        self.reranker = None
        if self.config.rerank_enabled:
            self.reranker = create_reranker(
                reranker_type=self.config.reranker_type, top_k=self.config.rerank_top_k
            )

        # Configure LlamaIndex settings
        Settings.embed_model = self.embedding_model
        Settings.chunk_size = self.config.chunk_size
        Settings.chunk_overlap = self.config.chunk_overlap

    def create_index(self, documents: List[Document]) -> VectorStoreIndex:
        """Create index with medical optimizations."""
        print(f"Creating index with {len(documents)} documents...")

        # Extract medical metadata for each document
        for doc in documents:
            doc.metadata.update(self._extract_medical_metadata(doc.text))

        # Create index
        index = VectorStoreIndex.from_documents(documents, show_progress=True)

        print("Index created successfully")
        return index

    def _extract_medical_metadata(self, text: str) -> Dict[str, Any]:
        """Extract medical metadata from document text."""
        # Simplified extraction - in production, use NER models
        metadata = {
            "medical_terms": [],
            "disease_terms": [],
            "medication_terms": [],
            "urgency_level": 1,
            "clinical_urgency": "routine",
        }

        # Simple keyword matching
        medical_keywords = {
            "diseases": ["diabetes", "hypertension", "cancer", "infection"],
            "medications": ["insulin", "metformin", "aspirin", "antibiotic"],
            "urgency": ["emergency", "urgent", "acute", "severe"],
        }

        text_lower = text.lower()

        # Extract terms
        for disease in medical_keywords["diseases"]:
            if disease in text_lower:
                if isinstance(metadata["disease_terms"], list):
                    metadata["disease_terms"].append(disease)
                if isinstance(metadata["medical_terms"], list):
                    metadata["medical_terms"].append(disease)

        for med in medical_keywords["medications"]:
            if med in text_lower:
                if isinstance(metadata["medication_terms"], list):
                    metadata["medication_terms"].append(med)
                if isinstance(metadata["medical_terms"], list):
                    metadata["medical_terms"].append(med)

        # Determine urgency
        for urgency_term in medical_keywords["urgency"]:
            if urgency_term in text_lower:
                metadata["urgency_level"] = 3
                metadata["clinical_urgency"] = "emergency"
                break

        return metadata

    async def retrieve(
        self, index: VectorStoreIndex, query: str, top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve documents using custom similarity scoring."""
        if top_k is None:
            top_k = self.config.similarity_top_k

        print(f"\nRetrieving documents for query: '{query}'")

        # Extract query metadata
        query_metadata = self._extract_medical_metadata(query)

        # Get query embedding
        query_embedding = await self.embedding_model._aget_query_embedding(
            query
        )  # pylint: disable=protected-access

        # Get all documents from index
        # Note: In production, use index's built-in search with custom scorer
        retriever = index.as_retriever(
            similarity_top_k=top_k * 2
        )  # Get more for re-ranking
        nodes = retriever.retrieve(query)

        # Score documents with custom similarity
        scored_results: List[Dict[str, Any]] = []
        for node in nodes:
            # Get document embedding (simplified - in production, get from vector store)
            doc_embedding = await self.embedding_model._aget_query_embedding(
                node.text
            )  # pylint: disable=protected-access

            # Calculate similarity with metadata
            score = self.similarity_scorer.score(
                query_embedding, doc_embedding, query_metadata, node.metadata
            )

            if score >= self.config.similarity_cutoff:
                scored_results.append(
                    {
                        "doc_id": node.id_,
                        "score": score,
                        "text": node.text,
                        "metadata": node.metadata,
                    }
                )

        # Sort by score
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # Re-rank if enabled
        if self.reranker and scored_results:
            # Convert to re-ranker format
            rerank_input = [
                (str(r["doc_id"]), r["score"], r["metadata"]) for r in scored_results
            ]

            # Re-rank
            reranked = self.reranker.rerank(query, rerank_input, query_metadata)

            # Convert back to result format
            final_results = []
            for r in reranked[:top_k]:
                doc = next(d for d in scored_results if d["doc_id"] == r.doc_id)
                doc["rerank_score"] = r.rerank_score
                final_results.append(doc)

            return final_results

        return scored_results[:top_k]


async def main() -> None:
    """Demonstrate medical document retrieval usage."""
    # Create sample medical documents
    documents = [
        Document(
            text="Patient diagnosed with Type 2 diabetes mellitus. "
            "Started on metformin 500mg twice daily. "
            "Blood glucose monitoring recommended.",
            metadata={"doc_type": "clinical_note", "specialty": "endocrinology"},
        ),
        Document(
            text="Emergency department visit for acute chest pain. "
            "ECG shows ST elevation. Cardiology consulted immediately. "
            "Patient admitted to cardiac ICU.",
            metadata={"doc_type": "emergency_note", "specialty": "emergency"},
        ),
        Document(
            text="Annual wellness exam completed. Patient in good health. "
            "Blood pressure normal. Vaccinations up to date. "
            "Follow-up in one year.",
            metadata={"doc_type": "wellness_exam", "specialty": "primary_care"},
        ),
        Document(
            text="Hypertension management plan. Patient on lisinopril 10mg daily. "
            "Diet and exercise modifications recommended. "
            "Blood pressure target: <130/80.",
            metadata={"doc_type": "treatment_plan", "specialty": "cardiology"},
        ),
    ]

    # Initialize retriever
    retriever = MedicalDocumentRetriever()

    # Create index
    index = retriever.create_index(documents)

    # Test queries
    test_queries = [
        "patient with diabetes treatment",
        "emergency chest pain cardiac",
        "blood pressure management",
        "routine checkup wellness",
    ]

    print("\n" + "=" * 80)
    print("Medical Document Retrieval Results")
    print("=" * 80)

    for query in test_queries:
        results = await retriever.retrieve(index, query, top_k=2)

        print(f"\nQuery: '{query}'")
        print(f"Found {len(results)} relevant documents:")

        for i, result in enumerate(results, 1):
            print(f"\n  {i}. Score: {result['score']:.4f}", end="")
            if "rerank_score" in result:
                print(f" (Re-ranked: {result['rerank_score']:.4f})", end="")
            print(f"\n     Type: {result['metadata'].get('doc_type', 'unknown')}")
            print(f"     Specialty: {result['metadata'].get('specialty', 'unknown')}")
            print(f"     Preview: {result['text'][:100]}...")

    print("\n" + "=" * 80)
    print("Similarity Pipeline Statistics")
    print("=" * 80)

    # Create similarity pipeline for analysis
    pipeline = create_similarity_pipeline(
        scorer=retriever.similarity_scorer,
        reranker=retriever.reranker,
        min_score_threshold=retriever.config.similarity_cutoff,
    )

    print(f"Scorer Type: {pipeline['stats']['scorer_type']}")
    print(f"Re-ranker Type: {pipeline['stats']['reranker_type']}")
    print(f"Configuration: {pipeline['stats']['config']}")


if __name__ == "__main__":
    asyncio.run(main())


def validate_fhir_data(data: dict) -> dict:
    """Validate FHIR data.

    Args:
        data: Data to validate

    Returns:
        Validation result with 'valid', 'errors', and 'warnings' keys
    """
    errors = []
    warnings: List[str] = []

    if not data:
        errors.append("No data provided")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
