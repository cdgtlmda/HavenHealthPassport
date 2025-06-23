# SMS Notification Configuration

## Overview

The Haven Health Passport supports SMS notifications through two providers:
- AWS SNS (Simple Notification Service)
- Twilio

## Configuration Options

### AWS SNS

To use AWS SNS for SMS notifications, set the following environment variables:

```bash
# Enable AWS SNS
AWS_SNS_ENABLED=true

# AWS Region (optional, defaults to us-east-1)
AWS_REGION=us-east-1

# AWS credentials (if not using IAM roles)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Twilio

To use Twilio for SMS notifications, set the following environment variables:

```bash
# Twilio Account Credentials
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890  # Your Twilio phone number
```

## Priority

If both providers are configured, AWS SNS takes priority. The system will fall back to logging SMS messages if neither provider is configured (useful for development).

## Phone Number Format

Phone numbers should be stored in E.164 format (e.g., +1234567890). The system will attempt to format numbers automatically, defaulting to US country code (+1) if no country code is provided.

## Rate Limiting

SMS notifications are subject to rate limiting configured in the `SMSBackupConfig` class to prevent abuse and control costs.

## Testing

To test SMS configuration without sending actual messages, set:

```bash
SMS_TEST_MODE=true
```

This will log messages instead of sending them, regardless of provider configuration.