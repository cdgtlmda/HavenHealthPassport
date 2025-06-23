"""Voice Search Module.

This module implements voice-based search functionality for the Haven Health Passport system,
allowing users to search for medical records, medications, appointments, and other health
information using natural language voice commands. Handles FHIR Bundle Resource
validation for search results.

Security Note: All PHI data processed through voice search must be encrypted at rest
and in transit using AES-256 encryption standards.

Access Control: Voice search functionality requires proper authentication and authorization
to ensure PHI data is only accessible to authorized users.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.healthcare.fhir_client import FHIRClient
from src.services.health_record_service import HealthRecordService
from src.translation.medical_terms import MedicalTermTranslator
from src.voice.confidence_thresholds import ConfidenceManager
from src.voice.language_detection import LanguageDetectionManager

logger = logging.getLogger(__name__)


class SearchCategory(Enum):
    """Categories of searchable content in the health passport."""

    ALL = "all"
    MEDICAL_RECORDS = "medical_records"
    MEDICATIONS = "medications"
    APPOINTMENTS = "appointments"
    PROVIDERS = "providers"
    TEST_RESULTS = "test_results"
    IMMUNIZATIONS = "immunizations"
    CONDITIONS = "conditions"
    PROCEDURES = "procedures"
    ALLERGIES = "allergies"
    VITALS = "vitals"
    DOCUMENTS = "documents"
    EMERGENCY_CONTACTS = "emergency_contacts"


class SearchIntent(Enum):
    """Types of search intents."""

    FIND_SPECIFIC = "find_specific"  # Looking for a specific item
    LIST_ALL = "list_all"  # List all items of a type
    RECENT = "recent"  # Recent items
    BY_DATE = "by_date"  # Items from specific date/range
    BY_PROVIDER = "by_provider"  # Items from specific provider
    BY_LOCATION = "by_location"  # Items from specific location
    BY_STATUS = "by_status"  # Items with specific status
    URGENT = "urgent"  # Urgent/emergency items


@dataclass
class SearchFilter:
    """Represents a filter to apply to search results."""

    field: str
    operator: str  # equals, contains, greater_than, less_than, between
    value: Any

    def apply(self, items: List[Dict]) -> List[Dict]:
        """Apply this filter to a list of items."""
        filtered = []
        for item in items:
            if self.field in item:
                if self.operator == "equals" and item[self.field] == self.value:
                    filtered.append(item)
                elif (
                    self.operator == "contains"
                    and str(self.value).lower() in str(item[self.field]).lower()
                ):
                    filtered.append(item)
                elif self.operator == "greater_than" and item[self.field] > self.value:
                    filtered.append(item)
                elif self.operator == "less_than" and item[self.field] < self.value:
                    filtered.append(item)
                elif self.operator == "between" and isinstance(self.value, tuple):
                    if self.value[0] <= item[self.field] <= self.value[1]:
                        filtered.append(item)
        return filtered


@dataclass
class SearchQuery:
    """Represents a parsed voice search query."""

    raw_text: str
    category: SearchCategory
    intent: SearchIntent
    keywords: List[str]
    filters: List[SearchFilter] = field(default_factory=list)
    language: str = "en"
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_fhir_params(self) -> Dict[str, Any]:
        """Convert search query to FHIR search parameters."""
        params = {}

        # Add keywords as text search
        if self.keywords:
            params["_text"] = " ".join(self.keywords)

        # Add date filters
        for search_filter in self.filters:
            if search_filter.field == "date" and search_filter.operator == "between":
                params["date"] = (
                    f"ge{search_filter.value[0].isoformat()}&date=le{search_filter.value[1].isoformat()}"
                )
            elif (
                search_filter.field == "date"
                and search_filter.operator == "greater_than"
            ):
                params["date"] = f"gt{search_filter.value.isoformat()}"

        return params


@dataclass
class SearchResult:
    """Represents a search result item."""

    id: str
    category: SearchCategory
    title: str
    summary: str
    date: Optional[datetime] = None
    relevance_score: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    highlight_text: Optional[str] = None

    def to_voice_response(self, language: str = "en") -> str:
        """Convert result to voice-friendly response."""
        # language parameter can be used for future localization
        _ = language  # Mark as intentionally unused
        response_parts = [self.title]

        if self.summary:
            response_parts.append(self.summary)

        if self.date:
            # Format date for voice
            date_str = self.date.strftime("%B %d, %Y")
            response_parts.append(f"from {date_str}")

        return ". ".join(response_parts)


class VoiceSearchEngine:
    """Main voice search engine implementation."""

    def __init__(
        self,
        fhir_client: Optional[FHIRClient] = None,
        health_service: Optional[HealthRecordService] = None,
    ):
        """Initialize the voice search engine.

        Args:
            fhir_client: FHIR client for health record searches
            health_service: Health record service for data access
        """
        self.fhir_client = fhir_client
        self.health_service = health_service
        self.language_detector = LanguageDetectionManager()
        self.confidence_manager = ConfidenceManager()
        self.medical_translator = MedicalTermTranslator()

        # Initialize search patterns
        self._init_search_patterns()

        # Cache for frequently searched items
        self._search_cache: Dict[str, Tuple[List[SearchResult], datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)

    def _init_search_patterns(self) -> None:
        """Initialize voice search patterns and keywords."""
        self.category_keywords = {
            SearchCategory.MEDICATIONS: [
                "medication",
                "medicine",
                "drug",
                "prescription",
                "pill",
                "tablet",
                "dose",
                "meds",
                "pharmacy",
            ],
            SearchCategory.APPOINTMENTS: [
                "appointment",
                "visit",
                "schedule",
                "booking",
                "consultation",
                "checkup",
                "follow-up",
                "meeting",
            ],
            SearchCategory.TEST_RESULTS: [
                "test",
                "result",
                "lab",
                "blood",
                "urine",
                "x-ray",
                "scan",
                "imaging",
                "report",
                "analysis",
            ],
            SearchCategory.PROVIDERS: [
                "doctor",
                "physician",
                "nurse",
                "specialist",
                "clinic",
                "hospital",
                "provider",
                "practitioner",
                "therapist",
            ],
            SearchCategory.IMMUNIZATIONS: [
                "vaccine",
                "vaccination",
                "immunization",
                "shot",
                "jab",
                "injection",
                "booster",
            ],
            SearchCategory.CONDITIONS: [
                "condition",
                "diagnosis",
                "disease",
                "illness",
                "disorder",
                "syndrome",
                "infection",
                "problem",
            ],
            SearchCategory.ALLERGIES: [
                "allergy",
                "allergic",
                "reaction",
                "intolerance",
                "sensitivity",
                "allergen",
            ],
            SearchCategory.VITALS: [
                "vital",
                "vitals",
                "blood pressure",
                "temperature",
                "pulse",
                "heart rate",
                "oxygen",
                "weight",
                "height",
                "bmi",
            ],
        }

        self.intent_patterns = {
            SearchIntent.RECENT: [
                r"\b(recent|latest|last|newest|current)\b",
                r"\b(today|yesterday|this week|this month)\b",
            ],
            SearchIntent.BY_DATE: [
                r"\b(on|from|between|since|before|after)\b.*\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2})\b",
                r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            ],
            SearchIntent.URGENT: [
                r"\b(urgent|emergency|critical|important|priority)\b",
                r"\b(asap|immediately|now)\b",
            ],
        }

    async def search_by_voice(
        self, voice_input: str, language: Optional[str] = None
    ) -> List[SearchResult]:
        """Search for health information using voice input.

        Args:
            voice_input: Raw voice input text
            language: Language code (auto-detected if not provided)

        Returns:
            List of search results
        """
        try:
            # Detect language if not provided
            if not language:
                language = await self.language_detector.detect_language(voice_input)

            # Parse the voice query
            query = await self._parse_voice_query(voice_input, language)

            # Check cache first
            cache_key = self._get_cache_key(query)
            if cache_key in self._search_cache:
                cached_results, timestamp = self._search_cache[cache_key]
                if datetime.now() - timestamp < self._cache_ttl:
                    logger.info("Returning cached results for: %s", voice_input)
                    return cached_results

            # Execute search based on category
            results = await self._execute_search(query)

            # Apply filters
            if query.filters:
                results = self._apply_filters(results, query.filters)

            # Rank results by relevance
            results = self._rank_results(results, query)

            # Cache results
            self._search_cache[cache_key] = (results, datetime.now())

            return results

        except (ValueError, KeyError, AttributeError) as e:
            logger.error("Voice search error: %s", str(e))
            return []

    async def _parse_voice_query(self, voice_input: str, language: str) -> SearchQuery:
        """Parse voice input into a structured search query."""
        # Convert to lowercase for analysis
        text_lower = voice_input.lower()

        # Detect search category
        category = self._detect_category(text_lower)

        # Detect search intent
        intent = self._detect_intent(text_lower)

        # Extract keywords
        keywords = self._extract_keywords(voice_input, category)

        # Extract filters
        filters = self._extract_filters(text_lower, intent)

        # Calculate confidence
        confidence = self._calculate_query_confidence(
            voice_input, category, intent, keywords
        )

        return SearchQuery(
            raw_text=voice_input,
            category=category,
            intent=intent,
            keywords=keywords,
            filters=filters,
            language=language,
            confidence=confidence,
        )

    def _detect_category(self, text: str) -> SearchCategory:
        """Detect the search category from voice input."""
        category_scores = {}

        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score

        if category_scores:
            # Return category with highest score
            return max(category_scores.items(), key=lambda x: x[1])[0]

        return SearchCategory.ALL

    def _detect_intent(self, text: str) -> SearchIntent:
        """Detect the search intent from voice input."""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return intent

        return SearchIntent.FIND_SPECIFIC

    def _extract_keywords(
        self, text: str, category: Optional[SearchCategory] = None
    ) -> List[str]:
        """Extract relevant keywords from voice input."""
        # category parameter can be used for category-specific keyword extraction
        _ = category  # Mark as intentionally unused
        # Remove common words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "find",
            "search",
            "show",
            "get",
            "look",
            "want",
            "please",
            "me",
            "my",
            "i",
        }

        # Tokenize and filter
        words = text.lower().split()
        keywords = []

        for word in words:
            # Clean punctuation
            word = re.sub(r"[^\w\s-]", "", word)

            # Skip stop words and category keywords
            if word and word not in stop_words:
                # Skip words that are just category indicators
                is_category_word = any(
                    word in keywords_list
                    for cat, keywords_list in self.category_keywords.items()
                )
                if not is_category_word:
                    keywords.append(word)

        return keywords

    def _extract_filters(self, text: str, intent: SearchIntent) -> List[SearchFilter]:
        """Extract search filters from voice input."""
        filters = []

        # Date filters
        if intent == SearchIntent.BY_DATE:
            date_filter = self._extract_date_filter(text)
            if date_filter:
                filters.append(date_filter)

        # Status filters
        status_patterns = {
            "active": ["active", "current", "ongoing"],
            "completed": ["completed", "finished", "done"],
            "cancelled": ["cancelled", "canceled", "stopped"],
        }

        for status, patterns in status_patterns.items():
            if any(pattern in text for pattern in patterns):
                filters.append(
                    SearchFilter(field="status", operator="equals", value=status)
                )

        return filters

    def _extract_date_filter(self, text: str) -> Optional[SearchFilter]:
        """Extract date filter from text."""
        # Today
        if "today" in text:
            today = datetime.now().date()
            return SearchFilter(field="date", operator="equals", value=today)

        # Yesterday
        if "yesterday" in text:
            yesterday = datetime.now().date() - timedelta(days=1)
            return SearchFilter(field="date", operator="equals", value=yesterday)

        # This week
        if "this week" in text:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            return SearchFilter(
                field="date", operator="between", value=(week_start, today)
            )

        return None

    def _calculate_query_confidence(
        self,
        text: Optional[str] = None,
        category: Optional[SearchCategory] = None,
        intent: Optional[SearchIntent] = None,
        keywords: Optional[List[str]] = None,
    ) -> float:
        """Calculate confidence score for the parsed query."""
        # text parameter can be used for more sophisticated confidence calculation
        _ = text  # Mark as intentionally unused
        confidence = 0.5  # Base confidence

        # Boost if category was clearly identified
        if category != SearchCategory.ALL:
            confidence += 0.2

        # Boost if intent was clearly identified
        if intent != SearchIntent.FIND_SPECIFIC:
            confidence += 0.1

        # Boost based on number of keywords
        if keywords:
            confidence += min(0.2, len(keywords) * 0.05)

        return min(1.0, confidence)

    async def _execute_search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute the search based on the parsed query."""
        results = []

        # Simple implementation - in production would use FHIR client
        # This is a placeholder to make the class functional
        if query.category == SearchCategory.MEDICATIONS:
            results = await self._search_medications(query)
        elif query.category == SearchCategory.APPOINTMENTS:
            results = await self._search_appointments(query)
        else:
            results = await self._search_all(query)

        return results

    async def _search_medications(self, query: SearchQuery) -> List[SearchResult]:
        """Search for medications."""
        results = []

        if self.fhir_client:
            # Search using FHIR
            search_params = {
                "_text": " ".join(query.keywords) if query.keywords else None,
                "_count": 50,
            }

            try:
                # TODO: FHIRClient needs search_resources method implementation
                # For now, return empty results to prevent runtime errors
                if hasattr(self.fhir_client, "search_resources"):
                    medications = await self.fhir_client.search_resources(
                        "MedicationRequest", search_params
                    )
                else:
                    medications = []

                for med in medications:
                    result = SearchResult(
                        id=med.get("id", ""),
                        category=SearchCategory.MEDICATIONS,
                        title=self._extract_medication_name(med),
                        summary=self._extract_medication_summary(med),
                        date=self._parse_fhir_date(med.get("authoredOn")),
                        data=med,
                    )
                    results.append(result)

            except (ValueError, KeyError, AttributeError) as e:
                logger.error("FHIR medication search error: %s", str(e))

        return results

    async def _search_appointments(self, query: SearchQuery) -> List[SearchResult]:
        """Search for appointments."""
        results = []

        if self.fhir_client:
            search_params = {
                "_text": " ".join(query.keywords) if query.keywords else None,
                "_count": 50,
            }

            try:
                # TODO: FHIRClient needs search_resources method implementation
                # For now, return empty results to prevent runtime errors
                if hasattr(self.fhir_client, "search_resources"):
                    appointments = await self.fhir_client.search_resources(
                        "Appointment", search_params
                    )
                else:
                    appointments = []

                for apt in appointments:
                    result = SearchResult(
                        id=apt.get("id", ""),
                        category=SearchCategory.APPOINTMENTS,
                        title=self._extract_appointment_title(apt),
                        summary=self._extract_appointment_summary(apt),
                        date=self._parse_fhir_date(apt.get("start")),
                        data=apt,
                    )
                    results.append(result)

            except (ValueError, KeyError, AttributeError) as e:
                logger.error("FHIR appointment search error: %s", str(e))

        return results

    async def _search_all(self, query: SearchQuery) -> List[SearchResult]:
        """Search across all categories."""
        # Simple implementation
        all_results = []

        # Execute searches in parallel
        search_tasks = [
            self._search_medications(query),
            self._search_appointments(query),
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Combine results
        for result_list in results:
            if isinstance(result_list, list):
                all_results.extend(result_list)

        return all_results

    def _apply_filters(
        self, results: List[SearchResult], filters: List[SearchFilter]
    ) -> List[SearchResult]:
        """Apply filters to search results."""
        filtered_results = results

        for search_filter in filters:
            # Convert results to dicts for filtering
            result_dicts = []
            for result in filtered_results:
                result_dict = {
                    "id": result.id,
                    "category": result.category.value,
                    "title": result.title,
                    "summary": result.summary,
                    "date": result.date,
                }
                result_dict.update(result.data)
                result_dicts.append(result_dict)

            # Apply filter
            filtered_dicts = search_filter.apply(result_dicts)

            # Convert back to SearchResult objects
            filtered_results = []
            for result in results:
                for filtered_dict in filtered_dicts:
                    if result.id == filtered_dict["id"]:
                        filtered_results.append(result)
                        break

        return filtered_results

    def _rank_results(
        self, results: List[SearchResult], query: SearchQuery
    ) -> List[SearchResult]:
        """Rank search results by relevance."""
        for result in results:
            score = 0.0

            # Score based on keyword matches in title
            title_lower = result.title.lower()
            for keyword in query.keywords:
                if keyword.lower() in title_lower:
                    score += 0.3

            # Score based on keyword matches in summary
            if result.summary:
                summary_lower = result.summary.lower()
                for keyword in query.keywords:
                    if keyword.lower() in summary_lower:
                        score += 0.1

            # Boost recent results
            if result.date and query.intent == SearchIntent.RECENT:
                days_old = (datetime.now() - result.date).days
                if days_old < 7:
                    score += 0.2
                elif days_old < 30:
                    score += 0.1

            result.relevance_score = min(1.0, score)

        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    def _get_cache_key(self, query: SearchQuery) -> str:
        """Generate cache key for a search query."""
        # Create a unique key based on query attributes
        key_parts = [
            query.category.value,
            query.intent.value,
            "-".join(sorted(query.keywords)),
            query.language,
        ]

        # Add filter information
        for search_filter in query.filters:
            key_parts.append(
                f"{search_filter.field}:{search_filter.operator}:{search_filter.value}"
            )

        return "|".join(key_parts)

    # Helper methods for extracting information from FHIR resources

    def _extract_medication_name(self, med_request: Dict) -> str:
        """Extract medication name from MedicationRequest."""
        if "medicationCodeableConcept" in med_request:
            coding = med_request["medicationCodeableConcept"].get("coding", [])
            if coding:
                display = coding[0].get("display", "Unknown medication")
                return str(display) if display else "Unknown medication"
            text = med_request["medicationCodeableConcept"].get("text")
            if text:
                return str(text)
        return "Unknown medication"

    def _extract_medication_summary(self, med_request: Dict) -> str:
        """Extract medication summary from MedicationRequest."""
        parts = []

        # Dosage
        if "dosageInstruction" in med_request and med_request["dosageInstruction"]:
            dosage = med_request["dosageInstruction"][0]
            if "text" in dosage:
                parts.append(dosage["text"])

        # Status
        if "status" in med_request:
            parts.append(f"Status: {med_request['status']}")
        return ". ".join(parts)

    def _extract_appointment_title(self, appointment: Dict) -> str:
        """Extract appointment title."""
        if "description" in appointment:
            desc = appointment["description"]
            return str(desc) if desc else "Medical appointment"
        elif "serviceType" in appointment and appointment["serviceType"]:
            service = appointment["serviceType"][0]
            if "text" in service:
                text = service["text"]
                return str(text) if text else "Medical appointment"
        return "Medical appointment"

    def _extract_appointment_summary(self, appointment: Dict) -> str:
        """Extract appointment summary."""
        parts = []

        # Status
        if "status" in appointment:
            parts.append(f"Status: {appointment['status']}")

        # Participant
        if "participant" in appointment:
            for participant in appointment["participant"]:
                if "actor" in participant and "display" in participant["actor"]:
                    parts.append(f"With: {participant['actor']['display']}")
                    break

        return ". ".join(parts)

    def _parse_fhir_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse FHIR date string to datetime."""
        if not date_string:
            return None

        try:
            # Handle different FHIR date formats
            if "T" in date_string:
                # DateTime format
                return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            else:
                # Date only format
                return datetime.strptime(date_string, "%Y-%m-%d")
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(
                "Failed to parse FHIR date: %s, error: %s", date_string, str(e)
            )
            return None

    def validate_search_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate search results for FHIR compliance.

        Args:
            results: Search results to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        errors = []
        warnings = []

        if not results:
            warnings.append("No search results to validate")
        elif "resourceType" in results and results["resourceType"] != "Bundle":
            errors.append("Search results must be a FHIR Bundle")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
