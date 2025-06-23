# Real Test Framework Configuration - Haven Health Passport

## Overview

This document describes the REAL test framework configuration for Haven Health Passport. Unlike typical test setups that rely heavily on mocks, this configuration uses actual service instances to ensure accurate testing for this life-critical healthcare system.

## ⚠️ CRITICAL: Why Real Services?

**This is a healthcare system for displaced refugees. Lives depend on accurate testing.**

- **NO MOCKS** for database operations - Real PostgreSQL with production schema
- **NO MOCKS** for encryption - Real KMS-grade encryption with actual keys
- **NO MOCKS** for medical validation - Real FHIR server validation
- **NO MOCKS** for authentication - Real JWT generation and validation
- **ONLY MOCK** external paid services with contract testing

## Quick Start

### 1. Start Test Services

```bash
cd tests/config
./start_test_services.sh
```

This starts:
- PostgreSQL (port 5433) - Real database with production schema
- Redis (port 6380) - Real caching layer
- LocalStack - Real AWS service calls (S3, KMS, DynamoDB)
- FHIR Server (port 8081) - Real medical data validation
- Mock OAuth Server (port 9090) - OAuth flow testing
- MailHog (port 8025) - Email capture
- Ganache (port 8545) - Blockchain network (if installed)

### 2. Run Tests

```bash
# Python tests with real services
pytest tests/integration/test_real_patient_creation.py -v

# JavaScript tests with real rendering
cd web && npm test PatientRegistration.real.test.jsx
```

### 3. Stop Services

```bash
cd tests/config
./stop_test_services.sh
```

## Architecture

### Real Test Services (`real_test_config.py`)

The `RealTestServices` class provides connections to all test services:

```python
services = RealTestConfig.get_real_test_services()

# Available services:
services.database          # SQLAlchemy session with real PostgreSQL
services.redis_client      # Redis client with actual caching
services.elasticsearch     # Elasticsearch for real search operations
services.s3_client        # S3 client via LocalStack
services.kms_client       # KMS for real encryption
services.fhir_client      # FHIR server for medical validation
services.blockchain_web3  # Web3 connection to test blockchain
services.encryption_service # Real PHI encryption service
services.audit_service    # Real audit logging to database
```

### Database Schema (`test_database_schema.py`)

Full production schema including:
- **Patients** table with encrypted PHI fields
- **HealthRecords** with field-level encryption
- **AuditLogs** for HIPAA compliance
- **EmergencyAccess** tracking
- Database triggers for automatic audit logging
- Row-level security policies

### Test Configuration Features

#### Real Encryption
```python
# Actual KMS-grade encryption for PHI
encrypted_name = services.encryption_service.encrypt_phi(
    "John Doe",
    {"field": "patient_name", "patient_id": "12345"}
)
```

#### Real Audit Logging
```python
# Creates actual database records
services.audit_service.log_access(
    user_id="provider-123",
    action="READ",
    resource_type="Patient",
    resource_id="patient-456"
)
```

#### Real Blockchain Verification
```python
# Deploys and interacts with actual smart contracts
result = blockchain_service.create_verification(
    patient_id="12345",
    record_hash="0xabcdef..."
)
```

## JavaScript/React Testing

### Real Component Testing Setup (`setupTests.js`)

Provides real implementations for:
- **Crypto API** - Actual encryption/decryption
- **localStorage/sessionStorage** - Real storage with events
- **IndexedDB** - Actual offline data storage
- **WebSocket** - Real-time communication
- **getUserMedia** - Camera/microphone access
- **Real API Client** - Actual HTTP requests to test backend

### Example Component Test
```javascript
test('creates patient with real API calls', async () => {
  // Uses real API client
  const patient = await global.realApiClient.post('/api/patients', {
    firstName: 'Test',
    lastName: 'Patient'
  });
  
  // Verify in real database
  expect(patient.id).toBeDefined();
  expect(patient.firstNameEncrypted).toBeDefined();
});
```

## Best Practices

### 1. Transaction Isolation
All tests run in database transactions that rollback after completion:
```python
@pytest.fixture
def real_db_session(real_test_services):
    session = real_test_services.database
    session.begin_nested()  # Savepoint
    yield session
    session.rollback()      # Rollback all changes
```

### 2. Data Cleanup
Automatic cleanup after test runs:
```python
def cleanup_test_data(services):
    services.database.execute("TRUNCATE TABLE patients CASCADE")
    services.redis_client.flushdb()
    services.elasticsearch.indices.delete(index="test_*")
```

### 3. Performance Monitoring
Real performance metrics during tests:
```javascript
performance.mark('operation-start');
// ... operation ...
performance.mark('operation-end');
const measure = performance.measure('duration', 'operation-start', 'operation-end');
expect(measure.duration).toBeLessThan(1000); // Must complete in < 1 second
```

### 4. Medical Compliance Validation
Every test automatically validates:
- FHIR resource compliance
- PHI encryption requirements
- Audit trail completeness
- No PHI on blockchain

## Troubleshooting

### Services Won't Start
```bash
# Check Docker status
docker ps -a

# View logs
docker-compose -f docker-compose.test.yml logs [service-name]

# Reset everything
docker-compose -f docker-compose.test.yml down -v
```

### Database Connection Issues
```bash
# Test connection
psql postgresql://test:test@localhost:5433/haven_test

# Reinitialize database
python tests/config/initialize_test_db.py
```

### LocalStack Issues
```bash
# Verify LocalStack is running
curl http://localhost:4566/_localstack/health

# Check AWS CLI works
aws --endpoint-url=http://localhost:4566 s3 ls
```

## Environment Variables

```bash
# Database
TEST_DATABASE_URL=postgresql://test:test@localhost:5433/haven_test

# Redis
TEST_REDIS_URL=redis://localhost:6380/1

# AWS (LocalStack)
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# FHIR Server
FHIR_SERVER_URL=http://localhost:8081/fhir

# Blockchain
BLOCKCHAIN_RPC_URL=http://localhost:8545
```

## CI/CD Integration

For CI environments:
```yaml
# .github/workflows/test.yml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: test
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      
  redis:
    image: redis:7
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s

steps:
  - name: Start LocalStack
    run: |
      pip install localstack
      localstack start -d
      
  - name: Initialize Database
    run: python tests/config/initialize_test_db.py
    
  - name: Run Tests
    run: pytest tests/ --cov=src
```

## Security Considerations

1. **Test Data Only** - Never use production data in tests
2. **Isolated Networks** - Test services run on isolated Docker network
3. **Temporary Keys** - Encryption keys are generated per test run
4. **No External Access** - Services bound to localhost only
5. **Automatic Cleanup** - All test data deleted after runs

## Conclusion

This real test framework ensures that Haven Health Passport is tested against actual service implementations, providing confidence that the system will work correctly in production where refugee lives depend on it.

Remember: **Every mock we don't write is a potential bug we catch before it impacts a refugee's access to healthcare.**
