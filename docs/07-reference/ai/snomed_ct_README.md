# SNOMED CT Integration

A comprehensive SNOMED CT (Systematized Nomenclature of Medicine Clinical Terms) integration system for the Haven Health Passport, providing advanced clinical terminology capabilities with hierarchical navigation, relationship traversal, and expression language support.

## Overview

SNOMED CT is the most comprehensive clinical terminology system globally, containing over 350,000 active concepts covering:
- Clinical findings (diseases, disorders, symptoms)
- Procedures (surgical, diagnostic, therapeutic)
- Body structures (anatomy)
- Organisms (bacteria, viruses)
- Substances (drugs, chemicals)
- Pharmaceutical products
- Devices
- Observable entities
- Situations and events

## Features

### Core Functionality
- **Concept Search**: Search by concept ID, FSN, preferred term, or synonyms
- **Hierarchical Navigation**: Traverse parent-child relationships
- **Relationship Management**: Access all concept relationships (IS-A, finding site, etc.)
- **Multi-language Support**: Access translations via language reference sets
- **Status Management**: Handle active/inactive concepts with replacement mappings
- **Semantic Tags**: Filter by semantic categories (disorder, finding, procedure, etc.)

### Advanced Features
- **Expression Constraint Language (ECL)**: Query concepts using SNOMED CT expressions
- **Post-coordination**: Create complex clinical expressions
- **Graph Operations**: NetworkX-based graph traversal (optional)
- **Fuzzy Matching**: Handle typos and variations
- **Batch Processing**: Async batch search capabilities
- **Common Ancestor Finding**: Identify shared parent concepts
- **Path Finding**: Find relationships between concepts

### Performance Features
- **LRU Caching**: Fast repeated searches
- **Parallel Processing**: Thread pool for concurrent operations
- **Optimized Indexing**: Multiple indices for different search types
- **Lazy Loading**: Load components only when needed
## Installation

The SNOMED CT integration is part of the Haven Health Passport medical NLP module.

### Basic Installation
```bash
cd /Users/cadenceapeiron/Documents/HavenHealthPassport
pip install -r src/ai/medical_nlp/requirements.txt
```

### Optional Dependencies

For fuzzy matching:
```bash
pip install fuzzywuzzy python-Levenshtein
```

For graph operations:
```bash
pip install networkx
```

## Usage

### Basic Usage

```python
from src.ai.medical_nlp.terminology.snomed_ct_integration import create_snomed_ct_integration

# Initialize integration
snomed = create_snomed_ct_integration()

# Search by concept ID
result = snomed.search("22298006")
concept = result.concepts[0]
print(f"{concept.preferred_term}")  # "Myocardial infarction"

# Search by clinical term
result = snomed.search("diabetes")
for concept in result.concepts[:5]:
    print(f"{concept.concept_id}: {concept.preferred_term}")

# Get a specific concept
mi_concept = snomed.get_concept("22298006")
print(f"FSN: {mi_concept.fsn}")
print(f"Semantic tag: {mi_concept.get_semantic_tag()}")
```
### Hierarchical Navigation

```python
# Get parent concepts
parents = snomed.get_parents("22298006")
for parent in parents:
    print(f"Parent: {parent.preferred_term}")

# Get child concepts
children = snomed.get_children("73211009")  # Diabetes
for child in children:
    print(f"Child: {child.preferred_term}")

# Get all ancestors (organized by level)
ancestors = snomed.get_ancestors("22298006")
for level, concepts in enumerate(ancestors):
    print(f"Level {level + 1}:")
    for concept in concepts:
        print(f"  - {concept.preferred_term}")

# Get all descendants
descendants = snomed.get_descendants("404684003")  # Clinical finding
print(f"Found {len(descendants)} descendant clinical findings")
```

### Filtered Search

```python
# Search only in specific hierarchies
procedures = snomed.search(
    "heart",
    hierarchies=[Hierarchy.PROCEDURE]
)

# Search by semantic tag
disorders = snomed.search(
    "chronic",
    semantic_tags=["disorder"]
)

# Active concepts only
active_results = snomed.search(
    "hypertension",
    active_only=True
)
```
### Expression Constraint Language (ECL)

