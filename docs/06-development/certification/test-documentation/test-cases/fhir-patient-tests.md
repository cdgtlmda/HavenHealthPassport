# FHIR Patient Resource Test Cases

## Test Suite: FHIR-PAT-001

### Test Case: TC-PAT-001 - Create Patient Resource

**Objective**: Validate creation of a new patient resource via FHIR API

**Prerequisites**:
- Test environment accessible
- Valid authentication token
- FHIR server operational

**Test Data**:
```json
{
  "resourceType": "Patient",
  "identifier": [{
    "system": "http://example.org/mrn",
    "value": "TEST-12345"
  }],
  "name": [{
    "family": "TestPatient",
    "given": ["John", "James"]
  }],
  "gender": "male",
  "birthDate": "1980-01-15"
}
```

**Test Steps**:
1. Send POST request to `/Patient` endpoint
2. Include test patient JSON in request body
3. Set Content-Type header to `application/fhir+json`
4. Include authorization header

**Expected Results**:
- HTTP 201 Created response
- Location header with new resource URL
- Response body contains created patient
- Resource ID assigned
- Meta.lastUpdated populated

**Pass/Fail Criteria**:
- Pass: All expected results achieved
- Fail: Any deviation from expected results
