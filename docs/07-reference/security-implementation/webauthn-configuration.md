# WebAuthn Configuration Guide

## Overview

Haven Health Passport implements WebAuthn/FIDO2 authentication for secure, passwordless login using biometric authenticators and security keys. This guide covers the configuration and deployment of WebAuthn support.

## Architecture

### Components

1. **WebAuthn Settings** (`src/config/webauthn_settings.py`)
   - Environment-based configuration management
   - Dynamic origin validation
   - Algorithm preference handling

2. **WebAuthn Service** (`src/services/webauthn_service.py`)
   - FIDO2 cryptographic operations
   - Credential registration and verification
   - Challenge management

3. **WebAuthn Middleware** (`src/middleware/webauthn_middleware.py`)
   - Origin validation
   - Security headers
   - Challenge verification

## Configuration

### Environment Variables

```bash
# Basic Settings
WEBAUTHN_RP_NAME="Haven Health Passport"
WEBAUTHN_RP_ID="havenhealthpassport.org"

# Allowed Origins (comma-separated)
WEBAUTHN_RP_ORIGINS="https://havenhealthpassport.org,https://app.havenhealthpassport.org"

# Authentication Requirements
WEBAUTHN_USER_VERIFICATION="required"  # required, preferred, discouraged
WEBAUTHN_AUTHENTICATOR_ATTACHMENT="platform"  # platform, cross-platform, or empty
WEBAUTHN_RESIDENT_KEY="preferred"  # required, preferred, discouraged

# Attestation Settings
WEBAUTHN_ATTESTATION="direct"  # none, indirect, direct, enterprise

# Timeouts (milliseconds)
WEBAUTHN_REGISTRATION_TIMEOUT_MS="60000"
WEBAUTHN_AUTHENTICATION_TIMEOUT_MS="60000"

# Security Settings
WEBAUTHN_REQUIRE_BACKUP_ELIGIBLE="false"
WEBAUTHN_REQUIRE_BACKUP_STATE="false"

# Supported Algorithms (COSE identifiers)
WEBAUTHN_ALGORITHMS="-7,-257,-8"  # ES256, RS256, EdDSA

# Challenge Settings
WEBAUTHN_CHALLENGE_SIZE="32"
WEBAUTHN_CHALLENGE_TIMEOUT="300"
```

### Development Configuration

For local development, use these settings:

```bash
WEBAUTHN_RP_ID="localhost"
WEBAUTHN_RP_ORIGINS="http://localhost:3000,http://localhost:8000"
ENVIRONMENT="development"
```

### Production Configuration

For production deployment:

```bash
WEBAUTHN_RP_ID="havenhealthpassport.org"
WEBAUTHN_RP_ORIGINS="https://havenhealthpassport.org,https://app.havenhealthpassport.org"
WEBAUTHN_USER_VERIFICATION="required"
WEBAUTHN_ATTESTATION="direct"
ENVIRONMENT="production"
```

## Security Considerations

### Origin Validation

The WebAuthn middleware validates all requests against allowed origins:

1. Explicit origin list from `WEBAUTHN_RP_ORIGINS`
2. Automatic subdomain matching for RP ID
3. Strict protocol validation (HTTPS required in production)

### Challenge Management

- Challenges are stored in Redis with automatic expiration
- Each challenge is single-use and deleted after verification
- Challenge size is configurable (default: 32 bytes)

### Authenticator Requirements

Configure authenticator requirements based on security needs:

- **Platform Authenticators**: Built-in biometric sensors (TouchID, Windows Hello)
- **Cross-Platform Authenticators**: External security keys (YubiKey, Titan)
- **Backup Requirements**: Enforce authenticators with backup capability

## Implementation Examples

### Frontend Registration

```javascript
// Using the webAuthnService
import { webAuthnService } from './services/webAuthnService';

async function registerWebAuthn() {
  if (!webAuthnService.isWebAuthnSupported()) {
    alert('WebAuthn is not supported on this device');
    return;
  }

  try {
    const result = await webAuthnService.startRegistration('My Laptop');
    if (result.success) {
      console.log('Registered credential:', result.credentialId);
    } else {
      console.error('Registration failed:', result.error);
    }
  } catch (error) {
    console.error('Registration error:', error);
  }
}
```

### Frontend Authentication

```javascript
async function authenticateWebAuthn() {
  try {
    const result = await webAuthnService.startAuthentication(userId);
    if (result.success) {
      // Store tokens
      localStorage.setItem('access_token', result.accessToken);
      // Redirect to dashboard
      window.location.href = '/dashboard';
    } else {
      console.error('Authentication failed:', result.error);
    }
  } catch (error) {
    console.error('Authentication error:', error);
  }
}
```

### Backend Integration

```python
from src.services.webauthn_service import WebAuthnService

# In your endpoint
webauthn_service = WebAuthnService(db_session)

# Create registration options
options = await webauthn_service.create_registration_options(user)

# Verify registration
success, credential_id = await webauthn_service.verify_registration(
    user, credential_data, device_name
)
```

## Deployment Checklist

- [ ] Set appropriate RP ID for your domain
- [ ] Configure allowed origins for all frontend URLs
- [ ] Enable HTTPS for production
- [ ] Configure Redis for challenge storage
- [ ] Set appropriate timeouts for user experience
- [ ] Test with various authenticator types
- [ ] Enable monitoring for failed authentications
- [ ] Configure backup authentication methods

## Browser Support

WebAuthn is supported in:
- Chrome/Edge 67+
- Firefox 60+
- Safari 14+
- Opera 54+

Mobile support:
- iOS 14.5+ (Safari)
- Android 7.0+ (Chrome)

## Troubleshooting

### Common Issues

1. **"Origin not allowed"**
   - Add origin to `WEBAUTHN_RP_ORIGINS`
   - Ensure HTTPS in production
   - Check for trailing slashes

2. **"Challenge verification failed"**
   - Check Redis connectivity
   - Verify challenge timeout settings
   - Ensure time sync between servers

3. **"Authenticator not supported"**
   - Update browser to latest version
   - Check authenticator requirements
   - Try different authenticator type

4. **"Registration timeout"**
   - Increase `WEBAUTHN_REGISTRATION_TIMEOUT_MS`
   - Check user verification requirements
   - Ensure authenticator is properly connected

## Testing

Run WebAuthn configuration tests:

```bash
pytest tests/config/test_webauthn_config.py -v
```

Test with real authenticators:
1. Use Chrome DevTools WebAuthn tab
2. Test with USB security keys
3. Test with platform authenticators
4. Verify cross-browser compatibility

## Monitoring

Monitor WebAuthn usage with these metrics:
- Registration success/failure rates
- Authentication success/failure rates
- Average registration/authentication time
- Authenticator type distribution
- Failed origin attempts

## Compliance

WebAuthn implementation complies with:
- FIDO2 specifications
- W3C WebAuthn standard
- NIST SP 800-63B authentication guidelines
- GDPR requirements for biometric data
