# Haven Health Passport Conformance Statements

## FHIR Conformance Statement

### Supported FHIR Version
- FHIR R4 (4.0.1)

### Supported Resources
- Patient (read, write, search, update, delete)
- Observation (read, write, search, update)
- MedicationRequest (read, write, search, update)
- Condition (read, write, search, update)
- Procedure (read, write, search)
- AllergyIntolerance (read, write, search)
- Immunization (read, write, search)
- DocumentReference (read, write, search)

### Supported Interactions
- RESTful CRUD operations
- Transaction bundles
- Batch operations
- Search with pagination
- History tracking

### Supported Search Parameters
- All standard search parameters per resource
- Custom search parameters for patient matching
- Chained searches
- Composite searches

## HL7 v2 Conformance

### Supported Message Types
- ADT (A01, A03, A04, A08, A28, A31)
- ORM (O01)
- ORU (R01)
- MDM (T02)

### Message Version
- HL7 v2.5.1

## Medical Coding System Support
- ICD-10-CM (2024 release)
- SNOMED CT (International Edition)
- LOINC (2.74)
- RxNorm (Current release)
- CPT (where applicable)

## Security Conformance
- TLS 1.2+ for all communications
- OAuth 2.0 / SMART on FHIR authentication
- AES-256 encryption at rest
- RBAC access controls
