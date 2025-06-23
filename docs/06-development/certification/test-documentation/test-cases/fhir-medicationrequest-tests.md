# FHIR MedicationRequest Resource Test Cases

## Test Suite: FHIR-MED-001

### Test Case: TC-MED-001 - Create MedicationRequest with RxNorm Code

**Objective**: Validate creation of medication request with proper RxNorm coding

**Prerequisites**:
- Valid patient resource exists
- RxNorm terminology service available
- Prescriber practitioner resource exists

**Test Data**:
```json
{
  "resourceType": "MedicationRequest",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": {
    "coding": [{
      "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
      "code": "197380",
      "display": "Aspirin 81 MG Oral Tablet"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "authoredOn": "2024-01-15T10:00:00Z",
  "requester": {
    "reference": "Practitioner/test-prescriber-001"
  },
  "dosageInstruction": [{
    "text": "Take 1 tablet by mouth daily",
    "timing": {
      "repeat": {
        "frequency": 1,
        "period": 1,
        "periodUnit": "d"
      }
    },
    "route": {
      "coding": [{
        "system": "http://snomed.info/sct",
        "code": "26643006",
        "display": "Oral route"
      }]
    },
    "doseAndRate": [{
      "doseQuantity": {
        "value": 1,
        "unit": "tablet",
        "system": "http://unitsofmeasure.org",
        "code": "{tablet}"
      }
    }]
  }]
}
```

**Test Steps**:
1. Send POST request to `/MedicationRequest` endpoint
2. Verify RxNorm code validation
3. Check dosage instruction structure
4. Validate SNOMED route code

**Expected Results**:
- HTTP 201 Created response
- RxNorm code validated
- Dosage timing parsed correctly
- Route validated against SNOMED
- Resource ID assigned

**Pass/Fail Criteria**:
- Pass: All validations successful
- Fail: Any validation error

---

### Test Case: TC-MED-002 - Create MedicationRequest with Dispense Instructions

**Objective**: Validate medication request with pharmacy dispense instructions

**Test Data**:
```json
{
  "resourceType": "MedicationRequest",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": {
    "coding": [{
      "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
      "code": "197696",
      "display": "Lisinopril 10 MG Oral Tablet"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "dispenseRequest": {
    "quantity": {
      "value": 30,
      "unit": "tablet",
      "system": "http://unitsofmeasure.org",
      "code": "{tablet}"
    },
    "numberOfRepeatsAllowed": 3,
    "expectedSupplyDuration": {
      "value": 30,
      "unit": "days",
      "system": "http://unitsofmeasure.org",
      "code": "d"
    }
  }
}
```

**Test Steps**:
1. Send POST request with dispense instructions
2. Verify quantity validation
3. Check refill authorization
4. Validate supply duration

**Expected Results**:
- Dispense quantity accepted
- Refills properly recorded
- Supply duration calculated
- HTTP 201 Created

---

### Test Case: TC-MED-003 - Search MedicationRequests by Patient and Status

**Objective**: Validate search functionality for medication requests

**Test Steps**:
1. Send GET request to `/MedicationRequest?patient=Patient/test-patient-001&status=active`
2. Verify bundle structure
3. Check filtering accuracy

**Expected Results**:
- Only active medications returned
- All belong to specified patient
- Bundle includes total count

**Pass/Fail Criteria**:
- Pass: Correct filtering applied
- Fail: Incorrect or missing results
