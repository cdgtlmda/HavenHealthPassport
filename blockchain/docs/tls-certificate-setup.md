# TLS Certificate Setup Documentation
Haven Health Passport - Blockchain Security

## Overview

This document describes the TLS certificate setup for the Haven Health Passport blockchain ordering service. The implementation provides secure communication between blockchain nodes using mutual TLS authentication with ECDSA certificates.

## Architecture

### Certificate Hierarchy

```
Root CA (10 years)
├── Ordering Service CA (5 years)
│   ├── orderer0.haven-health.local (1 year)
│   ├── orderer1.haven-health.local (1 year)
│   └── ... additional orderer nodes
└── Peer Service CA (5 years)
    ├── peer0.haven-health.local (1 year)
    ├── peer1.haven-health.local (1 year)
    └── ... additional peer nodes
```

### Key Specifications

- **Algorithm**: ECDSA (Elliptic Curve Digital Signature Algorithm)
- **Curve**: P-256 (secp256r1)
- **Signature**: SHA256WithECDSA
- **Key Storage**: AWS KMS for root CA, local for node certificates

## Configuration Files

### 1. Main TLS Configuration
- **Location**: `/blockchain/config/tls/tls-certificate-config.yaml`
- **Purpose**: Defines all TLS settings, certificate templates, and policies

### 2. Generated Certificates
- **Location**: `/blockchain/config/tls/certificates/`
- **Structure**:
  ```
  certificates/
  ├── ca/
  │   ├── root/          # Root CA certificate and key
  │   ├── intermediate/  # Intermediate CA certificates
  │   └── crl/          # Certificate Revocation Lists
  ├── orderer/          # Orderer node certificates
  └── peer/             # Peer node certificates
  ```

## Security Features

### 1. Mutual TLS (mTLS)
- **Orderer-to-Orderer**: Required for consensus
- **Client-to-Orderer**: Required for transactions
- **Peer-to-Peer**: Optional for gossip protocol

### 2. Cipher Suites
Configured strong cipher suites for TLS 1.2 and 1.3:
- TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
- TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
- TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
- TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256

### 3. Certificate Management
- **Auto-renewal**: 30 days before expiration
- **Rotation Strategy**: Rolling updates with grace period
- **Revocation**: CRL and OCSP support

## AWS Integration

### 1. AWS Certificate Manager (ACM)
- Import and manage certificates
- Automatic renewal notifications
- Integration with AWS services

### 2. AWS Secrets Manager
- Secure storage of private keys
- Automatic rotation capability
- Access control via IAM

### 3. AWS KMS
- Root CA key protection
- Hardware security module (HSM) backing
- Audit trail for key usage

## Implementation Scripts

### 1. Generate TLS Certificates
```bash
./scripts/generate-tls-certificates.sh
```
- Creates complete certificate hierarchy
- Generates node certificates
- Stores in AWS services

### 2. Manage Certificates
```bash
./scripts/manage-tls-certificates.sh <operation>
```
Operations:
- `check`: Check expiration dates
- `renew`: Renew expiring certificates
- `revoke`: Revoke compromised certificates
- `rotate`: Rotate all certificates
- `backup`: Backup to S3
- `monitor`: Real-time monitoring
- `report`: Generate HTML report

### 3. Verify Setup
```bash
./scripts/verify-tls-setup.sh
```
- Validates configuration
- Checks security settings
- Verifies AWS integration

## Certificate Operations

### Generating Initial Certificates

1. **Prerequisites**:
   ```bash
   # Ensure OpenSSL is installed
   openssl version

   # Configure AWS credentials
   aws configure
   ```

2. **Generate certificates**:
   ```bash
   cd blockchain/scripts
   ./generate-tls-certificates.sh
   ```

3. **Verify generation**:
   ```bash
   ls -la ../config/tls/certificates/
   ```

### Certificate Renewal Process

1. **Check expiration**:
   ```bash
   ./manage-tls-certificates.sh check
   ```

2. **Renew specific certificate**:
   ```bash
   ./manage-tls-certificates.sh renew --cert-id orderer0
   ```

3. **Renew all certificates**:
   ```bash
   ./manage-tls-certificates.sh rotate
   ```

### Certificate Revocation

1. **Revoke certificate**:
   ```bash
   ./manage-tls-certificates.sh revoke --cert-id peer1 --reason keyCompromise
   ```

2. **Update CRL**:
   - Automatically updates CRL
   - Uploads to S3
   - Notifies OCSP responder

## Monitoring and Alerts

### CloudWatch Metrics
- **Namespace**: HavenHealth/Blockchain/TLS
- **Key Metrics**:
  - CertificateExpiringSoon
  - CertificateExpiringCritical
  - TLSHandshakeFailures
  - CertificateValidationFailures

### Alerts Configuration
1. **Warning**: Certificate expiring in 30 days
2. **Critical**: Certificate expiring in 7 days
3. **Critical**: Certificate expired
4. **Critical**: TLS handshake failures > 10/minute

## Compliance

### FIPS 140-2 Level 2
- FIPS-approved algorithms only
- Hardware security module integration
- Validated cryptographic modules

### HIPAA Requirements
- Encryption in transit enforced
- TLS 1.2 minimum version
- Audit logging enabled

### Audit Trail
All certificate operations logged:
- Certificate issuance
- Certificate renewal
- Certificate revocation
- TLS connection establishment
- Authentication failures

## Troubleshooting

### Common Issues

1. **Certificate Expiration**
   ```bash
   # Check all certificates
   ./manage-tls-certificates.sh check

   # Renew expired certificate
   ./manage-tls-certificates.sh renew --cert-id <node-id>
   ```

2. **TLS Handshake Failures**
   - Check cipher suite compatibility
   - Verify certificate chain
   - Check certificate validity
   - Verify hostname matching

3. **Certificate Validation Errors**
   ```bash
   # Verify certificate chain
   openssl verify -CAfile ca/root/root-ca-cert.pem \
     -untrusted ca/intermediate/ordering-service-ca/ordering-service-ca-cert.pem \
     orderer/orderer0/server-cert.pem
   ```

4. **AWS Integration Issues**
   - Verify IAM permissions
   - Check KMS key access
   - Validate S3 bucket permissions

## Best Practices

1. **Regular Monitoring**
   - Daily certificate expiration checks
   - Weekly backup verification
   - Monthly recovery testing

2. **Security Hygiene**
   - Rotate certificates annually
   - Review cipher suites quarterly
   - Update TLS versions as needed

3. **Operational Excellence**
   - Automate renewal process
   - Maintain certificate inventory
   - Document all procedures

## Emergency Procedures

### Certificate Compromise
1. Immediately revoke certificate
2. Generate new certificate
3. Update all nodes
4. Investigate compromise

### Root CA Compromise
1. Activate disaster recovery plan
2. Generate new root CA
3. Re-issue all certificates
4. Update all systems

## Version History

- **v1.0.0**: Initial TLS setup with ECDSA certificates
- **Features**:
  - Complete certificate hierarchy
  - AWS integration
  - Automated management
  - Comprehensive monitoring
