# FHIR Authorization Configuration

## Overview

The Haven Health Passport FHIR server implements a comprehensive authorization system that integrates with the main application's authentication framework. This document describes the authorization configuration and how it works.

## Components

### 1. Python Authorization Handler (`src/healthcare/fhir_authorization.py`)
- Implements role-based access control (RBAC)
- Supports fine-grained permissions per resource type
- Handles patient consent management
- Provides emergency access override capabilities

### 2. HAPI FHIR Authorization Interceptor (`fhir-server/src/main/java/org/havenhealthpassport/interceptor/HavenAuthorizationInterceptor.java`)
- Custom HAPI FHIR interceptor that validates tokens
- Communicates with Python auth service via REST API
- Enforces authorization rules at the FHIR server level
- Supports role-based access patterns

### 3. Token Validation Endpoint (`src/api/fhir_auth_endpoints.py`)
- REST endpoint at `/api/v1/auth/validate`
- Validates JWT tokens from FHIR requests
- Returns user roles and permissions
- Provides additional authorization check endpoint

## Configuration

### Environment Variables
- `FHIR_AUTH_ENABLED`: Enable/disable authorization (default: true)
- `FHIR_TOKEN_ENDPOINT`: URL for token validation service
- `FHIR_OAUTH2_ISSUER`: OAuth2 token issuer URL
- `FHIR_OAUTH2_AUDIENCE`: Expected token audience
- `FHIR_ALLOW_ANONYMOUS_READ`: Allow anonymous read access

### Docker Compose Configuration
The FHIR server is configured to use the custom authorization:
```yaml
fhir-server:
  build:
    context: ./fhir-server
    dockerfile: Dockerfile
  environment:
    - FHIR_AUTH_ENABLED=true
    - FHIR_TOKEN_ENDPOINT=http://web:8000/api/v1/auth/validate
```

## Supported Roles

1. **Patient**
   - Read/update own patient record
   - Read own clinical data (observations, conditions, medications)
   - Create document references

2. **Practitioner**
   - Read all patient records
   - Create/update clinical resources
   - Delete medication requests
   - Perform search operations

3. **Admin**
   - Full access to all resources
   - All CRUD operations permitted

4. **Emergency Responder**
   - Read-only access to critical information
   - Patient demographics, allergies, conditions, active medications

5. **Caregiver**
   - Access to assigned patients only
   - Read-only access to clinical data

## Authorization Flow

1. Client sends request to FHIR server with JWT token in Authorization header
2. HAPI FHIR interceptor extracts token and calls validation endpoint
3. Python service validates token and returns user roles/permissions
4. Interceptor builds authorization rules based on roles
5. Request is allowed or denied based on rules

## Testing Authorization

### With cURL
```bash
# Get a token first
TOKEN=$(curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test@example.com","password":"password"}' | jq -r .access_token)

# Access FHIR resources with token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/fhir/Patient
```

### With Python
```python
import requests

# Get token
auth_response = requests.post('http://localhost:8000/api/v2/auth/login',
    json={'username': 'test@example.com', 'password': 'password'})
token = auth_response.json()['access_token']

# Access FHIR server
headers = {'Authorization': f'Bearer {token}'}
fhir_response = requests.get('http://localhost:8080/fhir/Patient', headers=headers)
```

## Extending Authorization

### Adding New Roles
1. Add role to `FHIRRole` enum in `fhir_authorization.py`
2. Define permissions in `DEFAULT_ROLES` dictionary
3. Update Java interceptor to handle new role

### Custom Authorization Policies
```python
from src.healthcare.fhir_authorization import (
    get_authorization_handler,
    AuthorizationPolicy,
    ResourcePermission
)

# Create custom policy
policy = AuthorizationPolicy(
    id="research-access",
    name="Research Data Access",
    effect="allow",
    resource_types=["Observation", "Condition"],
    actions=[ResourcePermission.READ],
    conditions={"research_consent": True}
)

# Add to handler
handler = get_authorization_handler()
handler.add_policy(policy)
```

## Troubleshooting

### Authorization Failures
1. Check token is valid: `GET /api/v1/auth/validate`
2. Verify user has required role
3. Check FHIR server logs for detailed error
4. Ensure `FHIR_AUTH_ENABLED=true` is set

### Common Issues
- **401 Unauthorized**: Invalid or missing token
- **403 Forbidden**: Valid token but insufficient permissions
- **Connection refused**: Auth service not reachable from FHIR server
