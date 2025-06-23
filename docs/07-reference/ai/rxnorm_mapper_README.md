# RxNorm Drug Mapper

A comprehensive RxNorm drug terminology mapping system for the Haven Health Passport, providing standardized drug naming, interaction checking, and prescription parsing capabilities.

## Overview

RxNorm is the normalized naming system for clinical drugs produced by the National Library of Medicine (NLM). It provides standard names for clinical drugs and links to many drug vocabularies commonly used in healthcare.

## Features

### Core Functionality
- **Drug Search**: Search by name, RxCUI, brand, generic, or ingredient
- **Concept Retrieval**: Get detailed drug information including strength, dose form, and route
- **Brand/Generic Mapping**: Find equivalent brand and generic medications
- **NDC Mapping**: Convert NDC codes to RxNorm concepts
- **ATC Mapping**: Find drugs by ATC classification codes
- **Drug Type Classification**: Identify ingredients, brands, clinical drugs, and packs

### Advanced Features
- **Drug Interaction Checking**: Identify potential drug-drug interactions with severity levels
- **Prescription Sig Parsing**: Parse prescription directions into structured components
- **Fuzzy Matching**: Handle typos and variations in drug names
- **Related Drug Finding**: Find drugs with same ingredients, different strengths, or therapeutic alternatives
- **Dose Unit Conversion**: Convert between different dosage units (optional with pint)
- **Batch Processing**: Async batch search for multiple queries

### Performance Features
- **LRU Caching**: Fast repeated searches with 20,000 entry cache
- **Parallel Processing**: Thread pool for concurrent operations
- **Optimized Indexing**: Multiple indices for different search strategies
- **Configurable Result Limits**: Control maximum results returned

## Installation

The RxNorm mapper is included with the Haven Health Passport medical NLP module.

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

For dose unit conversion:
```bash
pip install pint
```
## Usage

### Basic Usage

```python
from src.ai.medical_nlp.terminology.rxnorm_mapper import create_rxnorm_mapper

# Initialize mapper
mapper = create_rxnorm_mapper()

# Search by drug name
result = mapper.search("aspirin")
for concept in result.concepts[:5]:
    print(f"{concept.rxcui}: {concept.name} ({concept.tty.value})")

# Get specific concept
aspirin = mapper.get_concept("1191")
print(f"Name: {aspirin.name}")
print(f"Type: {aspirin.tty.value}")
print(f"Status: {aspirin.status.value}")
```

### Drug Search Options

```python
# Search for brand names only
brands = mapper.search("aspirin", search_type="brand")

# Search for prescribable drugs only
prescribable = mapper.search("metformin", prescribable_only=True)

# Search with strength
specific = mapper.search("ibuprofen 200 mg")

# Exclude brand names
generics = mapper.search("acetaminophen", include_brand=False)
```

### Drug Interaction Checking

```python
# Check interactions between multiple drugs
drug_list = ["1191", "5640", "6809"]  # Aspirin, Ibuprofen, Metformin
interactions = mapper.check_drug_interactions(drug_list)

for interaction in interactions:
    print(f"{interaction.drug1_name} + {interaction.drug2_name}")
    print(f"Severity: {interaction.severity}")
    print(f"Description: {interaction.description}")
    if interaction.management:
        print(f"Management: {interaction.management}")

# Get all interactions for a single drug
aspirin_interactions = mapper.get_interactions("1191")
```
### Prescription Sig Parsing

```python
# Parse prescription directions
sig = "Metformin 500 mg PO BID with meals"
parsed = mapper.parse_sig(sig)

print(f"Drug: {parsed.drug_name}")
print(f"RxCUI: {parsed.rxcui}")
print(f"Dose: {parsed.dose} {parsed.dose_unit}")
print(f"Route: {parsed.route}")
print(f"Frequency: {parsed.frequency}")

# Parse complex sig
complex_sig = "Ibuprofen 200mg 1-2 tabs tid prn for pain for 7 days"
parsed = mapper.parse_sig(complex_sig)
print(f"PRN: {parsed.prn}")
print(f"Duration: {parsed.duration}")
```

### Code Mappings

