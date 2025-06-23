# Multi-Factor Authentication (MFA) Implementation

## Overview

The Haven Health Passport MFA system provides comprehensive multi-factor authentication to protect user accounts and sensitive healthcare data. The implementation supports multiple authentication methods and enforces different security levels based on user roles.

## Features

### Supported MFA Methods

1. **TOTP (Time-based One-Time Password)**
   - Compatible with Google Authenticator, Authy, and other TOTP apps
   - 30-second time window with ±1 interval tolerance
   - QR code provisioning for easy setup

2. **SMS Verification**
   - 6-digit codes sent via SMS
   - 10-minute expiration window
   - Phone number masking for privacy

3. **Email Verification** (Ready for implementation)
   - Secure codes sent to verified email addresses
   - Backup method for account recovery

4. **Backup Codes**
   - 10 single-use recovery codes
   - 8-character alphanumeric format
   - Secure storage with one-way hashing

## Enforcement Levels

### Role-Based Requirements

| User Role | Enforcement Level | Requirements |
|-----------|------------------|--------------|
| Super Admin | STRICT | Minimum 2 MFA methods required |
| Admin | STRICT | Minimum 2 MFA methods required |
| Healthcare Provider | REQUIRED | At least 1 MFA method required |
| NGO Worker | REQUIRED | At least 1 MFA method required |
| Patient | OPTIONAL | MFA recommended but not required |

### Trusted Device Support

- Devices can be marked as trusted for 30 days
- Trusted devices skip MFA verification
- Trust expires automatically
- Admin users cannot use trusted devices


## Implementation Details

### Core Components

1. **MFAManager** (`src/auth/mfa.py`)
   - Central MFA operations handler
   - Rate limiting and lockout protection
   - Audit logging for all MFA events

2. **Database Models** (`src/models/auth.py`)
   - `MFAConfig`: Stores user MFA settings
   - `LoginAttempt`: Tracks MFA verification attempts
   - `DeviceInfo`: Manages trusted devices

3. **API Endpoints** (`src/api/mfa_endpoints.py`)
   - REST API for MFA operations
   - Secure token-based authentication
   - Comprehensive error handling

### Security Features

1. **Rate Limiting**
   - Maximum 5 failed attempts per 15 minutes
   - Automatic lockout for 30 minutes
   - IP-based tracking for additional security

2. **Secure Storage**
   - TOTP secrets encrypted with AES-256
   - Backup codes hashed with SHA-256
   - No plaintext sensitive data storage

3. **Audit Trail**
   - All MFA events logged
   - Success and failure tracking
   - Compliance-ready audit reports

## API Usage

### Check MFA Requirement
```
GET /api/v1/auth/mfa/requirement
Authorization: Bearer <token>

Response:
{
  "required": true,
  "enforcement_level": "required",
  "configured_methods": ["totp", "sms"],
  "message": "MFA enforcement level: required"
}
```


### Setup TOTP
```
POST /api/v1/auth/mfa/totp/setup
Authorization: Bearer <token>

Response:
{
  "secret": "JBSWY3DPEHPK3PXP",
  "provisioning_uri": "otpauth://totp/Haven%20Health%20Passport:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Haven%20Health%20Passport",
  "qr_code": null
}
```

### Verify MFA Code
```
POST /api/v1/auth/mfa/verify
Authorization: Bearer <token>
Content-Type: application/json

{
  "method": "totp",
  "code": "123456"
}

Response:
{
  "success": true,
  "method": "totp"
}
```

### Generate Backup Codes
```
POST /api/v1/auth/mfa/backup-codes/generate
Authorization: Bearer <token>

Response:
{
  "codes": [
    "ABCD1234",
    "EFGH5678",
    ...
  ],
  "generated_at": "2024-01-20T10:30:00Z"
}
```


## Integration Guide

### Frontend Implementation

1. **Login Flow**
   ```javascript
   // After initial authentication
   const response = await api.checkMFARequirement();
   if (response.required) {
     // Redirect to MFA verification
     showMFAPrompt(response.configured_methods);
   }
   ```

2. **MFA Setup Flow**
   ```javascript
   // Generate TOTP secret
   const setup = await api.setupTOTP();
   // Display QR code
   showQRCode(setup.provisioning_uri);
   // Verify setup
   const verified = await api.verifyTOTP(userCode);
   ```

### Backend Integration

1. **Protect Endpoints**
   ```python
   from src.auth.mfa import MFAManager

   @router.post("/sensitive-operation")
   async def sensitive_operation(
       current_user: UserAuth = Depends(get_current_user),
       db: Session = Depends(get_db)
   ):
       mfa_manager = MFAManager(db)
       if mfa_manager.enforce_mfa_requirement(current_user):
           raise HTTPException(401, "MFA verification required")
   ```

## Next Steps

1. **SMS Provider Integration**
   - Configure Twilio or AWS SNS
   - Update `_send_sms_code` method
   - Add phone number validation

2. **Email Verification**
   - Implement email code generation
   - Add email templates
   - Configure SMTP settings

3. **Enhanced Security**
   - Implement WebAuthn support
   - Add biometric authentication
   - Configure risk-based authentication


## Configuration

### Environment Variables
```bash
# MFA Settings
MFA_TOTP_ISSUER="Haven Health Passport"
MFA_TOTP_WINDOW=1
MFA_BACKUP_CODE_COUNT=10
MFA_MAX_ATTEMPTS=5
MFA_LOCKOUT_DURATION_MINUTES=30

# SMS Provider (Twilio)
TWILIO_ACCOUNT_SID="your_account_sid"
TWILIO_AUTH_TOKEN="your_auth_token"
TWILIO_FROM_NUMBER="+1234567890"
```

### Database Migration
```sql
-- MFA configuration is automatically created via SQLAlchemy
-- Run migrations to create necessary tables:
alembic upgrade head
```

## Compliance

This MFA implementation meets the following compliance requirements:

- **HIPAA**: Strong authentication for PHI access
- **GDPR**: User control over authentication methods
- **ISO 27001**: Multi-factor authentication controls
- **NIST 800-63B**: Authenticator assurance levels

## Support

For issues or questions regarding MFA implementation:
- Review error logs in CloudWatch
- Check audit trail for authentication events
- Contact security team for policy questions
