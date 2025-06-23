# Security Headers Module

## Overview

The Haven Health Passport Security Headers module provides comprehensive protection against common web vulnerabilities through proper HTTP security headers configuration. This module implements all modern security headers with healthcare-specific configurations.

## Features

### 1. Content Security Policy (CSP)
- **Dynamic CSP Generation**: Build policies programmatically
- **Nonce Support**: Automatic nonce generation for inline scripts/styles
- **Hash Support**: Generate hashes for trusted inline content
- **Report-Only Mode**: Test policies before enforcement
- **Violation Reporting**: Capture and analyze CSP violations
- **Healthcare Presets**: Pre-configured policies for medical applications

### 2. Core Security Headers
- **X-Frame-Options**: Clickjacking protection
- **X-Content-Type-Options**: MIME type sniffing prevention
- **X-XSS-Protection**: XSS filter activation (legacy)
- **Strict-Transport-Security**: HTTPS enforcement (HSTS)
- **Referrer-Policy**: Referrer information control

### 3. Modern Security Headers
- **Permissions-Policy**: Fine-grained feature control
- **Cross-Origin-Opener-Policy**: Window isolation
- **Cross-Origin-Embedder-Policy**: Resource isolation
- **Cross-Origin-Resource-Policy**: Resource sharing control
- **Report-To**: Structured violation reporting

### 4. Security.txt Implementation
- **RFC 9116 Compliant**: Standard security contact information
- **PGP Support**: Encryption key references
- **Multi-language**: Preferred language specification
- **Auto-expiration**: Automatic expiry date management

### 5. Violation Reporting
- **Report URI Handler**: Centralized violation collection
- **Real-time Monitoring**: Track security violations
- **Critical Alert Detection**: Identify serious security attempts
- **Report Analysis**: Aggregate and analyze violations

## Quick Start

### Basic Setup

```typescript
import { applySecurityHeaders, HealthcareSecuritySetup } from '@haven/security/headers';
import express from 'express';

const app = express();

// Apply healthcare-specific security headers
applySecurityHeaders(app, HealthcareSecuritySetup.patientPortal);

// Or create custom configuration
applySecurityHeaders(app, {
  headers: {
    frameOptions: 'DENY',
    contentTypeOptions: 'nosniff',
    xssProtection: '1; mode=block',
    hsts: {
      maxAge: 31536000,
      includeSubDomains: true,
      preload: true
    },
    referrerPolicy: 'strict-origin-when-cross-origin'
  },
  securityTxt: {
    contact: 'mailto:security@example.com',
    policy: 'https://example.com/security-policy'
  },
  reportUri: '/api/security/reports',
  enableReporting: true
});
```

### CSP Configuration

```typescript
import { CSPBuilder } from '@haven/security/headers';

const csp = new CSPBuilder({
  directives: {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'strict-dynamic'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", 'data:', 'https:'],
    'connect-src': ["'self'", 'wss://api.example.com'],
    'font-src': ["'self'"],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'frame-ancestors': ["'none'"]
  },
  reportUri: '/csp-report',
  useNonce: true
});

app.use(csp.middleware());
```

### Using Nonces

```typescript
// In your Express route
app.get('/page', (req, res) => {
  const nonce = res.locals.cspNonce;

  res.send(`
    <html>
      <head>
        <script nonce="${nonce}">
          console.log('This inline script is allowed');
        </script>
      </head>
    </html>
  `);
});
```

### Permissions Policy

```typescript
import { PermissionsPolicyBuilder } from '@haven/security/headers';

const permissions = new PermissionsPolicyBuilder()
  .deny('camera')
  .deny('microphone')
  .allowSelf('geolocation')
  .allow('payment', 'self', 'https://payment.example.com')
  .build();

app.use((req, res, next) => {
  res.setHeader('Permissions-Policy', permissions);
  next();
});
```

## Healthcare Configurations

### Patient Portal
```typescript
// Strict configuration for patient-facing applications
applySecurityHeaders(app, HealthcareSecuritySetup.patientPortal);
```

Features:
- Blocks all framing (clickjacking protection)
- Strict CSP with nonce requirements
- No camera/microphone access
- Minimal third-party resources

### Provider Application
```typescript
// Balanced configuration for healthcare providers
applySecurityHeaders(app, HealthcareSecuritySetup.providerApp);
```

Features:
- Allows same-origin framing for embedded viewers
- Permits camera/microphone for telehealth
- USB/Serial access for medical devices
- Controlled third-party resources

### API Endpoints
```typescript
// Optimized for API security
applySecurityHeaders(app, HealthcareSecuritySetup.api);
```

Features:
- No UI-specific headers
- Strict CORS policies
- Cache prevention
- Minimal attack surface

## Violation Reporting

### Setup Report Handler

