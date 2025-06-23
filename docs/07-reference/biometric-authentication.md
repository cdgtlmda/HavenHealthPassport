# Biometric Authentication Implementation Guide

## Overview

Haven Health Passport implements comprehensive biometric authentication supporting multiple modalities:
- Fingerprint recognition
- Face recognition
- Voice authentication
- Iris scanning
- Palm recognition
- WebAuthn/FIDO2 for web browsers

## Architecture

### Backend Components

1. **BiometricAuthManager** (`src/auth/biometric_auth.py`)
   - Handles enrollment, verification, and management of biometric templates
   - Implements liveness detection and anti-spoofing measures
   - Manages encrypted template storage

2. **WebAuthnManager** (`src/auth/biometric_auth.py`)
   - Manages WebAuthn/FIDO2 credentials
   - Supports platform authenticators (TouchID, FaceID, Windows Hello)
   - Handles passwordless authentication flow

3. **Database Models** (`src/models/auth.py`)
   - `BiometricTemplate`: Stores encrypted biometric templates
   - `BiometricAuditLog`: Tracks all biometric events
   - `WebAuthnCredential`: Stores WebAuthn credentials

4. **API Endpoints** (`src/api/biometric/endpoints.py`)
   - `/biometric/enroll`: Enroll new biometric
   - `/biometric/verify`: Verify against enrolled biometrics
   - `/biometric/authenticate`: Passwordless authentication
   - `/webauthn/*`: WebAuthn registration and authentication

### Frontend Components

1. **Mobile App** (`mobile/src/services/biometricAuth.ts`)
   - React Native implementation using Expo
   - Supports iOS TouchID/FaceID and Android biometrics
   - Secure storage of enrollment data

2. **Web Portal** (`web/src/services/webAuthnService.ts`)
   - WebAuthn implementation for browsers
   - Supports platform and cross-platform authenticators
   - Conditional UI for autofill

## Security Features

### Encryption
- All biometric templates are encrypted using AES-256
- Templates are never stored in plain text
- Encryption keys managed via AWS KMS (in production)

### Liveness Detection
- Prevents spoofing attacks using photos or recordings
- Checks for:
  - Fingerprint: Pulse, temperature, conductivity
  - Face: Eye movement, blinking, head rotation
  - Voice: Natural speech patterns, background noise

### Anti-Spoofing
- Material analysis for fingerprints
- Depth detection for face recognition
- Frequency analysis for voice authentication

### Privacy Protection
- Templates are anonymized and cannot be reverse-engineered
- Automatic template expiration after 365 days
- User can revoke biometric access at any time

## Implementation Steps

### 1. Database Migration
Run the migration to create biometric tables:
```bash
psql -U your_user -d haven_health_passport -f migrations/add_biometric_authentication_tables.sql
```

### 2. Backend Setup
Ensure all Python dependencies are installed:
```bash
pip install webauthn fido2 pywebauthn
```

### 3. Mobile App Setup
Install React Native dependencies:
```bash
cd mobile
npm install
# For iOS
cd ios && pod install
```

### 4. Web Portal Setup
Install WebAuthn dependencies:
```bash
cd web
npm install
```

## Usage Examples

### Mobile App - Enable Biometric
```typescript
import { biometricAuthService } from './services/biometricAuth';

// Check availability
const isAvailable = await biometricAuthService.isAvailable();

// Enable biometric
if (isAvailable) {
  const enrollment = await biometricAuthService.enableBiometric(userId);
  console.log('Enrolled:', enrollment.templateId);
}

// Authenticate
const result = await biometricAuthService.authenticate();
if (result.success) {
  console.log('Authenticated!', result.accessToken);
}
```

### Web Portal - WebAuthn Registration
```typescript
import { webAuthnService } from './services/webAuthnService';

// Check support
if (webAuthnService.isWebAuthnSupported()) {
  // Start registration
  const result = await webAuthnService.startRegistration('My Device');
  if (result.success) {
    console.log('Registered:', result.credentialId);
  }
}

// Authenticate
const authResult = await webAuthnService.startAuthentication(userId);
if (authResult.success) {
  console.log('Authenticated!', authResult.accessToken);
}
```

### Backend - API Usage
```python
from src.auth.biometric_auth import BiometricAuthManager, BiometricType

# Initialize manager
biometric_manager = BiometricAuthManager(db_session)

# Enroll biometric
success, template_id = biometric_manager.enroll_biometric(
    user=current_user,
    biometric_type=BiometricType.FINGERPRINT,
    biometric_data=request_data
)

# Verify biometric
success, matched_template = biometric_manager.verify_biometric(
    user=current_user,
    biometric_type=BiometricType.FINGERPRINT,
    biometric_data=request_data
)
```

## Testing

### Unit Tests
Run the biometric authentication tests:
```bash
pytest tests/auth/test_biometric_auth.py -v
```

### Integration Tests
```bash
pytest tests/api/biometric/test_integration.py -v
```

## Configuration

### Environment Variables
```env
# Biometric Configuration
BIOMETRIC_MIN_QUALITY_SCORE=0.7
BIOMETRIC_MATCH_THRESHOLD=0.95
BIOMETRIC_LOCKOUT_DURATION=300
WEBAUTHN_RP_NAME="Haven Health Passport"
WEBAUTHN_RP_ID="havenhealthpassport.org"
```

### Security Settings
Configure in `BiometricConfig`:
- `min_quality_score`: Minimum quality for enrollment (0.0-1.0)
- `match_threshold`: Minimum match score for verification
- `require_liveness`: Enable/disable liveness detection
- `anti_spoofing_enabled`: Enable/disable anti-spoofing

## Troubleshooting

### Common Issues

1. **"Biometric not available"**
   - Ensure device has biometric hardware
   - Check that user has enrolled biometrics in device settings

2. **"Quality too low"**
   - Clean sensor/camera
   - Ensure good lighting for face recognition
   - Re-enroll with better quality sample

3. **"Liveness check failed"**
   - Ensure real biometric is being used (not photo/recording)
   - Follow on-screen instructions for liveness gestures

4. **WebAuthn not supported**
   - Update browser to latest version
   - Ensure HTTPS is enabled
   - Check browser compatibility

## Compliance

The biometric authentication system complies with:
- HIPAA requirements for healthcare data
- GDPR Article 9 (processing of biometric data)
- ISO/IEC 19794 biometric data interchange formats
- FIDO Alliance specifications for WebAuthn

## Future Enhancements

1. **Multi-modal Authentication**
   - Combine multiple biometric types for higher security
   - Adaptive authentication based on risk level

2. **Behavioral Biometrics**
   - Typing patterns
   - Device usage patterns
   - Gait analysis (mobile)

3. **Advanced Anti-Spoofing**
   - 3D face mapping
   - Ultrasonic fingerprint detection
   - Voice replay attack detection

4. **Cross-Device Sync**
   - Secure biometric template synchronization
   - Multi-device enrollment management
