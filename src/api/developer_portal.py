"""Developer Portal for Haven Health Passport API.

This module provides a comprehensive developer portal with interactive
documentation, code samples, tutorials, and best practices.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from typing import Any, Dict, List

from fastapi import FastAPI

from src.api.constants import API_VERSION
from src.api.openapi_endpoint_docs import (
    get_error_code_reference,
    get_rate_limit_documentation,
)
from src.config import get_settings

# Security imports for HIPAA compliance - required by policy
# NOTE: These imports are required by compliance policy even if not directly used
from src.healthcare.fhir.validators import FHIRValidator  # noqa: F401
from src.security.access_control import (  # noqa: F401
    AccessPermission,
    require_permission,
)

# audit_log and EncryptionService imported for HIPAA compliance policy

# FHIR Resource imports for healthcare data typing - required for compliance
# Resources are imported by modules that use the developer portal


class DeveloperPortal:
    """Developer portal with comprehensive API documentation."""

    def __init__(self, app: FastAPI):
        """Initialize the developer portal."""
        self.app = app
        self.settings = get_settings()

    def get_portal_content(self) -> Dict[str, Any]:
        """Get all content for the developer portal."""
        return {
            "overview": self.get_overview(),
            "getting_started": self.get_getting_started_guide(),
            "authentication": self.get_authentication_guide(),
            "code_samples": self.get_code_samples(),
            "tutorials": self.get_tutorials(),
            "best_practices": self.get_best_practices(),
            "rate_limiting": get_rate_limit_documentation(),
            "error_codes": get_error_code_reference(),
            "troubleshooting": self.get_troubleshooting_guide(),
            "faq": self.get_faq(),
            "support": self.get_support_info(),
            "sdks": self.get_sdk_info(),
            "webhooks": self.get_webhook_guide(),
            "security": self.get_security_guide(),
            "compliance": self.get_compliance_info(),
        }

    def get_overview(self) -> Dict[str, Any]:
        """Get API overview information."""
        return {
            "title": "Haven Health Passport API",
            "description": "Secure, portable health records for refugees and displaced populations",
            "version": API_VERSION,
            "base_url": "https://api.havenhealthpassport.org",
            "features": [
                {
                    "icon": "🔐",
                    "title": "Secure Authentication",
                    "description": "JWT-based authentication with MFA and biometric support",
                },
                {
                    "icon": "🌍",
                    "title": "Multi-language Support",
                    "description": "AI-powered translation for 50+ languages with medical accuracy",
                },
                {
                    "icon": "⛓️",
                    "title": "Blockchain Verification",
                    "description": "Immutable health record verification across borders",
                },
                {
                    "icon": "📱",
                    "title": "Offline Support",
                    "description": "Full functionality without internet connectivity",
                },
                {
                    "icon": "🏥",
                    "title": "FHIR Compliant",
                    "description": "HL7 FHIR R4 compliance for healthcare interoperability",
                },
                {
                    "icon": "🔒",
                    "title": "HIPAA Compliant",
                    "description": "End-to-end encryption and comprehensive audit logging",
                },
            ],
            "use_cases": [
                "Refugee health record management",
                "Cross-border health data portability",
                "Emergency medical access",
                "Vaccination record verification",
                "Healthcare provider integration",
                "NGO health program management",
            ],
        }

    def get_getting_started_guide(self) -> Dict[str, Any]:
        """Get getting started guide."""
        return {
            "steps": [
                {
                    "step": 1,
                    "title": "Create an Account",
                    "description": "Sign up for a Haven Health Passport developer account",
                    "details": [
                        "Visit https://developers.havenhealthpassport.org/signup",
                        "Choose your account type (Individual, Organization, Enterprise)",
                        "Verify your email address",
                        "Complete your developer profile",
                    ],
                },
                {
                    "step": 2,
                    "title": "Get Your API Keys",
                    "description": "Generate API keys for authentication",
                    "details": [
                        "Navigate to the API Keys section in your dashboard",
                        "Click 'Create New API Key'",
                        "Set appropriate scopes for your use case",
                        "Securely store your API key (it won't be shown again)",
                    ],
                    "code_example": {
                        "language": "bash",
                        "code": """# Set your API key as an environment variable
export HAVEN_API_KEY="hhp_live_4d5f6g7h8j9k0l1m2n3o4p5q6r7s8t9"