```typescript
import { ReportUriHandler } from '@haven/security/headers';

const reportHandler = new ReportUriHandler();

// Register custom handlers
reportHandler.registerHandler('csp', (report) => {
  // Log to monitoring service
  logger.warn('CSP Violation', report);

  // Check for critical violations
  if (report['csp-report']['violated-directive'].includes('script-src')) {
    alertSecurityTeam(report);
  }
});

app.use('/api/security/reports', reportHandler.router());
```

### Analyzing Reports

```typescript
// Get recent violations
const cspViolations = reportHandler.getReports({
  type: 'csp',
  since: new Date(Date.now() - 24 * 60 * 60 * 1000) // Last 24 hours
});

// Analyze patterns
const violationsByDirective = cspViolations.reduce((acc, report) => {
  const directive = report.body['csp-report']['violated-directive'];
  acc[directive] = (acc[directive] || 0) + 1;
  return acc;
}, {});
```

## Security.txt

### Implementation

```typescript
import { SecurityTxtGenerator } from '@haven/security/headers';

const securityTxt = new SecurityTxtGenerator({
  contact: [
    'mailto:security@havenhealth.com',
    'https://havenhealth.com/security'
  ],
  encryption: 'https://havenhealth.com/pgp-key.txt',
  acknowledgments: 'https://havenhealth.com/security/thanks',
  preferredLanguages: ['en', 'es', 'fr'],
  policy: 'https://havenhealth.com/security-policy',
  hiring: 'https://havenhealth.com/careers/security'
});

app.get('/.well-known/security.txt', securityTxt.middleware());
```

## Best Practices

### 1. Start with Report-Only
```typescript
const csp = new CSPBuilder({
  // ... directives ...
  reportOnly: true, // Test before enforcing
  reportUri: '/csp-report'
});
```

### 2. Use Nonces for Inline Content
```typescript
// Good - with nonce
<script nonce="${nonce}">
  console.log('Secure inline script');
</script>

// Bad - unsafe-inline
<script>
  console.log('Insecure inline script');
</script>
```

### 3. Progressive Enhancement
```typescript
// Start strict, relax as needed
const csp = new CSPBuilder({
  directives: {
    'default-src': ["'none'"], // Start with nothing
    'script-src': ["'self'"],   // Add what you need
    'style-src': ["'self'"],
    'img-src': ["'self'"],
    'connect-src': ["'self'"]
  }
});
```

### 4. Monitor Violations
```typescript
// Set up alerts for suspicious patterns
reportHandler.registerHandler('csp', (report) => {
  const blockedUri = report['csp-report']['blocked-uri'];

  // Alert on potential XSS attempts
  if (blockedUri.includes('javascript:') ||
      blockedUri.includes('data:text/html')) {
    securityAlert('Potential XSS attempt detected', report);
  }
});
```

## Validation

### Check Headers

```typescript
import { SecurityHeadersValidator } from '@haven/security/headers';

// Validate response headers
const validation = SecurityHeadersValidator.validate(responseHeaders);
console.log(`Security Score: ${validation.score}/100`);

if (validation.missing.length > 0) {
  console.log('Missing headers:', validation.missing);
}

if (validation.insecure.length > 0) {
  console.warn('Security issues:', validation.insecure);
}
```

### Generate Report

```typescript
const report = SecurityHeadersValidator.generateReport(responseHeaders);
fs.writeFileSync('security-headers-report.txt', report);
```

## Troubleshooting

### Common Issues

1. **CSP Blocking Legitimate Resources**
   ```typescript
   // Check violation reports
   const violations = reportHandler.getReports({ type: 'csp' });

   // Add trusted sources
   csp.addSource('script-src', 'https://trusted-cdn.com');
   ```

2. **Inline Scripts Not Working**
   ```typescript
   // Use nonces
   const nonce = res.locals.cspNonce;

   // Or use hashes for static content
   const hash = CSPUtils.generateScriptHash(scriptContent);
   csp.addSource('script-src', hash);
   ```

3. **HSTS Issues**
   ```typescript
   // Start with shorter duration
   hsts: {
     maxAge: 300, // 5 minutes for testing
     includeSubDomains: false
   }

   // Gradually increase
   hsts: {
     maxAge: 31536000, // 1 year in production
     includeSubDomains: true,
     preload: true
   }
   ```

## Performance Considerations

- Headers are cached by browsers
- CSP evaluation happens in the browser
- Nonce generation is lightweight
- Report handling is asynchronous

## Compliance

This module helps achieve compliance with:
- **OWASP Security Headers**: All recommended headers
- **HIPAA**: Protects against common attack vectors
- **PCI DSS**: Required security controls
- **SOC 2**: Security header requirements

## API Reference

See the [API Documentation](./API.md) for detailed method descriptions.

## Contributing

When adding new security headers:
1. Update the SecurityHeadersConfig interface
2. Add implementation in SecurityHeaders class
3. Create healthcare-specific presets
4. Add validation rules
5. Update tests and documentation

## License

Part of Haven Health Passport - see root LICENSE file.
