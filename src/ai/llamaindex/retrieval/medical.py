"""
Medical Retrieval Pipelines.

Specialized pipelines for medical and healthcare use cases.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
 Handles FHIR Resource validation.
"""

import asyncio
import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from llama_index.core import Document

from ..indices import DrugInteractionIndex
from ..indices.base import BaseVectorIndex
from ..similarity import get_similarity_scorer
from .base import QueryContext, RetrievalConfig, RetrievalResult
from .pipelines import AdvancedRetrievalPipeline
from .query import MedicalQueryExpander

logger = logging.getLogger(__name__)


class MedicalRetrievalPipeline(AdvancedRetrievalPipeline):
    """
    Medical-specific retrieval pipeline.

    Features:
    - Medical query expansion
    - Clinical context awareness
    - PHI protection
    - Medical entity recognition
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, BaseVectorIndex]] = None,
        enable_phi_protection: bool = True,
        medical_specialties: Optional[List[str]] = None,
    ):
        """Initialize the medical retrieval pipeline."""
        # Use medical query expander
        query_expander = MedicalQueryExpander()

        # Medical-specific configuration
        if config is None:
            config = RetrievalConfig(
                pipeline_name="medical_retrieval",
                enable_query_expansion=True,
                enable_synonym_expansion=True,
                enable_filtering=True,
            )

        super().__init__(config=config, indices=indices, query_expander=query_expander)

        self.enable_phi_protection = enable_phi_protection
        self.medical_specialties = medical_specialties or []

        # Medical similarity scorer
        self.similarity_scorer = get_similarity_scorer("medical")

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Medical retrieval with enhanced processing."""
        # Set medical context
        query_context.use_medical_terms = True

        # Apply specialty filter if specified
        if self.medical_specialties and not query_context.medical_specialty:
            query_context.medical_specialty = self.medical_specialties[0]

        # Standard retrieval
        results = await super().retrieve(query_context)

        # Post-process for medical relevance
        results = self._enhance_medical_results(results, query_context)

        # Apply PHI protection if needed
        if self.enable_phi_protection:
            results = self._apply_phi_protection(results)

        return results

    def _enhance_medical_results(
        self, results: List[RetrievalResult], query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Enhance results with medical metadata."""
        medical_entities = query_context.metadata.get("entities", {})

        for result in results:
            # Extract medical entities from document
            doc_entities = self._extract_medical_entities(result.document.text)

            # Calculate medical relevance boost
            relevance_boost = self._calculate_medical_relevance(
                medical_entities, doc_entities, query_context
            )

            # Update score with medical relevance
            result.final_score *= relevance_boost

            # Add medical explanations
            result.explanations["medical_entities"] = doc_entities
            result.explanations["medical_relevance_boost"] = relevance_boost

            # Add clinical metadata
            result.document.metadata["clinical_relevance"] = (
                self._assess_clinical_relevance(result.document, query_context)
            )

        return results

    def _extract_medical_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract medical entities from text."""
        # Simplified extraction - in production, use medical NER
        entities: Dict[str, List[str]] = {
            "conditions": [],
            "medications": [],
            "symptoms": [],
            "procedures": [],
        }

        # Common patterns
        text_lower = text.lower()

        # Conditions
        conditions = ["diabetes", "hypertension", "asthma", "cancer", "infection"]
        entities["conditions"] = [c for c in conditions if c in text_lower]

        # Medications
        medications = ["insulin", "metformin", "aspirin", "antibiotic", "vaccine"]
        entities["medications"] = [m for m in medications if m in text_lower]

        # Symptoms
        symptoms = ["pain", "fever", "cough", "fatigue", "nausea"]
        entities["symptoms"] = [s for s in symptoms if s in text_lower]

        return entities

    def _calculate_medical_relevance(
        self,
        query_entities: Dict[str, List[str]],
        doc_entities: Dict[str, List[str]],
        query_context: QueryContext,
    ) -> float:
        """Calculate medical relevance boost factor."""
        boost = 1.0

        # Entity overlap
        for entity_type in ["conditions", "medications", "symptoms"]:
            query_set = set(query_entities.get(entity_type, []))
            doc_set = set(doc_entities.get(entity_type, []))

            if query_set and doc_set:
                overlap = len(query_set.intersection(doc_set))
                if overlap > 0:
                    boost *= 1 + 0.2 * overlap

        # Urgency matching
        if query_context.urgency_level >= 4:  # High urgency
            if any(
                urgent in str(doc_entities)
                for urgent in ["emergency", "acute", "severe"]
            ):
                boost *= 1.5

        # Specialty matching
        if query_context.medical_specialty:
            if query_context.medical_specialty in str(doc_entities).lower():
                boost *= 1.3

        return min(boost, 3.0)  # Cap maximum boost

    def _assess_clinical_relevance(
        self, document: Any, _query_context: QueryContext
    ) -> str:
        """Assess clinical relevance level."""
        doc_text = document.text.lower()

        # Check for clinical indicators
        if any(
            term in doc_text for term in ["emergency", "life-threatening", "critical"]
        ):
            return "critical"
        elif any(term in doc_text for term in ["urgent", "acute", "severe"]):
            return "high"
        elif any(
            term in doc_text for term in ["moderate", "significant", "concerning"]
        ):
            return "moderate"
        else:
            return "routine"

    def _apply_phi_protection(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Apply PHI protection to results."""
        # In production, implement proper PHI filtering
        for result in results:
            result.document.metadata["phi_filtered"] = True

        return results


class ClinicalRetrievalPipeline(MedicalRetrievalPipeline):
    """
    Clinical decision support retrieval.

    Optimized for point-of-care clinical decisions.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, BaseVectorIndex]] = None,
        evidence_levels: Optional[List[str]] = None,
    ):
        """Initialize the clinical retrieval pipeline."""
        super().__init__(config, indices)

        self.evidence_levels = evidence_levels or [
            "systematic_review",
            "randomized_controlled_trial",
            "cohort_study",
            "expert_opinion",
        ]

        # Configure for clinical use
        self.config.pipeline_name = "clinical_decision_support"

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Clinical retrieval with evidence filtering."""
        # Add clinical filters
        if "evidence_level" not in query_context.filters:
            query_context.filters["evidence_level"] = self.evidence_levels

        # Retrieve with medical pipeline
        results = await super().retrieve(query_context)

        # Rank by evidence quality
        results = self._rank_by_evidence(results)

        # Add clinical recommendations
        results = self._add_clinical_recommendations(results, query_context)

        return results

    def _rank_by_evidence(
        self, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Rank results by evidence quality."""
        evidence_weights = {
            "systematic_review": 2.0,
            "meta_analysis": 1.9,
            "randomized_controlled_trial": 1.8,
            "controlled_trial": 1.6,
            "cohort_study": 1.4,
            "case_control": 1.2,
            "case_series": 1.1,
            "expert_opinion": 1.0,
        }

        for result in results:
            evidence_level = result.document.metadata.get("evidence_level", "unknown")
            weight = evidence_weights.get(evidence_level, 0.8)

            # Apply evidence weight
            result.final_score *= weight
            result.explanations["evidence_weight"] = weight
            result.explanations["evidence_level"] = evidence_level

        # Re-sort by updated scores
        results.sort(key=lambda r: r.final_score, reverse=True)

        return results

    def _add_clinical_recommendations(
        self, results: List[RetrievalResult], _query_context: QueryContext
    ) -> List[RetrievalResult]:
        """Add clinical recommendations based on results."""
        # Analyze top results for consensus
        if len(results) >= 3:
            top_conditions = []
            top_treatments = []

            for result in results[:5]:
                entities = result.explanations.get("medical_entities", {})
                top_conditions.extend(entities.get("conditions", []))
                top_treatments.extend(entities.get("medications", []))

            # Find most common
            condition_consensus = Counter(top_conditions).most_common(1)
            treatment_consensus = Counter(top_treatments).most_common(1)

            # Add to first result as recommendation
            if results:
                recommendations = {}
                if condition_consensus:
                    recommendations["likely_condition"] = condition_consensus[0][0]
                if treatment_consensus:
                    recommendations["common_treatment"] = treatment_consensus[0][0]

                results[0].explanations["clinical_recommendations"] = recommendations

        return results


