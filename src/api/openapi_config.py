"""OpenAPI documentation configuration for Haven Health Passport API.

This module configures and enhances the OpenAPI documentation with
detailed descriptions, examples, and custom schemas.
"""

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from src.api.constants import API_VERSION
from src.api.openapi_enhancements import (
    add_endpoint_examples,
    add_error_code_documentation,
    generate_api_changelog,
    generate_migration_guide,
)
from src.config import get_settings


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    settings = get_settings()

    openapi_schema = get_openapi(
        title="Haven Health Passport API",
        version=API_VERSION,
        description="""
# Haven Health Passport API

## Overview

Haven Health Passport is a blockchain-verified, AI-powered health record management system designed for displaced populations and refugees. This API provides secure access to health records, patient management, and verification services.

## Key Features

- 🔐 **Secure Authentication**: JWT-based authentication with MFA support
- 🌍 **Multi-language Support**: AI-powered translation for 50+ languages
- ⛓️ **Blockchain Verification**: Immutable health record verification
- 📱 **Offline Support**: Sync capabilities for areas with limited connectivity
- 🏥 **FHIR Compliant**: Full HL7 FHIR R4 compliance for healthcare interoperability
- 🔒 **HIPAA Compliant**: End-to-end encryption and audit logging

## Authentication

The API uses JWT (JSON Web Token) authentication. To access protected endpoints:

1. Obtain an access token via `/api/v2/auth/login`
2. Include the token in the `Authorization` header: `Bearer <your-token>`
3. Refresh tokens when expired using `/api/v2/auth/refresh`

## Rate Limiting

- **Anonymous requests**: 100 requests per minute
- **Authenticated requests**: 1000 requests per minute
- **Burst allowance**: 10 requests

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Time when limit resets

## Error Handling

The API uses standard HTTP status codes and returns errors in a consistent format:

```json
{
    "error": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": [
        {
            "field": "field_name",
            "message": "Field-specific error"
        }
    ],
    "request_id": "unique-request-id"
}
```

## Versioning

The API uses URL versioning. The current version is `v2`. Version information is also available in the `X-API-Version` response header.

## FHIR Resources

The API supports the following FHIR resources:
- Patient
- Observation
- MedicationRequest
- Condition
- Procedure
- Immunization
- AllergyIntolerance
- DiagnosticReport

## GraphQL

A GraphQL endpoint is available at `/graphql` for flexible data queries. GraphiQL interface is available in development mode.

## WebSocket

Real-time updates are available via WebSocket at `/ws` for:
- Patient updates
- Health record changes
- Verification status updates
- Access log monitoring (admin only)
        """,
        routes=app.routes,
        tags=[
            {
                "name": "authentication",
                "description": "User authentication and session management",
            },
            {"name": "patients", "description": "Patient record management"},
            {"name": "health-records", "description": "Health record CRUD operations"},
            {"name": "verification", "description": "Blockchain verification services"},
            {
                "name": "translations",
                "description": "Multi-language translation services",
            },
            {"name": "files", "description": "File upload and management"},
            {"name": "analysis", "description": "AI-powered health data analysis"},
            {"name": "notifications", "description": "Notification management"},
        ],
        servers=[
            {
                "url": "https://api.havenhealthpassport.org",
                "description": "Production server",
            },
            {
                "url": "https://staging-api.havenhealthpassport.org",
                "description": "Staging server",
            },
            {
                "url": f"http://localhost:{settings.api_port}",
                "description": "Development server",
            },
        ],
    )

    # Add components
    openapi_schema["components"] = {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT authentication token",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for external integrations",
            },
        },
        "responses": {
            "UnauthorizedError": {
                "description": "Authentication required",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        "example": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                        },
                    }
                },
            },
            "ForbiddenError": {
                "description": "Insufficient permissions",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        "example": {
                            "error": "FORBIDDEN",
                            "message": "You don't have permission to access this resource",
                        },
                    }
                },
            },
            "NotFoundError": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        "example": {
                            "error": "NOT_FOUND",
                            "message": "Resource not found",
                        },
                    }
                },
            },
            "ValidationError": {
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        "example": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "details": [
                                {
                                    "field": "email",
                                    "message": "Invalid email format",
                                }
                            ],
                        },
                    }
                },
            },
            "RateLimitError": {
                "description": "Rate limit exceeded",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        "example": {
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Rate limit exceeded. Please try again later",
                        },
                    }
                },
                "headers": {
                    "Retry-After": {
                        "description": "Number of seconds to wait before retrying",
                        "schema": {"type": "integer"},
                    }
                },
            },
        },
    }

    # Add external docs
    openapi_schema["externalDocs"] = {
        "description": "Full API documentation",
        "url": "https://docs.havenhealthpassport.org/api",
    }

    # Add custom x-logo
    openapi_schema["info"]["x-logo"] = {
        "url": "https://havenhealthpassport.org/logo.png",
        "altText": "Haven Health Passport",
    }

    # Add contact information
    openapi_schema["info"]["contact"] = {
        "name": "API Support",
        "url": "https://support.havenhealthpassport.org",
        "email": "api-support@havenhealthpassport.org",
    }

    # Add license information
    openapi_schema["info"]["license"] = {
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    }

    # Add API changelog
    openapi_schema["info"][
        "x-changelog"
    ] = "https://docs.havenhealthpassport.org/api/changelog"

    # Add code samples
    openapi_schema["info"]["x-code-samples"] = [
        {"lang": "Python", "source": "https://github.com/haven-health/python-sdk"},
        {"lang": "JavaScript", "source": "https://github.com/haven-health/js-sdk"},
        {"lang": "Go", "source": "https://github.com/haven-health/go-sdk"},
    ]

    # Enhance with detailed documentation
    add_endpoint_examples(openapi_schema)
    add_error_code_documentation(openapi_schema)

    # Add changelog and migration guide
    openapi_schema["info"]["x-changelog-data"] = generate_api_changelog()
    openapi_schema["info"]["x-migration-guide"] = generate_migration_guide()

    # Add deprecation notices
    openapi_schema["info"]["x-deprecations"] = {
        "endpoints": [
            {
                "path": "/api/v1/*",
                "deprecated_date": "2023-12-01",
                "sunset_date": "2024-06-01",
                "migration_path": "/api/v2/*",
                "reason": "Version 1 API is being phased out in favor of improved v2 endpoints",
            }
        ]
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def configure_openapi(app: FastAPI) -> None:
    """Configure OpenAPI for the FastAPI application."""
    app.openapi = lambda: custom_openapi(app)  # type: ignore[method-assign]


# Export configuration function
__all__ = ["configure_openapi"]
