# FIDO2 Security Key Implementation

## Overview

The Haven Health Passport now supports FIDO2 security keys as a strong authentication method. This implementation provides support for hardware security keys like YubiKey, Google Titan Security Key, and other FIDO2-certified authenticators.

## Features

### 1. FIDO2 Key Registration
- Support for cross-platform authenticators (USB, NFC, Bluetooth)
- Direct attestation for enhanced security
- Automatic device name detection
- Multiple key registration support

### 2. FIDO2 Authentication
- User verification requirement
- Challenge-response authentication
- Usage tracking and analytics
- Last used timestamp tracking

### 3. Key Management
- List all registered FIDO2 keys
- Update key names and settings
- Revoke compromised keys
- Enforce minimum security requirements

## API Endpoints

### Registration Flow

1. **Begin Registration**
   ```
   POST /api/v2/auth/fido2/register/begin
   ```
   Request:
   ```json
   {
     "authenticator_type": "cross-platform",
     "device_name": "My YubiKey"
   }
   ```

2. **Complete Registration**
   ```
   POST /api/v2/auth/fido2/register/complete
   ```
   Request:
   ```json
   {
     "id": "credential-id",
     "rawId": "base64-raw-id",
     "type": "public-key",
     "response": {
       "clientDataJSON": "base64-client-data",
       "attestationObject": "base64-attestation"
     },
     "device_name": "My YubiKey"
   }
   ```

### Authentication Flow

1. **Begin Authentication**
   ```
   POST /api/v2/auth/fido2/authenticate/begin
   ```
   Request:
   ```json
   {
     "user_verification": "required"
   }
   ```

2. **Complete Authentication**
   ```
   POST /api/v2/auth/fido2/authenticate/complete
   ```
   Request:
   ```json
   {
     "id": "credential-id",
     "rawId": "base64-raw-id",
     "type": "public-key",
     "response": {
       "clientDataJSON": "base64-client-data",
       "authenticatorData": "base64-auth-data",
       "signature": "base64-signature"
     }
   }
   ```

### Key Management

- **List Keys**: `GET /api/v2/auth/fido2/keys`
- **Update Key**: `PUT /api/v2/auth/fido2/keys/{credential_id}`
- **Revoke Key**: `DELETE /api/v2/auth/fido2/keys/{credential_id}`
- **Supported Authenticators**: `GET /api/v2/auth/fido2/supported-authenticators`

## Configuration

### Environment Variables

```bash
# FIDO2 Key Requirements
FIDO2_MIN_CERTIFICATION_LEVEL=1        # Minimum FIDO certification level
FIDO2_REQUIRE_USER_VERIFICATION=true   # Require user verification
FIDO2_REQUIRE_RESIDENT_KEY=false       # Require resident key capability
FIDO2_ALLOWED_TRANSPORTS=usb,nfc,ble   # Allowed transport methods

# Attestation Settings
FIDO2_ATTESTATION=direct               # Attestation preference
FIDO2_ENTERPRISE_ATTESTATION=false     # Enterprise attestation support

# Metadata Service
FIDO2_USE_MDS=true                     # Use FIDO Metadata Service
FIDO2_MDS_ENDPOINT=https://mds.fidoalliance.org
FIDO2_MDS_ACCESS_TOKEN=your-token      # MDS access token

# Security Settings
FIDO2_REQUIRE_PIN=true                 # Require PIN
FIDO2_MIN_PIN_LENGTH=4                 # Minimum PIN length
FIDO2_MAX_KEY_AGE_DAYS=730            # Maximum key age (2 years)
```

## Security Considerations

### 1. Attestation Verification
- Direct attestation is required for FIDO2 keys
- Authenticator certificates are validated
- AAGUID verification against FIDO MDS

### 2. User Verification
- PIN or biometric verification required
- User presence always required
- Counter validation to prevent cloning

### 3. Transport Security
- TLS 1.3 for all communications
- Origin validation
- CSRF protection

## Supported Authenticators

### Recommended Devices

1. **YubiKey 5 Series**
   - FIDO2 L2 Certified
   - USB-A, USB-C, NFC, Lightning
   - FIPS 140-2 validated options

2. **Google Titan Security Key**
   - FIDO2 L1 Certified
   - USB-A, USB-C, NFC, Bluetooth
   - Built-in secure element

3. **SoloKeys Solo V2**
   - FIDO2 L1 Certified
   - Open source firmware
   - USB-A, USB-C, NFC

4. **Feitian ePass FIDO2**
   - FIDO2 L2 Certified
   - Multiple form factors
   - FIPS 140-2 Level 3

## Frontend Integration

### TypeScript Service

```typescript
import { fido2Service } from '@/services/fido2Service';

// Check support
if (fido2Service.isSupported()) {
  // Register new key
  await fido2Service.startRegistration('cross-platform', 'My YubiKey');

  // Authenticate with key
  await fido2Service.startAuthentication();

  // List registered keys
  const keys = await fido2Service.getRegisteredKeys();
}
```

### React Component Example

```tsx
import React, { useState } from 'react';
import { fido2Service } from '@/services/fido2Service';

export const Fido2Manager: React.FC = () => {
  const [keys, setKeys] = useState<Fido2KeyInfo[]>([]);

  const registerKey = async () => {
    try {
      await fido2Service.startRegistration();
      // Refresh keys list
      const updatedKeys = await fido2Service.getRegisteredKeys();
      setKeys(updatedKeys);
    } catch (error) {
      console.error('Registration failed:', error);
    }
  };

  return (
    <div>
      <h2>FIDO2 Security Keys</h2>
      <button onClick={registerKey}>Add Security Key</button>
      {/* Key list UI */}
    </div>
  );
};
```

## Testing

### Unit Tests
```bash
pytest tests/api/test_fido2_endpoints.py
```

### Integration Tests
```bash
pytest tests/integration/test_fido2_flow.py
```

### Manual Testing
1. Use Chrome/Edge with a physical FIDO2 key
2. Enable WebAuthn debugging in browser DevTools
3. Test registration and authentication flows
4. Verify key management operations

## Troubleshooting

### Common Issues

1. **"Authenticator not allowed"**
   - Check if authenticator meets minimum requirements
   - Verify AAGUID is not in banned list

2. **"User verification failed"**
   - Ensure PIN is set on the security key
   - Try using biometric if available

3. **"Transport not supported"**
   - Check browser compatibility
   - Ensure correct drivers installed for USB keys

### Debug Logging

Enable debug logging for FIDO2:
```python
import logging
logging.getLogger('src.services.webauthn_service').setLevel(logging.DEBUG)
```

## Compliance

- **FIDO2 Certified**: Implementation follows FIDO2 specifications
- **WebAuthn Compliant**: Full WebAuthn API compliance
- **HIPAA**: Meets HIPAA authentication requirements
- **NIST SP 800-63B**: AAL3 authentication assurance level

## Future Enhancements

1. **Passwordless Login**: Remove password requirement for FIDO2-only accounts
2. **Backup Authenticator**: Support for backup keys
3. **Enterprise Integration**: Support for enterprise attestation
4. **Mobile SDK**: Native mobile app FIDO2 support
