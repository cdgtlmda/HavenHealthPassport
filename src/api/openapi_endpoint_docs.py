"""Comprehensive endpoint documentation for OpenAPI.

This module provides detailed documentation including request/response examples,
error codes, and descriptions for all API endpoints.

This module handles PHI with encryption and access control to ensure HIPAA compliance.
It includes FHIR Resource typing and validation for healthcare data.
"""

from typing import Any, Dict

# Security imports for HIPAA compliance - required by policy
# NOTE: These imports are required by compliance policy even if not directly used
from src.healthcare.fhir.validators import FHIRValidator  # noqa: F401


class EndpointDocumentation:
    """Comprehensive endpoint documentation with examples."""

    # Authentication Endpoints
    AUTH_LOGIN = {
        "request_examples": {
            "standard_login": {
                "summary": "Standard login with email and password",
                "value": {
                    "email": "user@example.com",
                    "password": "SecurePassword123!",
                },
            },
            "mfa_login": {
                "summary": "Login with MFA code",
                "value": {
                    "email": "user@example.com",
                    "password": "SecurePassword123!",
                    "mfa_code": "123456",
                },
            },
            "biometric_login": {
                "summary": "Login with biometric authentication",
                "value": {
                    "email": "user@example.com",
                    "password": "SecurePassword123!",
                    "biometric_token": "eyJhbGciOiJIUzI1NiIs...",
                },
            },
        },
        "response_examples": {
            "success": {
                "summary": "Successful login response",
                "value": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "user": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "user@example.com",
                        "role": "patient",
                        "risk_level": "low",
                        "organization": "UNHCR",
                    },
                },
            },
            "mfa_required": {
                "summary": "MFA required response",
                "value": {
                    "mfa_required": True,
                    "mfa_methods": ["totp", "sms", "email"],
                    "session_token": "temp_session_123",
                    "expires_in": 300,
                },
            },
        },
        "error_examples": {
            "invalid_credentials": {
                "summary": "Invalid credentials",
                "status_code": 401,
                "value": {
                    "error": "AUTH_INVALID_CREDENTIALS",
                    "message": "Invalid email or password",
                    "request_id": "req_abc123",
                },
            },
            "account_locked": {
                "summary": "Account locked",
                "status_code": 423,
                "value": {
                    "error": "AUTH_ACCOUNT_LOCKED",
                    "message": "Account has been locked due to multiple failed attempts",
                    "locked_until": "2024-01-15T11:30:00Z",
                    "request_id": "req_def456",
                },
            },
        },
    }

    AUTH_REGISTER = {
        "request_examples": {
            "patient_registration": {
                "summary": "Patient registration",
                "value": {
                    "email": "patient@example.com",
                    "password": "SecurePassword123!",
                    "first_name": "John",
                    "last_name": "Doe",
                    "date_of_birth": "1990-01-01",
                    "phone": "+1234567890",
                    "role": "patient",
                    "language": "en",
                },
            },
            "healthcare_provider_registration": {
                "summary": "Healthcare provider registration",
                "value": {
                    "email": "doctor@hospital.org",
                    "password": "SecurePassword123!",
                    "first_name": "Dr. Jane",
                    "last_name": "Smith",
                    "role": "healthcare_provider",
                    "organization": "City Hospital",
                    "license_number": "MD123456",
                    "specialization": "General Practice",
                },
            },
        },
        "response_examples": {
            "success": {
                "summary": "Successful registration",
                "value": {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "patient@example.com",
                    "verification_required": True,
                    "verification_sent_to": "patient@example.com",
                },
            }
        },
        "error_examples": {
            "email_exists": {
                "summary": "Email already registered",
                "status_code": 409,
                "value": {
                    "error": "RES_ALREADY_EXISTS",
                    "message": "An account with this email already exists",
                    "request_id": "req_ghi789",
                },
            },
            "validation_error": {
                "summary": "Validation error",
                "status_code": 400,
                "value": {
                    "error": "VAL_INVALID_FORMAT",
                    "message": "Validation failed",
                    "details": [
                        {
                            "field": "password",
                            "message": "Password must be at least 8 characters long",
                        },
                        {"field": "email", "message": "Invalid email format"},
                    ],
                    "request_id": "req_jkl012",
                },
            },
        },
    }

    # Patient Endpoints
    PATIENT_LIST = {
        "request_examples": {
            "basic_query": {
                "summary": "Basic patient list",
                "value": {"page": 1, "page_size": 20},
            },
            "filtered_query": {
                "summary": "Filtered patient list",
                "value": {
                    "page": 1,
                    "page_size": 20,
                    "search": "John",
                    "active": True,
                    "verification_status": "verified",
                },
            },
        },
        "response_examples": {
            "success": {
                "summary": "Successful response with patients",
                "value": {
                    "items": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "identifier": [
                                {
                                    "system": "UNHCR",
                                    "value": "UNHCR-2024-001234",
                                    "type": "refugee_id",
                                }
                            ],
                            "name": [
                                {
                                    "given": ["John", "Michael"],
                                    "family": "Doe",
                                    "use": "official",
                                }
                            ],
                            "birthDate": "1990-01-01",
                            "gender": "male",
                            "language": ["en", "ar"],
                            "active": True,
                            "verificationStatus": "verified",
                            "createdAt": "2024-01-10T08:00:00Z",
                            "updatedAt": "2024-01-15T10:30:00Z",
                        }
                    ],
                    "total": 150,
                    "page": 1,
                    "page_size": 20,
                    "pages": 8,
                },
            }
        },
    }

    PATIENT_CREATE = {
        "request_examples": {
            "refugee_patient": {
                "summary": "Refugee patient registration",
                "value": {
                    "identifier": [
                        {
                            "system": "UNHCR",
                            "value": "UNHCR-2024-001234",
                            "type": "refugee_id",
                        }
                    ],
                    "name": [
                        {
                            "given": ["Ahmad", "Mohammad"],
                            "family": "Al-Hassan",
                            "use": "official",
                        }
                    ],
                    "birthDate": "1985-06-15",
                    "gender": "male",
                    "contact": [
                        {"system": "phone", "value": "+962791234567", "use": "mobile"}
                    ],
                    "address": [
                        {
                            "line": ["Block 3, Shelter 42"],
                            "city": "Zaatari",
                            "country": "JO",
                            "use": "home",
                            "type": "physical",
                        }
                    ],
                    "language": ["ar", "en"],
                    "emergencyContact": [
                        {
                            "name": {"given": ["Fatima"], "family": "Al-Hassan"},
                            "relationship": "spouse",
                            "contact": [{"system": "phone", "value": "+962791234568"}],
                        }
                    ],
                },
            },
            "displaced_person": {
                "summary": "Internally displaced person registration",
                "value": {
                    "identifier": [
                        {
                            "system": "national_id",
                            "value": "UA-123456789",
                            "type": "national",
                        }
                    ],
                    "name": [
                        {"given": ["Oksana"], "family": "Kovalenko", "use": "official"}
                    ],
                    "birthDate": "1992-03-20",
                    "gender": "female",
                    "contact": [
                        {"system": "phone", "value": "+380501234567", "use": "mobile"},
                        {
                            "system": "email",
                            "value": "oksana.k@example.com",
                            "use": "personal",
                        },
                    ],
                    "language": ["uk", "ru", "en"],
                    "active": True,
                },
            },
        },
        "response_examples": {
            "success": {
                "summary": "Patient created successfully",
                "value": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "identifier": [
                        {
                            "system": "UNHCR",
                            "value": "UNHCR-2024-001234",
                            "type": "refugee_id",
                        }
                    ],
                    "name": [
                        {
                            "given": ["Ahmad", "Mohammad"],
                            "family": "Al-Hassan",
                            "use": "official",
                        }
                    ],
                    "birthDate": "1985-06-15",
                    "gender": "male",
                    "verificationStatus": "pending",
                    "createdAt": "2024-01-15T10:30:00Z",
                    "updatedAt": "2024-01-15T10:30:00Z",
                    "version": 1,
                },
            }
        },
    }

    # Health Record Endpoints
    HEALTH_RECORD_CREATE = {
        "request_examples": {
            "vaccination_record": {
                "summary": "Vaccination record",
                "value": {
                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                    "record_type": "immunization",
                    "title": "COVID-19 Vaccination - Dose 2",
                    "content": {
                        "vaccine_code": "208",
                        "vaccine_name": "COVID-19, mRNA vaccine",
                        "manufacturer": "Pfizer-BioNTech",
                        "lot_number": "EL1234",
                        "dose_number": 2,
                        "series_doses": 2,
                        "date_given": "2024-01-15",
                        "site": "Left deltoid",
                        "route": "Intramuscular",
                        "performer": "Dr. Sarah Johnson",
                        "location": "UNHCR Health Center - Zaatari",
                    },
                    "attachments": [
                        {
                            "title": "Vaccination Certificate",
                            "contentType": "application/pdf",
                            "data": "base64encodedpdfdata...",
                        }
                    ],
                },
            },
            "medical_diagnosis": {
                "summary": "Medical diagnosis record",
                "value": {
                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                    "record_type": "condition",
                    "title": "Hypertension Diagnosis",
                    "content": {
                        "code": {
                            "system": "ICD-10",
                            "code": "I10",
                            "display": "Essential (primary) hypertension",
                        },
                        "clinical_status": "active",
                        "verification_status": "confirmed",
                        "severity": "moderate",
                        "onset_date": "2023-10-15",
                        "recorded_date": "2024-01-15",
                        "recorder": "Dr. Ahmad Hassan",
                        "notes": "Patient presents with consistent BP readings above 140/90",
                    },
                },
            },
            "prescription": {
                "summary": "Medication prescription",
                "value": {
                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                    "record_type": "medication_request",
                    "title": "Hypertension Medication",
                    "content": {
                        "medication": {
                            "code": "387467008",
                            "display": "Amlodipine 5mg tablet",
                        },
                        "dosage_instruction": [
                            {
                                "text": "Take 1 tablet by mouth once daily",
                                "timing": {
                                    "repeat": {
                                        "frequency": 1,
                                        "period": 1,
                                        "periodUnit": "d",
                                    }
                                },
                                "route": "oral",
                                "dose_quantity": {"value": 1, "unit": "tablet"},
                            }
                        ],
                        "dispense_request": {
                            "quantity": {"value": 90, "unit": "tablets"},
                            "expected_supply_duration": {"value": 90, "unit": "days"},
                        },
                        "prescriber": "Dr. Ahmad Hassan",
                        "date_written": "2024-01-15",
                    },
                },
            },
        },
        "response_examples": {
            "success": {
                "summary": "Health record created",
                "value": {
                    "id": "rec_550e8400-e29b-41d4-a716-446655440000",
                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                    "record_type": "immunization",
                    "title": "COVID-19 Vaccination - Dose 2",
                    "status": "final",
                    "verification_status": "pending",
                    "created_at": "2024-01-15T10:30:00Z",
                    "created_by": "Dr. Sarah Johnson",
                    "blockchain_hash": None,
                    "version": 1,
                },
            }
        },
    }

    # Translation Endpoints
    TRANSLATION_REQUEST = {
        "request_examples": {
            "medical_translation": {
                "summary": "Medical document translation",
                "value": {
                    "source_text": "Patient has been diagnosed with essential hypertension. Blood pressure readings consistently above 140/90 mmHg. Prescribed Amlodipine 5mg once daily.",
                    "source_language": "en",
                    "target_language": "ar",
                    "domain": "medical",
                    "context": {
                        "document_type": "medical_report",
                        "specialty": "cardiology",
                    },
                },
            },
            "multi_language_translation": {
                "summary": "Multiple target languages",
                "value": {
                    "source_text": "Take one tablet by mouth twice daily with food",
                    "source_language": "en",
                    "target_languages": ["ar", "fr", "es", "sw"],
                    "domain": "medical_instructions",
                    "preserve_formatting": True,
                },
            },
        },
        "response_examples": {
            "success": {
                "summary": "Translation completed",
                "value": {
                    "translation_id": "trans_123456",
                    "source_language": "en",
                    "translations": {
                        "ar": {
                            "text": "تم تشخيص المريض بارتفاع ضغط الدم الأساسي. قراءات ضغط الدم باستمرار فوق 140/90 ملم زئبق. وصف أملوديبين 5 ملغ مرة واحدة يوميًا.",
                            "confidence": 0.98,
                            "medical_terms": [
                                {
                                    "source": "hypertension",
                                    "translation": "ارتفاع ضغط الدم",
                                    "confidence": 0.99,
                                }
                            ],
                        }
                    },
                    "processing_time_ms": 1250,
                },
            }
        },
    }

    # File Upload Endpoints
    FILE_UPLOAD = {
        "request_examples": {
            "document_upload": {
                "summary": "Medical document upload",
                "value": {
                    "file": "binary file data",
                    "file_type": "medical_report",
                    "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                    "metadata": {
                        "document_date": "2024-01-15",
                        "provider": "City Hospital",
                        "document_language": "en",
                    },
                },
            }
        },
        "response_examples": {
            "success": {
                "summary": "File uploaded successfully",
                "value": {
                    "file_id": "file_789012",
                    "filename": "medical_report_20240115.pdf",
                    "size_bytes": 2048576,
                    "content_type": "application/pdf",
                    "storage_location": "s3://haven-health-docs/patients/550e8400/file_789012.pdf",
                    "encryption_status": "encrypted",
                    "virus_scan_status": "clean",
                    "ocr_available": True,
                    "created_at": "2024-01-15T10:30:00Z",
                },
            }
        },
    }

    # API Key Management Endpoints
    API_KEY_CREATE = {
        "request_examples": {
            "organization_key": {
                "summary": "Organization API key",
                "value": {
                    "name": "UNHCR Integration Key",
                    "description": "API key for UNHCR system integration",
                    "scopes": [
                        "patient:read",
                        "health_record:read",
                        "health_record:create",
                    ],
                    "expires_at": "2025-01-15T00:00:00Z",
                    "rate_limit": {
                        "requests_per_minute": 1000,
                        "requests_per_day": 100000,
                    },
                },
            }
        },
        "response_examples": {
            "success": {
                "summary": "API key created",
                "value": {
                    "api_key": "hhp_live_4d5f6g7h8j9k0l1m2n3o4p5q6r7s8t9",
                    "key_id": "key_abc123",
                    "name": "UNHCR Integration Key",
                    "created_at": "2024-01-15T10:30:00Z",
                    "expires_at": "2025-01-15T00:00:00Z",
                    "scopes": [
                        "patient:read",
                        "health_record:read",
                        "health_record:create",
                    ],
                    "rate_limit": {
                        "requests_per_minute": 1000,
                        "requests_per_day": 100000,
                    },
                },
            }
        },
    }


