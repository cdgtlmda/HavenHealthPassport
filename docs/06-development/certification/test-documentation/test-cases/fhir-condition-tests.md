# FHIR Condition Resource Test Cases

## Test Suite: FHIR-COND-001

### Test Case: TC-COND-001 - Create Condition with ICD-10 Code

**Objective**: Validate creation of condition with proper ICD-10 coding

**Prerequisites**:
- Valid patient resource exists
- ICD-10 terminology service available

**Test Data**:
```json
{
  "resourceType": "Condition",
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "active"
    }]
  },
  "verificationStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
      "code": "confirmed"
    }]
  },
  "code": {
    "coding": [{
      "system": "http://hl7.org/fhir/sid/icd-10-cm",
      "code": "E11.9",
      "display": "Type 2 diabetes mellitus without complications"
    }]
  },
  "subject": {
    "reference": "Patient/test-patient-001"
  },
  "onsetDateTime": "2023-06-15"
}
```

**Test Steps**:
1. Send POST request to `/Condition` endpoint
2. Verify ICD-10 code validation
3. Check clinical status validation
4. Validate verification status

**Expected Results**:
- HTTP 201 Created response
- ICD-10 code validated
- Status codes accepted
- Resource created with ID

---

### Test Case: TC-COND-002 - Update Condition Status

**Objective**: Validate condition status workflow transitions

**Test Steps**:
1. Update condition from "active" to "resolved"
2. Include abatement date
3. Verify status transition rules

**Expected Results**:
- Status updated successfully
- Abatement date required for resolved status
- Version incremented
