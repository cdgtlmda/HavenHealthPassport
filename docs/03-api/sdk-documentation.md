# Haven Health Passport SDK Documentation

## Overview

The Haven Health Passport SDK provides programmatic access to the platform's health record management and verification capabilities.

## Available SDKs

### Python SDK

The Python SDK provides comprehensive access to Haven Health Passport's blockchain and API functionality.

#### Installation

```bash
pip install haven-health-sdk
```

#### Quick Start

```python
from haven_health_sdk import HavenHealthClient

# Initialize client
client = HavenHealthClient(
    api_key="your-api-key",
    environment="production"
)

# Create a health record
record = client.health_records.create({
    "patient_id": "patient-123",
    "fhir_resource": {...},
    "blockchain_verify": True
})

# Query records
records = client.health_records.query(
    patient_id="patient-123",
    resource_type="Observation"
)
```

#### Key Features

- **Health Record Management**: Create, read, update, and query health records
- **Blockchain Verification**: Verify record authenticity via blockchain
- **Access Control**: Manage permissions and access grants
- **Offline Support**: Queue operations for later synchronization
- **Event Streaming**: Subscribe to real-time updates

### JavaScript/TypeScript SDK

```bash
npm install @haven-health/sdk
```

```typescript
import { HavenHealthClient } from '@haven-health/sdk';

const client = new HavenHealthClient({
    apiKey: 'your-api-key',
    environment: 'production'
});

// Create health record
const record = await client.healthRecords.create({
    patientId: 'patient-123',
    fhirResource: {...},
    blockchainVerify: true
});
```

## Core Functionality

### Authentication

All SDK calls require authentication via API key:

```python
client = HavenHealthClient(api_key="your-api-key")
```

API keys can be obtained from the Haven Health Passport admin portal.

### Health Records

#### Create Record
```python
record = client.health_records.create({
    "patient_id": "patient-123",
    "resource_type": "Observation",
    "fhir_resource": {
        "resourceType": "Observation",
        "status": "final",
        "code": {...},
        "valueQuantity": {...}
    }
})
```

#### Read Record
```python
record = client.health_records.get(record_id="record-456")
```

#### Update Record
```python
updated = client.health_records.update(
    record_id="record-456",
    fhir_resource={...}
)
```

#### Query Records
```python
results = client.health_records.query(
    patient_id="patient-123",
    resource_type="Observation",
    date_from="2024-01-01",
    date_to="2024-12-31"
)
```

### Blockchain Verification

#### Verify Single Record
```python
verification = client.blockchain.verify(record_id="record-456")
print(f"Valid: {verification.is_valid}")
print(f"Hash: {verification.blockchain_hash}")
```

#### Batch Verification
```python
verifications = client.blockchain.verify_batch(
    record_ids=["record-456", "record-789"]
)
```

### Access Control

#### Grant Access
```python
grant = client.access.grant({
    "patient_id": "patient-123",
    "provider_id": "provider-456",
    "resource_types": ["Observation", "Condition"],
    "expiration": "2024-12-31T23:59:59Z"
})
```

#### Revoke Access
```python
client.access.revoke(grant_id="grant-789")
```

#### Check Access
```python
has_access = client.access.check(
    provider_id="provider-456",
    patient_id="patient-123",
    resource_type="Observation"
)
```

## Error Handling

The SDK provides detailed error information:

```python
try:
    record = client.health_records.create({...})
except ValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Fields: {e.fields}")
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
except ApiError as e:
    print(f"API error: {e.status_code} - {e.message}")
```

## Rate Limiting

The SDK automatically handles rate limiting with exponential backoff:

```python
# Configure retry behavior
client = HavenHealthClient(
    api_key="your-api-key",
    max_retries=3,
    retry_delay=1.0
)
```

## Offline Support

Enable offline mode for mobile and low-connectivity environments:

```python
client = HavenHealthClient(
    api_key="your-api-key",
    offline_mode=True,
    offline_storage_path="/path/to/storage"
)

# Operations are queued when offline
record = client.health_records.create({...})  # Queued

# Sync when connection available
sync_results = client.sync()
print(f"Synced {sync_results.count} operations")
```

## Best Practices

1. **Use environment variables** for API keys
2. **Enable offline mode** for mobile applications
3. **Batch operations** when possible for efficiency
4. **Subscribe to events** for real-time updates
5. **Verify blockchain hashes** for critical records
6. **Handle errors gracefully** with proper fallbacks
7. **Respect rate limits** to avoid throttling

## Examples

### Complete Patient Record Creation

```python
# Create patient with full FHIR resource
patient = client.patients.create({
    "fhir_resource": {
        "resourceType": "Patient",
        "identifier": [{
            "system": "urn:oid:1.2.36.146.595.217.0.1",
            "value": "12345"
        }],
        "name": [{
            "family": "Smith",
            "given": ["John", "James"]
        }],
        "gender": "male",
        "birthDate": "1974-12-25"
    },
    "blockchain_verify": True
})

# Add observation
observation = client.health_records.create({
    "patient_id": patient.id,
    "resource_type": "Observation",
    "fhir_resource": {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8867-4",
                "display": "Heart rate"
            }]
        },
        "valueQuantity": {
            "value": 72,
            "unit": "beats/minute"
        }
    }
})
```

### Emergency Access Protocol

```python
# Grant emergency access (72-hour limit)
emergency_grant = client.access.grant_emergency({
    "patient_id": "patient-123",
    "provider_id": "emergency-provider-789",
    "reason": "Emergency treatment required",
    "location": {"lat": 51.5074, "lon": -0.1278}
})
```

## Support

- **Documentation**: https://docs.havenhealthpassport.org
- **API Reference**: https://api.havenhealthpassport.org/docs
- **Issues**: https://github.com/havenhealthpassport/sdk/issues
- **Support**: sdk-support@havenhealthpassport.org