# ICD-10 Code Mapper

A comprehensive ICD-10 code mapping system for the Haven Health Passport, providing advanced medical condition coding capabilities with multi-language support, fuzzy matching, and clinical context awareness.

## Features

### Core Functionality
- **Exact Code Matching**: Direct ICD-10 code lookup with full metadata
- **Description Search**: Natural language search through code descriptions
- **Hierarchical Navigation**: Parent-child code relationships and tree traversal
- **Billable Code Filtering**: Automatic identification of billable vs non-billable codes
- **Code Validation**: Verify code validity and billing eligibility
- **Compatibility Checking**: Ensure codes can be used together (Excludes1/2 rules)

### Advanced Search Capabilities
- **Fuzzy Matching**: Handle typos and variations in medical terminology
- **Synonym Mapping**: Match alternative names for conditions
- **Abbreviation Expansion**: Recognize medical abbreviations (URI, COPD, etc.)
- **Semantic Search**: Find related codes using TF-IDF similarity (optional)
- **Multi-language Support**: Search in multiple languages with translations
- **Clinical Variants**: Recognize different clinical presentations

### Performance Features
- **LRU Caching**: Fast repeated searches with configurable cache size
- **Batch Processing**: Async batch search for multiple queries
- **Parallel Processing**: Thread pool for concurrent operations
- **Lazy Loading**: Components loaded only when needed
- **Optimized Indexing**: Word-based and prefix-based indices

## Installation

The ICD-10 mapper is included with the Haven Health Passport medical NLP module. Install dependencies:

```bash
cd /Users/cadenceapeiron/Documents/HavenHealthPassport
pip install -r src/ai/medical_nlp/requirements.txt
```

For fuzzy matching support:
```bash
pip install fuzzywuzzy python-Levenshtein
```

For semantic search support:
```bash
pip install scikit-learn numpy
```
## Usage

### Basic Usage

```python
from src.ai.medical_nlp.terminology.icd10_mapper import create_icd10_mapper

# Initialize mapper
mapper = create_icd10_mapper()

# Search by code
result = mapper.search("J00")
print(f"Found: {result.codes[0].description}")  # "Acute nasopharyngitis [common cold]"

# Search by description
result = mapper.search("common cold")
for code in result.codes[:3]:
    print(f"{code.code}: {code.description} (confidence: {code.confidence:.2f})")

# Search with children
result = mapper.search("J45", include_children=True)
print(f"Found {len(result.codes)} codes including children")
```

### Advanced Search

```python
# Fuzzy search for typos
result = mapper.search("diabtes")  # Note the typo
# Still finds diabetes codes

# Abbreviation search
result = mapper.search("COPD")
# Finds Chronic Obstructive Pulmonary Disease codes

# Filter non-billable codes
result = mapper.search("asthma", include_non_billable=False)
# Only returns billable asthma codes

# Category filtering
result = mapper.search("infection", category_filter=["Respiratory infections"])
```

### Code Validation and Relationships

```python
# Validate a code
valid, message = mapper.validate_code("J00")
if valid:
    print("Code is valid and billable")
else:
    print(f"Code invalid: {message}")
# Check code compatibility
compatible, message = mapper.check_code_compatibility("J00", "J45")
if not compatible:
    print(f"Codes cannot be used together: {message}")

# Get code hierarchy
path = mapper.get_hierarchy_path("A00.0")
for code in path:
    print(f"{'  ' * (code.get_hierarchy_level()-1)}{code.code}: {code.description}")

# Get related codes
parent = mapper.get_parent("A00.0")
children = mapper.get_children("A00")
```

### Batch Processing

```python
import asyncio

async def batch_example():
    queries = [
        "common cold",
        "asthma",
        "diabetes type 2",
        "hypertension",
        "COVID-19"
    ]

    results = await mapper.batch_search(queries)

    for query, result in results.items():
        if result.codes:
            print(f"{query}: {result.codes[0].code}")

asyncio.run(batch_example())
```

### Multi-language Support

```python
# Search in Spanish
result = mapper.search_multi_language("resfriado", language="es")

# Search in French
result = mapper.search_multi_language("asthme", language="fr")
```
## API Reference

