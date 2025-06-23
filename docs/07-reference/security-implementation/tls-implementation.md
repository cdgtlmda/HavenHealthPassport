# TLS and Transport Security Implementation

## Overview

The Haven Health Passport implements comprehensive transport security using TLS 1.3 with fallback to TLS 1.2, perfect forward secrecy, and mutual TLS for administrative access.

## Features Implemented

### 1. TLS 1.3 Configuration
- Primary protocol with TLS 1.2 fallback
- Modern cipher suites with AEAD encryption
- Automatic certificate management via AWS ACM

### 2. Certificate Management
- AWS Certificate Manager for automatic renewal
- DNS validation via Route53
- Multi-domain support with SANs

### 3. Security Headers
- **HSTS**: 2-year max-age with preload
- **CSP**: Strict content security policy with nonces
- **X-Frame-Options**: DENY to prevent clickjacking
- **X-Content-Type-Options**: nosniff
- **Referrer-Policy**: strict-origin-when-cross-origin
- **Permissions-Policy**: Restrictive feature policy

### 4. Cipher Suite Configuration
```
TLS 1.3:
- TLS_AES_256_GCM_SHA384
- TLS_AES_128_GCM_SHA256
- TLS_CHACHA20_POLY1305_SHA256

TLS 1.2 (PFS only):
- ECDHE-ECDSA-AES256-GCM-SHA384
- ECDHE-RSA-AES256-GCM-SHA384
- ECDHE-ECDSA-CHACHA20-POLY1305
- ECDHE-RSA-CHACHA20-POLY1305
- ECDHE-ECDSA-AES128-GCM-SHA256
- ECDHE-RSA-AES128-GCM-SHA256
```

### 5. Perfect Forward Secrecy
- All cipher suites use ECDHE key exchange
- Session keys are ephemeral
- Past communications remain secure even if long-term keys are compromised
### 6. Certificate Pinning
- SHA256 fingerprint validation
- 30-day pin expiry with rotation
- Backup pins for certificate rotation

### 7. OCSP Stapling
- Enabled on all HTTPS endpoints
- Reduces latency for certificate validation
- Cached OCSP responses

### 8. Mutual TLS (mTLS)
- Required for admin and healthcare provider access
- Client certificate validation
- Certificate-based authorization
- Separate port (8443) for mTLS endpoints

### 9. Certificate Validation
- Full chain validation
- Revocation checking via OCSP and CRL
- Certificate purpose validation
- Path length constraints

## Implementation Details

### Nginx Configuration
- TLS 1.3 as primary protocol
- Secure cipher suite selection
- OCSP stapling enabled
- Session cache configuration
- Rate limiting per endpoint type

### Python/Flask Integration
```python
from src.security import SecurityHeaders, TLSConfig

# Initialize security headers
app = Flask(__name__)
init_security_headers(app, environment='production')

# Create secure SSL context
tls_config = TLSConfig(cert_path='/path/to/cert', key_path='/path/to/key')
ssl_context = tls_config.create_ssl_context()
```

### Load Balancer Configuration
- AWS ALB with TLS 1.3 policy
- CloudFront with minimum TLS 1.2
- End-to-end encryption enforced
## Monitoring and Compliance

### SSL/TLS Monitoring
- Certificate expiry monitoring
- Protocol version tracking
- Cipher suite usage analytics
- OCSP response time monitoring

### Security Scans
- Regular SSL Labs testing (A+ rating required)
- Automated vulnerability scanning
- Certificate transparency monitoring

### Compliance
- **HIPAA**: Encryption in transit for all PHI
- **PCI DSS**: Strong cryptography requirements met
- **NIST**: Follows NIST SP 800-52 Rev. 2 guidelines

## Best Practices

1. **Certificate Rotation**: Automated via ACM with 30-day advance renewal
2. **Key Management**: Private keys never leave AWS KMS/ACM
3. **Protocol Updates**: Regular review of TLS configuration
4. **Monitoring**: Real-time alerts for certificate issues
5. **Testing**: Automated SSL/TLS testing in CI/CD pipeline

## Troubleshooting

### Common Issues
1. **Certificate Mismatch**: Verify SANs include all domains
2. **Protocol Errors**: Check client TLS version support
3. **OCSP Failures**: Verify firewall allows OCSP endpoints
4. **mTLS Issues**: Validate client certificate chain

### Debug Commands
```bash
# Test TLS configuration
openssl s_client -connect havenhealthpassport.org:443 -tls1_3

# Check certificate
openssl s_client -connect havenhealthpassport.org:443 -showcerts

# Test mTLS
openssl s_client -connect admin.havenhealthpassport.org:8443 \
  -cert client.crt -key client.key -CAfile ca.crt
```
