# HL7 v2 Message Test Cases

## Test Suite: HL7-MSG-001

### Test Case: TC-HL7-001 - Process ADT^A01 Admission Message

**Objective**: Validate processing of patient admission messages

**Test Message**:
```
MSH|^~\&|SENDING_APP|SENDING_FAC|RECEIVING_APP|RECEIVING_FAC|20240115103000||ADT^A01|MSG00001|P|2.5|||AL|NE|
EVN|A01|20240115103000|||
PID|1||TEST12345^^^MRN^MR||TestPatient^John^J||19800115|M|||123 Main St^^Boston^MA^02101^USA|||||||
PV1|1|I|ICU^101^A||||||||||||||||V00001|||||||||||||||||||||||||20240115103000|
```

**Test Steps**:
1. Send HL7 message to interface engine
2. Verify message parsing
3. Check ACK response
4. Validate patient creation in FHIR

**Expected Results**:
- ACK with AA (Application Accept)
- Patient resource created
- Encounter resource created
- Identifiers mapped correctly

---

### Test Case: TC-HL7-002 - Process ORU^R01 Lab Result Message

**Objective**: Validate lab result message processing

**Test Steps**:
1. Send ORU message with lab results
2. Verify OBX segment parsing
3. Check LOINC code mapping
4. Validate observation creation

**Expected Results**:
- Observations created in FHIR
- LOINC codes properly mapped
- Units converted to UCUM
- Reference ranges preserved