```python
# Find drug by NDC
ndc = "0363-0160-01"
drug = mapper.find_by_ndc(ndc)
if drug:
    print(f"NDC {ndc} -> {drug.name} (RxCUI: {drug.rxcui})")

# Find drugs by ATC code
atc = "N02BE01"  # Paracetamol/Acetaminophen
drugs = mapper.find_by_atc(atc)
for drug in drugs:
    print(f"ATC {atc} -> {drug.name}")

# Get ingredients
clinical_drug = mapper.get_concept("198440")  # Aspirin 81 MG Oral Tablet
ingredients = mapper.get_ingredients(clinical_drug.rxcui)
for ing in ingredients:
    print(f"Contains: {ing.name} (RxCUI: {ing.rxcui})")
```

### Finding Related Drugs

```python
# Find brand/generic equivalents
rxcui = "104490"  # Tylenol 325 MG
equivalents = mapper.find_related_drugs(rxcui, "brand_generic")

# Find different strengths of same drug
strengths = mapper.find_related_drugs(rxcui, "different_strength")

# Find drugs with same ingredients
same_ingredients = mapper.find_related_drugs(rxcui, "same_ingredient")
```
### Batch Operations

```python
import asyncio

async def batch_example():
    queries = [
        "aspirin 81 mg",
        "blood pressure medication",
        "diabetes",
        "antibiotic",
        "198440"  # RxCUI
    ]

    results = await mapper.batch_search(
        queries,
        search_type=None,
        prescribable_only=True,
        max_results=5
    )

    for query, result in results.items():
        print(f"{query}: {len(result.concepts)} results")

asyncio.run(batch_example())
```

### Unit Conversion

```python
# Convert dose units (requires pint)
if mapper.enable_unit_conversion:
    # Convert 1000 mcg to mg
    converted = mapper.convert_dose_units(1000, "mcg", "mg")
    print(f"1000 mcg = {converted} mg")

    # Convert 5 mL to teaspoons
    converted = mapper.convert_dose_units(5, "mL", "teaspoon")
    print(f"5 mL = {converted} teaspoons")
```

## API Reference

### RxNormMapper Class

#### Constructor Parameters
- `data_path` (str, optional): Path to RxNorm data files
- `enable_fuzzy_matching` (bool): Enable fuzzy string matching (default: True)
- `enable_unit_conversion` (bool): Enable dose unit conversion (default: True)
- `min_confidence` (float): Minimum confidence threshold (default: 0.7)
- `max_results` (int): Maximum results to return (default: 20)
- `cache_size` (int): LRU cache size (default: 20000)
- `include_obsolete` (bool): Include obsolete drugs (default: False)
- `check_interactions` (bool): Enable interaction checking (default: True)
#### Main Methods

##### search()
```python
search(query: str,
       search_type: str = None,
       include_brand: bool = True,
       include_generic: bool = True,
       prescribable_only: bool = False,
       max_results: int = None) -> RxNormSearchResult
```
Search for drug concepts with various filters.

##### get_concept()
```python
get_concept(rxcui: str) -> Optional[RxNormConcept]
```
Get a specific drug concept by RxCUI.

##### check_drug_interactions()
```python
check_drug_interactions(rxcui_list: List[str],
                       severity_filter: str = None) -> List[DrugInteraction]
```
Check for interactions between multiple drugs.

##### parse_sig()
```python
parse_sig(sig_text: str) -> PrescriptionSig
```
Parse prescription directions into structured components.

##### find_by_ndc()
```python
find_by_ndc(ndc: str) -> Optional[RxNormConcept]
```
Find drug by National Drug Code.

##### find_related_drugs()
```python
find_related_drugs(rxcui: str,
                  relationship: str = "same_ingredient") -> List[RxNormConcept]
```
Find drugs with specified relationships.
### Data Classes

#### RxNormConcept
Represents a drug concept in RxNorm:
- `rxcui`: RxNorm Concept Unique Identifier
- `name`: Drug name
- `tty`: Term type (TermType enum)
- `status`: Drug status (active/obsolete)
- `ingredients`: List of ingredient RxCUIs
- `strength`: Drug strength
- `dose_form`: Dosage form
- `brand_names`: Associated brand names
- `generic_name`: Generic name
- `route`: Administration route
- `prescribable`: Whether drug can be prescribed