### ICD10Mapper Class

#### Constructor Parameters
- `data_path` (str, optional): Path to ICD-10 data files
- `enable_fuzzy_matching` (bool): Enable fuzzy string matching (default: True)
- `enable_semantic_matching` (bool): Enable semantic similarity (default: True)
- `min_confidence` (float): Minimum confidence threshold (default: 0.7)
- `max_results` (int): Maximum results to return (default: 10)
- `cache_size` (int): LRU cache size (default: 10000)
- `language` (str): Primary language (default: "en")

#### Main Methods

##### search()
```python
search(query: str,
       include_children: bool = False,
       include_non_billable: bool = True,
       category_filter: List[str] = None,
       max_results: int = None) -> ICD10SearchResult
```
Search for ICD-10 codes matching the query.

##### get_code()
```python
get_code(code_id: str) -> Optional[ICD10Code]
```
Get a specific ICD-10 code by ID.

##### validate_code()
```python
validate_code(code_id: str) -> Tuple[bool, Optional[str]]
```
Validate if a code exists and is billable.

##### check_code_compatibility()
```python
check_code_compatibility(code1: str, code2: str) -> Tuple[bool, Optional[str]]
```
Check if two codes can be used together.
### Data Classes

#### ICD10Code
Represents a complete ICD-10 code with metadata:
- `code`: The ICD-10 code
- `description`: Full description
- `category`: Category name
- `parent_code`: Parent code if hierarchical
- `is_billable`: Whether code is billable
- `confidence`: Search confidence score
- `match_type`: How the code was matched (MatchType enum)
- `excludes1/2`: Exclusion codes
- `includes`: Included conditions
- `clinical_notes`: Additional clinical information

#### ICD10SearchResult
Contains search results:
- `query`: Original search query
- `codes`: List of matching ICD10Code objects
- `processing_time`: Search duration in seconds
- `search_metadata`: Additional search information

#### MatchType Enum
- `EXACT`: Exact code or description match
- `PARTIAL`: Partial text match
- `SYNONYM`: Matched via synonym
- `ABBREVIATION`: Matched via abbreviation
- `FUZZY`: Fuzzy string match
- `SEMANTIC`: Semantic similarity match
- `HIERARCHY`: Child of matched code
- `CLINICAL_VARIANT`: Clinical variant match

## Data Format

The mapper expects JSON data files in the configured data directory:

### icd10_codes.json
```json
{
  "J00": {
    "description": "Acute nasopharyngitis [common cold]",
    "category": "Acute upper respiratory infections",
    "is_billable": true,
    "includes": ["Coryza (acute)"],
    "excludes1": ["J02.-"]
  }
}
```
### synonyms.json
```json
{
  "J00": ["common cold", "cold", "head cold", "URI"],
  "J45": ["asthma", "bronchial asthma"]
}
```

### abbreviations.json
```json
{
  "URI": ["J00", "J06"],
  "COPD": ["J44"],
  "DM": ["E11", "E10"]
}
```

## Performance Optimization

### Caching Strategy
- LRU cache for search results
- Configurable cache size (default 10,000 entries)
- Cache statistics available via `get_statistics()`

### Indexing
- Word-based inverted index for descriptions
- Prefix index for code lookups
- Pre-computed TF-IDF vectors for semantic search

### Best Practices
1. Enable caching for repeated searches
2. Use batch_search() for multiple queries
3. Disable semantic search if not needed (faster startup)
4. Limit max_results for better performance
5. Use specific category filters when possible

## Integration with Haven Health Passport

The ICD-10 mapper integrates with:
- Medical entity recognition for automatic code suggestion
- Translation services for multi-language diagnosis coding
- Clinical decision support for code validation
- Billing systems for reimbursement eligibility
- Analytics for population health insights

## Contributing

To add new ICD-10 codes or improve mappings:
1. Update the JSON data files in `/data/terminologies/icd10/`
2. Add test cases for new codes
3. Update synonym and abbreviation mappings
4. Run the test suite to ensure compatibility

## License

Part of the Haven Health Passport project. See main project license.
