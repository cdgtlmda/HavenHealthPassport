# Security Considerations for Offline Functionality

## Overview

This document outlines security considerations, threats, and mitigation strategies for Haven Health Passport's offline functionality. Security in offline-first applications presents unique challenges that require careful planning and implementation.

## Table of Contents

1. [Threat Model](#threat-model)
2. [Data Security](#data-security)
3. [Authentication & Authorization](#authentication--authorization)
4. [Sync Security](#sync-security)
5. [Device Security](#device-security)
6. [Network Security](#network-security)
7. [Compliance](#compliance)
8. [Security Best Practices](#security-best-practices)

## Threat Model

### Identified Threats

1. **Device Theft/Loss**
   - Risk: Unauthorized access to health records
   - Impact: High - HIPAA violation, privacy breach
   - Likelihood: Medium

2. **Man-in-the-Middle Attacks**
   - Risk: Interception of sync data
   - Impact: High - Data breach
   - Likelihood: Low (with proper TLS)

3. **Local Storage Tampering**
   - Risk: Modified health records
   - Impact: Critical - Medical safety
   - Likelihood: Low (with encryption)

4. **Replay Attacks**
   - Risk: Duplicate sync operations
   - Impact: Medium - Data corruption
   - Likelihood: Low (with proper tokens)

5. **Offline Token Abuse**
   - Risk: Extended unauthorized access
   - Impact: High - Prolonged breach
   - Likelihood: Medium

## Data Security

### Encryption at Rest

#### Mobile Implementation
```typescript
import CryptoJS from 'crypto-js';
import * as Keychain from 'react-native-keychain';

class EncryptionService {
  private masterKey: string;
  
  async initialize() {
    // Generate or retrieve master key
    const credentials = await Keychain.getInternetCredentials('haven-health');
    
    if (!credentials) {
      // Generate new master key
      this.masterKey = this.generateMasterKey();
      await Keychain.setInternetCredentials(
        'haven-health',
        'masterKey',
        this.masterKey
      );
    } else {
      this.masterKey = credentials.password;
    }
  }
  
  encryptField(data: string, fieldKey: string): string {
    const key = this.deriveFieldKey(fieldKey);
    return CryptoJS.AES.encrypt(data, key).toString();
  }
  
  decryptField(encryptedData: string, fieldKey: string): string {
    const key = this.deriveFieldKey(fieldKey);
    const bytes = CryptoJS.AES.decrypt(encryptedData, key);
    return bytes.toString(CryptoJS.enc.Utf8);
  }
  
  private deriveFieldKey(fieldKey: string): string {
    return CryptoJS.PBKDF2(
      fieldKey,
      this.masterKey,
      { keySize: 256/32, iterations: 1000 }
    ).toString();
  }
}
```

#### Web Implementation
```typescript
class WebEncryptionService {
  private key: CryptoKey;
  
  async initialize() {
    // Use Web Crypto API
    this.key = await this.getOrCreateKey();
  }
  
  private async getOrCreateKey(): Promise<CryptoKey> {
    const keyData = localStorage.getItem('encryptionKey');
    
    if (keyData) {
      const jwk = JSON.parse(keyData);
      return crypto.subtle.importKey(
        'jwk',
        jwk,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
      );
    }
    
    // Generate new key
    const key = await crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt']
    );
    
    const exported = await crypto.subtle.exportKey('jwk', key);
    localStorage.setItem('encryptionKey', JSON.stringify(exported));
    
    return key;
  }
  
  async encryptData(data: string): Promise<ArrayBuffer> {
    const encoder = new TextEncoder();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    
    const encrypted = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      this.key,
      encoder.encode(data)
    );
    
    // Prepend IV to encrypted data
    const combined = new Uint8Array(iv.length + encrypted.byteLength);
    combined.set(iv);
    combined.set(new Uint8Array(encrypted), iv.length);
    
    return combined.buffer;
  }
}
```

### Field-Level Encryption

```typescript
// Define sensitive fields
const SENSITIVE_FIELDS = {
  patients: ['ssn', 'passport_number', 'national_id'],
  medical_records: ['diagnosis', 'medications', 'allergies'],
  documents: ['content', 'metadata']
};

// Encrypt sensitive fields before storage
function encryptSensitiveFields(collection: string, record: any): any {
  const encrypted = { ...record };
  const sensitiveFields = SENSITIVE_FIELDS[collection] || [];
  
  sensitiveFields.forEach(field => {
    if (encrypted[field]) {
      encrypted[field] = encryptionService.encryptField(
        encrypted[field],
        `${collection}.${field}`
      );
      encrypted[`${field}_encrypted`] = true;
    }
  });
  
  return encrypted;
}
```

### Database Security

#### WatermelonDB Security
```typescript
// Configure SQLCipher for encrypted database
const adapter = new SQLiteAdapter({
  schema,
  migrations,
  jsi: true,
  onSetUpError: error => {
    console.error('Database setup error:', error);
  }
});

// Additional security for database
if (Platform.OS === 'ios') {
  // iOS: Use Data Protection
  await adapter.setDatabaseEncryption({
    key: await getEncryptionKey(),
    algorithm: 'aes-256-cbc'
  });
} else if (Platform.OS === 'android') {
  // Android: Use SQLCipher
  await adapter.enableSQLCipher(await getEncryptionKey());
}
```

#### IndexedDB Security
```typescript
// Encrypt all data before storing in IndexedDB
class SecureIndexedDB {
  async put(storeName: string, data: any) {
    const encrypted = await this.encrypt(data);
    const tx = this.db.transaction(storeName, 'readwrite');
    await tx.objectStore(storeName).put({
      id: data.id,
      encrypted: encrypted,
      checksum: this.calculateChecksum(encrypted)
    });
  }
  
  async get(storeName: string, id: string) {
    const tx = this.db.transaction(storeName, 'readonly');
    const record = await tx.objectStore(storeName).get(id);
    
    if (!record) return null;
    
    // Verify checksum
    if (this.calculateChecksum(record.encrypted) !== record.checksum) {
      throw new Error('Data integrity check failed');
    }
    
    return this.decrypt(record.encrypted);
  }
}
```

## Authentication & Authorization

### Offline Authentication

```typescript
class OfflineAuthService {
  private readonly MAX_OFFLINE_DAYS = 30;
  
  async authenticateOffline(credentials: Credentials): Promise<AuthResult> {
    // Check cached credentials
    const cachedAuth = await this.getCachedAuth(credentials.username);
    
    if (!cachedAuth) {
      throw new Error('No offline credentials available');
    }
    
    // Verify password hash
    const passwordValid = await this.verifyPassword(
      credentials.password,
      cachedAuth.passwordHash
    );
    
    if (!passwordValid) {
      await this.recordFailedAttempt(credentials.username);
      throw new Error('Invalid credentials');
    }
    
    // Check offline token validity
    if (this.isOfflineTokenExpired(cachedAuth.offlineToken)) {
      throw new Error('Offline access expired');
    }
    
    // Generate session
    return this.createOfflineSession(cachedAuth);
  }
  
  private async verifyPassword(password: string, hash: string): Promise<boolean> {
    // Use Argon2 or similar
    return argon2.verify(hash, password);
  }
  
  private isOfflineTokenExpired(token: OfflineToken): boolean {
    const daysOffline = (Date.now() - token.lastOnlineAuth) / (1000 * 60 * 60 * 24);
    return daysOffline > this.MAX_OFFLINE_DAYS;
  }
}
```

### Biometric Authentication

```typescript
import TouchID from 'react-native-touch-id';
import * as LocalAuthentication from 'expo-local-authentication';

class BiometricAuth {
  async authenticate(): Promise<boolean> {
    try {
      // Check availability
      const isAvailable = await this.checkAvailability();
      if (!isAvailable) {
        return false;
      }
      
      // Prompt for biometric
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Authenticate to access health records',
        fallbackLabel: 'Use passcode',
        disableDeviceFallback: false
      });
      
      return result.success;
    } catch (error) {
      console.error('Biometric auth error:', error);
      return false;
    }
  }
  
  private async checkAvailability(): Promise<boolean> {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    const isEnrolled = await LocalAuthentication.isEnrolledAsync();
    return hasHardware && isEnrolled;
  }
}
```

### Role-Based Access Control

```typescript
class OfflineRBAC {
  private permissions: Map<string, Set<string>>;
  
  async checkPermission(
    user: User,
    resource: string,
    action: string
  ): Promise<boolean> {
    // Load cached permissions
    const userPermissions = await this.loadUserPermissions(user.id);
    
    // Check direct permissions
    if (userPermissions.has(`${resource}:${action}`)) {
      return true;
    }
    
    // Check role-based permissions
    for (const role of user.roles) {
      const rolePermissions = await this.loadRolePermissions(role);
      if (rolePermissions.has(`${resource}:${action}`)) {
        return true;
      }
    }
    
    return false;
  }
  
  async enforcePermission(
    user: User,
    resource: string,
    action: string
  ): Promise<void> {
    const hasPermission = await this.checkPermission(user, resource, action);
    if (!hasPermission) {
      throw new UnauthorizedError(
        `User ${user.id} lacks permission ${action} on ${resource}`
      );
    }
  }
}
```

## Sync Security

### Secure Sync Protocol

```typescript
class SecureSyncProtocol {
  private readonly SYNC_TOKEN_EXPIRY = 3600000; // 1 hour
  
  async initializeSync(): Promise<SyncSession> {
    // Generate sync session
    const session = {
      id: generateSecureId(),
      deviceId: await this.getDeviceId(),
      timestamp: Date.now(),
      nonce: generateNonce()
    };
    
    // Sign session
    const signature = await this.signSession(session);
    
    // Exchange keys
    const keys = await this.performKeyExchange();
    
    return {
      ...session,
      signature,
      encryptionKey: keys.shared,
      expires: Date.now() + this.SYNC_TOKEN_EXPIRY
    };
  }
  
  async encryptSyncData(data: any, session: SyncSession): Promise<string> {
    // Add anti-replay nonce
    const payload = {
      data,
      nonce: generateNonce(),
      timestamp: Date.now(),
      sessionId: session.id
    };
    
    // Encrypt with session key
    return this.encrypt(JSON.stringify(payload), session.encryptionKey);
  }
  
  private async performKeyExchange(): Promise<KeyPair> {
    // ECDH key exchange
    const keyPair = await crypto.subtle.generateKey(
      { name: 'ECDH', namedCurve: 'P-256' },
      true,
      ['deriveKey']
    );
    
    // Exchange public keys with server
    const serverPublicKey = await this.exchangePublicKeys(keyPair.publicKey);
    
    // Derive shared secret
    const sharedSecret = await crypto.subtle.deriveKey(
      {
        name: 'ECDH',
        public: serverPublicKey
      },
      keyPair.privateKey,
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt']
    );
    
    return { shared: sharedSecret };
  }
}
```

### Conflict Resolution Security

```typescript
class SecureConflictResolver {
  async resolveConflict(conflict: Conflict): Promise<Resolution> {
    // Verify both versions are authentic
    await this.verifyAuthenticity(conflict.local);
    await this.verifyAuthenticity(conflict.server);
    
    // Check for tampering
    if (this.detectTampering(conflict)) {
      await this.reportSecurityIncident({
        type: 'CONFLICT_TAMPERING',
        conflict,
        timestamp: Date.now()
      });
      throw new SecurityError('Conflict data tampering detected');
    }
    
    // Apply resolution with audit trail
    const resolution = await this.applyResolution(conflict);
    await this.auditConflictResolution(conflict, resolution);
    
    return resolution;
  }
  
  private detectTampering(conflict: Conflict): boolean {
    // Check vector clocks for anomalies
    const clockAnomalies = this.detectClockAnomalies(
      conflict.local.vectorClock,
      conflict.server.vectorClock
    );
    
    // Verify checksums
    const localValid = this.verifyChecksum(conflict.local);
    const serverValid = this.verifyChecksum(conflict.server);
    
    return clockAnomalies || !localValid || !serverValid;
  }
}
```

## Device Security

### Device Trust Management

```typescript
class DeviceTrustManager {
  private readonly MAX_DEVICES = 5;
  
  async registerDevice(device: DeviceInfo): Promise<DeviceRegistration> {
    // Check device limit
    const existingDevices = await this.getUserDevices();
    if (existingDevices.length >= this.MAX_DEVICES) {
      throw new Error('Maximum device limit reached');
    }
    
    // Verify device integrity
    const integrity = await this.verifyDeviceIntegrity(device);
    if (!integrity.valid) {
      throw new SecurityError('Device integrity check failed');
    }
    
    // Generate device certificate
    const certificate = await this.generateDeviceCertificate(device);
    
    // Store device registration
    return {
      deviceId: device.id,
      certificate,
      publicKey: device.publicKey,
      registeredAt: Date.now(),
      trustLevel: integrity.trustLevel
    };
  }
  
  private async verifyDeviceIntegrity(device: DeviceInfo): Promise<IntegrityResult> {
    const checks = {
      jailbroken: await this.checkJailbreak(),
      debuggerAttached: await this.checkDebugger(),
      tampered: await this.checkAppTampering()
    };
    
    const trustLevel = this.calculateTrustLevel(checks);
    
    return {
      valid: trustLevel > 0,
      trustLevel,
      checks
    };
  }
}
```

### Secure Storage

```typescript
// iOS Keychain Integration
class IOSSecureStorage {
  async store(key: string, value: string, options?: KeychainOptions) {
    await Keychain.setInternetCredentials(
      'haven-health-passport',
      key,
      value,
      {
        accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        ...options
      }
    );
  }
  
  async retrieve(key: string): Promise<string | null> {
    try {
      const credentials = await Keychain.getInternetCredentials(
        'haven-health-passport'
      );
      return credentials[key] || null;
    } catch {
      return null;
    }
  }
}

// Android Keystore Integration
class AndroidSecureStorage {
  async store(key: string, value: string) {
    // Use Android Keystore
    const encryptedValue = await this.encryptWithKeystore(value);
    await AsyncStorage.setItem(`secure_${key}`, encryptedValue);
  }
  
  private async encryptWithKeystore(data: string): Promise<string> {
    // Use Android Keystore for encryption
    const cipher = await AndroidKeystore.getCipher('AES/GCM/NoPadding');
    return cipher.encrypt(data);
  }
}
```

## Network Security

### Certificate Pinning

```typescript
// React Native Certificate Pinning
import { NetworkingModule } from 'react-native';

class CertificatePinning {
  private readonly pins = {
    'api.havenhealthpassport.org': [
      'sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
      'sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB='
    ]
  };
  
  async configurePinning() {
    if (Platform.OS === 'ios') {
      await NetworkingModule.addCertificatePinner({
        hosts: Object.keys(this.pins),
        pins: this.pins
      });
    } else if (Platform.OS === 'android') {
      // Android implementation
      await this.configureAndroidPinning();
    }
  }
  
  private async configureAndroidPinning() {
    // OkHttp certificate pinning configuration
    const config = {
      certificatePinner: {
        pins: this.pins
      }
    };
    await NetworkingModule.setNetworkConfig(config);
  }
}
```

### Request Signing

```typescript
class RequestSigner {
  async signRequest(request: Request): Promise<SignedRequest> {
    // Create canonical request
    const canonical = this.createCanonicalRequest(request);
    
    // Generate signature
    const signature = await this.generateSignature(canonical);
    
    // Add security headers
    return {
      ...request,
      headers: {
        ...request.headers,
        'X-Request-Signature': signature,
        'X-Request-Timestamp': Date.now().toString(),
        'X-Request-Nonce': generateNonce(),
        'X-Device-Id': await this.getDeviceId()
      }
    };
  }
  
  private createCanonicalRequest(request: Request): string {
    const parts = [
      request.method,
      request.url,
      this.canonicalizeHeaders(request.headers),
      this.hashPayload(request.body)
    ];
    
    return parts.join('\n');
  }
  
  private async generateSignature(data: string): Promise<string> {
    const key = await this.getSigningKey();
    const signature = await crypto.subtle.sign(
      'HMAC',
      key,
      new TextEncoder().encode(data)
    );
    
    return btoa(String.fromCharCode(...new Uint8Array(signature)));
  }
}
```

## Compliance

### HIPAA Compliance

```typescript
class HIPAACompliance {
  // Audit logging for all PHI access
  async logPHIAccess(event: PHIAccessEvent) {
    const auditEntry = {
      timestamp: Date.now(),
      userId: event.userId,
      patientId: event.patientId,
      action: event.action,
      resource: event.resource,
      deviceId: event.deviceId,
      location: await this.getDeviceLocation(),
      outcome: event.outcome
    };
    
    // Store in tamper-proof audit log
    await this.auditLog.append(auditEntry);
  }
  
  // Automatic logoff for HIPAA compliance
  setupAutoLogoff() {
    let lastActivity = Date.now();
    const TIMEOUT = 15 * 60 * 1000; // 15 minutes
    
    const checkInactivity = () => {
      if (Date.now() - lastActivity > TIMEOUT) {
        this.performSecureLogoff();
      }
    };
    
    // Monitor user activity
    ['touch', 'keypress', 'scroll'].forEach(event => {
      document.addEventListener(event, () => {
        lastActivity = Date.now();
      });
    });
    
    setInterval(checkInactivity, 60000); // Check every minute
  }
}
```

### GDPR Compliance

```typescript
class GDPRCompliance {
  // Right to erasure
  async deleteUserData(userId: string): Promise<void> {
    // Delete from local storage
    await this.deleteLocalData(userId);
    
    // Queue deletion request for sync
    await this.queueDeletionRequest(userId);
    
    // Ensure cryptographic erasure
    await this.cryptographicErasure(userId);
  }
  
  private async cryptographicErasure(userId: string) {
    // Delete encryption keys for user data
    await this.keyManager.deleteUserKeys(userId);
    
    // Overwrite key storage locations
    await this.secureOverwrite(userId);
  }
  
  // Data portability
  async exportUserData(userId: string): Promise<ExportedData> {
    const data = await this.collectUserData(userId);
    
    // Encrypt export with user-provided password
    const password = await this.promptExportPassword();
    const encrypted = await this.encryptExport(data, password);
    
    return {
      format: 'FHIR',
      encrypted: true,
      data: encrypted,
      checksum: this.calculateChecksum(encrypted)
    };
  }
}
```

## Security Best Practices

### Code Security

```typescript
// 1. Input Validation
class InputValidator {
  validatePatientData(data: any): PatientData {
    const schema = Joi.object({
      name: Joi.string().max(100).required(),
      dateOfBirth: Joi.date().max('now').required(),
      nationalId: Joi.string().pattern(/^[A-Z0-9]+$/).optional()
    });
    
    const { error, value } = schema.validate(data);
    if (error) {
      throw new ValidationError(error.details);
    }
    
    // Sanitize input
    return this.sanitize(value);
  }
  
  private sanitize(data: any): any {
    // Remove potential XSS
    return Object.keys(data).reduce((acc, key) => {
      if (typeof data[key] === 'string') {
        acc[key] = DOMPurify.sanitize(data[key]);
      } else {
        acc[key] = data[key];
      }
      return acc;
    }, {});
  }
}

// 2. Secure Random Generation
function generateSecureId(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

// 3. Constant-Time Comparison
function secureCompare(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  
  return result === 0;
}
```

### Security Monitoring

```typescript
class SecurityMonitor {
  private readonly ANOMALY_THRESHOLD = 5;
  
  async detectAnomalies(user: User) {
    const anomalies = [];
    
    // Check access patterns
    const accessPattern = await this.analyzeAccessPattern(user);
    if (accessPattern.anomalyScore > this.ANOMALY_THRESHOLD) {
      anomalies.push({
        type: 'ACCESS_PATTERN',
        score: accessPattern.anomalyScore,
        details: accessPattern.details
      });
    }
    
    // Check data volume
    const dataVolume = await this.analyzeDataVolume(user);
    if (dataVolume.anomalyScore > this.ANOMALY_THRESHOLD) {
      anomalies.push({
        type: 'DATA_VOLUME',
        score: dataVolume.anomalyScore,
        details: dataVolume.details
      });
    }
    
    // Report anomalies
    if (anomalies.length > 0) {
      await this.reportAnomalies(user, anomalies);
    }
  }
}
```

## Security Checklist

### Development
- [ ] All sensitive data encrypted at rest
- [ ] Field-level encryption for PII/PHI
- [ ] Certificate pinning implemented
- [ ] Request signing enabled
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention
- [ ] XSS protection enabled

### Authentication
- [ ] Biometric authentication available
- [ ] Offline token expiration implemented
- [ ] Device registration limits enforced
- [ ] Failed login attempt monitoring
- [ ] Session timeout configured
- [ ] Multi-factor authentication support

### Data Protection
- [ ] Encryption keys properly managed
- [ ] Key rotation implemented
- [ ] Secure key storage (Keychain/Keystore)
- [ ] Data minimization practiced
- [ ] Secure data deletion implemented
- [ ] Backup encryption enabled

### Compliance
- [ ] HIPAA audit logging active
- [ ] GDPR data portability ready
- [ ] Right to erasure implemented
- [ ] Consent management in place
- [ ] Data retention policies enforced
- [ ] Privacy policy updated

### Monitoring
- [ ] Security event logging enabled
- [ ] Anomaly detection active
- [ ] Incident response plan ready
- [ ] Regular security audits scheduled
- [ ] Penetration testing completed
- [ ] Vulnerability scanning automated

## Incident Response

### Security Incident Procedures

1. **Detection**
   - Automated anomaly detection
   - User reports
   - System monitoring alerts

2. **Containment**
   - Isolate affected devices
   - Revoke compromised tokens
   - Disable affected accounts

3. **Investigation**
   - Analyze audit logs
   - Identify breach scope
   - Determine root cause

4. **Recovery**
   - Reset affected credentials
   - Re-encrypt compromised data
   - Update security measures

5. **Post-Incident**
   - Document lessons learned
   - Update security procedures
   - Notify affected users
   - Report to authorities if required

## Conclusion

Security in offline-first healthcare applications requires a multi-layered approach. By implementing these security measures, Haven Health Passport ensures the confidentiality, integrity, and availability of sensitive health data while maintaining usability in offline scenarios. Regular security audits and updates are essential to maintain this security posture.