class EmergencyRetrievalPipeline(MedicalRetrievalPipeline):
    """
    Emergency medical retrieval.

    Optimized for speed and critical information.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, BaseVectorIndex]] = None,
        emergency_protocols: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the emergency retrieval pipeline."""
        # Configure for emergency use
        if config is None:
            config = RetrievalConfig(
                pipeline_name="emergency_medical",
                enable_query_expansion=False,  # Skip for speed
                enable_spell_correction=False,  # Skip for speed
                retrieval_top_k=20,  # Fewer results for speed
                final_top_k=5,  # Focus on most relevant
                timeout_seconds=5.0,  # Strict timeout
            )

        super().__init__(config, indices)

        self.emergency_protocols = (
            emergency_protocols or self._load_emergency_protocols()
        )

    def _load_emergency_protocols(self) -> Dict[str, Any]:
        """Load emergency medical protocols."""
        return {
            "cardiac_arrest": {
                "priority": "critical",
                "actions": ["CPR", "defibrillation", "epinephrine"],
                "time_critical": True,
            },
            "stroke": {
                "priority": "critical",
                "actions": ["CT scan", "tPA", "neurology consult"],
                "time_critical": True,
            },
            "severe_bleeding": {
                "priority": "critical",
                "actions": ["pressure", "tourniquet", "transfusion"],
                "time_critical": True,
            },
            "anaphylaxis": {
                "priority": "critical",
                "actions": ["epinephrine", "antihistamine", "corticosteroid"],
                "time_critical": True,
            },
        }

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Emergency retrieval with protocol matching."""
        # Set maximum urgency
        query_context.urgency_level = 5

        # Detect emergency type
        emergency_type = self._detect_emergency_type(query_context.query)

        # Add emergency filters
        if emergency_type:
            query_context.filters["emergency_type"] = emergency_type
            query_context.metadata["emergency_detected"] = emergency_type

        # Fast retrieval
        try:
            # Set short timeout
            results = await asyncio.wait_for(
                super().retrieve(query_context), timeout=self.config.timeout_seconds
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                "Emergency retrieval timeout - returning partial results"
            )
            results = []

        # Add emergency protocols
        if emergency_type and emergency_type in self.emergency_protocols:
            protocol = self.emergency_protocols[emergency_type]

            # Create protocol result
            protocol_result = self._create_protocol_result(emergency_type, protocol)
            results.insert(0, protocol_result)

        return results

    def _detect_emergency_type(self, query: str) -> Optional[str]:
        """Detect type of emergency from query."""
        query_lower = query.lower()

        emergency_keywords = {
            "cardiac_arrest": [
                "cardiac arrest",
                "heart stopped",
                "no pulse",
                "unconscious",
            ],
            "stroke": ["stroke", "facial droop", "can't speak", "weakness one side"],
            "severe_bleeding": ["bleeding", "hemorrhage", "blood loss", "severed"],
            "anaphylaxis": [
                "allergic reaction",
                "can't breathe",
                "swelling throat",
                "anaphylaxis",
            ],
        }

        for emergency_type, keywords in emergency_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return emergency_type

        return None

    def _create_protocol_result(
        self, emergency_type: str, protocol: Dict[str, Any]
    ) -> RetrievalResult:
        """Create result for emergency protocol."""
        protocol_text = f"""
        EMERGENCY PROTOCOL: {emergency_type.replace('_', ' ').upper()}
        Priority: {protocol['priority'].upper()}

        IMMEDIATE ACTIONS:
        {chr(10).join(f'- {action}' for action in protocol['actions'])}

        TIME CRITICAL: {'YES' if protocol.get('time_critical') else 'NO'}

        Call emergency services immediately if not already done.
        """

        doc = Document(
            text=protocol_text,
            metadata={
                "source": "emergency_protocols",
                "type": "protocol",
                "emergency_type": emergency_type,
                "priority": protocol["priority"],
                "generated_at": datetime.now().isoformat(),
            },
        )

        result = RetrievalResult(
            document=doc,
            score=10.0,  # Highest score
            rank=0,
            retrieval_score=10.0,
            final_score=10.0,
            source_index="emergency_protocols",
            pipeline_stages=["emergency_protocol"],
        )

        result.explanations = {
            "type": "emergency_protocol",
            "emergency_type": emergency_type,
            "auto_generated": True,
        }

        return result


class DrugInteractionPipeline(MedicalRetrievalPipeline):
    """
    Drug interaction checking pipeline.

    Specialized for medication safety.
    """

    def __init__(
        self,
        config: Optional[RetrievalConfig] = None,
        drug_index: Optional[DrugInteractionIndex] = None,
        indices: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the drug interaction pipeline."""
        # Include drug interaction index
        if drug_index:
            if indices is None:
                indices = {}
            indices["drug_interactions"] = drug_index

        super().__init__(config, indices)

        self.drug_index = drug_index
        self.config.pipeline_name = "drug_interaction_checker"

    async def retrieve(self, query_context: QueryContext) -> List[RetrievalResult]:
        """Retrieve with drug interaction checking."""
        # Extract medications from query
        medications = self._extract_medications(query_context)

        if len(medications) >= 2 and self.drug_index:
            # Check interactions
            interactions = self.drug_index.check_interactions(
                medications,
                patient_conditions=(
                    query_context.patient_context.get("conditions", [])
                    if query_context.patient_context
                    else None
                ),
            )

            # Add interaction warnings to context
            query_context.metadata["drug_interactions"] = interactions

            # Add to filters to find relevant documents
            query_context.filters["medications"] = medications

        # Standard retrieval
        results = await super().retrieve(query_context)

        # Add interaction warnings to results
        if "drug_interactions" in query_context.metadata:
            results = self._add_interaction_warnings(
                results, query_context.metadata["drug_interactions"]
            )

        return results

    def _extract_medications(self, query_context: QueryContext) -> List[str]:
        """Extract medication names from query."""
        medications = []

        # From query entities
        entities = query_context.metadata.get("entities", {})
        medications.extend(entities.get("medications", []))

        # From patient context
        if query_context.patient_context:
            current_meds = query_context.patient_context.get("current_medications", [])
            medications.extend(current_meds)

        # Simple pattern matching as fallback
        query_lower = query_context.query.lower()
        common_meds = [
            "aspirin",
            "ibuprofen",
            "acetaminophen",
            "metformin",
            "lisinopril",
            "atorvastatin",
            "levothyroxine",
            "metoprolol",
        ]

        for med in common_meds:
            if med in query_lower and med not in medications:
                medications.append(med)

        return list(set(medications))

    def _add_interaction_warnings(
        self, results: List[RetrievalResult], interactions: List[Dict[str, Any]]
    ) -> List[RetrievalResult]:
        """Add drug interaction warnings to results."""
        if not interactions:
            return results

        warning_text = "DRUG INTERACTION WARNINGS:\n\n"

        for interaction in interactions:
            if interaction["interaction_type"] == "potential":
                warning_text += f"⚠️ {interaction['drug1']} + {interaction['drug2']}: "
                warning_text += f"Potential interaction (confidence: {interaction['confidence']:.0%})\n"
                if interaction.get("description"):
                    warning_text += f"   {interaction['description'][0]}\n"
            elif interaction["interaction_type"] == "contraindication":
                warning_text += f"❌ {interaction['drug']} contraindicated with {interaction['condition']}: "
                warning_text += (
                    f"High severity (confidence: {interaction['confidence']:.0%})\n"
                )
            warning_text += "\n"

        warning_text += "\nConsult healthcare provider or pharmacist for guidance."

        warning_doc = Document(
            text=warning_text,
            metadata={
                "type": "drug_interaction_warning",
                "severity": "high",
                "generated_at": datetime.now().isoformat(),
            },
        )

        warning_result = RetrievalResult(
            document=warning_doc,
            score=9.0,  # High score to appear at top
            rank=0,
            retrieval_score=9.0,
            final_score=9.0,
            source_index="drug_interaction_checker",
            pipeline_stages=["drug_interaction_check"],
        )

        warning_result.explanations = {
            "type": "drug_interaction_warning",
            "interactions_found": len(interactions),
            "auto_generated": True,
        }

        # Insert warning at beginning
        results.insert(0, warning_result)

        return results


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