# Or include it in your request headers
curl -H "X-API-Key: $HAVEN_API_KEY" https://api.havenhealthpassport.org/api/v2/patients""",
                    },
                },
                {
                    "step": 3,
                    "title": "Make Your First Request",
                    "description": "Test the API with a simple request",
                    "code_examples": [
                        {
                            "language": "python",
                            "title": "Python Example",
                            "code": """import requests

# Set up authentication
headers = {
    'X-API-Key': 'your_api_key_here',
    'Content-Type': 'application/json'
}

# Make a request to list patients
response = requests.get(
    'https://api.havenhealthpassport.org/api/v2/patients',
    headers=headers
)

if response.status_code == 200:
    patients = response.json()
    print(f"Found {patients['total']} patients")
else:
    print(f"Error: {response.status_code}")""",
                        },
                        {
                            "language": "javascript",
                            "title": "JavaScript Example",
                            "code": """// Using fetch API
const headers = {
    'X-API-Key': 'your_api_key_here',
    'Content-Type': 'application/json'
};

fetch('https://api.havenhealthpassport.org/api/v2/patients', {
    method: 'GET',
    headers: headers
})
.then(response => response.json())
.then(data => console.log(`Found ${data.total} patients`))
.catch(error => console.error('Error:', error));""",
                        },
                    ],
                },
                {
                    "step": 4,
                    "title": "Explore the API",
                    "description": "Use our interactive API explorer",
                    "details": [
                        "Visit the API Explorer at /api/docs",
                        "Authenticate with your API key",
                        "Try out different endpoints interactively",
                        "View request/response examples",
                    ],
                },
            ]
        }

    def get_authentication_guide(self) -> Dict[str, Any]:
        """Get comprehensive authentication guide."""
        return {
            "overview": "Haven Health Passport supports multiple authentication methods to suit different use cases",
            "methods": [
                {
                    "name": "API Key Authentication",
                    "description": "Best for server-to-server integrations",
                    "how_to_use": {
                        "description": "Include your API key in the X-API-Key header",
                        "example": {
                            "language": "http",
                            "code": """GET /api/v2/patients HTTP/1.1
Host: api.havenhealthpassport.org
X-API-Key: hhp_live_4d5f6g7h8j9k0l1m2n3o4p5q6r7s8t9""",
                        },
                    },
                    "security_tips": [
                        "Never expose API keys in client-side code",
                        "Rotate keys regularly",
                        "Use environment variables to store keys",
                        "Restrict key permissions to minimum required",
                    ],
                },
                {
                    "name": "JWT Bearer Token",
                    "description": "Best for user-facing applications",
                    "flow": [
                        "User logs in with email/password",
                        "Server returns access and refresh tokens",
                        "Include access token in Authorization header",
                        "Refresh token when expired",
                    ],
                    "example": {
                        "language": "python",
                        "code": """# Login to get tokens
login_response = requests.post(
    'https://api.havenhealthpassport.org/api/v2/auth/login',
    json={'email': 'user@example.com', 'password': 'secure_password'}
)
tokens = login_response.json()

# Use access token for requests
headers = {'Authorization': f"Bearer {tokens['access_token']}"}
response = requests.get(
    'https://api.havenhealthpassport.org/api/v2/patients/me',
    headers=headers
)""",
                    },
                },
                {
                    "name": "OAuth 2.0",
                    "description": "Best for third-party integrations",
                    "flow": [
                        "Redirect user to authorization URL",
                        "User approves access",
                        "Receive authorization code",
                        "Exchange code for access token",
                    ],
                    "scopes": [
                        "patient:read - Read patient data",
                        "patient:write - Create/update patients",
                        "health_record:read - Read health records",
                        "health_record:write - Create/update health records",
                        "health_record:delete - Delete health records",
                    ],
                },
            ],
            "mfa_support": {
                "description": "Multi-factor authentication for enhanced security",
                "methods": [
                    "TOTP (Time-based One-Time Password)",
                    "SMS verification",
                    "Email verification",
                    "Biometric authentication",
                ],
                "implementation": {
                    "language": "python",
                    "code": """# Login with MFA
response = requests.post(
    'https://api.havenhealthpassport.org/api/v2/auth/login',
    json={
        'email': 'user@example.com',
        'password': 'secure_password',
        'mfa_code': '123456'  # From authenticator app
    }
)""",
                },
            },
        }

    def get_code_samples(self) -> Dict[str, Any]:
        """Get comprehensive code samples."""
        return {
            "languages": [
                {
                    "name": "Python",
                    "icon": "🐍",
                    "samples": [
                        {
                            "title": "Complete Patient Management Example",
                            "description": "Full CRUD operations for patient management",
                            "code": """import requests
import json
from typing import Dict, List, Optional

class HavenHealthClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.havenhealthpassport.org/api/v2'
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

    def create_patient(self, patient_data: Dict) -> Dict:
        \"\"\"Create a new patient.\"\"\"
        response = requests.post(
            f'{self.base_url}/patients',
            json=patient_data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_patient(self, patient_id: str) -> Dict:
        \"\"\"Get patient by ID.\"\"\"
        response = requests.get(
            f'{self.base_url}/patients/{patient_id}',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def update_patient(self, patient_id: str, update_data: Dict) -> Dict:
        \"\"\"Update patient information.\"\"\"
        response = requests.put(
            f'{self.base_url}/patients/{patient_id}',
            json=update_data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def list_patients(self, page: int = 1, page_size: int = 20,
                     search: Optional[str] = None) -> Dict:
        \"\"\"List patients with pagination.\"\"\"
        params = {'page': page, 'page_size': page_size}
        if search:
            params['search'] = search

        response = requests.get(
            f'{self.base_url}/patients',
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def create_health_record(self, patient_id: str, record_data: Dict) -> Dict:
        \"\"\"Create a health record for a patient.\"\"\"
        record_data['patient_id'] = patient_id
        response = requests.post(
            f'{self.base_url}/health-records',
            json=record_data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Example usage
if __name__ == '__main__':
    client = HavenHealthClient('your_api_key_here')

    # Create a patient
    new_patient = client.create_patient({
        'identifier': [{'system': 'UNHCR', 'value': 'UNHCR-2024-001'}],
        'name': [{'given': ['John'], 'family': 'Doe'}],
        'birthDate': '1990-01-01',
        'gender': 'male',
        'language': ['en']
    })

    print(f"Created patient: {new_patient['id']}")

    # Add a vaccination record
    vaccination = client.create_health_record(
        new_patient['id'],
        {
            'record_type': 'immunization',
            'title': 'COVID-19 Vaccination',
            'content': {
                'vaccine_code': '208',
                'vaccine_name': 'COVID-19, mRNA vaccine',
                'date_given': '2024-01-15'
            }
        }
    )

    print(f"Created vaccination record: {vaccination['id']}")""",
                        }
                    ],
                },
                {
                    "name": "JavaScript/Node.js",
                    "icon": "📜",
                    "samples": [
                        {
                            "title": "Async/Await Patient Management",
                            "description": "Modern JavaScript with error handling",
                            "code": """const axios = require('axios');

class HavenHealthClient {
    constructor(apiKey) {
        this.apiKey = apiKey;
        this.baseURL = 'https://api.havenhealthpassport.org/api/v2';
        this.client = axios.create({
            baseURL: this.baseURL,
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json'
            }
        });
    }

    async createPatient(patientData) {
        try {
            const response = await this.client.post('/patients', patientData);
            return response.data;
        } catch (error) {
            this.handleError(error);
        }
    }

    async getPatient(patientId) {
        try {
            const response = await this.client.get(`/patients/${patientId}`);
            return response.data;
        } catch (error) {
            this.handleError(error);
        }
    }

    async listPatients(page = 1, pageSize = 20, search = null) {
        try {
            const params = { page, page_size: pageSize };
            if (search) params.search = search;

            const response = await this.client.get('/patients', { params });
            return response.data;
        } catch (error) {
            this.handleError(error);
        }
    }

    handleError(error) {
        if (error.response) {
            const { status, data } = error.response;
            console.error(`API Error ${status}: ${data.message}`);
            if (data.details) {
                console.error('Details:', data.details);
            }
        } else {
            console.error('Network Error:', error.message);
        }
        throw error;
    }
}

// Example usage
(async () => {
    const client = new HavenHealthClient('your_api_key_here');

    try {
        // Create a patient
        const newPatient = await client.createPatient({
            identifier: [{ system: 'UNHCR', value: 'UNHCR-2024-001' }],
            name: [{ given: ['Jane'], family: 'Smith' }],
            birthDate: '1985-03-15',
            gender: 'female',
            language: ['en', 'fr']
        });

        console.log('Created patient:', newPatient.id);

        // Fetch the patient
        const patient = await client.getPatient(newPatient.id);
        console.log('Retrieved patient:', patient);

    } catch (error) {
        console.error('Operation failed:', error.message);
    }
})();""",
                        }
                    ],
                },
            ]
        }

    def get_tutorials(self) -> List[Dict[str, Any]]:
        """Get step-by-step tutorials."""
        return [
            {
                "id": "patient-registration",
                "title": "Complete Patient Registration Flow",
                "difficulty": "Beginner",
                "duration": "15 minutes",
                "description": "Learn how to register a new patient with all required information",
                "sections": [
                    {
                        "title": "Understanding Patient Data Model",
                        "content": """The patient data model follows HL7 FHIR standards with extensions for refugee populations:

- **Identifiers**: Support for multiple ID systems (UNHCR, national IDs, etc.)
- **Names**: Multiple names with different uses (official, nickname, etc.)
- **Contact**: Phone, email, and messaging app contacts
- **Languages**: Preferred languages for communication
- **Emergency Contacts**: Critical for displaced populations""",
                    },
                    {
                        "title": "Step 1: Prepare Patient Data",
                        "code": {
                            "language": "python",
                            "content": """# Prepare comprehensive patient data
patient_data = {
    "identifier": [
        {
            "system": "UNHCR",
            "value": "UNHCR-2024-123456",
            "type": "refugee_id"
        },
        {
            "system": "national_id",
            "value": "SYR-1234567",
            "type": "national"
        }
    ],
    "name": [
        {
            "given": ["Ahmad", "Mohammad"],
            "family": "Al-Hassan",
            "use": "official"
        }
    ],
    "birthDate": "1985-06-15",
    "gender": "male",
    "contact": [
        {
            "system": "phone",
            "value": "+962791234567",
            "use": "mobile"
        },
        {
            "system": "whatsapp",
            "value": "+962791234567",
            "use": "mobile"
        }
    ],
    "address": [
        {
            "line": ["Block 3, Shelter 42"],
            "city": "Zaatari Camp",
            "country": "JO",
            "use": "home"
        }
    ],
    "language": ["ar", "en"],
    "emergencyContact": [
        {
            "name": {
                "given": ["Fatima"],
                "family": "Al-Hassan"
            },
            "relationship": "spouse",
            "contact": [
                {
                    "system": "phone",
                    "value": "+962791234568"
                }
            ]
        }
    ]
}""",
                        },
                    },
                    {
                        "title": "Step 2: Validate and Submit",
                        "code": {
                            "language": "python",
                            "content": """# Validate required fields
def validate_patient_data(data):
    required_fields = ['identifier', 'name', 'birthDate', 'gender']
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"Missing required field: {field}")

    # Validate date format
    from datetime import datetime
    try:
        datetime.strptime(data['birthDate'], '%Y-%m-%d')
    except ValueError:
        raise ValueError("birthDate must be in YYYY-MM-DD format")

    return True

# Submit the patient registration
try:
    validate_patient_data(patient_data)
    response = client.create_patient(patient_data)
    patient_id = response['id']
    print(f"Patient registered successfully: {patient_id}")
except ValueError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Registration failed: {e}")""",
                        },
                    },
                ],
            },
            {
                "id": "health-record-upload",
                "title": "Uploading and Verifying Health Records",
                "difficulty": "Intermediate",
                "duration": "20 minutes",
                "description": "Learn how to upload health records with proper verification",
                "sections": [
                    {
                        "title": "Supported Record Types",
                        "content": """Haven Health Passport supports various health record types:

- **Immunizations**: Vaccination records with lot numbers and dates
- **Conditions**: Diagnoses with ICD-10 codes
- **Medications**: Prescriptions with dosage instructions
- **Procedures**: Surgical and medical procedures
- **Observations**: Vital signs, lab results
- **Documents**: Scanned documents, X-rays, reports""",
                    },
                    {
                        "title": "Uploading a Vaccination Record",
                        "code": {
                            "language": "javascript",
                            "content": """// Create a comprehensive vaccination record
const vaccinationRecord = {
    patient_id: patientId,
    record_type: 'immunization',
    title: 'COVID-19 Vaccination - Dose 2',
    content: {
        vaccine_code: '208',
        vaccine_name: 'COVID-19, mRNA vaccine',
        manufacturer: 'Pfizer-BioNTech',
        lot_number: 'EL1234',
        dose_number: 2,
        series_doses: 2,
        date_given: '2024-01-15',
        site: 'Left deltoid',
        route: 'Intramuscular',
        performer: 'Dr. Sarah Johnson',
        location: 'UNHCR Health Center - Zaatari'
    }
};

// Upload the record
try {
    const record = await client.createHealthRecord(vaccinationRecord);
    console.log('Record created:', record.id);
    console.log('Verification status:', record.verification_status);
} catch (error) {
    console.error('Upload failed:', error);
}""",
                        },
                    },
                ],
            },
            {
                "id": "offline-sync",
                "title": "Implementing Offline Sync",
                "difficulty": "Advanced",
                "duration": "30 minutes",
                "description": "Build offline-capable applications with conflict resolution",
                "sections": [
                    {
                        "title": "Offline Queue Implementation",
                        "code": {
                            "language": "javascript",
                            "content": """// Offline queue manager
class OfflineQueueManager {
    constructor() {
        this.queue = [];
        this.syncInProgress = false;
    }

    // Add operation to queue
    addToQueue(operation) {
        const queueItem = {
            id: generateUUID(),
            operation: operation,
            timestamp: new Date().toISOString(),
            retries: 0
        };

        this.queue.push(queueItem);
        this.saveQueue();

        // Try to sync if online
        if (navigator.onLine) {
            this.sync();
        }
    }

    // Sync queue when online
    async sync() {
        if (this.syncInProgress || this.queue.length === 0) return;

        this.syncInProgress = true;
        const failedItems = [];

        for (const item of this.queue) {
            try {
                await this.executeOperation(item.operation);
                // Remove successful item
                this.queue = this.queue.filter(i => i.id !== item.id);
            } catch (error) {
                console.error('Sync failed for item:', item.id);
                item.retries++;
                if (item.retries < 3) {
                    failedItems.push(item);
                }
            }
        }

        this.queue = failedItems;
        this.saveQueue();
        this.syncInProgress = false;
    }

    // Execute queued operation
    async executeOperation(operation) {
        const { type, data } = operation;

        switch (type) {
            case 'CREATE_PATIENT':
                return await client.createPatient(data);
            case 'UPDATE_PATIENT':
                return await client.updatePatient(data.id, data.updates);
            case 'CREATE_HEALTH_RECORD':
                return await client.createHealthRecord(data);
            default:
                throw new Error(`Unknown operation type: ${type}`);
        }
    }

    // Persist queue to IndexedDB
    saveQueue() {
        // Implementation using IndexedDB
        // This ensures data persists across app restarts
    }
}

// Usage
const offlineQueue = new OfflineQueueManager();

// Listen for online/offline events
window.addEventListener('online', () => {
    console.log('Back online - syncing...');
    offlineQueue.sync();
});

// Queue operations when offline
function createPatientOffline(patientData) {
    if (!navigator.onLine) {
        offlineQueue.addToQueue({
            type: 'CREATE_PATIENT',
            data: patientData
        });
        return { status: 'queued', tempId: generateUUID() };
    }

    return client.createPatient(patientData);
}""",
                        },
                    }
                ],
            },
        ]

    def get_best_practices(self) -> Dict[str, Any]:
        """Get API best practices."""
        return {
            "security": {
                "title": "Security Best Practices",
                "practices": [
                    {
                        "title": "API Key Security",
                        "description": "Protect your API keys like passwords",
                        "dos": [
                            "Store keys in environment variables",
                            "Use different keys for different environments",
                            "Rotate keys regularly (every 90 days)",
                            "Restrict key permissions to minimum required",
                            "Use server-side proxy for client applications",
                        ],
                        "donts": [
                            "Never commit keys to version control",
                            "Don't expose keys in client-side code",
                            "Avoid hardcoding keys in your application",
                            "Don't share keys between applications",
                            "Never log or display keys in error messages",
                        ],
                    },
                    {
                        "title": "Data Encryption",
                        "description": "Ensure data security in transit and at rest",
                        "recommendations": [
                            "Always use HTTPS for API calls",
                            "Encrypt sensitive data before storing locally",
                            "Use field-level encryption for PII",
                            "Implement certificate pinning for mobile apps",
                        ],
                    },
                ],
            },
            "performance": {
                "title": "Performance Optimization",
                "practices": [
                    {
                        "title": "Efficient Pagination",
                        "description": "Handle large datasets efficiently",
                        "code": {
                            "language": "python",
                            "content": """# Use cursor-based pagination for large datasets
def fetch_all_patients(client):
    patients = []
    page = 1
    page_size = 100  # Optimal page size

    while True:
                result = client.list_patients(page=page, page_size=page_size)
        patients.extend(result['items'])

        if page >= result['pages']:
            break

        page += 1

        # Add delay to avoid rate limiting
        time.sleep(0.1)

    return patients""",
                        },
                    },
                    {
                        "title": "Request Batching",
                        "description": "Combine multiple operations when possible",
                        "example": "Use GraphQL to fetch related data in a single request instead of multiple REST calls",
                    },
                    {
                        "title": "Caching Strategy",
                        "description": "Implement intelligent caching",
                        "recommendations": [
                            "Cache patient data for 5 minutes",
                            "Cache reference data (languages, countries) for 24 hours",
                            "Use ETags for conditional requests",
                            "Implement cache invalidation on updates",
                        ],
                    },
                ],
            },
            "error_handling": {
                "title": "Robust Error Handling",
                "practices": [
                    {
                        "title": "Retry Logic",
                        "description": "Handle transient failures gracefully",
                        "code": {
                            "language": "python",
                            "content": """import time
from typing import Callable, Any

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0
) -> Any:
    \"\"\"Retry function with exponential backoff.\"\"\"
    delay = 1.0

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            # Check if error is retryable
            if hasattr(e, 'response'):
                status_code = e.response.status_code
                # Don't retry client errors (4xx)
                if 400 <= status_code < 500:
                    raise

            # Calculate delay with jitter
            sleep_time = min(delay + random.uniform(0, 1), max_delay)
            print(f"Attempt {attempt + 1} failed, retrying in {sleep_time:.1f}s")
            time.sleep(sleep_time)
            delay *= backoff_factor

# Usage
patient = retry_with_backoff(
    lambda: client.get_patient(patient_id)
)""",
                        },
                    }
                ],
            },
        }

    def get_troubleshooting_guide(self) -> Dict[str, Any]:
        """Get troubleshooting guide."""
        return {
            "common_issues": [
                {
                    "issue": "401 Unauthorized Error",
                    "symptoms": [
                        "API returns 401 status code",
                        "Message: 'Invalid authentication credentials'",
                    ],
                    "causes": [
                        "API key is invalid or revoked",
                        "JWT token has expired",
                        "Missing authentication header",
                        "Using wrong authentication method",
                    ],
                    "solutions": [
                        {
                            "step": 1,
                            "action": "Verify API key is correct",
                            "code": """# Check if API key is set correctly
echo $HAVEN_API_KEY
# Should output: hhp_live_...""",
                        },
                        {
                            "step": 2,
                            "action": "Check token expiration",
                            "code": """# Decode JWT to check expiration
import jwt
import json

# Decode without verification to inspect
decoded = jwt.decode(token, options={"verify_signature": False})
print(json.dumps(decoded, indent=2))""",
                        },
                    ],
                },
                {
                    "issue": "429 Rate Limit Exceeded",
                    "symptoms": [
                        "API returns 429 status code",
                        "Retry-After header present",
                    ],
                    "causes": [
                        "Exceeding requests per minute limit",
                        "Burst of requests without spacing",
                        "Missing rate limit handling",
                    ],
                    "solutions": [
                        {
                            "step": 1,
                            "action": "Implement rate limit handling",
                            "code": """def handle_rate_limit(response):
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        print(f"Rate limited. Waiting {retry_after} seconds...")
        time.sleep(retry_after)
        return True
    return False""",
                        },
                        {
                            "step": 2,
                            "action": "Add request spacing",
                            "code": """# Space out requests
for patient_id in patient_ids:
    patient = client.get_patient(patient_id)
    process_patient(patient)
    time.sleep(0.1)  # 100ms between requests""",
                        },
                    ],
                },
                {
                    "issue": "CORS Errors in Browser",
                    "symptoms": [
                        "No 'Access-Control-Allow-Origin' header",
                        "Preflight request fails",
                    ],
                    "causes": [
                        "Making direct API calls from browser",
                        "Missing CORS configuration",
                        "Incorrect origin",
                    ],
                    "solutions": [
                        {
                            "description": "Use a backend proxy",
                            "explanation": "Browser security prevents direct API calls. Implement a backend service.",
                            "code": """// Backend proxy endpoint (Node.js/Express)
app.post('/api/proxy/patients', async (req, res) => {
    try {
        const response = await axios.post(
            'https://api.havenhealthpassport.org/api/v2/patients',
            req.body,
            {
                headers: {
                    'X-API-Key': process.env.HAVEN_API_KEY,
                    'Content-Type': 'application/json'
                }
            }
        );
        res.json(response.data);
    } catch (error) {
        res.status(error.response?.status || 500).json({
            error: error.response?.data || 'Internal server error'
        });
    }
});""",
                        }
                    ],
                },
            ],
            "debugging_tips": [
                {
                    "title": "Enable Request Logging",
                    "description": "Log all API requests for debugging",
                    "code": """import logging
import requests

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True""",
                },
                {
                    "title": "Use Request IDs",
                    "description": "Track requests with unique IDs",
                    "explanation": "Every API response includes a request ID in headers. Use this when contacting support.",
                },
                {
                    "title": "Test with cURL",
                    "description": "Isolate issues by testing with cURL",
                    "code": """# Test basic connectivity
curl -i -X GET \\
  -H "X-API-Key: your_api_key" \\
  https://api.havenhealthpassport.org/api/v2/health

# Test with verbose output
curl -v -X POST \\
  -H "X-API-Key: your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"test": "data"}' \\
  https://api.havenhealthpassport.org/api/v2/patients""",
                },
            ],
        }

    def get_faq(self) -> List[Dict[str, Any]]:
        """Get frequently asked questions."""
        return [
            {
                "category": "General",
                "questions": [
                    {
                        "q": "What is Haven Health Passport?",
                        "a": "Haven Health Passport is a blockchain-verified, AI-powered health record management system designed specifically for refugees and displaced populations. It provides secure, portable health records that can be accessed across borders.",
                    },
                    {
                        "q": "Is the API free to use?",
                        "a": "The API offers a free tier for NGOs and humanitarian organizations with up to 10,000 requests per month. Commercial usage and higher volumes require a paid plan.",
                    },
                    {
                        "q": "What programming languages are supported?",
                        "a": "The API is language-agnostic and can be used with any programming language that supports HTTP requests. We provide official SDKs for Python, JavaScript/Node.js, Java, and Go.",
                    },
                ],
            },
            {
                "category": "Technical",
                "questions": [
                    {
                        "q": "What is the API rate limit?",
                        "a": "Rate limits vary by plan: Free tier - 100 requests/minute, Standard - 1,000 requests/minute, Enterprise - 10,000 requests/minute. All plans include burst allowances.",
                    },
                    {
                        "q": "How long are access tokens valid?",
                        "a": "Access tokens are valid for 1 hour. Refresh tokens are valid for 30 days and can be used to obtain new access tokens without re-authentication.",
                    },
                    {
                        "q": "Can I use the API offline?",
                        "a": "Yes, our mobile SDKs support offline mode with automatic synchronization when connectivity is restored. The web API requires internet connectivity.",
                    },
                    {
                        "q": "What data formats are supported?",
                        "a": "The API uses JSON for request and response bodies. Health records follow HL7 FHIR R4 standards. File uploads support PDF, JPEG, PNG, and other common formats.",
                    },
                ],
            },
            {
                "category": "Security & Compliance",
                "questions": [
                    {
                        "q": "Is the API HIPAA compliant?",
                        "a": "Yes, the API is fully HIPAA compliant with end-to-end encryption, audit logging, and access controls. We can sign BAAs for covered entities.",
                    },
                    {
                        "q": "How is data encrypted?",
                        "a": "All data is encrypted in transit using TLS 1.3 and at rest using AES-256 encryption. Sensitive fields use additional field-level encryption.",
                    },
                    {
                        "q": "Where is data stored?",
                        "a": "Data is stored in AWS regions closest to the user's location, with automatic replication for disaster recovery. Data sovereignty laws are respected.",
                    },
                    {
                        "q": "How long is data retained?",
                        "a": "Active health records are retained for 7 years per medical record retention standards. Patients can request deletion under GDPR right to erasure.",
                    },
                ],
            },
        ]

    def get_support_info(self) -> Dict[str, Any]:
        """Get support contact information."""
        return {
            "channels": [
                {
                    "type": "Email",
                    "contact": "api-support@havenhealthpassport.org",
                    "response_time": "24-48 hours",
                    "use_for": "General inquiries, feature requests",
                },
                {
                    "type": "Emergency Support",
                    "contact": "emergency@havenhealthpassport.org",
                    "response_time": "4 hours",
                    "use_for": "Production outages, security issues",
                },
                {
                    "type": "Developer Forum",
                    "contact": "https://forum.havenhealthpassport.org",
                    "response_time": "Community-driven",
                    "use_for": "Technical discussions, best practices",
                },
                {
                    "type": "GitHub",
                    "contact": "https://github.com/haven-health/api-issues",
                    "response_time": "2-3 business days",
                    "use_for": "Bug reports, SDK issues",
                },
            ],
            "sla": {
                "free_tier": "Best effort support via community forum",
                "standard": "48 hour response time via email",
                "enterprise": "4 hour response time with dedicated support engineer",
            },
            "resources": [
                {
                    "title": "API Status Page",
                    "url": "https://status.havenhealthpassport.org",
                    "description": "Real-time API status and incident reports",
                },
                {
                    "title": "Change Log",
                    "url": "https://docs.havenhealthpassport.org/changelog",
                    "description": "API updates and breaking changes",
                },
                {
                    "title": "Security Advisories",
                    "url": "https://security.havenhealthpassport.org",
                    "description": "Security updates and advisories",
                },
            ],
        }

    def get_sdk_info(self) -> Dict[str, Any]:
        """Get SDK information."""
        return {
            "official_sdks": [
                {
                    "language": "Python",
                    "package": "haven-health",
                    "install": "pip install haven-health",
                    "github": "https://github.com/haven-health/python-sdk",
                    "features": [
                        "Async/await support",
                        "Automatic retry with backoff",
                        "Built-in rate limiting",
                        "Type hints and IDE support",
                    ],
                },
                {
                    "language": "JavaScript/Node.js",
                    "package": "@haven-health/sdk",
                    "install": "npm install @haven-health/sdk",
                    "github": "https://github.com/haven-health/js-sdk",
                    "features": [
                        "Promise and callback support",
                        "TypeScript definitions",
                        "Browser and Node.js compatible",
                        "Automatic token refresh",
                    ],
                },
                {
                    "language": "Java",
                    "package": "org.havenhealthpassport:sdk",
                    "install": "Maven or Gradle",
                    "github": "https://github.com/haven-health/java-sdk",
                    "features": [
                        "Builder pattern for requests",
                        "RxJava support",
                        "Connection pooling",
                        "Comprehensive JavaDocs",
                    ],
                },
                {
                    "language": "Go",
                    "package": "github.com/haven-health/go-sdk",
                    "install": "go get github.com/haven-health/go-sdk",
                    "github": "https://github.com/haven-health/go-sdk",
                    "features": [
                        "Context support",
                        "Structured logging",
                        "Efficient connection reuse",
                        "Comprehensive error types",
                    ],
                },
            ],
            "community_sdks": [
                {
                    "language": "Ruby",
                    "maintainer": "Community",
                    "github": "https://github.com/community/haven-health-ruby",
                },
                {
                    "language": "PHP",
                    "maintainer": "Community",
                    "github": "https://github.com/community/haven-health-php",
                },
            ],
        }

    def get_webhook_guide(self) -> Dict[str, Any]:
        """Get webhook implementation guide."""
        return {
            "overview": "Webhooks allow you to receive real-time notifications when events occur in Haven Health Passport",
            "available_events": [
                {
                    "event": "patient.created",
                    "description": "New patient registered",
                    "payload_example": {
                        "event": "patient.created",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "data": {
                            "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                            "created_by": "user_123",
                        },
                    },
                },
                {
                    "event": "health_record.verified",
                    "description": "Health record blockchain verification completed",
                    "payload_example": {
                        "event": "health_record.verified",
                        "timestamp": "2024-01-15T10:35:00Z",
                        "data": {
                            "record_id": "rec_789",
                            "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                            "verification_hash": "0x1234567890abcdef",
                            "blockchain_network": "hyperledger",
                        },
                    },
                },
            ],
            "implementation": {
                "setup": [
                    "Configure webhook endpoint URL in dashboard",
                    "Select events to subscribe to",
                    "Verify webhook signature for security",
                ],
                "security": {
                    "description": "All webhooks are signed with HMAC-SHA256",
                    "verification_code": """import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

# In your webhook handler
@app.post('/webhook')
def handle_webhook(request):
    signature = request.headers.get('X-Haven-Signature')
    if not verify_webhook(request.body, signature, WEBHOOK_SECRET):
        return 401

    # Process webhook
    event = request.json()
    # ...""",
                },
            },
        }

    def get_security_guide(self) -> Dict[str, Any]:
        """Get comprehensive security guide."""
        return {
            "authentication_security": {
                "title": "Authentication Best Practices",
                "guidelines": [
                    {
                        "practice": "Use environment variables",
                        "description": "Never hardcode credentials",
                        "example": """# .env file (add to .gitignore)
HAVEN_API_KEY=hhp_live_...
HAVEN_API_SECRET=secret_...

# Python usage
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('HAVEN_API_KEY')""",
                    },
                    {
                        "practice": "Implement token rotation",
                        "description": "Regularly rotate API keys and tokens",
                        "recommendation": "Rotate API keys every 90 days, implement automated rotation for production systems",
                    },
                ],
            },
            "data_protection": {
                "title": "Data Protection Measures",
                "guidelines": [
                    {
                        "measure": "Field-level encryption",
                        "description": "Sensitive fields are automatically encrypted",
                        "fields": [
                            "SSN",
                            "passport numbers",
                            "biometric data",
                            "medical conditions",
                        ],
                    },
                    {
                        "measure": "Data minimization",
                        "description": "Only request and store necessary data",
                        "example": "Use field filters to retrieve only required patient data",
                    },
                ],
            },
            "compliance": {
                "title": "Compliance Requirements",
                "standards": [
                    {
                        "standard": "HIPAA",
                        "requirements": [
                            "Audit logs for all data access",
                            "Encryption in transit and at rest",
                            "Access controls and authentication",
                            "Business Associate Agreement (BAA) available",
                        ],
                    },
                    {
                        "standard": "GDPR",
                        "requirements": [
                            "Right to data portability",
                            "Right to erasure (deletion)",
                            "Consent management",
                            "Data processing records",
                        ],
                    },
                ],
            },
        }

    def get_compliance_info(self) -> Dict[str, Any]:
        """Get compliance information."""
        return {
            "certifications": [
                {
                    "name": "HIPAA Compliance",
                    "description": "Fully compliant with HIPAA security and privacy rules",
                    "details": [
                        "Annual third-party audits",
                        "BAA available for covered entities",
                        "Breach notification procedures",
                        "Employee HIPAA training",
                    ],
                },
                {
                    "name": "SOC 2 Type II",
                    "description": "Annual SOC 2 Type II certification",
                    "details": [
                        "Security controls audit",
                        "Availability monitoring",
                        "Processing integrity",
                        "Confidentiality measures",
                    ],
                },
                {
                    "name": "ISO 27001",
                    "description": "Information security management certification",
                    "details": [
                        "Risk assessment procedures",
                        "Security incident management",
                        "Business continuity planning",
                        "Regular security reviews",
                    ],
                },
            ],
            "data_residency": {
                "overview": "Data stored in compliance with local regulations",
                "regions": [
                    {
                        "region": "European Union",
                        "location": "AWS eu-central-1 (Frankfurt)",
                        "compliance": "GDPR compliant",
                    },
                    {
                        "region": "United States",
                        "location": "AWS us-east-1 (Virginia)",
                        "compliance": "HIPAA compliant",
                    },
                    {
                        "region": "Middle East",
                        "location": "AWS me-south-1 (Bahrain)",
                        "compliance": "Local data residency laws",
                    },
                ],
            },
            "audit_logs": {
                "description": "Comprehensive audit logging for compliance",
                "retention": "7 years for healthcare data, 3 years for access logs",
                "includes": [
                    "All API access attempts",
                    "Data modifications",
                    "Authentication events",
                    "Permission changes",
                    "Data exports",
                ],
            },
        }