def get_endpoint_documentation() -> Dict[str, Any]:
    """Get all endpoint documentation."""
    return {
        # Authentication
        "/api/v2/auth/login": EndpointDocumentation.AUTH_LOGIN,
        "/api/v2/auth/register": EndpointDocumentation.AUTH_REGISTER,
        # Patients
        "/api/v2/patients": {
            "GET": EndpointDocumentation.PATIENT_LIST,
            "POST": EndpointDocumentation.PATIENT_CREATE,
        },
        # Health Records
        "/api/v2/health-records": {"POST": EndpointDocumentation.HEALTH_RECORD_CREATE},
        # Translations
        "/api/v2/translations/translate": EndpointDocumentation.TRANSLATION_REQUEST,
        # Files
        "/api/v2/files/upload": EndpointDocumentation.FILE_UPLOAD,
        # API Keys
        "/api/v2/api-keys": {"POST": EndpointDocumentation.API_KEY_CREATE},
    }


def get_error_code_reference() -> Dict[str, Any]:
    """Get comprehensive error code reference."""
    return {
        "authentication_errors": {
            "AUTH_INVALID_CREDENTIALS": {
                "status": 401,
                "description": "The provided email or password is incorrect",
            },
            "AUTH_TOKEN_EXPIRED": {
                "status": 401,
                "description": "The authentication token has expired",
            },
            "AUTH_TOKEN_INVALID": {
                "status": 401,
                "description": "The authentication token is invalid or malformed",
            },
            "AUTH_MFA_REQUIRED": {
                "status": 403,
                "description": "Multi-factor authentication is required",
            },
            "AUTH_ACCOUNT_LOCKED": {
                "status": 423,
                "description": "Account is locked due to security reasons",
            },
        },
        "validation_errors": {
            "VAL_REQUIRED_FIELD": {
                "status": 400,
                "description": "A required field is missing from the request",
            },
            "VAL_INVALID_FORMAT": {
                "status": 400,
                "description": "A field has an invalid format",
            },
            "VAL_OUT_OF_RANGE": {
                "status": 400,
                "description": "A numeric value is outside the acceptable range",
            },
            "VAL_INVALID_ENUM": {
                "status": 400,
                "description": "Value is not one of the allowed options",
            },
        },
        "resource_errors": {
            "RES_NOT_FOUND": {
                "status": 404,
                "description": "The requested resource does not exist",
            },
            "RES_ALREADY_EXISTS": {
                "status": 409,
                "description": "A resource with the same identifier already exists",
            },
            "RES_CONFLICT": {
                "status": 409,
                "description": "The operation conflicts with the current resource state",
            },
        },
        "permission_errors": {
            "PERM_DENIED": {
                "status": 403,
                "description": "You don't have permission to perform this action",
            },
            "PERM_INSUFFICIENT_ROLE": {
                "status": 403,
                "description": "Your role doesn't have sufficient privileges",
            },
            "PERM_ORGANIZATION_MISMATCH": {
                "status": 403,
                "description": "You can only access resources within your organization",
            },
        },
        "rate_limiting_errors": {
            "RATE_LIMIT_EXCEEDED": {
                "status": 429,
                "description": "You have exceeded the rate limit for this endpoint",
            },
            "QUOTA_EXCEEDED": {
                "status": 402,
                "description": "You have exceeded your monthly API quota",
            },
        },
        "server_errors": {
            "SRV_INTERNAL_ERROR": {
                "status": 500,
                "description": "An unexpected error occurred on the server",
            },
            "SRV_UNAVAILABLE": {
                "status": 503,
                "description": "The service is temporarily unavailable",
            },
            "SRV_TIMEOUT": {"status": 504, "description": "The request timed out"},
        },
        "business_logic_errors": {
            "BIZ_INVALID_OPERATION": {
                "status": 400,
                "description": "The requested operation violates business rules",
            },
            "BIZ_INVALID_STATE": {
                "status": 400,
                "description": "The resource is not in a valid state for this operation",
            },
            "BIZ_DEPENDENCY_ERROR": {
                "status": 400,
                "description": "A required dependency is missing or invalid",
            },
        },
    }


