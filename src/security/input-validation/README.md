# Input Validation Security Module

## Overview

The Haven Health Passport Input Validation module provides comprehensive security for all user inputs, protecting against injection attacks, data corruption, and abuse. This module implements defense-in-depth strategies with multiple layers of validation and sanitization.

## Features

### 1. Input Sanitization
- **HTML/Script Sanitization**: Removes dangerous HTML and JavaScript
- **SQL Injection Prevention**: Escapes SQL metacharacters
- **NoSQL Injection Prevention**: Filters MongoDB operators
- **Command Injection Prevention**: Removes shell metacharacters
- **Path Traversal Prevention**: Blocks directory traversal attempts
- **Healthcare-Specific Sanitization**: MRN, FHIR ID sanitization

### 2. Allowlist Validation
- **Medical Code Validation**: ICD-10, CPT, LOINC, RxNorm, SNOMED
- **File Type Validation**: Extension and MIME type checking
- **Domain Validation**: Trusted external resources
- **Enum Validation**: Predefined value lists (blood types, genders, etc.)
- **Dynamic Allowlists**: Runtime-configurable allowed values

### 3. Regex Pattern Validation
- **Healthcare Patterns**: NPI, DEA, MRN, insurance numbers
- **Personal Information**: Email, phone, SSN, addresses
- **Security Patterns**: Passwords, API keys, tokens
- **Financial Patterns**: Credit cards, bank accounts
- **Custom Pattern Builder**: Create patterns dynamically

### 4. Length Validation
- **Field-Specific Limits**: Predefined limits for all field types
- **Byte-Length Validation**: UTF-8 aware length checking
- **Dynamic Truncation**: Safe string truncation
- **Array/Object Size**: Collection size validation

### 5. Type Checking
- **Runtime Type Validation**: 50+ supported types
- **Type Coercion**: Safe type conversion
- **Complex Type Support**: UUID, credit card, coordinates
- **Nullable Handling**: Optional field support
- **Custom Validators**: Extensible type system

### 6. Encoding Validation
- **Encoding Detection**: Automatic charset detection
- **Character Validation**: Unicode normalization
- **Homoglyph Detection**: Detects lookalike characters
- **Zero-Width Character Removal**: Security against hidden characters
- **Line Ending Normalization**: Cross-platform compatibility

### 7. File Upload Security
- **Magic Number Validation**: True file type detection
- **Virus Scanning**: ClamAV integration
- **Image Processing**: Metadata stripping, resizing
- **Quarantine System**: Infected file isolation
- **Size Limits**: Configurable per file type

### 8. API Validation
- **Schema Validation**: Joi-based request/response validation
- **Healthcare Schemas**: Pre-built patient, prescription, lab schemas
- **Request Sanitization**: Automatic input cleaning
- **Response Validation**: Output verification
- **Depth Limiting**: Prevent deeply nested objects

### 9. Rate Limiting
- **Multiple Strategies**: Fixed window, sliding window, token bucket
- **Distributed Support**: Redis-backed for multiple servers
- **Flexible Configuration**: Per-endpoint limits
- **Healthcare Presets**: Optimized for medical APIs

### 10. Request Throttling
- **Queue Management**: Prevents server overload
- **Circuit Breaker**: Automatic failure recovery
- **Backpressure Handling**: System load management
- **Adaptive Throttling**: Dynamic concurrency adjustment

### 11. Abuse Detection
- **Behavioral Analysis**: Pattern-based threat detection
- **Geographic Blocking**: Country-based restrictions
- **Device Fingerprinting**: Track suspicious devices
- **Honeypot System**: Trap malicious actors
- **Automated Blocking**: Progressive response to threats

## Quick Start

### Basic Setup

```typescript
import {
  sanitizeRequest,
  APIValidator,
  createRateLimiter,
  createAbuseDetector,
  HealthcareSchemas
} from '@haven/security/input-validation';

// Apply to Express app
app.use(sanitizeRequest());
app.use(createRateLimiter({ windowMs: 60000, max: 100 }).middleware());
app.use(createAbuseDetector().middleware());

// Validate specific endpoints
app.post('/api/patients',
  APIValidator.validate({
    body: HealthcareSchemas.patient
  }),
  createPatientHandler
);
```

### Healthcare Example

```typescript
import { HealthcareValidators, sanitizeMRN } from '@haven/security/input-validation';

// Validate patient registration
async function registerPatient(data: any) {
  // Sanitize MRN
  const mrn = sanitizeMRN(data.mrn);

  // Validate complete patient data
  const validation = HealthcareValidators.validatePatient(data);
  if (!validation.valid) {
    throw new ValidationError(validation.errors);
  }

  // Process validated data
  return createPatient(validation.data);
}
```

