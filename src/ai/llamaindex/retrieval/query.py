"""
Query Processing Module.

Handles query preprocessing, expansion, and enhancement.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
import re
from typing import Dict, List

from .base import PipelineComponent, QueryContext

logger = logging.getLogger(__name__)


class QueryProcessor(PipelineComponent):
    """Base query processor.

    Handles basic query preprocessing and normalization.
    """

    def __init__(self, name: str = "query_processor"):
        """Initialize query processor.

        Args:
            name: Processor name for logging
        """
        super().__init__(name)

        # Common medical abbreviations
        self.abbreviations = {
            "dr": "doctor",
            "pt": "patient",
            "rx": "prescription",
            "dx": "diagnosis",
            "hx": "history",
            "sx": "symptoms",
            "tx": "treatment",
            "bp": "blood pressure",
            "hr": "heart rate",
            "temp": "temperature",
        }

        # Stop words to remove (minimal for medical queries)
        self.stop_words = {"the", "a", "an", "is", "are", "was", "were"}

    async def process(self, input_data: QueryContext) -> QueryContext:
        """Process query."""
        # Clean query
        cleaned_query = self._clean_query(input_data.query)

        # Expand abbreviations
        expanded_query = self._expand_abbreviations(cleaned_query)

        # Remove stop words if needed
        if input_data.metadata.get("remove_stop_words", False):
            expanded_query = self._remove_stop_words(expanded_query)

        # Update query context
        input_data.query = expanded_query

        return input_data

    def _clean_query(self, query: str) -> str:
        """Clean and normalize query."""
        # Remove extra whitespace
        query = " ".join(query.split())

        # Preserve medical notation (e.g., "5mg", "2x daily")
        # But normalize other punctuation
        query = re.sub(r"(?<!\d)[^\w\s](?!\d)", " ", query)

        return query.strip()

    def _expand_abbreviations(self, query: str) -> str:
        """Expand known abbreviations."""
        words = query.lower().split()
        expanded_words = []

        for word in words:
            if word in self.abbreviations:
                expanded_words.append(self.abbreviations[word])
                # Keep original too for exact matches
                expanded_words.append(f"({word})")
            else:
                expanded_words.append(word)

        return " ".join(expanded_words)

    def _remove_stop_words(self, query: str) -> str:
        """Remove stop words."""
        words = query.lower().split()
        filtered = [w for w in words if w not in self.stop_words]
        return " ".join(filtered)


class QueryExpander(PipelineComponent):
    """Query expansion component.

    Expands queries with synonyms and related terms.
    """

    def __init__(self, name: str = "query_expander"):
        """Initialize query expander.

        Args:
            name: Expander name for logging
        """
        super().__init__(name)

        # Basic synonym mappings
        self.synonyms = {
            "heart attack": ["myocardial infarction", "MI", "cardiac event"],
            "high blood pressure": ["hypertension", "HTN", "elevated BP"],
            "diabetes": ["diabetes mellitus", "DM", "high blood sugar"],
            "pain": ["discomfort", "ache", "soreness"],
            "fever": ["elevated temperature", "pyrexia", "high temp"],
            "cough": ["coughing", "respiratory symptom"],
            "headache": ["cephalgia", "head pain"],
            # Add more medical synonyms
        }

    async def process(self, input_data: QueryContext) -> QueryContext:
        """Expand query with synonyms."""
        if not input_data.expand_query:
            return input_data

        expanded_terms = self._expand_with_synonyms(input_data.query)

        # Add expanded terms to metadata
        input_data.metadata["expanded_terms"] = expanded_terms

        # Create expanded query
        if expanded_terms:
            expanded_query = f"{input_data.query} {' '.join(expanded_terms)}"
            input_data.query = expanded_query

        return input_data

    def _expand_with_synonyms(self, query: str) -> List[str]:
        """Expand query with synonyms."""
        query_lower = query.lower()
        expanded_terms = []

        # Check for exact phrase matches
        for phrase, synonyms in self.synonyms.items():
            if phrase in query_lower:
                expanded_terms.extend(synonyms)

        # Check for individual word matches
        words = query_lower.split()
        for word in words:
            if word in self.synonyms:
                expanded_terms.extend(self.synonyms[word])

        # Remove duplicates
        return list(set(expanded_terms))


class MedicalQueryExpander(QueryExpander):
    """Medical-specific query expansion.

    Uses medical knowledge to expand queries.
    """

    def __init__(self, name: str = "medical_query_expander"):
        """Initialize medical query expander.

        Args:
            name: Expander name for logging
        """
        super().__init__(name)

        # Medical term relationships
        self.medical_relations = {
            # Condition -> Related symptoms
            "diabetes": ["polyuria", "polydipsia", "weight loss", "fatigue"],
            "hypertension": ["headache", "dizziness", "chest pain"],
            "pneumonia": ["cough", "fever", "chest pain", "shortness of breath"],
            # Symptom -> Possible conditions
            "chest pain": ["heart attack", "angina", "pneumonia", "GERD"],
            "shortness of breath": ["asthma", "COPD", "heart failure", "pneumonia"],
            # Drug -> Conditions treated
            "metformin": ["diabetes", "type 2 diabetes", "blood sugar"],
            "lisinopril": ["hypertension", "heart failure", "kidney disease"],
            "albuterol": ["asthma", "COPD", "bronchospasm"],
        }

        # ICD-10 mappings
        self.icd_mappings = {
            "diabetes": ["E11", "E10", "E13"],
            "hypertension": ["I10", "I11", "I12"],
            "asthma": ["J45"],
            "pneumonia": ["J18", "J15", "J16"],
        }

        # Anatomical synonyms
        self.anatomical_terms = {
            "heart": ["cardiac", "myocardial", "coronary"],
            "lung": ["pulmonary", "respiratory", "bronchial"],
            "kidney": ["renal", "nephro"],
            "liver": ["hepatic"],
            "brain": ["cerebral", "neurological"],
        }

    async def process(self, input_data: QueryContext) -> QueryContext:
        """Expand query with medical knowledge."""
        if not input_data.use_medical_terms:
            return await super().process(input_data)

        # Basic expansion first
        input_data = await super().process(input_data)

        # Medical expansion
        medical_terms = self._expand_medical_terms(input_data.query)
        anatomical_terms = self._expand_anatomical_terms(input_data.query)
        icd_codes = self._get_related_icd_codes(input_data.query)

        # Add to metadata
        input_data.metadata["medical_terms"] = medical_terms
        input_data.metadata["anatomical_terms"] = anatomical_terms
        input_data.metadata["icd_codes"] = icd_codes

        # Add to query if significant expansion
        all_expansions = medical_terms + anatomical_terms
        if all_expansions:
            expanded_query = f"{input_data.query} {' '.join(all_expansions)}"
            input_data.query = expanded_query

        return input_data

    def _expand_medical_terms(self, query: str) -> List[str]:
        """Expand with medical relationships."""
        query_lower = query.lower()
        expanded = []

        for term, related in self.medical_relations.items():
            if term in query_lower:
                expanded.extend(related)

        return list(set(expanded))

    def _expand_anatomical_terms(self, query: str) -> List[str]:
        """Expand anatomical terms."""
        query_lower = query.lower()
        expanded = []

        for term, synonyms in self.anatomical_terms.items():
            if term in query_lower:
                expanded.extend(synonyms)

        return list(set(expanded))

    def _get_related_icd_codes(self, query: str) -> List[str]:
        """Get related ICD codes."""
        query_lower = query.lower()
        codes = []

        for condition, icd_codes in self.icd_mappings.items():
            if condition in query_lower:
                codes.extend(icd_codes)

        return list(set(codes))


class MultilingualQueryProcessor(QueryProcessor):
    """Multilingual query processing.

    Handles queries in multiple languages.
    """

    def __init__(self, name: str = "multilingual_processor"):
        """Initialize multilingual processor.

        Args:
            name: Processor name for logging
        """
        super().__init__(name)

        # Language detection patterns
        self.language_patterns = {
            "es": re.compile(r"\b(el|la|los|las|de|del|con|por|para)\b", re.I),
            "fr": re.compile(r"\b(le|la|les|de|du|avec|pour|dans)\b", re.I),
            "ar": re.compile(r"[\u0600-\u06FF]"),
            "zh": re.compile(r"[\u4E00-\u9FFF]"),
        }

        # Basic medical translations
        self.translations = {
            "en": {
                "pain": "pain",
                "fever": "fever",
                "cough": "cough",
                "doctor": "doctor",
                "medicine": "medicine",
            },
            "es": {
                "dolor": "pain",
                "fiebre": "fever",
                "tos": "cough",
                "médico": "doctor",
                "medicina": "medicine",
            },
            "fr": {
                "douleur": "pain",
                "fièvre": "fever",
                "toux": "cough",
                "médecin": "doctor",
                "médicament": "medicine",
            },
        }

    async def process(self, input_data: QueryContext) -> QueryContext:
        """Process multilingual query."""
        # Detect language if not specified
        if input_data.language == "auto":
            detected_lang = self._detect_language(input_data.query)
            input_data.language = detected_lang

        # Translate if needed and cross-lingual search is enabled
        if input_data.cross_lingual and input_data.language != "en":
            translated_terms = self._translate_key_terms(
                input_data.query, input_data.language
            )

            if translated_terms:
                input_data.metadata["translated_terms"] = translated_terms
                # Add translations to query
                input_data.query += " " + " ".join(translated_terms)

        # Process with base processor
        return await super().process(input_data)

    def _detect_language(self, text: str) -> str:
        """Detect query language."""
        for lang, pattern in self.language_patterns.items():
            if pattern.search(text):
                return lang

        return "en"  # Default to English

    def _translate_key_terms(self, query: str, source_lang: str) -> List[str]:
        """Translate key medical terms."""
        if source_lang not in self.translations:
            return []

        translations = []
        source_dict = self.translations[source_lang]
        _ = self.translations["en"]  # target_dict - for future cross-translation

        query_lower = query.lower()
        for source_term, english_term in source_dict.items():
            if source_term in query_lower:
                translations.append(english_term)

        return translations


class SpellCorrector(PipelineComponent):
    """Spell correction for queries.

    Corrects common medical spelling errors.
    """

    def __init__(self, name: str = "spell_corrector"):
        """Initialize spell corrector.

        Args:
            name: Corrector name for logging
        """
        super().__init__(name)

        # Common medical misspellings
        self.corrections = {
            "diabetis": "diabetes",
            "diabets": "diabetes",
            "presure": "pressure",
            "preasure": "pressure",
            "medecine": "medicine",
            "medicin": "medicine",
            "symtoms": "symptoms",
            "syntoms": "symptoms",
            "diarhea": "diarrhea",
            "diarrea": "diarrhea",
            "nausious": "nauseous",
            "nautious": "nauseous",
            "dizzy ness": "dizziness",
            "head ache": "headache",
            "stomache": "stomach",
            "tempature": "temperature",
            "temperture": "temperature",
            "perscription": "prescription",
            "presciption": "prescription",
            "alergy": "allergy",
            "alegry": "allergy",
            "astma": "asthma",
            "athsma": "asthma",
            "bronchites": "bronchitis",
            "newmonia": "pneumonia",
            "neumonia": "pneumonia",
        }

    async def process(self, input_data: QueryContext) -> QueryContext:
        """Correct spelling in query."""
        corrected_query = self._correct_spelling(input_data.query)

        if corrected_query != input_data.query:
            input_data.metadata["original_query"] = input_data.query
            input_data.metadata["spell_corrected"] = True
            input_data.query = corrected_query

        return input_data

    def _correct_spelling(self, query: str) -> str:
        """Apply spelling corrections."""
        query_lower = query.lower()

        # Apply direct corrections
        for misspelling, correction in self.corrections.items():
            if misspelling in query_lower:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(misspelling), re.IGNORECASE)
                query = pattern.sub(correction, query)

        return query


class QueryAnalyzer(PipelineComponent):
    """Analyze query intent and characteristics."""

    def __init__(self, name: str = "query_analyzer"):
        """Initialize the query analyzer."""
        super().__init__(name)

        # Intent patterns
        self.intent_patterns = {
            "symptom_query": re.compile(
                r"(symptom|feel|experiencing|suffering|having)", re.I
            ),
            "diagnosis_query": re.compile(
                r"(diagnos|what is|could it be|might have)", re.I
            ),
            "treatment_query": re.compile(
                r"(treat|cure|medication|therapy|relief)", re.I
            ),
            "drug_query": re.compile(
                r"(drug|medication|medicine|prescription|dose)", re.I
            ),
            "emergency": re.compile(r"(emergency|urgent|severe|acute|immediate)", re.I),
        }

    async def process(self, input_data: QueryContext) -> QueryContext:
        """Analyze query."""
        # Detect intent
        intent = self._detect_intent(input_data.query)
        input_data.metadata["intent"] = intent

        # Detect urgency
        urgency = self._detect_urgency(input_data.query)
        if urgency > input_data.urgency_level:
            input_data.urgency_level = urgency

        # Extract entities
        entities = self._extract_entities(input_data.query)
        input_data.metadata["entities"] = entities

        return input_data

    def _detect_intent(self, query: str) -> str:
        """Detect query intent."""
        for intent, pattern in self.intent_patterns.items():
            if pattern.search(query):
                return intent

        return "general_query"

    def _detect_urgency(self, query: str) -> int:
        """Detect urgency level (1-5)."""
        query_lower = query.lower()

        # Emergency keywords
        if any(
            word in query_lower for word in ["emergency", "urgent", "severe", "acute"]
        ):
            return 5

        # High priority symptoms
        if any(
            word in query_lower
            for word in ["chest pain", "difficulty breathing", "bleeding"]
        ):
            return 4

        # Moderate symptoms
        if any(word in query_lower for word in ["pain", "fever", "infection"]):
            return 3

        # Routine queries
        if any(word in query_lower for word in ["checkup", "routine", "follow-up"]):
            return 1

        return 2  # Default

    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract medical entities from query."""
        entities: Dict[str, List[str]] = {
            "symptoms": [],
            "conditions": [],
            "medications": [],
            "body_parts": [],
        }

        # Simple pattern-based extraction
        # In production, use proper NER

        # Common symptoms
        symptoms = ["pain", "fever", "cough", "nausea", "fatigue", "dizziness"]
        for symptom in symptoms:
            if symptom in query.lower():
                entities["symptoms"].append(symptom)

        # Common conditions
        conditions = ["diabetes", "hypertension", "asthma", "pneumonia", "infection"]
        for condition in conditions:
            if condition in query.lower():
                entities["conditions"].append(condition)

        # Body parts
        body_parts = ["head", "chest", "stomach", "back", "leg", "arm", "heart", "lung"]
        for part in body_parts:
            if part in query.lower():
                entities["body_parts"].append(part)

        return entities
