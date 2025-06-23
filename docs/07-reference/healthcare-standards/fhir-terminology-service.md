# FHIR Terminology Service Setup

## Overview

The Haven Health Passport FHIR server includes a comprehensive terminology service that supports validation and expansion of medical codes using standard terminologies like LOINC, SNOMED CT, ICD-10, and RxNorm.

## Configuration

### Terminology Configuration File
Located at: `fhir-server/config/terminology-config.yaml`

Key settings:
- Enable/disable specific code systems
- Configure file paths for terminology data
- Set caching and performance parameters
- Define validation behavior

### Supported Terminologies

1. **LOINC** (Logical Observation Identifiers Names and Codes)
   - Laboratory and clinical observations
   - Requires LOINC data files from Regenstrief Institute

2. **SNOMED CT** (Systematized Nomenclature of Medicine Clinical Terms)
   - Comprehensive clinical terminology
   - Requires SNOMED International RF2 release files

3. **ICD-10** (International Classification of Diseases, 10th Revision)
   - Diagnosis and procedure codes
   - Supports both ICD-10-CM and ICD-10-PCS

4. **RxNorm**
   - Normalized names for clinical drugs
   - Drug ingredient and dose form information

5. **Custom Code Systems**
   - Haven-specific codes for refugee health scenarios
   - Displacement status, camp locations, etc.

## Setup Instructions

### 1. Obtain Terminology Files

#### LOINC
1. Register at https://loinc.org
2. Download LOINC Table File (CSV format)
3. Place in `/app/terminology/loinc/`

#### SNOMED CT
1. Register at https://www.snomed.org
2. Download RF2 release files
3. Extract to `/app/terminology/snomed/`

#### ICD-10
1. Download from https://www.cms.gov/medicare/coding/icd10
2. Place XML files in `/app/terminology/icd10/`

#### RxNorm
1. Download from https://www.nlm.nih.gov/research/umls/rxnorm
2. Extract RRF files to `/app/terminology/rxnorm/`

### 2. Configure File Paths

Update `terminology-config.yaml` with actual file locations:

```yaml
code_systems:
  loinc:
    file_path: /app/terminology/loinc/Loinc.csv
  snomed:
    files:
      - /app/terminology/snomed/SnomedCT_InternationalRF2_Full.zip
  icd10:
    files:
      cm: /app/terminology/icd10/icd10cm_tabular_2024.xml
  rxnorm:
    files:
      concepts: /app/terminology/rxnorm/RXNCONSO.RRF
```

### 3. Initial Loading

Terminology loading happens automatically on server startup if files are present.

Monitor logs for loading progress:
```bash
docker logs haven-fhir-server | grep terminology
```

## Usage

### Code Validation

The terminology service automatically validates codes in resources:

```json
{
  "resourceType": "Observation",
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "2345-7",
      "display": "Glucose [Mass/volume] in Serum or Plasma"
    }]
  }
}
```

### ValueSet Expansion

Expand a ValueSet to get all included codes:

```
GET /fhir/ValueSet/$expand?url=https://havenhealthpassport.org/fhir/ValueSet/refugee-status
```

### Code System Lookup

Look up details about a specific code:

```
GET /fhir/CodeSystem/$lookup?system=http://loinc.org&code=2345-7
```

### Concept Translation

Translate between code systems using ConceptMaps:

```
GET /fhir/ConceptMap/$translate?code=2345-7&system=http://loinc.org&target=http://snomed.info/sct
```

## Custom Terminologies

### Refugee Health Codes

The system includes custom code systems for refugee-specific concepts:

- **Refugee Status**: registered, asylum-seeker, internally-displaced, stateless
- **Displacement Reasons**: conflict, persecution, natural-disaster, economic
- **Camp Locations**: Specific refugee camp identifiers

### Adding Custom Codes

1. Update `HavenTerminologyLoaderService.java`
2. Add concepts to the custom code system
3. Rebuild and redeploy the FHIR server

## Performance Optimization

### Caching
- Validation results cached for 1 hour
- ValueSet expansions cached
- Concept translations cached for 2 hours

### Indexing
- Lucene indexes for fast terminology searches
- Indexes stored in `/app/data/terminology-index`

### Memory Management
- Deferred loading for large code systems (>1000 codes)
- Configurable memory limits for terminology loading

## Troubleshooting

### Common Issues

1. **Out of Memory during loading**
   - Increase Java heap size in Dockerfile
   - Enable deferred loading for large code systems

2. **Slow validation performance**
   - Ensure caching is enabled
   - Check index directory permissions
   - Monitor cache hit rates

3. **Missing terminology files**
   - Verify file paths in configuration
   - Check file permissions
   - Ensure files are in correct format

### Debug Logging

Enable detailed terminology logging:

```yaml
logging:
  level:
    ca.uhn.fhir.jpa.term: DEBUG
    ca.uhn.fhir.context.support: DEBUG
```

## Maintenance

### Updating Terminologies

1. Download new version of terminology files
2. Replace old files in terminology directories
3. Clear terminology caches
4. Restart FHIR server
5. Monitor logs for successful loading

### Backup

Important directories to backup:
- `/app/terminology/` - Source terminology files
- `/app/data/terminology-index/` - Search indexes
- Database tables: `TRM_*` tables contain loaded terminology data

## API Examples

### Validate a LOINC code
```bash
curl -X GET "http://localhost:8080/fhir/CodeSystem/$validate-code?url=http://loinc.org&code=2345-7"
```

### Expand emergency conditions ValueSet
```bash
curl -X GET "http://localhost:8080/fhir/ValueSet/$expand?url=https://havenhealthpassport.org/fhir/ValueSet/emergency-conditions"
```

### Search for concepts by name
```bash
curl -X GET "http://localhost:8080/fhir/CodeSystem?name:contains=glucose"
```
