# FHIR Observation Resource Test Cases

## Test Suite: FHIR-OBS-001

### Test Case: TC-OBS-001 - Create Vital Signs Observation

**Objective**: Validate creation of vital signs observation with proper LOINC coding

**Prerequisites**:
- Test environment accessible
- Valid authentication token
- Patient resource exists (Patient/test-patient-001)
- LOINC terminology service available

**Test Data**:
```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "vital-signs",
      "display": "Vital Signs"
    }]
  }],
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "85354-9",
      "display": "Blood pressure panel with all children optional"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "effectiveDateTime": "2024-01-15T09:30:00Z",
  "component": [
    {
      "code": {
        "coding": [{
          "system": "http://loinc.org",
          "code": "8480-6",
          "display": "Systolic blood pressure"
        }]
      },
      "valueQuantity": {
        "value": 120,
        "unit": "mmHg",
        "system": "http://unitsofmeasure.org",
        "code": "mm[Hg]"
      }
    },
    {
      "code": {
        "coding": [{
          "system": "http://loinc.org",
          "code": "8462-4",
          "display": "Diastolic blood pressure"
        }]
      },
      "valueQuantity": {
        "value": 80,
        "unit": "mmHg",
        "system": "http://unitsofmeasure.org",
        "code": "mm[Hg]"
      }
    }
  ]
}
```

**Test Steps**:
1. Send POST request to `/Observation` endpoint
2. Include observation JSON in request body
3. Set Content-Type header to `application/fhir+json`
4. Include authorization header

**Expected Results**:
- HTTP 201 Created response
- Location header with new resource URL
- Resource ID assigned
- All LOINC codes validated
- Units of measure validated
- Subject reference verified

**Pass/Fail Criteria**:
- Pass: All validations successful, resource created
- Fail: Any validation error or creation failure

---

### Test Case: TC-OBS-002 - Create Laboratory Result Observation

**Objective**: Validate laboratory result observation with reference ranges

**Prerequisites**:
- Test environment accessible
- Valid authentication token
- Patient resource exists
- LOINC terminology service available

**Test Data**:
```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "laboratory",
      "display": "Laboratory"
    }]
  }],
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "2947-0",
      "display": "Sodium [Moles/volume] in Blood"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "effectiveDateTime": "2024-01-15T14:00:00Z",
  "valueQuantity": {
    "value": 140,
    "unit": "mmol/L",
    "system": "http://unitsofmeasure.org",
    "code": "mmol/L"
  },
  "referenceRange": [{
    "low": {
      "value": 136,
      "unit": "mmol/L",
      "system": "http://unitsofmeasure.org",
      "code": "mmol/L"
    },
    "high": {
      "value": 145,
      "unit": "mmol/L",
      "system": "http://unitsofmeasure.org",
      "code": "mmol/L"
    }
  }],
  "interpretation": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
      "code": "N",
      "display": "Normal"
    }]
  }]
}
```

**Test Steps**:
1. Send POST request to `/Observation` endpoint
2. Include laboratory observation JSON
3. Verify LOINC code validation
4. Verify unit validation
5. Check reference range processing

**Expected Results**:
- HTTP 201 Created response
- LOINC code validated against terminology service
- Units validated as UCUM codes
- Reference range stored correctly
- Interpretation code validated

**Pass/Fail Criteria**:
- Pass: All validations pass, observation created
- Fail: Any validation failure

---

### Test Case: TC-OBS-003 - Search Observations by Patient

**Objective**: Validate search functionality for patient observations

**Prerequisites**:
- Multiple observations exist for test patient
- Various categories and dates
- Search index updated

**Test Steps**:
1. Send GET request to `/Observation?patient=Patient/test-patient-001`
2. Verify response bundle structure
3. Check all observations belong to specified patient
4. Verify pagination if applicable

**Expected Results**:
- HTTP 200 OK response
- Bundle type = "searchset"
- All entries have correct patient reference
- Total count accurate
- Self link included

**Pass/Fail Criteria**:
- Pass: Correct observations returned
- Fail: Missing or incorrect observations

---

### Test Case: TC-OBS-004 - Search Observations by Code and Date

**Objective**: Validate complex search with multiple parameters

**Prerequisites**:
- Observations with various LOINC codes
- Observations across date range
- Search indexes operational

**Test Steps**:
1. Send GET request to `/Observation?code=85354-9&date=ge2024-01-01&date=le2024-01-31`
2. Verify all results match search criteria
3. Check date range filtering
4. Verify LOINC code matching

**Expected Results**:
- Only observations with specified LOINC code
- Only observations within date range
- Proper bundle structure
- Accurate total count

**Pass/Fail Criteria**:
- Pass: All search criteria correctly applied
- Fail: Incorrect filtering or missing results

---

### Test Case: TC-OBS-005 - Update Observation Status

**Objective**: Validate observation update with status change

**Prerequisites**:
- Existing observation in "preliminary" status
- Valid observation ID
- Appropriate permissions

**Test Data**:
```json
{
  "resourceType": "Observation",
  "id": "test-obs-001",
  "status": "final",
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "85354-9"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "effectiveDateTime": "2024-01-15T09:30:00Z",
  "valueQuantity": {
    "value": 120,
    "unit": "mmHg"
  }
}
```

**Test Steps**:
1. Send PUT request to `/Observation/test-obs-001`
2. Include updated observation with status="final"
3. Include If-Match header with current version
4. Verify update processing

**Expected Results**:
- HTTP 200 OK response
- Status changed to "final"
- Version incremented
- Last updated timestamp updated
- Audit trail created

**Pass/Fail Criteria**:
- Pass: Update successful with proper versioning
- Fail: Update rejected or version conflict

---

### Test Case: TC-OBS-006 - Validate Observation with Invalid LOINC Code

**Objective**: Ensure proper validation of terminology bindings

**Prerequisites**:
- Terminology service configured
- Validation enabled

**Test Data**:
```json
{
  "resourceType": "Observation",
  "status": "final",
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "INVALID-CODE",
      "display": "Invalid LOINC code"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "valueString": "Test value"
}
```

**Test Steps**:
1. Send POST request with invalid LOINC code
2. Verify validation response
3. Check error details

**Expected Results**:
- HTTP 400 Bad Request or 422 Unprocessable Entity
- OperationOutcome with validation error
- Clear error message about invalid code
- No resource created

**Pass/Fail Criteria**:
- Pass: Validation correctly rejects invalid code
- Fail: Invalid code accepted

---

### Test Case: TC-OBS-007 - Delete Observation

**Objective**: Validate observation deletion handling

**Prerequisites**:
- Existing observation
- No dependent resources
- Delete permissions

**Test Steps**:
1. Send DELETE request to `/Observation/test-obs-001`
2. Verify deletion response
3. Attempt to read deleted observation
4. Verify audit trail

**Expected Results**:
- HTTP 204 No Content or 200 OK
- Subsequent read returns 410 Gone or 404 Not Found
- Audit record created
- History preserved if versioning enabled

**Pass/Fail Criteria**:
- Pass: Deletion handled per FHIR specification
- Fail: Resource still accessible or improper handling

---

## Test Data Sets

### Vital Signs Test Set
- Blood pressure readings (multiple)
- Heart rate observations
- Temperature measurements
- Respiratory rate
- Oxygen saturation

### Laboratory Test Set
- Complete blood count components
- Basic metabolic panel
- Liver function tests
- Lipid panel results
- Glucose measurements

### Edge Cases
- Missing required fields
- Invalid units of measure
- Future-dated observations
- Null value handling
- Maximum value boundaries