```python
# Get all descendants of a concept
heart_diseases = snomed.execute_ecl("< 56265001")  # Heart disease

# Get concept and all descendants
all_diabetes = snomed.execute_ecl("<< 73211009")  # Diabetes and subtypes

# Get all ancestors
mi_ancestors = snomed.execute_ecl("> 22298006")

# Get concept and all ancestors
all_ancestors = snomed.execute_ecl(">> 195967001")  # Asthma and parents
```

### Relationships

```python
# Get all relationships for a concept
relationships = snomed.get_relationships("22298006")
for rel_type, targets in relationships.items():
    print(f"{rel_type}:")
    for target in targets:
        print(f"  -> {target.preferred_term}")

# Get specific relationship type
finding_sites = snomed.get_relationships(
    "22298006",
    relationship_type=RelationshipType.FINDING_SITE.value
)
```

### Post-coordinated Expressions

```python
# Create a complex clinical expression
expression = snomed.create_expression(
    focus_concepts=["22298006"],  # Myocardial infarction
    refinements={
        "363698007": [("=", "277005")],  # Finding site = Inferior wall
        "116676008": [("=", "55641003")]  # Morphology = Infarct
    }
)

print(f"Expression: {expression.to_string()}")
# Output: "22298006 : 363698007 = 277005 , 116676008 = 55641003"
```
### Multi-language Support

```python
# Get translations
spanish = snomed.get_translation("22298006", "es")
print(f"Spanish: {spanish}")  # "Infarto de miocardio"

# Search with language preference
snomed_es = create_snomed_ct_integration(language="es")
result = snomed_es.search("infarto")
```

### Batch Operations

```python
import asyncio

async def batch_example():
    queries = [
        "diabetes mellitus",
        "essential hypertension",
        "bronchial asthma",
        "22298006",
        "chronic kidney disease"
    ]

    results = await snomed.batch_search(
        queries,
        hierarchies=[Hierarchy.CLINICAL_FINDING],
        max_results=5
    )

    for query, result in results.items():
        print(f"{query}: {len(result.concepts)} results")

asyncio.run(batch_example())
```

### Advanced Graph Operations

```python
# Find common ancestors
common = snomed.get_common_ancestors([
    "22298006",  # MI
    "38341003"   # Hypertension
])
print("Common ancestors:", [c.preferred_term for c in common])

# Find path between concepts (requires graph operations enabled)
path = snomed.find_path("22298006", "404684003")
if path:
    print(f"Path length: {len(path)}")
```
## API Reference

### SnomedCTIntegration Class

#### Constructor Parameters
- `data_path` (str, optional): Path to SNOMED CT data files
- `enable_fuzzy_matching` (bool): Enable fuzzy string matching (default: True)
- `enable_graph_operations` (bool): Enable graph-based operations (default: True)
- `min_confidence` (float): Minimum confidence threshold (default: 0.7)
- `max_results` (int): Maximum results to return (default: 50)
- `cache_size` (int): LRU cache size (default: 50000)
- `language` (str): Language reference set (default: "en-US")
- `load_relationships` (bool): Load relationship data (default: True)
- `enable_ecl` (bool): Enable Expression Constraint Language (default: True)

#### Main Methods

##### search()
```python
search(query: str,
       hierarchies: List[Hierarchy] = None,
       semantic_tags: List[str] = None,
       active_only: bool = True,
       include_fsn: bool = True,
       include_synonyms: bool = True,
       max_results: int = None) -> SnomedSearchResult
```
Search for SNOMED CT concepts with various filters.

##### get_concept()
```python
get_concept(concept_id: str) -> Optional[SnomedConcept]
```
Get a specific concept by ID.

##### execute_ecl()
```python
execute_ecl(expression: str) -> List[SnomedConcept]
```
Execute an Expression Constraint Language query.
### Data Classes

#### SnomedConcept
Represents a SNOMED CT concept:
- `concept_id`: Unique concept identifier
- `fsn`: Fully Specified Name
- `preferred_term`: Preferred term for display
- `status`: Concept status (active/inactive)
- `parents`: List of parent concept IDs
- `children`: List of child concept IDs
- `relationships`: Dictionary of relationships
- `hierarchy`: Top-level hierarchy
- `semantic_tag`: Semantic category

