# Quality Gates Documentation

## Overview

Quality Gates are automated checkpoints that ensure code meets healthcare industry standards before deployment. The Haven Health Passport project implements comprehensive quality gates covering code quality, security, performance, compliance, architecture, and documentation.

## Quality Gate Categories

### 1. Code Quality Gates
- **ESLint/PyLint Analysis**: Enforces coding standards with healthcare-specific rules
- **Complexity Checks**: Limits cyclomatic complexity (max 10 for general code, max 5 for critical functions)
- **Duplication Detection**: Prevents code duplication (max 3% allowed)
- **PHI Pattern Detection**: Identifies potential unencrypted PHI exposure

### 2. Security Gates
- **SAST Analysis**: Semgrep with HIPAA/OWASP rulesets
- **Dependency Scanning**: Zero tolerance for critical vulnerabilities
- **Secret Detection**: Prevents hardcoded credentials
- **Encryption Verification**: Ensures all PHI fields are encrypted

### 3. Performance Gates
- **Bundle Size**: Max 5MB for web application
- **Lighthouse Scores**: Min 90% performance score
- **API Response Time**: Max 200ms average latency
- **Database Query Performance**: Max 100ms for patient queries

### 4. Compliance Gates
- **HIPAA Compliance**: Validates all security rule requirements
- **FHIR Validation**: Ensures R4 compliance for interoperability
- **PHI Protection**: Verifies no PHI in logs or error messages
- **Access Control**: Validates RBAC implementation

### 5. Architecture Gates
- **Layer Dependencies**: Prevents circular dependencies
- **API Contracts**: Validates OpenAPI specifications
- **Database Schema**: Ensures proper indexing and constraints

### 6. Documentation Gates
- **Code Documentation**: 80% minimum coverage
- **API Documentation**: All endpoints must be documented
- **README Completeness**: Critical sections required

## Running Quality Gates

### GitHub Actions (Automated)
Quality gates run automatically on:
- Pull requests
- Pushes to main/develop branches
- Manual workflow dispatch

### Local Execution

#### Run All Quality Gates
```bash
# From project root
./scripts/run-quality-gates.sh
```

#### Run Individual Gates

**Code Quality:**
```bash
# JavaScript/React
cd web && npm run lint:strict

# Python
pylint src/ --rcfile=.pylintrc

# Complexity
python scripts/validate-complexity.py --max-complexity=10
```

**Security:**
```bash
# Vulnerability scan
python scripts/check-vulnerabilities.py --max-critical=0 --max-high=0

# Encryption coverage
python scripts/verify-encryption-coverage.py

# SAST
semgrep --config=auto --config=p/hipaa --config=p/owasp src/
```

**Performance:**
```bash
# Lighthouse CI
npm install -g @lhci/cli
lhci autorun

# Bundle analysis
cd web && npm run build
npm run analyze
```

**Compliance:**
```bash
# HIPAA compliance
python scripts/hipaa-compliance-check.py

# FHIR validation
python scripts/validate-fhir-resources.py
```

## Quality Gate Thresholds

| Metric | Threshold | Criticality |
|--------|-----------|-------------|
| Test Coverage | 80% (90% for PHI code) | Required |
| Code Complexity | 10 (5 for critical) | Required |
| Security Vulnerabilities | 0 Critical/High | Required |
| Bundle Size | < 5MB | Required |
| API Response Time | < 200ms avg | Required |
| Lighthouse Performance | > 90% | Required |
| HIPAA Compliance | 100% | Required |
| Documentation Coverage | > 80% | Recommended |

## Fixing Quality Gate Failures

### Code Quality Issues

**High Complexity:**
```python
# ❌ Bad - Complex function
def process_patient_data(data):
    if data:
        if data.get('type') == 'emergency':
            if data.get('severity') > 5:
                if data.get('age') < 18:
                    # ... deep nesting
                    
# ✅ Good - Simplified with early returns
def process_patient_data(data):
    if not data:
        return None
        
    if data.get('type') != 'emergency':
        return process_regular_patient(data)
        
    if data.get('severity') <= 5:
        return process_low_severity(data)
        
    return process_emergency_patient(data)
```

**PHI Exposure:**
```javascript
// ❌ Bad - Unencrypted PHI
const patient = {
    ssn: userInput.ssn,
    diagnosis: userInput.diagnosis
};

// ✅ Good - Encrypted PHI
const patient = {
    ssn: await encryptPHI(userInput.ssn, 'ssn'),
    diagnosis: await encryptPHI(userInput.diagnosis, 'medical')
};
```

### Security Issues

**Dependency Vulnerabilities:**
```bash
# Check vulnerabilities
npm audit
safety check

# Fix automatically where possible
npm audit fix
pip install --upgrade vulnerable-package
```

### Performance Issues

**Bundle Size:**
```javascript
// ❌ Bad - Importing entire library
import * as _ from 'lodash';

// ✅ Good - Import only needed functions
import debounce from 'lodash/debounce';
```

### Compliance Issues

**Missing Audit Logs:**
```python
# ❌ Bad - No audit trail
def access_patient_record(patient_id):
    return PatientRecord.get(patient_id)

# ✅ Good - With audit logging
@audit_required
def access_patient_record(patient_id, user_id):
    record = PatientRecord.get(patient_id)
    AuditLog.create(
        user_id=user_id,
        action="VIEW_PATIENT_RECORD",
        resource_id=patient_id,
        timestamp=datetime.utcnow()
    )
    return record
```

## Bypassing Quality Gates (Emergency Only)

In critical situations, quality gates can be temporarily bypassed:

1. Add `[skip-quality-gates]` to commit message
2. Requires approval from 2 senior developers
3. Must create follow-up issue to address skipped checks
4. Automatic reminder after 24 hours

**Example:**
```bash
git commit -m "EMERGENCY: Critical patient data fix [skip-quality-gates]

Issue #123: Fixing data corruption in emergency access flow
Follow-up: #124 to address quality gate issues"
```

## Quality Gate Reports

Reports are generated for each run:
- `quality-gates-report.md` - Summary report
- `coverage/` - Test coverage reports
- `lighthouse-ci/` - Performance reports
- `security-scan-results/` - Security findings
- Individual JSON reports for each check

## Monitoring Quality Trends

Access quality metrics dashboard:
- GitHub Actions tab → Quality Gates workflow
- View trends over time
- Set up alerts for degradation

## Support

For quality gate issues:
1. Check error logs in GitHub Actions
2. Run failing check locally with verbose mode
3. Consult team lead for threshold adjustments
4. Create issue with `quality-gates` label

Remember: **Quality gates protect patient data and ensure reliable healthcare delivery. Never disable them without proper justification.**
