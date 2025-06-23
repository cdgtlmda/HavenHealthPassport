# Risk-Based Authentication Implementation

## Overview

Haven Health Passport now implements adaptive risk-based authentication that analyzes multiple factors to determine the authentication requirements for each login attempt. The system adapts security measures based on the assessed risk level.

## Features

### 1. Risk Factors Analyzed
- **Device Analysis**: New or untrusted devices
- **Location Analysis**: New locations, impossible travel detection
- **Time Pattern Analysis**: Unusual login hours
- **Failed Attempts**: Recent failed login attempts
- **Network Analysis**: VPN, Tor, proxy detection
- **Behavioral Analysis**: Deviations from normal patterns
- **Credential Breach Check**: Known compromised credentials
- **Bot Detection**: Automated login attempts

### 2. Risk Levels
- **LOW** (0.0 - 0.3): Standard authentication
- **MEDIUM** (0.3 - 0.6): Requires MFA
- **HIGH** (0.6 - 0.8): Requires strong MFA + additional verification
- **CRITICAL** (0.8 - 1.0): Blocks login or requires manual review

### 3. Adaptive Authentication
Based on risk level, the system automatically:
- Allows standard login (low risk)
- Requires multi-factor authentication (medium risk)
- Limits MFA methods to stronger options (high risk)
- Blocks login attempts (critical risk)
- Sends security notifications
- Logs assessment for audit

## Architecture

### Components

1. **RiskBasedAuthService** (`src/services/risk_based_auth_service.py`)
   - Core risk assessment engine
   - Analyzes multiple risk factors
   - Calculates overall risk score

2. **RiskBasedAuthIntegration** (`src/services/risk_based_auth_integration.py`)
   - Integrates risk assessment into auth flow
   - Determines authentication requirements
   - Manages risk context

3. **RiskAssessmentLog** (`src/models/risk_assessment.py`)
   - Database model for audit logging
   - Tracks all risk assessments

### Integration Points

The risk-based authentication is integrated into:
- Login endpoint (`/api/v2/auth/login`)
- Password reset flows
- Session validation

## Configuration

### Risk Weights
Risk factors have configurable weights:
```python
risk_weights = {
    RiskFactor.NEW_DEVICE: 0.3,
    RiskFactor.NEW_LOCATION: 0.25,
    RiskFactor.IMPOSSIBLE_TRAVEL: 0.9,
    RiskFactor.SUSPICIOUS_TIME: 0.15,
    RiskFactor.FAILED_ATTEMPTS: 0.4,
    RiskFactor.VPN_DETECTED: 0.35,
    RiskFactor.TOR_DETECTED: 0.8,
    RiskFactor.BEHAVIORAL_ANOMALY: 0.5,
    RiskFactor.CREDENTIAL_BREACH: 0.7,
    RiskFactor.BOT_DETECTED: 0.85
}
```

### Risk Thresholds
```python
risk_thresholds = {
    RiskLevel.LOW: 0.3,
    RiskLevel.MEDIUM: 0.6,
    RiskLevel.HIGH: 0.8,
    RiskLevel.CRITICAL: 0.9
}
```

## API Changes

### Login Endpoint Enhancement
The login endpoint now returns risk information:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {
    "id": "...",
    "email": "...",
    "role": "...",
    "risk_level": "medium",
    "mfa_required": true,
    "mfa_methods": ["totp", "sms", "email", "fido2"]
  }
}
```

### Risk-Based MFA
When MFA is required due to risk:
1. Initial login returns empty tokens with `mfa_required: true`
2. Client must complete MFA using allowed methods
3. Final tokens issued after successful MFA

## Security Benefits

1. **Adaptive Security**: Security measures scale with risk
2. **Attack Prevention**: Blocks suspicious attempts automatically
3. **User Experience**: Low-risk users get frictionless access
4. **Audit Trail**: Complete logging for compliance
5. **Early Detection**: Identifies attacks before compromise

## Usage Examples

### Low Risk Login
```
User: Regular user from known device at usual time
Risk Score: 0.1 (LOW)
Result: Standard authentication proceeds
```

### Medium Risk Login
```
User: Login from new device
Risk Score: 0.4 (MEDIUM)
Result: MFA required, user can choose method
```

### High Risk Login
```
User: Login from new location + failed attempts
Risk Score: 0.7 (HIGH)
Result: Only TOTP or FIDO2 allowed, security alert sent
```

### Critical Risk Login
```
User: Impossible travel + Tor network detected
Risk Score: 0.95 (CRITICAL)
Result: Login blocked, manual review required
```

## Database

### Risk Assessment Logs Table
```sql
CREATE TABLE risk_assessment_logs (
    id UUID PRIMARY KEY,
    assessment_id UUID UNIQUE NOT NULL,
    user_id UUID REFERENCES user_auth(id),
    email VARCHAR(255) NOT NULL,
    risk_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    risk_factors JSONB,
    ip_address VARCHAR(45) NOT NULL,
    -- Additional fields for context and outcomes
);
```

## Testing

Run risk-based auth tests:
```bash
pytest tests/services/test_risk_based_auth.py
```

## Future Enhancements

1. **Machine Learning**: Train models on historical data
2. **Device Trust**: Build device reputation over time
3. **Behavioral Biometrics**: Typing patterns, mouse movements
4. **External Intelligence**: Integrate threat intelligence feeds
5. **Custom Rules**: Allow organization-specific risk rules
6. **Risk Scoring API**: Expose risk assessment for other services

## Compliance

- **NIST 800-63B**: Implements risk-based authentication per guidelines
- **HIPAA**: Enhanced authentication for healthcare data
- **SOC 2**: Comprehensive audit logging
- **GDPR**: Privacy-preserving risk assessment