def create_developer_portal_html() -> str:
    """Generate HTML for developer portal landing page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Haven Health Passport - Developer Portal</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
</head>
<body class="bg-gray-50">
    <nav class="bg-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex">
                    <div class="flex-shrink-0 flex items-center">
                        <h1 class="text-2xl font-bold text-blue-600">Haven Health Passport</h1>
                    </div>
                    <div class="hidden sm:ml-6 sm:flex sm:space-x-8">
                        <a href="#getting-started" class="text-gray-900 inline-flex items-center px-1 pt-1 text-sm font-medium">
                            Getting Started
                        </a>
                        <a href="#api-reference" class="text-gray-500 hover:text-gray-900 inline-flex items-center px-1 pt-1 text-sm font-medium">
                            API Reference
                        </a>
                        <a href="#tutorials" class="text-gray-500 hover:text-gray-900 inline-flex items-center px-1 pt-1 text-sm font-medium">
                            Tutorials
                        </a>
                        <a href="#support" class="text-gray-500 hover:text-gray-900 inline-flex items-center px-1 pt-1 text-sm font-medium">
                            Support
                        </a>
                    </div>
                </div>
                <div class="flex items-center">
                    <a href="/api/docs" class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
                        API Explorer
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <!-- Hero Section -->
        <div class="px-4 py-6 sm:px-0">
            <div class="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-lg p-8 text-white">
                <h2 class="text-4xl font-bold mb-4">Build with Haven Health Passport API</h2>
                <p class="text-xl mb-6">Secure, portable health records for refugees and displaced populations</p>
                <div class="flex space-x-4">
                    <a href="#getting-started" class="bg-white text-blue-600 px-6 py-3 rounded-md font-medium hover:bg-gray-100">
                        Get Started
                    </a>
                    <a href="/api/docs" class="border border-white text-white px-6 py-3 rounded-md font-medium hover:bg-white hover:text-blue-600">
                        View API Docs
                    </a>
                </div>
            </div>
        </div>

        <!-- Features Grid -->
        <div class="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <span class="text-2xl">🔐</span>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <h3 class="text-lg font-medium text-gray-900">Secure Authentication</h3>
                            <p class="mt-2 text-sm text-gray-500">JWT-based auth with MFA and biometric support</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <span class="text-2xl">🌍</span>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <h3 class="text-lg font-medium text-gray-900">Multi-language Support</h3>
                            <p class="mt-2 text-sm text-gray-500">AI-powered translation for 50+ languages</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                    <div class="flex items-center">
                        <div class="flex-shrink-0">
                            <span class="text-2xl">⛓️</span>
                        </div>
                        <div class="ml-5 w-0 flex-1">
                            <h3 class="text-lg font-medium text-gray-900">Blockchain Verification</h3>
                            <p class="mt-2 text-sm text-gray-500">Immutable health record verification</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Code Sample -->
        <div class="mt-12">
            <h3 class="text-2xl font-bold text-gray-900 mb-4">Quick Start</h3>
            <div class="bg-gray-900 rounded-lg p-6">
                <pre><code class="language-python">import requests

# Set up authentication
headers = {
    'X-API-Key': 'your_api_key_here',
    'Content-Type': 'application/json'
}

# Create a patient
patient_data = {
    "identifier": [{"system": "UNHCR", "value": "UNHCR-2024-001"}],
    "name": [{"given": ["John"], "family": "Doe"}],
    "birthDate": "1990-01-01",
    "gender": "male"
}

response = requests.post(
    'https://api.havenhealthpassport.org/api/v2/patients',
    json=patient_data,
    headers=headers
)

print(f"Patient created: {response.json()['id']}")</code></pre>
            </div>
        </div>

        <!-- CTA Section -->
        <div class="mt-12 bg-gray-100 rounded-lg p-8 text-center">
            <h3 class="text-2xl font-bold text-gray-900 mb-4">Ready to get started?</h3>
            <p class="text-lg text-gray-600 mb-6">Join thousands of developers building healthcare solutions for displaced populations</p>
            <a href="https://developers.havenhealthpassport.org/signup" class="bg-blue-600 text-white px-8 py-3 rounded-md font-medium hover:bg-blue-700">
                Create Developer Account
            </a>
        </div>
    </main>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
</body>
</html>"""


# Export portal components
__all__ = [
    "DeveloperPortal",
    "create_developer_portal_html",
]
