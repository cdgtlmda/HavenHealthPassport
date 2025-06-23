# Medical Coding Systems Reference

## Overview

Haven Health Passport integrates multiple international medical coding systems to ensure comprehensive clinical documentation and interoperability. This reference guide covers implementation details, mapping strategies, and best practices for each coding system.

## Supported Coding Systems

| System | Version | Purpose | Update Frequency |
|--------|---------|---------|------------------|
| ICD-10-CM | 2024 | Clinical diagnoses | Annual (October) |
| ICD-10-PCS | 2024 | Inpatient procedures | Annual (October) |
| SNOMED CT | Int'l Edition 2024-05 | Clinical terminology | Bi-annual |
| LOINC | 2.76 | Laboratory observations | Bi-annual |
| RxNorm | 2024-05 | Medications | Monthly |
| CVX | Current | Vaccines | As needed |
| CPT-4 | 2024 | Procedures (US) | Annual |

## ICD-10 Implementation

### Structure and Hierarchy

```python
class ICD10Service:
    """ICD-10 code management and validation service"""

    def __init__(self):
        self.code_hierarchy = self.load_icd10_hierarchy()
        self.inclusion_terms = self.load_inclusion_terms()
        self.exclusion_notes = self.load_exclusion_notes()

    def validate_code(self, code):
        """Validate ICD-10 code format and existence"""
        # ICD-10-CM format: A00-Z99.999
        pattern = r'^[A-Z]\d{2}\.?\d{0,3}[A-Z]?$'

        if not re.match(pattern, code):
            return False, "Invalid ICD-10 code format"

        if code not in self.code_hierarchy:
            return False, "Code not found in ICD-10 database"

        return True, "Valid ICD-10 code"

    def get_code_details(self, code):
        """Get detailed information about an ICD-10 code"""
        return {
            "code": code,
            "description": self.code_hierarchy[code]["description"],
            "category": self.get_category(code),
            "includes": self.inclusion_terms.get(code, []),
            "excludes1": self.exclusion_notes.get(code, {}).get("excludes1", []),
            "excludes2": self.exclusion_notes.get(code, {}).get("excludes2", []),
            "parent": self.get_parent_code(code),
            "children": self.get_child_codes(code)
        }
```

### Common Refugee Health Conditions

```json
{
  "common_conditions": {
    "malnutrition": {
      "codes": ["E40-E46"],
      "preferred": "E44.0",
      "description": "Moderate protein-energy malnutrition"
    },
    "ptsd": {
      "codes": ["F43.10", "F43.11", "F43.12"],
      "preferred": "F43.10",
      "description": "Post-traumatic stress disorder, unspecified"
    },
    "tuberculosis": {
      "codes": ["A15-A19"],
      "preferred": "A15.0",
      "description": "Tuberculosis of lung"
    }
  }
}
```

## SNOMED CT Integration

### Concept Model

```python
class SNOMEDCTService:
    """SNOMED CT terminology service implementation"""

    HIERARCHIES = {
        "clinical_finding": "404684003",
        "procedure": "71388002",
        "body_structure": "123037004",
        "organism": "410607006",
        "substance": "105590001",
        "pharmaceutical": "373873005",
        "physical_object": "260787004",
        "physical_force": "78621006",
        "event": "272379006",
        "environment": "308916002",
        "situation": "243796009"
    }

    def find_concepts(self, search_term, hierarchy=None, limit=10):
        """Search for SNOMED CT concepts"""
        query = {
            "term": search_term,
            "activeOnly": True,
            "limit": limit
        }

        if hierarchy:
            query["eclQuery"] = f"<< {self.HIERARCHIES[hierarchy]}"

        return self.search_service.search(query)

    def get_preferred_term(self, concept_id, language="en"):
        """Get preferred term for a concept in specified language"""
        descriptions = self.get_descriptions(concept_id)

        return next(
            (d for d in descriptions
             if d["typeId"] == "900000000000003001"  # Preferred term
             and d["languageCode"] == language
             and d["active"]),
            None
        )
```

### Expression Constraints

```python
# Common SNOMED CT expression constraints for refugee health

# All infectious diseases
infectious_diseases = "<< 40733004 |Infectious disease|"

# Mental health conditions
mental_health = "<< 74732009 |Mental disorder|"

# Nutritional disorders
nutritional = "<< 2492009 |Nutritional disorder|"

# Vaccine-preventable diseases
vaccine_preventable = """
    << 40733004 |Infectious disease| :
    370395004 |Has preventive procedure| = << 33879002 |Immunization|
"""
```

## LOINC Implementation

### Laboratory Result Mapping

