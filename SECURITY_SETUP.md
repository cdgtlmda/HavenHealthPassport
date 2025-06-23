# Security Setup Guide

⚠️ **IMPORTANT**: This repository has been sanitized for public use. All credentials, API keys, and sensitive information have been removed or replaced with placeholders.

## Required Credentials

You must configure the following credentials before running the application:

### 1. Database Credentials

Set these environment variables:

```bash
export DATABASE_URL="postgresql://username:password@localhost/database_name"
export DB_PASSWORD="your_secure_db_password"
```

### 2. AWS Credentials

Configure AWS credentials (do NOT hardcode in source):

```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_REGION="us-east-1"
```

### 3. JWT Security Keys

Generate secure JWT keys:

```bash
export JWT_SECRET_KEY="$(openssl rand -base64 64)"
export ENCRYPTION_KEY="$(openssl rand -base64 32)"
export PHI_ENCRYPTION_KEY="$(openssl rand -base64 32)"
```

Update `data/keys/jwt_keys.json`:

```json
{
  "current": {
    "kid": "your_unique_key_id",
    "key": "your_jwt_secret_key_base64",
    "created_at": "2025-01-01T00:00:00.000000+00:00",
    "expires_at": "2025-12-31T23:59:59.999999+00:00",
    "algorithm": "HS256"
  }
}
```

### 4. Redis Configuration

```bash
export REDIS_URL="redis://localhost:6379"
export TEST_REDIS_URL="redis://localhost:6379/1"
```

### 5. Test Credentials

For testing only:

```bash
export TEST_USER_PASSWORD="YourSecureTestPassword123!"
export TEST_ENCRYPTION_KEY="your_test_encryption_key"
```

### 6. Blockchain Certificates

Replace all certificate placeholders in:

- `blockchain/sdk/connection-profile.yaml`
- `blockchain/config/consensus/consenter-set.yaml`

Generate or obtain proper TLS certificates and private keys from your certificate authority.

### 7. Certificate Authority Passwords

Update all instances of `enrollSecret: REPLACE_WITH_SECURE_PASSWORD` in blockchain configuration files with secure passwords.

## Files That Were Sanitized

The following files contained credentials that were removed:

1. **scripts/test-bedrock.py** - Removed hardcoded AWS credentials
2. **data/keys/jwt_keys.json** - Removed actual JWT signing key
3. **scripts/verify_glossary.py** - Removed database password
4. **run-single-test.sh** - Replaced hardcoded test encryption key
5. **cypress.config.ts** - Replaced hardcoded test password
6. **src/database.py** - Sanitized default database URL
7. **blockchain/sdk/connection-profile.yaml** - Removed private keys and certificates
8. **blockchain/config/consensus/consenter-set.yaml** - Removed certificate placeholders

## Security Best Practices

1. **Never commit credentials to version control**
2. **Use environment variables for all secrets**
3. **Rotate keys regularly**
4. **Use secure key management systems in production**
5. **Enable encryption at rest and in transit**
6. **Audit access to sensitive systems regularly**

## Environment Setup Script

Create a `.env` file (never commit this):

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost/database_name
DB_PASSWORD=your_secure_password

# AWS
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Security Keys
JWT_SECRET_KEY=your_jwt_secret_base64
ENCRYPTION_KEY=your_encryption_key_base64
PHI_ENCRYPTION_KEY=your_phi_encryption_key_base64

# Redis
REDIS_URL=redis://localhost:6379
TEST_REDIS_URL=redis://localhost:6379/1

# Testing
TEST_USER_PASSWORD=YourSecureTestPassword123!
TEST_ENCRYPTION_KEY=your_test_key
```

## Production Deployment

For production deployments:

1. Use AWS Secrets Manager or similar service
2. Configure proper TLS certificates
3. Enable audit logging
4. Use least-privilege IAM policies
5. Enable encryption for all data stores
6. Set up monitoring and alerting

## Support

If you need help setting up credentials or have security questions, please:

1. Review the documentation in the `docs/` directory
2. Check the security implementation guides in `docs/07-reference/security-implementation/`
3. Create an issue in the repository (do NOT include actual credentials)

⚠️ **WARNING**: Never share or commit actual credentials, API keys, or certificates to version control systems.
