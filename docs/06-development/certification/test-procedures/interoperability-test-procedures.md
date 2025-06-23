# Interoperability Test Procedures

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-05-31
- **Status**: Active
- **Owner**: Quality Assurance Team

## Table of Contents
1. [General Prerequisites](#general-prerequisites)
2. [FHIR API Test Procedures](#fhir-api-test-procedures)
3. [HL7 Messaging Test Procedures](#hl7-messaging-test-procedures)
4. [Data Import/Export Test Procedures](#data-importexport-test-procedures)
5. [Integration Workflow Test Procedures](#integration-workflow-test-procedures)
6. [Standards Compliance Test Procedures](#standards-compliance-test-procedures)
7. [Performance Test Procedures](#performance-test-procedures)
8. [Error Handling Test Procedures](#error-handling-test-procedures)

## General Prerequisites

### Environment Setup
1. Ensure test environment is configured with:
   - Test FHIR server endpoint: `https://test-fhir.havenhealth.io`
   - Test HL7 interface endpoint: `tcp://test-hl7.havenhealth.io:2575`
   - Test API gateway: `https://test-api.havenhealth.io`
   - Test database with synthetic data loaded

2. Required test accounts:
   - Admin user: `test-admin@havenhealth.io`
   - Standard user: `test-user@havenhealth.io`
   - External system: `test-ehr@partner.io`

3. Test data sets available in `/tests/fixtures/interoperability_test_data.py`

### Testing Tools Required
- Postman Collection: `Haven-Health-Interoperability-Tests.postman_collection.json`
- FHIR Validator: `https://validator.fhir.org`
- HL7 Inspector: Version 2.2 or higher
- JMeter test plans: `/tests/performance/interop-load-tests.jmx`

## FHIR API Test Procedures

### TEST-FHIR-001: Capability Statement Validation

**Objective**: Verify FHIR server capability statement is complete and accurate

**Prerequisites**:
- FHIR server running
- Network access to test environment

**Test Steps**:
1. Open Postman and load Haven Health collection
2. Navigate to FHIR > Metadata folder
3. Execute GET request to `{{fhir_base_url}}/metadata`
4. Verify response status is 200 OK
5. Validate response contains CapabilityStatement resource
6. Check following fields are present:
   - `status` = "active"
   - `fhirVersion` = "4.0.1"
   - `format` includes ["json", "xml"]
   - `rest[0].mode` = "server"
7. For each supported resource in `rest[0].resource[]`:
   - Verify `type` is a valid FHIR resource
   - Check `interaction` array contains expected operations
   - Validate `searchParam` definitions
8. Save response to test evidence folder

**Expected Results**:
- CapabilityStatement validates against FHIR schema
- All required resources are listed
- Interactions match implementation

**Pass Criteria**:
- Response time < 500ms
- Valid FHIR CapabilityStatement returned
- No schema validation errors

### TEST-FHIR-002: Patient Resource CRUD Operations

**Objective**: Test Create, Read, Update, Delete operations on Patient resource

**Prerequisites**:
- Valid OAuth token obtained
- Test patient data prepared

**Test Steps**:

#### Create Patient
1. In Postman, navigate to FHIR > Patient > Create
2. Set Authorization header: `Bearer {{access_token}}`
3. Set Content-Type: `application/fhir+json`
4. Use test patient JSON from fixtures:
```json
{
  "resourceType": "Patient",
  "identifier": [{
    "system": "http://havenhealth.io/mrn",
    "value": "TEST-{{timestamp}}"
  }],
  "name": [{
    "use": "official",
    "family": "TestPatient",
    "given": ["Interop", "Test"]
  }],
  "gender": "female",
  "birthDate": "1990-01-01"
}
```
5. Execute POST to `{{fhir_base_url}}/Patient`
6. Verify response status is 201 Created
7. Extract patient ID from Location header
8. Validate response body matches sent data
9. Record patient ID for subsequent tests

#### Read Patient
1. Navigate to FHIR > Patient > Read
2. Set patient ID in URL: `{{fhir_base_url}}/Patient/{{patient_id}}`
3. Execute GET request
4. Verify status is 200 OK
5. Validate returned patient matches created data
6. Check ETag header is present
7. Verify Last-Modified header

#### Update Patient
1. Navigate to FHIR > Patient > Update
2. Modify patient data (add phone number):
```json
{
  "telecom": [{
    "system": "phone",
    "value": "+1-555-123-4567",
    "use": "mobile"
  }]
}
```
3. Set If-Match header with ETag value
4. Execute PUT to `{{fhir_base_url}}/Patient/{{patient_id}}`
5. Verify status is 200 OK
6. Validate version incremented in response
7. Confirm phone number added

#### Delete Patient
1. Navigate to FHIR > Patient > Delete
2. Execute DELETE to `{{fhir_base_url}}/Patient/{{patient_id}}`
3. Verify status is 204 No Content
4. Attempt to read deleted patient
5. Verify GET returns 410 Gone

**Expected Results**:
- All CRUD operations complete successfully
- Proper HTTP status codes returned
- Resource versioning works correctly

**Pass Criteria**:
- Each operation completes in < 500ms
- All validations pass
- Audit logs created for each operation
### TEST-FHIR-003: Bundle Transaction Processing

**Objective**: Test transactional bundle processing for atomic operations

**Prerequisites**:
- Multiple test resources prepared
- Transaction bundle template available

**Test Steps**:
1. Create transaction bundle with multiple operations:
```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "fullUrl": "urn:uuid:patient-1",
      "resource": { /* Patient resource */ },
      "request": {
        "method": "POST",
        "url": "Patient"
      }
    },
    {
      "fullUrl": "urn:uuid:observation-1",
      "resource": { /* Observation referencing patient */ },
      "request": {
        "method": "POST",
        "url": "Observation"
      }
    }
  ]
}
```
2. POST bundle to `{{fhir_base_url}}/`
3. Verify response status is 200 OK
4. Check response bundle type is "transaction-response"
5. Validate each entry has location and status
6. Verify resources are created with correct references
7. Test rollback by including invalid resource
8. Confirm entire transaction is rolled back

**Expected Results**:
- Bundle processed atomically
- All resources created or none created
- References resolved correctly

**Pass Criteria**:
- Transaction completes in < 2 seconds
- Atomicity maintained
- No partial commits on failure

### TEST-FHIR-004: Search Parameter Testing

**Objective**: Validate search functionality across resources

**Prerequisites**:
- Test data loaded with various patients, observations, medications

**Test Steps**:
1. Test simple search by name:
   - GET `{{fhir_base_url}}/Patient?name=Smith`
   - Verify Bundle returned with matching patients

2. Test date range search:
   - GET `{{fhir_base_url}}/Observation?date=ge2024-01-01&date=le2024-12-31`
   - Validate observations within date range

3. Test chained search:
   - GET `{{fhir_base_url}}/Observation?patient.name=Smith`
   - Verify observations for patients named Smith

4. Test include parameter:
   - GET `{{fhir_base_url}}/Observation?_include=Observation:patient`
   - Check bundle includes referenced patients

5. Test sorting:
   - GET `{{fhir_base_url}}/Patient?_sort=-birthdate`
   - Verify results sorted by birthdate descending

6. Test pagination:
   - GET `{{fhir_base_url}}/Patient?_count=10`
   - Verify 10 results returned
   - Check for next link in bundle

**Expected Results**:
- All search parameters function correctly
- Results match search criteria
- Pagination links work

**Pass Criteria**:
- Search response time < 1 second
- Accurate search results
- Valid bundle structure

## HL7 Messaging Test Procedures

### TEST-HL7-001: ADT Message Processing

**Objective**: Test HL7 ADT (Admit, Discharge, Transfer) message handling

**Prerequisites**:
- HL7 interface configured and running
- HL7 Inspector or similar tool available
- Test ADT messages prepared

**Test Steps**:
1. Configure HL7 Inspector to connect to test interface:
   - Host: `test-hl7.havenhealth.io`
   - Port: `2575`
   - Encoding: ER7

2. Send ADT^A01 (Patient Admission) message:
```
MSH|^~\&|TEST_SENDER|TEST_FACILITY|HAVEN|HEALTH|20250531120000||ADT^A01|MSG00001|P|2.5|||
EVN|A01|20250531120000|||
PID|1||TEST123456^^^FACILITY^MR||DOE^JOHN^A||19800115|M||C|123 MAIN ST^^ANYTOWN^ST^12345||555-123-4567|||M||ACCT123456|123-45-6789|||
PV1|1|I|ROOM123^BED1^UNIT2^FACILITY||||ATTEND^DOCTOR^PRIMARY|||||||||||VISIT123456|||||||||||||||||||||||||20250531120000|||
```

3. Verify ACK received with AA (Application Accept)
4. Query FHIR server for created patient
5. Validate patient demographics match HL7 data
6. Check encounter created from PV1 segment

7. Send ADT^A03 (Patient Discharge):
   - Update PV1 with discharge time
   - Send message
   - Verify encounter updated with end date

8. Test error handling with invalid message:
   - Send message with missing required field
   - Verify NAK with appropriate error

**Expected Results**:
- Messages processed and acknowledged
- Data correctly mapped to FHIR resources
- Errors handled appropriately

**Pass Criteria**:
- ACK received within 1 second
- Data integrity maintained
- Proper error messages for invalid data
### TEST-HL7-002: ORM/ORU Laboratory Workflow

**Objective**: Test lab order and result message processing

**Prerequisites**:
- Lab order test messages
- Result messages with various formats

**Test Steps**:
1. Send ORM^O01 (Lab Order) message:
```
MSH|^~\&|CPOE|FACILITY|LAB|SYSTEM|20250531130000||ORM^O01|ORD00001|P|2.5|||
PID|1||TEST123456^^^FACILITY^MR||DOE^JOHN^A||19800115|M|||
ORC|NW|ORD123456|||||^^^20250531140000||20250531130000|||PHYSICIAN^ORDERING^DR|||
OBR|1|ORD123456||PANEL001^Complete Blood Count^L|||20250531130000|||||||||PHYSICIAN^ORDERING^DR|||||||LAB|F|||
```

2. Verify order created in system
3. Check ServiceRequest resource created
4. Send ORU^R01 (Lab Result) message:
```
MSH|^~\&|LAB|SYSTEM|HAVEN|HEALTH|20250531150000||ORU^R01|RES00001|P|2.5|||
PID|1||TEST123456^^^FACILITY^MR||DOE^JOHN^A||19800115|M|||
OBR|1|ORD123456||PANEL001^Complete Blood Count^L|||20250531130000||||||||20250531145000|BLOOD|PHYSICIAN^ORDERING^DR|||||||LAB|F|||
OBX|1|NM|WBC^White Blood Cell Count^L||7.5|10*9/L|4.5-11.0||||F|||20250531145000||
OBX|2|NM|RBC^Red Blood Cell Count^L||4.8|10*12/L|4.2-5.4||||F|||20250531145000||
OBX|3|NM|HGB^Hemoglobin^L||14.5|g/dL|12.0-16.0||||F|||20250531145000||
```

5. Verify Observation resources created
6. Check values, units, and reference ranges
7. Validate status updates on ServiceRequest

**Expected Results**:
- Orders and results linked correctly
- All OBX segments create observations
- Units and ranges preserved

**Pass Criteria**:
- Message processing < 500ms
- All data elements mapped
- Result status updates reflected
## Data Import/Export Test Procedures

### TEST-IMPORT-001: CCD/C-CDA Document Import

**Objective**: Test Clinical Document Architecture import functionality

**Prerequisites**:
- Sample CCD documents in test data folder
- Patient account for import

**Test Steps**:
1. Login to Haven Health web portal
2. Navigate to Import/Export > Import Documents
3. Select "Clinical Summary (CCD)" as document type
4. Upload test CCD file: `test-ccd-complete.xml`
5. Review import preview showing:
   - Patient demographics
   - Problems list
   - Medications
   - Allergies
   - Immunizations
6. Click "Confirm Import"
7. Verify import results:
   - Check patient demographics updated
   - Navigate to Problems and verify conditions imported
   - Check Medications list for active medications
   - Verify allergy list populated
   - Confirm immunization records created
8. Review audit log for import transaction

**Expected Results**:
- All sections of CCD imported correctly
- Data mapped to appropriate FHIR resources
- No data loss or corruption

**Pass Criteria**:
- Import completes in < 30 seconds
- All data elements preserved
- Validation report shows no errors

### TEST-IMPORT-002: FHIR Bundle Import

**Objective**: Test FHIR Bundle import with multiple resources

**Prerequisites**:
- FHIR Bundle JSON file with patient data
- API access token

**Test Steps**:
1. Using Postman, authenticate to API
2. Load test bundle: `patient-bundle-complete.json`
3. POST to `{{api_base_url}}/import/fhir`
4. Set headers:
   - Content-Type: application/fhir+json
   - Authorization: Bearer {{token}}
5. Review response for import summary:
   - Resources processed
   - Resources created/updated
   - Any errors or warnings
6. Validate each resource type:
   - GET imported patient record
   - Verify observations imported
   - Check document references
   - Validate encounter data
7. Test duplicate detection:
   - Re-import same bundle
   - Verify duplicates prevented
   - Check update vs create logic
**Expected Results**:
- Bundle imported atomically
- All resources validated
- References resolved correctly

**Pass Criteria**:
- Import time < 10 seconds for 100 resources
- Zero data loss
- Accurate duplicate detection

### TEST-EXPORT-001: Patient Summary Export

**Objective**: Test comprehensive patient data export

**Prerequisites**:
- Test patient with complete medical history
- Export permissions configured

**Test Steps**:
1. Navigate to patient record in web portal
2. Click "Export" button
3. Select export format:
   - FHIR JSON
   - CCD/C-CDA
   - PDF Summary
   - CSV (structured data)
4. For FHIR JSON export:
   - Verify Bundle created with all patient data
   - Check resource inclusion:
     * Patient demographics
     * Conditions/Problems
     * Medications
     * Observations
     * Procedures
     * Immunizations
     * Documents
   - Validate references between resources
5. For CCD export:
   - Verify valid XML structure
   - Check all required sections present
   - Validate against CCD schema
6. Download exported file
7. Test re-import to verify round-trip
**Expected Results**:
- Export contains complete patient data
- Format validates against standards
- Data integrity maintained

**Pass Criteria**:
- Export generated in < 5 seconds
- All formats validate successfully
- Round-trip import successful

## Integration Workflow Test Procedures

### TEST-WORKFLOW-001: End-to-End Patient Registration

**Objective**: Test complete patient registration across systems

**Prerequisites**:
- External EHR test system available
- Integration credentials configured

**Test Steps**:
1. External system creates new patient:
   - POST patient to Haven Health API
   - Include demographics and identifiers
2. Verify patient created in Haven Health:
   - Check FHIR Patient resource
   - Validate identifier mapping
   - Confirm audit trail
3. Test patient update from external:
   - PUT updated demographics
   - Verify changes reflected
4. Register patient encounter:
   - Create encounter via API
   - Link to patient
   - Set encounter type and period
5. Verify bi-directional sync:
   - Update patient in Haven Health
   - Confirm webhook fired to external system
   - Validate external system updated
6. Test error scenarios:
   - Duplicate patient registration
   - Invalid identifiers
   - Missing required fields
**Expected Results**:
- Patient registered in both systems
- Updates synchronized bi-directionally
- Errors handled gracefully

**Pass Criteria**:
- Registration completed in < 3 seconds
- Data consistency maintained
- Proper error responses

### TEST-WORKFLOW-002: Laboratory Order to Result Workflow

**Objective**: Test complete lab workflow from order to result delivery

**Prerequisites**:
- Lab interface configured
- Test provider and patient accounts

**Test Steps**:
1. Provider places lab order:
   - Login to provider portal
   - Select patient
   - Navigate to Orders > New Lab Order
   - Select "Complete Blood Count"
   - Add clinical notes
   - Submit order
2. Verify order transmission:
   - Check HL7 ORM message sent
   - Confirm order in lab system
   - Validate order status "active"
3. Simulate lab processing:
   - Update order status to "in-progress"
   - Generate test results
   - Create HL7 ORU message
4. Process lab results:
   - Receive ORU message
   - Create Observation resources
   - Link to original order
   - Update order status "completed"
5. Verify result delivery:
   - Provider receives notification
   - Results viewable in portal
   - Patient notified (if configured)
   - PDF report available
6. Test abnormal results:
   - Send results with critical values
   - Verify urgent notification sent
   - Confirm provider acknowledgment required
**Expected Results**:
- Order flows through complete lifecycle
- Results accurately mapped
- Notifications delivered appropriately

**Pass Criteria**:
- Order-to-result time < 5 minutes (simulated)
- All data elements preserved
- Critical values flagged correctly

## Standards Compliance Test Procedures

### TEST-STANDARDS-001: FHIR R4 Conformance Validation

**Objective**: Validate FHIR resources against R4 specification

**Prerequisites**:
- FHIR Validator tool installed
- Sample resources from system

**Test Steps**:
1. Export sample resources from system:
   - Patient (10 samples)
   - Observation (20 samples)
   - MedicationRequest (10 samples)
   - Condition (10 samples)
   - Procedure (10 samples)
2. Run FHIR Validator on each resource:
   ```bash
   java -jar validator_cli.jar -version 4.0.1 patient-sample.json
   ```
3. Review validation report for:
   - Structure conformance
   - Terminology binding errors
   - Required element violations
   - Cardinality issues
   - Invalid references
4. Test profile conformance:
   - Validate against US Core profiles
   - Check custom profile compliance
   - Verify extensions properly defined
5. Validate terminology usage:
   - Check code system URLs
   - Verify value set membership
   - Validate display names
6. Document any errors or warnings
**Expected Results**:
- All resources validate successfully
- No critical errors found
- Warnings documented and justified

**Pass Criteria**:
- 100% resources pass structural validation
- No required element violations
- All terminology bindings valid

### TEST-STANDARDS-002: HL7 Message Conformance

**Objective**: Validate HL7 v2.x message conformance

**Prerequisites**:
- HL7 message samples
- HL7 validation tool

**Test Steps**:
1. Collect message samples:
   - ADT messages (A01, A03, A08)
   - ORM messages (lab orders)
   - ORU messages (lab results)
   - MDM messages (documents)
2. Validate message structure:
   - Check segment order
   - Verify required fields
   - Validate field lengths
   - Check data types
3. Test encoding rules:
   - Verify escape sequences
   - Check delimiter usage
   - Validate character encoding
4. Validate vocabularies:
   - Check table values
   - Verify code systems
   - Validate user-defined tables
5. Test message acknowledgment:
   - Verify ACK structure
   - Check error reporting
   - Validate MSA segment
**Expected Results**:
- Messages conform to HL7 standards
- All required fields present
- Valid vocabulary usage

**Pass Criteria**:
- Zero structural errors
- All messages parse successfully
- ACK generation correct

## Performance Test Procedures

### TEST-PERF-001: API Load Testing

**Objective**: Validate API performance under load

**Prerequisites**:
- JMeter configured with test plans
- Test data sets prepared
- Performance monitoring enabled

**Test Steps**:
1. Configure JMeter test plan:
   - Set base URL to test environment
   - Load authentication tokens
   - Configure thread groups:
     * 10 concurrent users (baseline)
     * 50 concurrent users (normal load)
     * 100 concurrent users (peak load)
2. Execute baseline test:
   - Run 10-user test for 10 minutes
   - Monitor response times
   - Check error rates
   - Verify resource utilization
3. Execute normal load test:
   - Ramp up to 50 users over 2 minutes
   - Maintain load for 30 minutes
   - Monitor all metrics
4. Execute peak load test:
   - Ramp up to 100 users over 5 minutes
   - Maintain load for 15 minutes
   - Watch for degradation
5. Test scenarios include:
   - Patient search (30%)
   - Resource creation (20%)
   - Bundle transactions (10%)
   - Document upload (10%)
   - Bulk export (5%)
   - General reads (25%)
**Expected Results**:
- Response times within SLA
- No errors under normal load
- Graceful degradation at peak

**Pass Criteria**:
- P95 response time < 500ms (baseline)
- P95 response time < 2s (peak load)
- Error rate < 0.1%
- No memory leaks detected

### TEST-PERF-002: Message Processing Throughput

**Objective**: Test HL7 message processing capacity

**Prerequisites**:
- Message generator tool
- Queue monitoring access

**Test Steps**:
1. Configure message generator:
   - Set message types (ADT, ORM, ORU)
   - Configure message rate
   - Set test duration
2. Execute throughput tests:
   - 10 messages/second for 5 minutes
   - 50 messages/second for 5 minutes
   - 100 messages/second for 2 minutes
   - 200 messages/second for 1 minute
3. Monitor during test:
   - Queue depth
   - Processing time
   - ACK generation time
   - Error rates
   - Database performance
4. Verify message processing:
   - All messages acknowledged
   - Data correctly stored
   - No message loss
   - Proper error handling
**Expected Results**:
- Sustained throughput achieved
- Queue remains manageable
- All messages processed

**Pass Criteria**:
- Process 100 msgs/sec sustained
- Queue depth < 1000 messages
- ACK time < 100ms
- Zero message loss

## Error Handling Test Procedures

### TEST-ERROR-001: API Error Response Testing

**Objective**: Validate proper error handling and responses

**Prerequisites**:
- API test collection with error scenarios
- Invalid test data prepared

**Test Steps**:
1. Test authentication errors:
   - Missing authorization header
   - Invalid token
   - Expired token
   - Insufficient permissions
   - Verify 401/403 responses
2. Test validation errors:
   - POST invalid FHIR resource
   - Missing required fields
   - Invalid data types
   - Check 400 response with details
3. Test resource errors:
   - GET non-existent resource
   - UPDATE deleted resource
   - DELETE already deleted
   - Verify 404/410 responses
4. Test business logic errors:
   - Duplicate identifier
   - Invalid state transitions
   - Constraint violations
   - Check 422 responses
5. Test system errors:
   - Simulate database outage
   - Trigger timeout
   - Force memory error
   - Verify 500/503 responses
6. Validate error format:
   - OperationOutcome resource
   - Appropriate severity
   - Helpful diagnostics
   - Error codes present
**Expected Results**:
- Appropriate HTTP status codes
- Detailed error information
- No sensitive data exposed

**Pass Criteria**:
- All errors handled gracefully
- Consistent error format
- Actionable error messages

### TEST-ERROR-002: Recovery and Resilience Testing

**Objective**: Test system recovery from failures

**Prerequisites**:
- Failure injection tools
- Monitoring dashboards

**Test Steps**:
1. Test network failures:
   - Disconnect external system
   - Verify queuing of messages
   - Restore connection
   - Confirm automatic retry
   - Validate no data loss
2. Test partial failures:
   - Fail one service component
   - Verify degraded operation
   - Check failover behavior
   - Monitor recovery time
3. Test data recovery:
   - Simulate transaction failure
   - Verify rollback completed
   - Check data consistency
   - Validate audit trail
4. Test circuit breaker:
   - Trigger repeated failures
   - Verify circuit opens
   - Check fallback behavior
   - Monitor circuit recovery

**Expected Results**:
- Automatic recovery from failures
- No data loss or corruption
- Appropriate user feedback

**Pass Criteria**:
- Recovery time < 5 minutes
- Zero data loss
- Clear error communication

## Test Evidence Collection

For each test procedure, collect and store:
1. Test execution logs
2. Screenshots/recordings
3. Request/response samples
4. Performance metrics
5. Error messages
6. Validation reports

## Test Report Template

Each test execution should document:
- Test ID and name
- Execution date/time
- Tester name
- Environment details
- Test data used
- Steps executed
- Results observed
- Pass/Fail status
- Issues found
- Evidence location

---
**Document Status**: Complete
**Next Review Date**: 2025-08-31
**Approval**: Pending QA Team Review