#### RxNormSearchResult
Search result container:
- `query`: Original search query
- `concepts`: List of matching concepts
- `total_matches`: Total number of matches
- `processing_time`: Search duration
- `approximate_match`: Whether results are approximate

#### DrugInteraction
Drug-drug interaction information:
- `drug1_rxcui/name`: First drug
- `drug2_rxcui/name`: Second drug
- `severity`: Interaction severity (high/moderate/low)
- `description`: Interaction description
- `mechanism`: Mechanism of interaction
- `management`: Management recommendations

#### PrescriptionSig
Parsed prescription signature:
- `drug_name`: Extracted drug name
- `rxcui`: Matched RxCUI if found
- `dose`: Numeric dose value
- `dose_unit`: Dose unit (mg, mcg, etc.)
- `route`: Administration route
- `frequency`: Dosing frequency
- `duration`: Treatment duration
- `prn`: As-needed flag
- `instructions`: Original sig text
### Enumerations

#### TermType
RxNorm term types:
- `IN`: Ingredient
- `PIN`: Precise Ingredient
- `BN`: Brand Name
- `SBD`: Semantic Branded Drug
- `SCD`: Semantic Clinical Drug
- `BPCK`: Brand Name Pack
- `GPCK`: Generic Pack
- `DF`: Dose Form

#### DrugStatus
Drug availability status:
- `ACTIVE`: Currently available
- `OBSOLETE`: No longer available
- `RETIRED`: Retired from use
- `NEVER_ACTIVE`: Never marketed

## Data Format

The mapper expects JSON data files:

### rxnorm_concepts.json
```json
{
  "1191": {
    "name": "Aspirin",
    "tty": "IN",
    "status": "active",
    "synonyms": ["acetylsalicylic acid", "ASA"]
  },
  "198440": {
    "name": "Aspirin 81 MG Oral Tablet",
    "tty": "SCD",
    "ingredients": ["1191"],
    "strength": "81 mg",
    "dose_form": "Oral Tablet",
    "prescribable": true
  }
}
```

### interactions.json
```json
[
  {
    "drug1_rxcui": "1191",
    "drug1_name": "Aspirin",
    "drug2_rxcui": "5640",
    "drug2_name": "Ibuprofen",
    "severity": "moderate",
    "description": "Increased risk of bleeding"
  }
]
```
## Performance Optimization

### Indexing Strategy
- Name-based inverted index for fast text search
- Ingredient index for component searches
- Brand index for brand name lookups
- NDC to RxCUI direct mapping
- ATC classification mapping

### Caching
- LRU cache for search results (20,000 entries)
- Interaction cache for repeated checks
- Configurable cache sizes

### Best Practices
1. Use specific search types when possible
2. Enable caching for repeated searches
3. Use batch_search() for multiple queries
4. Limit max_results for large datasets
5. Disable obsolete drugs unless needed

## Integration with Haven Health Passport

The RxNorm mapper integrates with:
- **Prescription Management**: Standardize drug names in prescriptions
- **Medication Reconciliation**: Match drugs across different sources
- **Clinical Decision Support**: Check drug interactions
- **Pharmacy Systems**: Convert between NDC and RxNorm
- **EHR Integration**: Normalize drug data from different systems
- **Patient Safety**: Real-time interaction checking
- **Analytics**: Standardized drug usage reporting

## Common Use Cases

1. **E-Prescribing**: Convert free-text drug names to RxCUI
2. **Medication History**: Standardize drugs from multiple sources
3. **Formulary Checking**: Find generic alternatives
4. **Drug Alerts**: Check interactions before prescribing
5. **Sig Translation**: Parse prescription directions
6. **Inventory Management**: Map NDC codes to drugs

## Limitations

1. **Sample Data**: Default installation includes sample drugs only
2. **Full RxNorm**: Requires RxNorm data files from NLM
3. **Interaction Data**: Basic interaction set included
4. **Sig Parsing**: Handles common formats, may miss complex sigs
5. **Unit Conversion**: Optional, requires pint library

## Contributing

To extend the RxNorm mapper:
1. Add drug concepts to `/data/terminologies/rxnorm/`
2. Update interaction database
3. Extend sig parsing patterns
4. Add more route/frequency mappings
5. Implement additional relationship types

## License

Part of Haven Health Passport. RxNorm is produced by the National Library of Medicine.