#### SnomedSearchResult
Search result container:
- `query`: Original search query
- `concepts`: List of matching concepts
- `total_matches`: Total number of matches
- `processing_time`: Search duration
- `search_metadata`: Additional metadata
- `applied_filters`: Filters used in search

#### SnomedExpression
Post-coordinated expression:
- `focus_concepts`: List of focus concept IDs
- `refinements`: Dictionary of attribute refinements

### Enumerations

#### Hierarchy
Top-level SNOMED CT hierarchies:
- `BODY_STRUCTURE`: Anatomical structures
- `CLINICAL_FINDING`: Diseases, disorders, symptoms
- `PROCEDURE`: Medical procedures
- `PHARMACEUTICAL`: Drug products
- `SUBSTANCE`: Chemical substances
- `ORGANISM`: Living organisms
- `PHYSICAL_OBJECT`: Devices, instruments
- `QUALIFIER_VALUE`: Qualifiers
- `OBSERVABLE_ENTITY`: Observable properties
- `EVENT`: Clinical events
- `SOCIAL_CONTEXT`: Social circumstances
- `ENVIRONMENT`: Environmental locations
- `SITUATION`: Clinical situations
- `SPECIMEN`: Laboratory specimens
#### RelationshipType
Common SNOMED CT relationships:
- `IS_A`: Hierarchical parent relationship
- `FINDING_SITE`: Anatomical location
- `ASSOCIATED_MORPHOLOGY`: Morphologic abnormality
- `CAUSATIVE_AGENT`: Causative organism/substance
- `PART_OF`: Part-whole relationship
- `LATERALITY`: Body side
- `HAS_ACTIVE_INGREDIENT`: Drug ingredient
- `HAS_DOSE_FORM`: Drug form

## Data Format

The integration expects JSON data files:

### concepts.json
```json
{
  "22298006": {
    "fsn": "Myocardial infarction (disorder)",
    "preferred_term": "Myocardial infarction",
    "status": "active",
    "hierarchy": "404684003",
    "parents": ["57809008"],
    "semantic_tag": "disorder"
  }
}
```

### descriptions.json
```json
{
  "22298006": [
    {"term": "Myocardial infarction", "type": "preferred", "language": "en"},
    {"term": "MI", "type": "synonym", "language": "en"},
    {"term": "Heart attack", "type": "synonym", "language": "en"}
  ]
}
```

### relationships.json
```json
{
  "22298006": {
    "116680003": ["57809008"],
    "363698007": ["80891009"]
  }
}
```
## Performance Optimization

### Indexing Strategy
- Concept ID index for direct lookups
- FSN word-based inverted index
- Preferred term index
- Hierarchy-based index
- Semantic tag index
- Language-specific indices

### Caching
- LRU cache for search results (50,000 entries)
- ECL query cache
- Path finding cache
- Configurable cache sizes

### Best Practices
1. Use specific hierarchies when possible
2. Enable only needed features (ECL, graph operations)
3. Limit max_results for large result sets
4. Use batch_search() for multiple queries
5. Cache integration instance for repeated use

## Integration with Haven Health Passport

The SNOMED CT integration works with:
- **Medical Entity Recognition**: Automatic concept suggestion
- **Clinical Decision Support**: Evidence-based recommendations
- **Multi-language Support**: Cross-language concept mapping
- **ICD-10 Mapping**: Cross-terminology mapping
- **Clinical Documentation**: Structured clinical notes
- **Analytics**: Population health analysis
- **Quality Measures**: Clinical quality reporting

## Limitations

1. **Sample Data**: Default installation includes sample concepts only
2. **Full SNOMED CT**: Requires license from SNOMED International
3. **Graph Operations**: Optional, requires NetworkX
4. **ECL Support**: Basic implementation, not full specification
5. **Post-coordination**: Limited to simple expressions

## Contributing

To extend the SNOMED CT integration:
1. Add concepts to `/data/terminologies/snomed_ct/`
2. Implement additional ECL operators
3. Add more relationship types
4. Extend language support
5. Add cross-terminology mappings

## License

Part of Haven Health Passport. SNOMED CT content requires separate licensing from SNOMED International.
