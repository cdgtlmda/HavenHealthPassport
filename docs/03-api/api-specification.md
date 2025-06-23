# Haven Health Passport - API Specification

## API Overview

The Haven Health Passport API provides secure, RESTful and GraphQL endpoints for managing refugee health records, verification, and cross-border data sharing.

### Base URLs
- Production: `https://api.havenhealthpassport.org`
- Staging: `https://api-staging.havenhealthpassport.org`
- Development: `https://api-dev.havenhealthpassport.org`

### API Versioning
- Current Version: `v1`
- Version in URL: `/api/v1/`
- GraphQL endpoint: `/graphql`

## Authentication

### JWT Token Authentication
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "securepassword",
  "mfa_code": "123456"
}

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### API Key Authentication
For service-to-service communication:
```http
GET /api/v1/health-records
X-API-Key: your-api-key-here
```

## Core Endpoints

### Patient Management

#### Create Patient Profile
```http
POST /api/v1/patients
Authorization: Bearer {token}
Content-Type: application/json

{
  "demographics": {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-01",
    "nationality": "SYR",
    "languages": ["ar", "en"]
  },
  "contact": {
    "phone": "+1234567890",
    "email": "john.doe@example.com"
  }
}
```

#### Get Patient Profile
```http
GET /api/v1/patients/{patient_id}
Authorization: Bearer {token}

Response:
{
  "id": "pat_1234567890",
  "demographics": {...},
  "verification_status": "VERIFIED",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Health Records

#### Upload Health Record
```http
POST /api/v1/health-records
Authorization: Bearer {token}
Content-Type: multipart/form-data

{
  "patient_id": "pat_1234567890",
  "record_type": "VACCINATION",
  "file": <binary>,
  "metadata": {
    "provider": "UNHCR Clinic",
    "date": "2024-01-01",
    "location": "Jordan"
  }
}
```

#### Verify Health Record
```http
POST /api/v1/health-records/{record_id}/verify
Authorization: Bearer {token}

{
  "verification_method": "BLOCKCHAIN",
  "verifier_id": "org_unhcr"
}

Response:
{
  "record_id": "rec_1234567890",
  "verification_status": "VERIFIED",
  "blockchain_hash": "0x1234...",
  "blockchain_tx_id": "mock_tx_abc123def456",
  "blockchain_network": "aws-n-12345abcde",
  "verified_at": "2024-01-01T00:00:00Z",
  "verifier": {
    "id": "org_unhcr",
    "name": "UNHCR"
  }
}
```

### Translation Services

#### Translate Document
```http
POST /api/v1/translate
Authorization: Bearer {token}
Content-Type: application/json

{
  "text": "تاريخ طبي",
  "source_language": "ar",
  "target_language": "en",
  "context": "medical_history",
  "cultural_adaptation": true
}

Response:
{
  "original_text": "تاريخ طبي",
  "translated_text": "Medical History",
  "confidence": 0.98,
  "cultural_notes": "Term commonly used in Middle Eastern medical contexts"
}
```

## GraphQL API

### Schema Overview
```graphql
type Query {
  patient(id: ID!): Patient
  healthRecords(patientId: ID!, filters: RecordFilters): [HealthRecord]
  verificationStatus(recordId: ID!): VerificationStatus
}

type Mutation {
  createPatient(input: PatientInput!): Patient
  uploadHealthRecord(input: HealthRecordInput!): HealthRecord
  verifyRecord(recordId: ID!, verifierId: ID!): VerificationResult
  grantAccess(patientId: ID!, providerId: ID!, duration: Int): AccessGrant
}

type Patient {
  id: ID!
  demographics: Demographics!
  healthRecords: [HealthRecord]
  accessGrants: [AccessGrant]
  verificationStatus: VerificationStatus!
}
```

### Example Query
```graphql
query GetPatientRecords($patientId: ID!) {
  patient(id: $patientId) {
    id
    demographics {
      firstName
      lastName
    }
    healthRecords(last: 10) {
      id
      type
      verificationStatus
      uploadedAt
    }
  }
}
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request validation failed",
    "details": [
      {
        "field": "patient_id",
        "message": "Invalid patient ID format"
      }
    ],
    "request_id": "req_1234567890"
  }
}
```

### Common Error Codes
- `UNAUTHORIZED`: Invalid or missing authentication
- `FORBIDDEN`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `VALIDATION_ERROR`: Request validation failed
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Server error

## Rate Limiting

### Limits by Tier
- **Basic**: 100 requests per minute
- **Standard**: 1,000 requests per minute
- **Enterprise**: 10,000 requests per minute

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## Webhooks

### Event Types
- `patient.created`
- `health_record.uploaded`
- `health_record.verified`
- `access.granted`
- `access.revoked`

### Webhook Payload
```json
{
  "id": "evt_1234567890",
  "type": "health_record.verified",
  "created": "2024-01-01T00:00:00Z",
  "data": {
    "record_id": "rec_1234567890",
    "patient_id": "pat_1234567890",
    "verification_status": "VERIFIED"
  }
}
```
