# SMS Backup Implementation

## Overview

The Haven Health Passport SMS backup system provides a reliable fallback authentication method for users who cannot access their TOTP authenticator app. It includes multi-provider support, rate limiting, and comprehensive security features.

## Features

### Multi-Provider Support
- **Twilio**: Primary SMS provider with delivery tracking
- **AWS SNS**: Backup provider for reliability
- **Mock Provider**: Development and testing support
- **Automatic Failover**: Seamless switching between providers

### Security Features
- **Rate Limiting**: Per-minute, per-hour, and per-day limits
- **Cooldown Periods**: Prevents SMS flooding
- **Phone Validation**: Country code and pattern checking
- **Anti-Fraud**: Suspicious number detection
- **Secure Code Generation**: Cryptographically secure codes

### User Experience
- **Configurable Code Length**: 4-10 digits
- **Custom Message Templates**: Localization support
- **Phone Number Masking**: Privacy protection
- **Resend Capability**: With rate limiting

## Architecture

### Core Components

1. **SMS Providers** (`src/services/sms/`)
   - Abstract provider interface
   - Provider implementations (Twilio, AWS SNS, Mock)
   - Delivery status tracking

2. **SMS Service** (`src/services/sms/sms_service.py`)
   - Provider management and failover
   - Rate limiting enforcement
   - Message routing

3. **SMS Backup Config** (`src/auth/sms_backup_config.py`)
   - Configuration management
   - Phone validation rules
   - Message formatting

4. **MFA Integration**
   - Seamless integration with existing MFA system
   - SMS as backup method for TOTP


## Configuration

### Environment Variables

```bash
# Twilio Configuration
TWILIO_ENABLED=true
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890

# AWS SNS Configuration
AWS_SNS_ENABLED=true
AWS_SNS_REGION=us-east-1
AWS_SNS_SENDER_ID=HavenHealth

# SMS Backup Settings
SMS_BACKUP_ENABLED=true
SMS_CODE_LENGTH=6
SMS_CODE_VALIDITY_MINUTES=10
SMS_MAX_ATTEMPTS=3
SMS_COOLDOWN_MINUTES=1
SMS_DAILY_LIMIT=10
```

### Provider Configuration

```python
# Priority order (lower = higher priority)
TWILIO = 1
AWS_SNS = 2
MOCK = 100

# Rate limits
MAX_MESSAGES_PER_MINUTE = 60
MAX_MESSAGES_PER_HOUR = 1000
MAX_MESSAGES_PER_DAY = 10000
```

## API Usage

### Initiate SMS Verification

```python
# In MFA manager
masked_phone = mfa_manager.initiate_sms_verification(
    user=current_user,
    phone_number="+1234567890"  # Optional, uses user's phone if not provided
)
```

### Verify SMS Code

```python
# Verify the received code
is_valid = mfa_manager.verify_sms_code(
    user=current_user,
    code="123456"
)
```


## Security Considerations

### Rate Limiting
- **Per-Provider Limits**: Each provider has independent rate limits
- **User-Level Limits**: Daily SMS limit per user
- **Cooldown Periods**: Prevents rapid-fire SMS requests
- **IP-Based Tracking**: Additional layer of abuse prevention

### Phone Number Security
- **E.164 Format**: Strict phone number validation
- **Country Code Filtering**: Allow/block specific countries
- **Pattern Detection**: Identify suspicious numbers
- **Ownership Verification**: Confirm user owns the phone

### Code Security
- **Cryptographically Secure**: Using `secrets` module
- **One-Way Hashing**: Codes stored as hashes
- **Time-Limited**: Automatic expiration
- **Single Use**: Codes invalidated after use

## Monitoring

### Metrics to Track
- SMS send success/failure rates
- Provider failover frequency
- Average delivery time
- Cost per SMS by provider
- Fraud detection triggers

### Alerts
- High failure rate alerts
- Rate limit violations
- Suspicious activity patterns
- Provider availability issues

## Compliance

This SMS implementation meets requirements for:
- **HIPAA**: Secure transmission of verification codes
- **GDPR**: User consent and data minimization
- **TCPA**: Compliance with SMS regulations
- **ISO 27001**: Access control requirements

## Next Steps

1. Configure production SMS providers
2. Set up delivery tracking webhooks
3. Implement SMS cost optimization
4. Add support for WhatsApp Business API
5. Enable voice call fallback
