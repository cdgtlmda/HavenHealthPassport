# Haven Health Passport - Medical-Compliant Test Infrastructure

## Overview

This test infrastructure enforces strict medical compliance standards for the Haven Health Passport system. **EVERY test must pass medical compliance checks** or the system cannot be deployed.

## Critical Requirements

### 1. **ZERO Unencrypted PHI on Blockchain**
- The `blockchain_phi_validator` fixture prevents ANY patient data on-chain
- Only hashes and encrypted references allowed
- Violation = Immediate test failure

### 2. **HIPAA Compliance**
- All PHI must be encrypted (AES-256-GCM minimum)
- Every PHI access must create audit log
- Access control must follow minimum necessary principle
- 7-year audit retention required

### 3. **FHIR R4 Compliance**
- All healthcare resources must validate against FHIR R4
- Required for interoperability with WHO/UNHCR systems
- Refugee-specific identifiers supported

### 4. **Emergency Access Protocols**
- Full audit trail for emergency overrides
- Support for mass casualty events
- Offline operation capability
- Cross-border emergency transfers

## Test Structure

```
tests/
├── conftest.py                    # Medical compliance fixtures
├── compliance/                    # Compliance verification tests
│   ├── test_fhir_compliance.py   # FHIR R4 validation
│   ├── test_hipaa_compliance.py  # HIPAA security tests
│   ├── test_blockchain_phi.py    # Blockchain safety tests
│   └── test_hl7_compliance.py    # HL7 message validation
├── unit/                          # 1:1 mapping with src/ files
├── integration/                   # System integration tests
├── e2e/                          # End-to-end user journeys
└── performance/                   # Load and stress tests
```

## Running Tests

### Full Compliance Suite
```bash
cd /Users/cadenceapeiron/Documents/HavenHealthPassport
./tests/run_compliance_tests.py
```

### Python Tests Only
```bash
pytest tests/ -v --cov=src --cov-fail-under=80
```

### JavaScript Tests Only
```bash
cd web && npm test -- --coverage --watchAll=false
```

### Compliance Check
```bash
./scripts/check-compliance-improved.sh
```

## Test Markers

Use these pytest markers for medical compliance:

- `@pytest.mark.fhir_compliance` - Tests requiring FHIR validation
- `@pytest.mark.hipaa_required` - Tests with HIPAA requirements
- `@pytest.mark.emergency_access` - Emergency scenario tests
- `@pytest.mark.phi_encryption` - Tests handling encrypted PHI
- `@pytest.mark.audit_required` - Tests requiring audit logs
- `@pytest.mark.blockchain_safe` - Blockchain PHI safety tests

## Writing New Tests

### Example: Testing a Patient Service

```python
import pytest
from tests.conftest import MedicalComplianceError

@pytest.mark.hipaa_required
@pytest.mark.fhir_compliance
class TestPatientService:
    def test_create_patient_with_encryption(
        self, 
        create_test_patient, 
        hipaa_audit_logger,
        blockchain_phi_validator
    ):
        # Create FHIR-compliant patient with encrypted PHI
        patient = create_test_patient(
            patient_id="test-001",
            name="Test Patient"  # Will be encrypted
        )
        
        # Log access per HIPAA
        hipaa_audit_logger(
            user_id="test-user",
            action="CREATE",
            resource_type="Patient",
            resource_id=patient["id"]
        )
        
        # Verify safe for blockchain (no PHI)
        safe_data = {"patient_hash": hash(patient["id"])}
        assert blockchain_phi_validator(safe_data) is True
```

## Coverage Requirements

- **Overall**: 80% minimum (medical software standard)
- **Critical Components**: 90% minimum
  - Patient data handling
  - Encryption services
  - Emergency access
  - Audit logging
- **Security Components**: 95% minimum
  - Authentication
  - Authorization
  - PHI encryption

## Common Issues and Solutions

### Issue: "PHILeakageError: Unencrypted PHI detected"
**Solution**: Use the `encrypt_phi` fixture for all patient data

### Issue: "Missing audit log for PHI access"
**Solution**: Use `hipaa_audit_logger` for every PHI operation

### Issue: "FHIR validation failed"
**Solution**: Use `fhir_validator` fixture and follow FHIR R4 structure

### Issue: "Coverage below 80%"
**Solution**: Add tests for all code paths, especially error handling

## Emergency Testing Scenarios

Always test these critical scenarios:

1. **Mass Casualty Event**
   - System handles 100+ simultaneous casualties
   - Emergency access activated for multiple staff
   - Audit trail maintained

2. **Network Outage**
   - Offline mode activates automatically
   - Local encryption still enforced
   - Sync queue maintained

3. **Cross-Border Transfer**
   - Patient data properly encrypted
   - Compliance with both countries
   - UNHCR authorization verified

## Compliance Verification

After adding new tests, verify compliance:

```bash
# Check no PHI in test files
grep -r "123-45-6789\|patient.*name\|diagnosis" tests/

# Verify test markers
grep -r "@pytest.mark" tests/ | grep -v "hipaa_required\|fhir_compliance"

# Run security scan
bandit -r src/ tests/
```

## CRITICAL WARNINGS

1. **NEVER** store real patient data in tests
2. **NEVER** disable encryption for "easier testing"
3. **NEVER** skip audit logging in tests
4. **NEVER** put PHI in test file names or comments
5. **ALWAYS** use test-specific encryption keys

## Support

For questions about medical compliance testing:
1. Review the compliance checklist at `.demo/checklists/12-testing-strategy.md`
2. Check the compliance script at `scripts/check-compliance-improved.sh`
3. Consult HIPAA Security Rule (45 CFR §164.308-316)
4. Review FHIR R4 specification at https://hl7.org/fhir/R4/

Remember: **This system handles refugee medical data. Every test failure could mean a life at risk.**
