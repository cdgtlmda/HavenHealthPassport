# TLS Certificate Configuration

## Overview

This directory contains TLS certificate configuration for Haven Health Passport.

## Certificate Setup

### Development Environment

For local development, use self-signed certificates:

```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
    -subj "/C=US/ST=State/L=City/O=Haven Health/CN=localhost"
```

### Staging/Production

For staging and production environments:

1. **AWS Certificate Manager (ACM)**:
   - Certificates are automatically provisioned via ACM
   - Integrated with CloudFront and ALB
   - Auto-renewal enabled

2. **Let's Encrypt** (alternative):
   ```bash
   # Install certbot
   sudo apt-get install certbot
   
   # Generate certificate
   sudo certbot certonly --standalone -d api.havenhealthpassport.org
   ```

## Certificate Files

- `cert.pem` - Public certificate
- `key.pem` - Private key (never commit!)
- `chain.pem` - Certificate chain
- `dhparam.pem` - Diffie-Hellman parameters

## Security Configuration

### Nginx SSL Configuration

```nginx
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_stapling on;
ssl_stapling_verify on;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### FastAPI HTTPS Configuration

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=443,
        ssl_keyfile="./key.pem",
        ssl_certfile="./cert.pem",
        ssl_version=ssl.PROTOCOL_TLSv1_2
    )
```

## Certificate Pinning

For mobile applications, implement certificate pinning:

### iOS (Swift)
```swift
let pinnedCertificates = [
    "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
]
```

### Android (Kotlin)
```xml
<network-security-config>
    <domain-config>
        <domain includeSubdomains="true">api.havenhealthpassport.org</domain>
        <pin-set>
            <pin digest="SHA-256">AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

## Certificate Monitoring

- Certificate expiry alerts set up in CloudWatch
- Weekly automated checks via Lambda
- Integration with PagerDuty for critical alerts

## Renewal Process

1. **ACM Certificates**: Auto-renewed by AWS
2. **Let's Encrypt**: Auto-renewed via certbot cron job
3. **Manual certificates**: 30-day warning alerts configured