### File Upload Example

```typescript
import { createFileUploadSecurity, DefaultFileUploadConfigs } from '@haven/security/input-validation';

const uploadSecurity = createFileUploadSecurity(DefaultFileUploadConfigs.medicalImages);

app.post('/api/upload', async (req, res) => {
  const validation = await uploadSecurity.validateFile(
    req.file.path,
    req.file.originalname,
    req.file.size
  );

  if (!validation.valid) {
    return res.status(400).json({ errors: validation.errors });
  }

  // Process validated file
  const result = await uploadSecurity.processFile(
    req.file.path,
    req.file.originalname
  );
});
```

## Configuration

### Rate Limiting

```typescript
const rateLimiter = createRateLimiter({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP',
  standardHeaders: true, // Return rate limit info in headers
  legacyHeaders: false,
  store: new RedisStore(redis), // Use Redis for distributed apps
  skip: (req) => req.user?.role === 'admin' // Skip for admins
});
```

### Abuse Detection

```typescript
const abuseDetector = createAbuseDetector({
  maxFailedLogins: 5,
  maxFailedLoginWindow: 15 * 60 * 1000,
  blockedCountries: ['XX', 'YY'],
  enableFingerprinting: true,
  onAbuse: (type, details) => {
    logger.warn('Abuse detected', { type, details });
    // Send alert to security team
  }
});
```

### Custom Validation

```typescript
// Add custom medical code format
PatternManager.addPattern('custom-code', /^HC\d{6}$/);

// Add custom allowlist
DynamicAllowlistManager.addCustomAllowlist('departments', [
  'cardiology',
  'neurology',
  'pediatrics'
]);

// Create custom schema
const customSchema = new SchemaBuilder()
  .requiredString('patientId', { pattern: /^P\d{8}$/ })
  .requiredArray('conditions', Joi.string(), { min: 1, max: 10 })
  .enum('priority', ['low', 'medium', 'high', 'critical'])
  .build();
```

## Security Best Practices

### 1. Always Sanitize First
```typescript
// Bad
const name = req.body.name;

// Good
const name = sanitize(req.body.name);
```

### 2. Use Strict Type Validation
```typescript
// Bad
if (req.body.age) { /* ... */ }

// Good
const { valid, coerced } = validateType(req.body.age, 'integer', {
  required: true,
  min: 0,
  max: 150
});
```

### 3. Implement Defense in Depth
```typescript
// Apply multiple layers
app.use([
  sanitizeRequest(),
  validateSchema(requestSchema),
  rateLimiter.middleware(),
  abuseDetector.middleware()
]);
```

### 4. Healthcare-Specific Validation
```typescript
// Always validate medical codes
const validICD = validateMedicalCode(diagnosis, 'icd10');
const validNPI = validateMedicalCode(provider, 'npi');

// Validate prescriptions thoroughly
const prescription = validatePrescription({
  medication: sanitize(req.body.medication),
  dosage: validateDosage(req.body.dosage),
  rxnorm: validateMedicalCode(req.body.rxnorm, 'rxnorm')
});
```

## Performance Considerations

- **Caching**: Validation results are cached where appropriate
- **Async Operations**: File scanning and heavy operations are async
- **Resource Limits**: Built-in protection against resource exhaustion
- **Optimized Patterns**: Regex patterns are pre-compiled

## Compliance

This module helps achieve compliance with:
- **HIPAA**: PHI sanitization and access control
- **OWASP Top 10**: Protection against common vulnerabilities
- **PCI DSS**: Credit card data validation
- **GDPR**: Data validation and sanitization

## Troubleshooting

### Common Issues

1. **Rate Limit Too Restrictive**
   ```typescript
   // Increase limits for authenticated users
   const limiter = createRateLimiter({
     max: req => req.user ? 1000 : 100
   });
   ```

2. **Valid Input Rejected**
   ```typescript
   // Check allowlists
   console.log(AllowlistValidator.getAllowedValues('documentTypes'));

   // Add to dynamic allowlist
   DynamicAllowlistManager.addToAllowlist('customList', newValue);
   ```

3. **Performance Issues**
   ```typescript
   // Use Redis for distributed rate limiting
   const store = new RedisStore(redis);

   // Disable expensive validations
   const validator = createValidator({
     validateFormats: false // Skip format validation
   });
   ```

## API Reference

See the [API Documentation](./API.md) for detailed method descriptions and parameters.

## Contributing

When adding new validation features:
1. Add sanitization rules to `sanitizer.ts`
2. Update allowlists in `allowlists.ts`
3. Add patterns to `regex-patterns.ts`
4. Include tests in `input-validation.test.ts`
5. Update this README

## License

Part of Haven Health Passport - see root LICENSE file.
