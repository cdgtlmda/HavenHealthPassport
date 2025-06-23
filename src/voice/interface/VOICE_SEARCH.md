# Voice Search Module Documentation

## Overview

The Voice Search module provides natural language voice-based search capabilities for the Haven Health Passport system. It allows users to search for medical records, medications, appointments, and other health information using conversational voice commands in multiple languages.

## Features

### 1. Natural Language Processing
- Understands conversational queries like "Find my blood pressure medications from last week"
- Extracts relevant keywords, dates, and search intent automatically
- Supports multiple phrasings for the same query

### 2. Multi-Category Search
The system can search across multiple categories:
- **Medical Records**: Complete health records and documents
- **Medications**: Prescriptions, dosages, and medication history
- **Appointments**: Past and upcoming medical appointments
- **Providers**: Doctors, specialists, and healthcare facilities
- **Test Results**: Lab results, imaging, and diagnostic tests
- **Immunizations**: Vaccination records and schedules
- **Conditions**: Medical conditions and diagnoses
- **Procedures**: Medical procedures and surgeries
- **Allergies**: Allergy information and reactions
- **Vitals**: Blood pressure, temperature, heart rate, etc.
- **Documents**: Medical documents and reports
- **Emergency Contacts**: Emergency contact information

### 3. Smart Filtering
Automatically detects and applies filters based on voice input:
- **Date Filters**: "today", "yesterday", "this week", "last month", "last 7 days"
- **Status Filters**: "active", "completed", "cancelled"
- **Provider Filters**: "from Dr. Smith", "by nurse Johnson"
- **Urgency Filters**: "urgent", "emergency", "critical"

### 4. Intent Recognition
Recognizes different search intents:
- **Find Specific**: Looking for a particular item
- **List All**: Show all items of a type
- **Recent**: Show recent items
- **By Date**: Items from specific dates
- **By Provider**: Items from specific healthcare providers
- **By Location**: Items from specific locations
- **By Status**: Items with specific status
- **Urgent**: Emergency or critical items

### 5. Multi-Language Support
Supports 50+ languages with medical accuracy:
- Automatic language detection
- Medical terminology preservation across languages
- Cultural adaptation for different regions

### 6. Result Ranking
Intelligent ranking based on:
- Keyword relevance
- Recency (for recent searches)
- Urgency (for emergency searches)
- Exact matches vs. partial matches

## Usage Examples

### Basic Search Commands

```
"Find aspirin"
"Search for my medications"
"Show me blood test results"
"Where is my vaccination record"
"Look for appointments with Dr. Smith"
```

### Date-Based Searches

```
"Find blood pressure readings from today"
"Show me test results from yesterday"
"Appointments this week"
"Medications prescribed last month"
"Lab results from last 7 days"
```

### Category-Specific Searches

```
"List all my allergies"
"Show me recent prescriptions"
"Find urgent test results"
"Get my vaccination history"
"Display vital signs from this morning"
```

### Complex Queries

```
"Find blood pressure medications prescribed by Dr. Johnson last week"
"Show me all urgent test results from the emergency room"
"List antibiotics I took in January"
"Find appointments with cardiologists this month"
```

## Integration with Voice Command System

The Voice Search module integrates seamlessly with the Haven Health Passport's voice command grammar system:

1. **Command Registration**: Search commands are automatically registered with the grammar engine
2. **Parameter Extraction**: Query text, category, and time filters are extracted as command parameters
3. **Priority Handling**: Search commands can be prioritized (normal, medical, emergency)
4. **Confirmation**: Optional confirmation for sensitive searches

## API Reference

### VoiceSearchEngine

Main class for voice search functionality.

#### Methods

##### `search_by_voice(voice_input: str, language: Optional[str] = None) -> List[SearchResult]`

Performs a voice search based on natural language input.

**Parameters:**
- `voice_input`: The voice command text
- `language`: Language code (auto-detected if not provided)

**Returns:**
- List of `SearchResult` objects

**Example:**
```python
engine = VoiceSearchEngine(fhir_client, health_service)
results = await engine.search_by_voice("find my blood pressure medications")
```

### SearchResult

Represents a single search result.

#### Properties
- `id`: Unique identifier
- `category`: Search category (SearchCategory enum)
- `title`: Result title
- `summary`: Brief summary
- `date`: Associated date (optional)
- `relevance_score`: Relevance score (0.0 to 1.0)
- `data`: Complete data dictionary

#### Methods

##### `to_voice_response(language: str = "en") -> str`

Converts the result to a voice-friendly response.

### VoiceSearchIntegration

Integrates voice search with the command grammar system.

#### Methods

##### `handle_search_command(parsed_command: ParsedCommand) -> List[SearchResult]`

Handles a parsed search command from the grammar engine.

## Configuration

### Search Settings

```python
# Cache TTL for search results
CACHE_TTL = timedelta(minutes=5)

# Maximum results per search
MAX_RESULTS = 50

# Confidence threshold for query parsing
CONFIDENCE_THRESHOLD = 0.5
```

### Category Keywords

The system uses keyword mapping to detect search categories. These can be customized:

```python
CATEGORY_KEYWORDS = {
    SearchCategory.MEDICATIONS: [
        "medication", "medicine", "drug", "prescription",
        "pill", "tablet", "dose", "meds"
    ],
    SearchCategory.APPOINTMENTS: [
        "appointment", "visit", "schedule", "booking",
        "consultation", "checkup"
    ],
    # ... more categories
}
```

## Performance Considerations

1. **Caching**: Results are cached for 5 minutes to improve performance
2. **Parallel Search**: When searching all categories, queries run in parallel
3. **Result Limiting**: Default limit of 50 results per search
4. **Indexing**: FHIR resources should be properly indexed for text search

## Security and Privacy

1. **Access Control**: Searches are limited to the authenticated user's data
2. **Audit Logging**: All searches are logged for audit purposes
3. **Data Encryption**: Search queries and results are encrypted in transit
4. **No Cloud Storage**: Voice data is processed locally when possible

## Error Handling

The system handles various error scenarios:
- Invalid queries return empty results
- FHIR connection errors are logged and handled gracefully
- Malformed data is skipped without crashing
- Language detection failures fall back to English

## Testing

Comprehensive test coverage includes:
- Query parsing and intent detection
- Category detection
- Filter extraction
- Result ranking
- Multi-language support
- Error scenarios
- Integration with command grammar

Run tests with:
```bash
pytest src/voice/interface/test_voice_search.py -v
```

## Future Enhancements

1. **Fuzzy Matching**: Handle typos and mispronunciations
2. **Synonym Expansion**: Understand medical synonyms
3. **Context Awareness**: Remember previous searches
4. **Voice Feedback**: Read results back to user
5. **Smart Suggestions**: Suggest related searches
6. **Offline Search**: Search cached data when offline

## Troubleshooting

### Common Issues

1. **No Results Found**
   - Check if keywords match any data
   - Verify category detection
   - Check date filters

2. **Slow Searches**
   - Clear search cache
   - Check FHIR server performance
   - Reduce result limit

3. **Wrong Category Detected**
   - Use more specific keywords
   - Explicitly mention category

4. **Language Not Detected**
   - Specify language explicitly
   - Check language detector configuration

## Related Modules

- `voice_command_grammar.py`: Command parsing system
- `transcribe_medical.py`: Medical voice transcription
- `fhir_search.py`: FHIR search parameters
- `medical_terms.py`: Medical terminology handling
