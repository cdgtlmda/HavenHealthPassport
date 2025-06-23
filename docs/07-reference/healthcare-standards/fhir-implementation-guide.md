# FHIR Implementation Guide

## Overview

Haven Health Passport implements HL7 FHIR R4 (4.0.1) as the primary healthcare data exchange standard. This guide provides detailed information about our FHIR server configuration, resource profiles, and implementation specifics.

## Server Configuration

### Base Configuration

Haven Health Passport uses AWS HealthLake as its FHIR R4 server implementation.

```yaml
fhir_server:
  provider: "AWS HealthLake"
  api_version: "FHIR R4 (4.0.1)"
  base_url_pattern: "https://healthlake.{region}.amazonaws.com/datastore/{datastore_id}/r4/"
  default_format: "application/fhir+json"
  supported_formats:
    - "application/fhir+json"
    - "application/fhir+xml"

  features:
    - bulk_data_export
    - preloaded_terminology_support
    - smart_on_fhir
    - patch_support
    - search_parameters
    - chained_search
```

### Authentication & Authorization

```javascript
// AWS IAM-based authentication with API Gateway integration
const authConfig = {
  authType: "AWS_IAM",
  apiGateway: "https://api.havenhealthpassport.org/fhir-proxy",
  scopes: {
    patient: [
      "patient/*.read",
      "patient/*.write"
    ],
    practitioner: [
      "patient/*.read",
      "patient/*.write",
      "practitioner/*.read"
    ],
    system: [
      "system/*.read",
      "system/*.write"
    ]
  }
};
```

## Resource Profiles

### Patient Resource Profile

```json
{
  "resourceType": "StructureDefinition",
  "id": "haven-patient",
  "url": "https://havenpassport.org/fhir/StructureDefinition/haven-patient",
  "name": "HavenPatient",
  "status": "active",
  "kind": "resource",
  "abstract": false,
  "type": "Patient",
  "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Patient",
  "derivation": "constraint",
  "differential": {
    "element": [
      {
        "id": "Patient.identifier",
        "path": "Patient.identifier",
        "slicing": {
          "discriminator": [
            {
              "type": "value",
              "path": "system"
            }
          ],
          "rules": "open"
        },
        "min": 1
      },
      {
        "id": "Patient.identifier:unhcrId",
        "path": "Patient.identifier",
        "sliceName": "unhcrId",
        "min": 0,
        "max": "1",
        "type": [
          {
            "code": "Identifier"
          }
        ]
      }
    ]
  }
}
```

### Observation Resource Implementation

```python
class ObservationResource:
    """Haven-specific Observation resource implementation"""

    VITAL_SIGNS_PROFILES = {
        "blood_pressure": "http://hl7.org/fhir/StructureDefinition/bp",
        "heart_rate": "http://hl7.org/fhir/StructureDefinition/heartrate",
        "temperature": "http://hl7.org/fhir/StructureDefinition/bodytemp",
        "oxygen_saturation": "http://hl7.org/fhir/StructureDefinition/oxygensat"
    }

    @staticmethod
    def create_vital_sign(patient_id, vital_type, value, unit, performed_datetime):
        observation = {
            "resourceType": "Observation",
            "meta": {
                "profile": [ObservationResource.VITAL_SIGNS_PROFILES[vital_type]]
            },
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs"
                }]
            }],
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "effectiveDateTime": performed_datetime,
            "valueQuantity": {
                "value": value,
                "unit": unit,
                "system": "http://unitsofmeasure.org"
            }
        }
        return observation
```

## Search Parameters

### Custom Search Parameters

```xml
<SearchParameter xmlns="http://hl7.org/fhir">
  <id value="patient-refugee-status"/>
  <url value="https://havenpassport.org/fhir/SearchParameter/patient-refugee-status"/>
  <name value="refugee-status"/>
  <status value="active"/>
  <description value="Search patients by refugee status"/>
  <code value="refugee-status"/>
  <base value="Patient"/>
  <type value="token"/>
  <expression value="Patient.extension('https://havenpassport.org/fhir/StructureDefinition/refugee-status').value"/>
</SearchParameter>
```

### Search Examples

```bash
# Search for patients by name
GET /Patient?name=Ahmad

# Search with refugee status
GET /Patient?refugee-status=registered

# Search observations by date range
GET /Observation?patient=123&date=ge2024-01-01&date=le2024-12-31

# Search with include
GET /MedicationRequest?patient=123&_include=MedicationRequest:medication
```

## Operations

### Custom Operations

```python
@operation(name="$emergency-access", resource_types=["Patient"])
def emergency_access(request):
    """
    Grant emergency access to patient records

    Parameters:
    - patient: Reference to patient
    - practitioner: Reference to requesting practitioner
    - reason: CodeableConcept for access reason
    - duration: Period for access validity
    """
    patient_id = request.parameter["patient"]
    practitioner_id = request.parameter["practitioner"]

    # Audit emergency access
    audit_entry = create_audit_entry(
        type="emergency-access",
        patient=patient_id,
        practitioner=practitioner_id,
        reason=request.parameter["reason"]
    )

    # Grant time-limited access
    grant_emergency_access(
        patient_id,
        practitioner_id,
        duration=request.parameter.get("duration", "PT24H")
    )

    return OperationOutcome(success=True)
```