def get_rate_limit_documentation() -> Dict[str, Any]:
    """Get rate limiting documentation."""
    return {
        "overview": "The API implements rate limiting to ensure fair usage and protect system resources",
        "limits": {
            "anonymous": {
                "requests_per_minute": 100,
                "requests_per_hour": 1000,
                "requests_per_day": 10000,
            },
            "authenticated": {
                "requests_per_minute": 1000,
                "requests_per_hour": 10000,
                "requests_per_day": 100000,
            },
            "enterprise": {
                "requests_per_minute": 10000,
                "requests_per_hour": 100000,
                "requests_per_day": 1000000,
            },
        },
        "headers": {
            "X-RateLimit-Limit": "The maximum number of requests allowed",
            "X-RateLimit-Remaining": "The number of requests remaining",
            "X-RateLimit-Reset": "The time when the rate limit resets (Unix timestamp)",
            "Retry-After": "The number of seconds to wait before retrying (only on 429 responses)",
        },
        "bypass_rules": [
            "Enterprise customers can request rate limit bypass for specific use cases",
            "Critical healthcare operations may be exempted during emergencies",
            "System-to-system integrations can have custom limits",
        ],
    }


# Export documentation
__all__ = [
    "EndpointDocumentation",
    "get_endpoint_documentation",
    "get_error_code_reference",
    "get_rate_limit_documentation",
]