```python
class LOINCService:
    """LOINC code service for laboratory and clinical observations"""

    COMMON_PANELS = {
        "CBC": {
            "code": "58410-2",
            "display": "Complete blood count panel",
            "components": [
                {"code": "6690-2", "display": "WBC"},
                {"code": "789-8", "display": "RBC"},
                {"code": "718-7", "display": "Hemoglobin"},
                {"code": "4544-3", "display": "Hematocrit"},
                {"code": "777-3", "display": "Platelets"}
            ]
        },
        "BMP": {
            "code": "51990-0",
            "display": "Basic metabolic panel",
            "components": [
                {"code": "2160-0", "display": "Creatinine"},
                {"code": "3094-0", "display": "BUN"},
                {"code": "2345-7", "display": "Glucose"},
                {"code": "2951-2", "display": "Sodium"},
                {"code": "2823-3", "display": "Potassium"},
                {"code": "2075-0", "display": "Chloride"},
                {"code": "2028-9", "display": "CO2"}
            ]
        }
    }

    def create_observation_bundle(self, panel_code, results):
        """Create FHIR Observation bundle for lab panel"""
        panel = self.COMMON_PANELS[panel_code]

        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": []
        }

        # Create panel observation
        panel_obs = self.create_panel_observation(panel)
        bundle["entry"].append({"resource": panel_obs})

        # Create component observations
        for component in panel["components"]:
            if component["code"] in results:
                comp_obs = self.create_component_observation(
                    component,
                    results[component["code"]],
                    panel_obs["id"]
                )
                bundle["entry"].append({"resource": comp_obs})

        return bundle
```

### Unit Conversion

```python
LOINC_UNIT_MAPPINGS = {
    "glucose": {
        "mg/dL": {"system": "http://unitsofmeasure.org", "code": "mg/dL"},
        "mmol/L": {"system": "http://unitsofmeasure.org", "code": "mmol/L"},
        "conversion": lambda mgdl_to_mmol: mgdl_to_mmol / 18.0182
    },
    "creatinine": {
        "mg/dL": {"system": "http://unitsofmeasure.org", "code": "mg/dL"},
        "umol/L": {"system": "http://unitsofmeasure.org", "code": "umol/L"},
        "conversion": lambda mgdl_to_umol: mgdl_to_umol * 88.42
    }
}
```

## RxNorm Integration

### Medication Mapping

```python
class RxNormService:
    """RxNorm medication terminology service"""

    def find_medication(self, search_term, term_type="IN"):
        """
        Search for medications in RxNorm

        Term types:
        - IN: Ingredient
        - BN: Brand name
        - SCD: Semantic clinical drug
        - SBD: Semantic branded drug
        """

        query = {
            "term": search_term,
            "termType": term_type,
            "maxResults": 20
        }

        results = self.api_client.search(query)
        return self.enrich_results(results)

    def get_drug_interactions(self, rxcui_list):
        """Check for drug-drug interactions"""
        interactions = []

        for i, rxcui1 in enumerate(rxcui_list):
            for rxcui2 in rxcui_list[i+1:]:
                interaction = self.check_interaction(rxcui1, rxcui2)
                if interaction:
                    interactions.append({
                        "drug1": rxcui1,
                        "drug2": rxcui2,
                        "severity": interaction["severity"],
                        "description": interaction["description"]
                    })

        return interactions

    def get_generic_equivalent(self, brand_rxcui):
        """Find generic equivalent for brand medication"""
        relationships = self.get_relationships(brand_rxcui)

        return next(
            (r for r in relationships
             if r["relationshipName"] == "has_tradename"),
            None
        )
```

### Dose Form Mapping

```json
{
  "dose_form_map": {
    "TAB": {
      "display": "Tablet",
      "snomed": "385055001",
      "fhir_code": "TAB"
    },
    "CAP": {
      "display": "Capsule",
      "snomed": "385049006",
      "fhir_code": "CAP"
    },
    "SUSP": {
      "display": "Suspension",
      "snomed": "387069000",
      "fhir_code": "SUSP"
    },
    "INJ": {
      "display": "Injection",
      "snomed": "385219001",
      "fhir_code": "INJ"
    }
  }
}
```

## Cross-Terminology Mapping

### ICD-10 to SNOMED CT

```python
class TerminologyMapper:
    """Cross-terminology mapping service"""

    def icd10_to_snomed(self, icd10_code):
        """Map ICD-10 code to SNOMED CT concept"""

        # Use SNOMED CT ICD-10 map reference set
        map_refset_id = "447562003"  # ICD-10 complex map reference set

        query = f"""
            SELECT conceptId, mapTarget, mapPriority
            FROM map_refset
            WHERE refsetId = '{map_refset_id}'
            AND mapTarget = '{icd10_code}'
            AND active = 1
            ORDER BY mapPriority
        """

        results = self.db.execute(query)

        return [{
            "snomedCode": r["conceptId"],
            "icd10Code": r["mapTarget"],
            "priority": r["mapPriority"]
        } for r in results]
```