## Bulk Data Operations

### Export Configuration

```json
{
  "export_config": {
    "max_resources_per_file": 10000,
    "output_format": "application/fhir+ndjson",
    "file_naming": "{resource_type}_{timestamp}_{sequence}.ndjson",
    "compression": "gzip",
    "encryption": "AES-256-GCM"
  }
}
```

### Export Example

```python
async def initiate_bulk_export(patient_group_id, since_date=None):
    """Initiate bulk data export for a patient group"""

    export_request = {
        "resourceType": "Group",
        "id": patient_group_id,
        "_type": ["Patient", "Observation", "MedicationRequest", "Condition"],
        "_since": since_date,
        "_outputFormat": "application/fhir+ndjson"
    }

    # Initiate async export
    job_id = await fhir_client.bulk_export(export_request)

    return {
        "jobId": job_id,
        "status": "accepted",
        "pollingUrl": f"/fhir/bulk-status/{job_id}"
    }
```

## Terminology Service Integration

### ValueSet Expansion

```python
def expand_valueset(valueset_url, filter_text=None):
    """Expand a ValueSet with optional filtering"""

    expansion_params = {
        "url": valueset_url,
        "filter": filter_text,
        "count": 100,
        "includeDesignations": True,
        "activeOnly": True
    }

    return terminology_service.expand(expansion_params)
```

### Code Validation

```python
def validate_code(code, system, valueset_url=None):
    """Validate a code against a system or ValueSet"""

    validation_params = {
        "code": code,
        "system": system,
        "display": None,  # Will be populated if valid
        "valueSet": valueset_url
    }

    result = terminology_service.validate_code(validation_params)

    return {
        "valid": result.result,
        "message": result.message,
        "display": result.display
    }
```

## Error Handling

### OperationOutcome Examples

```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "invalid",
      "details": {
        "coding": [
          {
            "system": "https://havenpassport.org/fhir/CodeSystem/errors",
            "code": "INVALID_REFUGEE_ID",
            "display": "Invalid refugee identification number"
          }
        ]
      },
      "diagnostics": "The provided UNHCR ID does not match the expected format",
      "expression": ["Patient.identifier[0]"]
    }
  ]
}
```

## Performance Optimization

### Caching Strategy

```yaml
caching:
  terminology_cache:
    type: "redis"
    ttl: 86400  # 24 hours
    max_size: "10GB"

  resource_cache:
    type: "in-memory"
    ttl: 3600   # 1 hour
    max_entries: 10000

  search_cache:
    type: "elasticsearch"
    ttl: 300    # 5 minutes
    max_results: 1000
```

## Monitoring and Metrics

### Key Metrics

```python
FHIR_METRICS = {
    "resource_operations": [
        "fhir.resource.create.count",
        "fhir.resource.read.count",
        "fhir.resource.update.count",
        "fhir.resource.delete.count"
    ],
    "performance": [
        "fhir.operation.duration",
        "fhir.search.duration",
        "fhir.validation.duration"
    ],
    "errors": [
        "fhir.error.validation",
        "fhir.error.authorization",
        "fhir.error.server"
    ]
}
```

## Testing

### Conformance Testing

```bash
# Run FHIR validator
java -jar validator_cli.jar /data/patient-example.json -version 4.0.1

# Run touchstone tests
npm run test:touchstone -- --config=haven-fhir-config.json

# Run crucible tests
bundle exec rake crucible:test SERVER_URL=https://api.havenpassport.org/fhir
```

## Migration Guide

### From Legacy Systems

```python
class LegacyToFHIRMigration:
    """Migrate legacy health records to FHIR format"""

    def migrate_patient(self, legacy_patient):
        fhir_patient = {
            "resourceType": "Patient",
            "identifier": self.map_identifiers(legacy_patient),
            "name": self.map_names(legacy_patient),
            "telecom": self.map_contact_info(legacy_patient),
            "address": self.map_addresses(legacy_patient),
            "birthDate": legacy_patient.get("dob"),
            "gender": self.map_gender(legacy_patient.get("sex"))
        }

        # Add refugee-specific extensions
        if legacy_patient.get("refugee_status"):
            fhir_patient["extension"] = [{
                "url": "https://havenpassport.org/fhir/StructureDefinition/refugee-status",
                "valueCodeableConcept": {
                    "coding": [{
                        "system": "https://havenpassport.org/fhir/CodeSystem/refugee-status",
                        "code": legacy_patient["refugee_status"]
                    }]
                }
            }]

        return fhir_patient
```

## Troubleshooting

### Common Issues

1. **Bundle Transaction Failures**
   - Check referential integrity
   - Verify resource dependencies
   - Review transaction operation types

2. **Search Performance**
   - Enable search parameter indexing
   - Use _count parameter for large result sets
   - Consider using GraphQL for complex queries

3. **Terminology Service Timeouts**
   - Increase cache TTL for frequently used ValueSets
   - Pre-expand common ValueSets
   - Use local terminology server for offline support

## References

- [FHIR R4 Specification](http://hl7.org/fhir/R4/)
- [SMART on FHIR](https://docs.smarthealthit.org/)
- [FHIR Bulk Data Access](https://hl7.org/fhir/uv/bulkdata/)
- [US Core Implementation Guide](http://hl7.org/fhir/us/core/)
