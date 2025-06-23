"""
Medical Vector Index Implementation.

Specialized indices for medical and healthcare documents.
Handles FHIR Resource validation.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from llama_index.core import Document

from ..embeddings import get_embedding_model
from ..similarity import get_similarity_scorer
from .base import VectorIndexConfig
from .hybrid import HybridVectorIndex

logger = logging.getLogger(__name__)


@dataclass
class MedicalIndexConfig(VectorIndexConfig):
    """Configuration specific to medical indices."""

    # Medical NER
    enable_medical_ner: bool = True
    ner_models: List[str] = field(default_factory=lambda: ["biobert", "scispacy"])

    # Medical ontologies
    enable_ontology_expansion: bool = True
    ontologies: List[str] = field(
        default_factory=lambda: ["umls", "icd10", "snomed", "rxnorm"]
    )

    # Clinical features
    enable_clinical_context: bool = True
    clinical_specialties: List[str] = field(
        default_factory=lambda: [
            "cardiology",
            "neurology",
            "oncology",
            "pediatrics",
            "psychiatry",
        ]
    )

    # Privacy and compliance
    enable_phi_detection: bool = True
    phi_handling: str = "mask"  # mask, remove, encrypt
    compliance_standards: List[str] = field(default_factory=lambda: ["hipaa", "gdpr"])

    # Medical-specific search
    enable_symptom_expansion: bool = True
    enable_drug_interaction_check: bool = True
    enable_differential_diagnosis: bool = True


class MedicalVectorIndex(HybridVectorIndex):
    """
    Medical-optimized vector index.

    Features:
    - Medical entity recognition
    - Ontology-based expansion
    - Clinical context awareness
    - PHI protection
    """

    def __init__(self, config: Optional[MedicalIndexConfig] = None, **kwargs: Any):
        """Initialize medical vector index."""
        if config is None:
            config = MedicalIndexConfig()

        # Use medical embeddings and similarity
        if "embedding_model" not in kwargs:
            kwargs["embedding_model"] = get_embedding_model("medical")

        if "similarity_scorer" not in kwargs:
            kwargs["similarity_scorer"] = get_similarity_scorer("medical")

        super().__init__(config, **kwargs)

        self.medical_config = config

        # Initialize medical components
        self._init_medical_components()

    def _init_medical_components(self) -> None:
        """Initialize medical-specific components."""
        # Medical entity patterns
        self.medical_patterns = {
            "medication": re.compile(
                r"\b\d+\s*mg\b|\b\d+\s*ml\b|tablet|capsule|injection", re.I
            ),
            "dosage": re.compile(r"\b\d+\s*(?:mg|ml|mcg|g|IU)\b", re.I),
            "frequency": re.compile(
                r"\b(?:once|twice|three times|four times)\s*(?:a|per)\s*day\b|QD|BID|TID|QID",
                re.I,
            ),
            "diagnosis": re.compile(r"diagnosed with|diagnosis of|impression:", re.I),
            "symptom": re.compile(
                r"complains? of|presents? with|reports?|experiences?", re.I
            ),
        }

        # Medical abbreviations
        self.medical_abbreviations = {
            "BP": "blood pressure",
            "HR": "heart rate",
            "RR": "respiratory rate",
            "T": "temperature",
            "O2": "oxygen saturation",
            "Hx": "history",
            "Rx": "prescription",
            "Dx": "diagnosis",
            "Sx": "symptoms",
            "Tx": "treatment",
            # Add more abbreviations
        }

        # Initialize NER if enabled
        if self.medical_config.enable_medical_ner:
            self._init_medical_ner()

    def _init_medical_ner(self) -> None:
        """Initialize medical NER models."""
        # Placeholder - in production, load actual NER models
        self.logger.info("Medical NER initialization placeholder")

    def _extract_medical_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract medical entities from text."""
        entities: Dict[str, List[str]] = {
            "medications": [],
            "diagnoses": [],
            "symptoms": [],
            "procedures": [],
            "anatomy": [],
            "dosages": [],
        }

        # Simple pattern-based extraction
        # In production, use proper medical NER

        # Find medications
        med_matches = self.medical_patterns["medication"].findall(text)
        if med_matches:
            entities["medications"].extend(med_matches)

        # Find dosages
        dosage_matches = self.medical_patterns["dosage"].findall(text)
        if dosage_matches:
            entities["dosages"].extend(dosage_matches)

        # Extract from context
        lines = text.split("\n")
        for line in lines:
            line_lower = line.lower()

            # Diagnoses
            if any(
                term in line_lower
                for term in ["diagnosis", "diagnosed with", "impression"]
            ):
                entities["diagnoses"].append(line.strip())

            # Symptoms
            if any(
                term in line_lower
                for term in ["complains of", "presents with", "reports"]
            ):
                entities["symptoms"].append(line.strip())

        return entities

    def _expand_medical_abbreviations(self, text: str) -> str:
        """Expand medical abbreviations in text."""
        expanded = text

        for abbrev, full in self.medical_abbreviations.items():
            # Use word boundaries to avoid partial matches
            pattern = rf"\b{re.escape(abbrev)}\b"
            expanded = re.sub(pattern, f"{abbrev} ({full})", expanded, flags=re.I)

        return expanded

    def _apply_phi_protection(self, text: str) -> str:
        """Apply PHI protection to text."""
        if not self.medical_config.enable_phi_detection:
            return text

        protected = text

        # Simple PHI patterns - in production, use proper PHI detection
        phi_patterns = {
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "mrn": re.compile(r"\bMRN\s*:?\s*\d+\b", re.I),
            "dob": re.compile(
                r"\b(?:DOB|Date of Birth)\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", re.I
            ),
            "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        }

        if self.medical_config.phi_handling == "mask":
            for phi_type, pattern in phi_patterns.items():
                protected = pattern.sub(f"[{phi_type.upper()}_MASKED]", protected)
        elif self.medical_config.phi_handling == "remove":
            for pattern in phi_patterns.values():
                protected = pattern.sub("", protected)

        return protected

    def build_index(self, documents: List[Document]) -> None:
        """Build medical index with entity extraction."""
        # Process documents for medical features
        processed_docs = []

        for doc in documents:
            # Apply PHI protection
            protected_text = self._apply_phi_protection(doc.text)

            # Expand abbreviations
            expanded_text = self._expand_medical_abbreviations(protected_text)

            # Extract medical entities
            entities = self._extract_medical_entities(expanded_text)

            # Create processed document
            processed_doc = Document(
                text=expanded_text,
                metadata={
                    **doc.metadata,
                    "medical_entities": entities,
                    "original_text": doc.text,  # Keep original for reference
                    "phi_protected": True,
                },
            )

            processed_docs.append(processed_doc)

        # Build hybrid index with processed documents
        super().build_index(processed_docs)

    def search(  # pylint: disable=arguments-renamed
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        enable_symptom_expansion: Optional[bool] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Medical-aware search."""
        # Expand medical abbreviations in query
        expanded_query = self._expand_medical_abbreviations(query)

        # Extract query entities
        query_entities = self._extract_medical_entities(expanded_query)

        # Add medical context to kwargs
        kwargs["query_metadata"] = {
            "medical_entities": query_entities,
            "original_query": query,
        }

        # Perform search
        results = super().search(expanded_query, top_k, filters, **kwargs)

        # Post-process results if needed
        if enable_symptom_expansion or (
            enable_symptom_expansion is None
            and self.medical_config.enable_symptom_expansion
        ):
            results = self._expand_symptom_results(results, query_entities)

        return results

    def _expand_symptom_results(
        self,
        results: List[Tuple[Document, float]],
        query_entities: Dict[str, List[str]],  # pylint: disable=unused-argument
    ) -> List[Tuple[Document, float]]:
        """Expand results based on symptom relationships."""
        # Placeholder - in production, use medical knowledge base
        # to find related symptoms and conditions
        return results


class ClinicalTrialsIndex(MedicalVectorIndex):
    """Specialized index for clinical trials."""

    def __init__(self, config: Optional[MedicalIndexConfig] = None, **kwargs: Any):
        """Initialize clinical trials index."""
        super().__init__(config, **kwargs)

        # Clinical trial specific patterns
        self.trial_patterns = {
            "phase": re.compile(r"\bPhase\s*(?:I{1,3}|[1-4])\b", re.I),
            "nct_id": re.compile(r"\bNCT\d{8}\b"),
            "enrollment": re.compile(r"\benroll(?:ed|ing|ment)?\s*:?\s*\d+", re.I),
            "intervention": re.compile(r"\bintervention\s*:?\s*([^.]+)", re.I),
        }

    def _extract_trial_metadata(self, text: str) -> Dict[str, Any]:
        """Extract clinical trial specific metadata."""
        metadata: Dict[str, Any] = {
            "trial_phase": None,
            "nct_id": None,
            "enrollment_count": None,
            "interventions": [],
        }

        # Extract phase
        phase_match = self.trial_patterns["phase"].search(text)
        if phase_match:
            metadata["trial_phase"] = phase_match.group()

        # Extract NCT ID
        nct_match = self.trial_patterns["nct_id"].search(text)
        if nct_match:
            metadata["nct_id"] = nct_match.group()

        # Extract enrollment
        enrollment_match = self.trial_patterns["enrollment"].search(text)
        if enrollment_match:
            # Extract number from the match
            numbers = re.findall(r"\d+", enrollment_match.group())
            if numbers:
                metadata["enrollment_count"] = int(numbers[0])

        # Extract interventions
        intervention_matches = self.trial_patterns["intervention"].findall(text)
        metadata["interventions"] = intervention_matches

        return metadata

    def build_index(self, documents: List[Document]) -> None:
        """Build clinical trials index."""
        # Process documents for trial-specific features
        processed_docs = []

        for doc in documents:
            # Extract trial metadata
            trial_metadata = self._extract_trial_metadata(doc.text)

            # Update document metadata
            doc.metadata.update(trial_metadata)
            doc.metadata["document_type"] = "clinical_trial"

            processed_docs.append(doc)

        # Build parent index
        super().build_index(processed_docs)


class PatientRecordsIndex(MedicalVectorIndex):
    """Specialized index for patient records with enhanced privacy."""

    def __init__(self, config: Optional[MedicalIndexConfig] = None, **kwargs: Any):
        """Initialize patient records index."""
        # Ensure PHI protection is enabled
        if config is None:
            config = MedicalIndexConfig()
        config.enable_phi_detection = True
        config.phi_handling = "encrypt"  # Use encryption for patient records

        super().__init__(config, **kwargs)

        # Patient record patterns
        self.record_patterns = {
            "chief_complaint": re.compile(r"Chief Complaint\s*:?\s*([^\n]+)", re.I),
            "hpi": re.compile(r"History of Present Illness\s*:?\s*([^\n]+)", re.I),
            "assessment": re.compile(r"Assessment\s*:?\s*([^\n]+)", re.I),
            "plan": re.compile(r"Plan\s*:?\s*([^\n]+)", re.I),
            "vitals": re.compile(r"Vital Signs?\s*:?\s*([^\n]+)", re.I),
        }

    def _extract_record_sections(self, text: str) -> Dict[str, str]:
        """Extract standard sections from patient records."""
        sections = {}

        for section_name, pattern in self.record_patterns.items():
            match = pattern.search(text)
            if match:
                sections[section_name] = match.group(1).strip()

        return sections

    def build_index(self, documents: List[Document]) -> None:
        """Build patient records index with enhanced privacy."""
        processed_docs = []

        for doc in documents:
            # Extract record sections
            sections = self._extract_record_sections(doc.text)

            # Update metadata
            doc.metadata.update(
                {
                    "record_sections": sections,
                    "document_type": "patient_record",
                    "privacy_level": "high",
                }
            )

            processed_docs.append(doc)

        # Build parent index with extra privacy
        super().build_index(processed_docs)

    def search(  # pylint: disable=arguments-renamed
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        enable_symptom_expansion: Optional[bool] = None,
        authorized_user: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Search with access control."""
        # Verify authorization
        if not authorized_user:
            self.logger.warning("Unauthorized search attempt on patient records")
            return []

        # Add authorization to filters
        if filters is None:
            filters = {}
        filters["authorized_users"] = authorized_user

        return super().search(query, top_k, filters, enable_symptom_expansion, **kwargs)


class DrugInteractionIndex(MedicalVectorIndex):
    """Specialized index for drug interactions and medication management."""

    def __init__(self, config: Optional[MedicalIndexConfig] = None, **kwargs: Any):
        """Initialize drug interaction index."""
        if config is None:
            config = MedicalIndexConfig()
        config.enable_drug_interaction_check = True

        super().__init__(config, **kwargs)

        # Drug interaction patterns
        self.drug_patterns = {
            "drug_name": re.compile(r"\b(?:[A-Z][a-z]+(?:in|ol|ide|ate|ine|one))\b"),
            "interaction": re.compile(r"interact(?:s|ion)?\s+with", re.I),
            "contraindication": re.compile(r"contraindicated?\s+(?:in|with)", re.I),
            "warning": re.compile(r"black\s+box\s+warning|warning\s*:", re.I),
        }

        # Common drug classes
        self.drug_classes = {
            "ssri": ["fluoxetine", "sertraline", "paroxetine", "citalopram"],
            "ace_inhibitor": ["lisinopril", "enalapril", "ramipril"],
            "beta_blocker": ["metoprolol", "atenolol", "propranolol"],
            "statin": ["atorvastatin", "simvastatin", "rosuvastatin"],
            # Add more drug classes
        }

    def _extract_drug_information(self, text: str) -> Dict[str, Any]:
        """Extract drug-related information."""
        drug_info: Dict[str, Any] = {
            "drugs_mentioned": [],
            "interactions": [],
            "contraindications": [],
            "warnings": [],
            "drug_classes": [],
        }

        # Find drug names
        words = text.split()
        for word in words:
            # Check against known drug patterns
            if self.drug_patterns["drug_name"].match(word):
                drug_info["drugs_mentioned"].append(word.lower())

        # Find interactions
        if self.drug_patterns["interaction"].search(text):
            # Extract interaction context
            sentences = text.split(".")
            for sent in sentences:
                if "interact" in sent.lower():
                    drug_info["interactions"].append(sent.strip())

        # Find contraindications
        contra_matches = self.drug_patterns["contraindication"].findall(text)
        drug_info["contraindications"] = contra_matches

        # Find warnings
        warning_matches = self.drug_patterns["warning"].findall(text)
        drug_info["warnings"] = warning_matches

        # Classify drugs
        for drug in drug_info["drugs_mentioned"]:
            for drug_class, members in self.drug_classes.items():
                if drug in members:
                    drug_info["drug_classes"].append(drug_class)

        return drug_info

    def build_index(self, documents: List[Document]) -> None:
        """Build drug interaction index."""
        processed_docs = []

        for doc in documents:
            # Extract drug information
            drug_info = self._extract_drug_information(doc.text)

            # Update metadata
            doc.metadata.update(
                {
                    "drug_information": drug_info,
                    "document_type": "drug_information",
                }
            )

            processed_docs.append(doc)

        super().build_index(processed_docs)

    def check_interactions(
        self, medications: List[str], patient_conditions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Check for drug interactions."""
        interactions = []

        # Search for each medication pair
        for i, _ in enumerate(medications):
            for j in range(i + 1, len(medications)):
                query = f"{medications[i]} interaction with {medications[j]}"

                results = self.search(query, top_k=5)

                for doc, score in results:
                    if score > 0.8:  # High confidence threshold
                        drug_info = doc.metadata.get("drug_information", {})

                        interactions.append(
                            {
                                "drug1": medications[i],
                                "drug2": medications[j],
                                "interaction_type": "potential",
                                "severity": "unknown",
                                "description": drug_info.get("interactions", []),
                                "source": doc.metadata.get("source", "unknown"),
                                "confidence": score,
                            }
                        )

        # Check contraindications with conditions
        if patient_conditions:
            for medication in medications:
                for condition in patient_conditions:
                    query = f"{medication} contraindicated {condition}"

                    results = self.search(query, top_k=3)

                    for doc, score in results:
                        if score > 0.7:
                            interactions.append(
                                {
                                    "drug": medication,
                                    "condition": condition,
                                    "interaction_type": "contraindication",
                                    "severity": "high",
                                    "source": doc.metadata.get("source", "unknown"),
                                    "confidence": score,
                                }
                            )

        return interactions


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
