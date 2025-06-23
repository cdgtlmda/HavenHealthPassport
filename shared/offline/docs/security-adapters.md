# Platform-Specific Security Adapters

## Overview

The platform-specific security adapters provide encryption, decryption, hashing, and secure storage capabilities tailored for React Native and Web platforms. These adapters implement the `CryptoAdapter` interface and provide additional platform-specific security features.

## React Native Security Adapter

### Features

- **Biometric Authentication**: Uses device biometrics (Face ID, Touch ID, fingerprint) for enhanced security
- **Keychain Integration**: Stores encryption keys securely in iOS Keychain and Android Keystore
- **Hardware-backed Security**: Leverages platform-specific secure hardware when available
- **Secure Storage**: Uses expo-secure-store for storing sensitive data
- **Device Security Checks**: Detects rooted/jailbroken devices and screen lock status

### Usage

```typescript
import { ReactNativeSecurityAdapter } from '@haven/offline/adapters';

const security = new ReactNativeSecurityAdapter();
await security.initialize();

// Encrypt data
const encrypted = await security.encrypt('sensitive data');

// Decrypt data
const decrypted = await security.decrypt(encrypted);

// Enable biometric protection
const biometricsEnabled = await security.enableBiometricProtection();

// Check device security status
const status = await security.getDeviceSecurityStatus();
console.log('Security level:', status.securityLevel); // 'high', 'medium', or 'low'
```

### Security Levels

- **High**: Device has screen lock, biometrics enrolled, not rooted, and encryption enabled
- **Medium**: Device has screen lock and not rooted
- **Low**: Basic security only

## Web Security Adapter

### Features

- **Web Crypto API**: Uses browser's native cryptographic functions
- **WebAuthn Support**: Enables FIDO2/WebAuthn for passwordless authentication- **IndexedDB Encryption**: Secure storage using encrypted IndexedDB
- **Persistent Storage**: Requests persistent storage permission for reliability
- **HTTPS Enforcement**: Only works in secure contexts (HTTPS)

### Usage

```typescript
import { WebSecurityAdapter } from '@haven/offline/adapters';

const security = new WebSecurityAdapter();
await security.initialize();

// Encrypt data
const encrypted = await security.encrypt('sensitive data');

// Decrypt data
const decrypted = await security.decrypt(encrypted);

// Enable WebAuthn
const webAuthnEnabled = await security.enableWebAuthn();

// Request persistent storage
const isPersistent = await security.requestPersistentStorage();

// Check browser security status
const status = await security.getBrowserSecurityStatus();
console.log('Security level:', status.securityLevel);
```

### Browser Security Levels

- **High**: HTTPS, Web Crypto API, WebAuthn available, and persistent storage
- **Medium**: HTTPS and Web Crypto API available
- **Low**: Basic security only

## Implementation Details

### Encryption Algorithm

Both adapters use AES-256-GCM for encryption:
- **Key Size**: 256 bits
- **Mode**: Galois/Counter Mode (GCM) for authenticated encryption
- **IV**: Random 128-bit initialization vector for each encryption

### Key Management

- **React Native**: Keys stored in Keychain/Keystore with biometric protection
- **Web**: Keys stored in encrypted IndexedDB with optional WebAuthn protection

### Platform Detection

The adapters are automatically selected based on the runtime environment:

```typescript
import { getSecurityAdapter } from '@haven/offline/adapters';

const security = getSecurityAdapter(); // Returns appropriate adapter
```

## Security Best Practices

### For React Native

1. Always check device security status before storing sensitive data
2. Enable biometric protection for high-security operations
3. Handle biometric enrollment changes appropriately
4. Implement fallback mechanisms for devices without biometrics

### For Web

1. Always serve your application over HTTPS
2. Request persistent storage for critical data
3. Implement WebAuthn for passwordless authentication where possible
4. Handle browser compatibility gracefully

## Error Handling

Both adapters provide detailed error messages for common scenarios:

```typescript
try {
  const encrypted = await security.encrypt(data);
} catch (error) {
  if (error.message.includes('No encryption key')) {
    // Handle missing key
  } else if (error.message.includes('Encryption failed')) {
    // Handle encryption failure
  }
}
```

## Testing

The security adapters include comprehensive test suites. Run tests with:

```bash
npm test -- SecurityAdapters.test.ts
```

## Migration Guide

If migrating from basic encryption to platform-specific security:

1. Initialize the new security adapter
2. Decrypt existing data with old method
3. Re-encrypt with new security adapter
4. Update storage references

## Performance Considerations

- **React Native**: Biometric operations may add 100-500ms latency
- **Web**: WebAuthn operations may take 1-3 seconds
- Both adapters cache master keys to minimize repeated authentication

## Compliance

The security adapters are designed to meet:
- HIPAA encryption requirements
- GDPR data protection standards
- Healthcare industry security best practices