## Terminology Service API

### ValueSet Operations

```python
@app.route("/terminology/valuesets/<id>/expand", methods=["POST"])
def expand_valueset(id):
    """Expand a ValueSet with optional filtering"""

    request_data = request.json

    params = {
        "valueSetId": id,
        "filter": request_data.get("filter"),
        "offset": request_data.get("offset", 0),
        "count": request_data.get("count", 100),
        "includeDesignations": request_data.get("includeDesignations", True),
        "activeOnly": request_data.get("activeOnly", True)
    }

    expansion = terminology_service.expand_valueset(**params)

    return jsonify({
        "resourceType": "ValueSet",
        "expansion": {
            "timestamp": datetime.utcnow().isoformat(),
            "total": expansion["total"],
            "offset": params["offset"],
            "contains": expansion["concepts"]
        }
    })
```

## Best Practices

### 1. Code Selection Priority

```python
CODE_SYSTEM_PRIORITY = [
    "http://snomed.info/sct",        # SNOMED CT - most specific
    "http://loinc.org",               # LOINC - for observations
    "http://www.nlm.nih.gov/research/umls/rxnorm",  # RxNorm - for medications
    "http://hl7.org/fhir/sid/icd-10",  # ICD-10 - for billing/reporting
    "http://www.ama-assn.org/go/cpt"   # CPT - for procedures (US)
]
```

### 2. Multi-Language Support

```python
def get_translated_term(concept_code, system, language):
    """Get translated term for a medical concept"""

    if system == "http://snomed.info/sct":
        # SNOMED CT has built-in language support
        return snomed_service.get_preferred_term(concept_code, language)

    elif system == "http://loinc.org":
        # LOINC linguistic variants
        return loinc_service.get_linguistic_variant(concept_code, language)

    else:
        # Use custom translation service for other systems
        return translation_service.translate_medical_term(
            concept_code,
            system,
            language
        )
```

### 3. Validation Rules

```yaml
terminology_validation:
  rules:
    - name: "diagnosis_requires_code"
      condition: "Condition.code exists"
      requirement: "Condition.code.coding where system in ('http://hl7.org/fhir/sid/icd-10', 'http://snomed.info/sct')"

    - name: "lab_result_requires_loinc"
      condition: "Observation.category contains 'laboratory'"
      requirement: "Observation.code.coding where system = 'http://loinc.org'"

    - name: "medication_requires_rxnorm"
      condition: "MedicationRequest exists"
      requirement: "MedicationRequest.medicationCodeableConcept.coding where system = 'http://www.nlm.nih.gov/research/umls/rxnorm'"
```

## Performance Considerations

### Caching Strategy

```python
TERMINOLOGY_CACHE_CONFIG = {
    "snomed_concepts": {
        "ttl": 86400,  # 24 hours
        "max_size": 100000
    },
    "icd10_mappings": {
        "ttl": 604800,  # 7 days
        "max_size": 50000
    },
    "rxnorm_interactions": {
        "ttl": 3600,   # 1 hour
        "max_size": 10000
    },
    "valueset_expansions": {
        "ttl": 43200,  # 12 hours
        "max_size": 1000
    }
}
```

## Updates and Maintenance

### Version Management

```python
class TerminologyVersionManager:
    """Manage terminology system versions and updates"""

    def check_for_updates(self):
        """Check for available terminology updates"""
        updates = []

        for system in self.managed_systems:
            current = self.get_current_version(system)
            latest = self.check_latest_version(system)

            if latest > current:
                updates.append({
                    "system": system,
                    "current_version": current,
                    "latest_version": latest,
                    "update_available": True
                })

        return updates

    def schedule_update(self, system, target_date):
        """Schedule terminology system update"""
        # Create update job
        job = {
            "system": system,
            "scheduled_date": target_date,
            "steps": [
                "download_update",
                "validate_update",
                "backup_current",
                "apply_update",
                "reindex_search",
                "clear_caches",
                "run_tests"
            ]
        }

        return self.scheduler.schedule(job)
```

## References

- [ICD-10 Browser](https://icd.who.int/browse10/2024/en)
- [SNOMED CT Browser](https://browser.ihtsdotools.org/)
- [LOINC Search](https://loinc.org/search/)
- [RxNorm API](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html)
- [FHIR Terminology Service](https://www.hl7.org/fhir/terminology-service.html)
