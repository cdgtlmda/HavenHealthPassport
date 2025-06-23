"""FHIR Server Configuration Module.

This module provides configuration settings and initialization for the HAPI FHIR server
used by Haven Health Passport. Handles FHIR CapabilityStatement Resource validation.
"""

from typing import Any, Dict, List

from pydantic import Field
from pydantic_settings import BaseSettings

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "CapabilityStatement"


class FHIRServerConfig(BaseSettings):
    """Configuration for HAPI FHIR Server."""

    # Initialize FHIR validator
    _validator: FHIRValidator = FHIRValidator()

    # Server Base Settings
    server_address: str = Field(default="http://localhost:8080/fhir")
    server_name: str = Field(default="Haven Health Passport FHIR Server")
    server_id: str = Field(default="haven-health-fhir")
    fhir_version: str = Field(default="R4")

    # Database Configuration
    db_url: str = Field(default="jdbc:postgresql://postgres:5432/haven_health_fhir")
    db_username: str = Field(default="haven_user")
    db_password: str = Field(default="haven_password")
    db_driver: str = Field(default="org.postgresql.Driver")
    db_pool_size: int = Field(default=10)

    # CORS Configuration
    cors_enabled: bool = Field(default=True)
    cors_allowed_origins: List[str] = Field(default=["*"])
    cors_allowed_headers: List[str] = Field(
        default=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
        ]
    )
    cors_allowed_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    )
    cors_allow_credentials: bool = Field(default=True)
    # Authentication Configuration
    auth_enabled: bool = Field(default=True)

    # Authorization Configuration
    authorization_enabled: bool = Field(default=True)
    authorization_mode: str = Field(default="combined")  # rbac, abac, or combined

    # Audit Configuration
    audit_enabled: bool = Field(default=True)
    audit_log_requests: bool = Field(default=True)
    audit_log_responses: bool = Field(default=False)

    # Subscription Configuration
    subscription_resthook_enabled: bool = Field(default=True)
    subscription_websocket_enabled: bool = Field(default=True)

    # Search Configuration
    search_total_mode: str = Field(default="ACCURATE")
    search_default_page_size: int = Field(default=20)
    search_max_page_size: int = Field(default=200)

    # Bulk Export Configuration
    bulk_export_enabled: bool = Field(default=True)
    bulk_export_max_file_size: int = Field(default=104857600)  # 100MB

    # Validation Configuration
    validation_enabled: bool = Field(default=True)
    validation_requests: bool = Field(default=True)
    validation_responses: bool = Field(default=False)

    # Terminology Service Configuration
    terminology_enabled: bool = Field(default=True)
    terminology_graphql_enabled: bool = Field(default=True)
    terminology_server_url: str = Field(default="http://localhost:8080/fhir")
    terminology_validation_enabled: bool = Field(default=True)

    # Performance Settings
    advanced_lucene_indexing: bool = Field(default=True)
    defer_indexing_for_codesystems_of_size: int = Field(default=101)

    # Referential Integrity
    enforce_referential_integrity_on_write: bool = Field(default=False)
    enforce_referential_integrity_on_delete: bool = Field(default=False)
    allow_external_references: bool = Field(default=True)

    # Narrative Generation
    narrative_enabled: bool = Field(default=True)

    def get_server_metadata(self) -> Dict[str, Any]:
        """Get server metadata for capability statement."""
        return {
            "server_name": self.server_name,
            "server_id": self.server_id,
            "fhir_version": self.fhir_version,
            "server_address": self.server_address,
            "implementation_description": "Haven Health Passport FHIR Server - Secure health data management for displaced populations",
        }

    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration."""
        return {
            "enabled": self.cors_enabled,
            "allowed_origins": self.cors_allowed_origins,
            "allowed_headers": self.cors_allowed_headers,
            "allowed_methods": self.cors_allowed_methods,
            "allow_credentials": self.cors_allow_credentials,
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return {
            "url": self.db_url,
            "username": self.db_username,
            "password": self.db_password,
            "driver": self.db_driver,
            "pool_size": self.db_pool_size,
        }

    def get_validation_config(self) -> Dict[str, Any]:
        """Get validation configuration."""
        return {
            "enabled": self.validation_enabled,
            "validate_requests": self.validation_requests,
            "validate_responses": self.validation_responses,
        }

    def get_search_config(self) -> Dict[str, Any]:
        """Get search configuration."""
        return {
            "total_mode": self.search_total_mode,
            "default_page_size": self.search_default_page_size,
            "max_page_size": self.search_max_page_size,
            "advanced_lucene_indexing": self.advanced_lucene_indexing,
        }

    def to_env_dict(self) -> Dict[str, str]:
        """Convert configuration to environment variables."""
        return {
            "HAPI_FHIR_SERVER_ADDRESS": self.server_address,
            "HAPI_FHIR_FHIR_VERSION": self.fhir_version,
            "HAPI_FHIR_CORS_ALLOW_CREDENTIALS": str(
                self.cors_allow_credentials
            ).lower(),
            "HAPI_FHIR_CORS_ALLOWED_ORIGIN": ",".join(self.cors_allowed_origins),
            "HAPI_FHIR_SUBSCRIPTION_RESTHOOK_ENABLED": str(
                self.subscription_resthook_enabled
            ).lower(),
            "HAPI_FHIR_SUBSCRIPTION_WEBSOCKET_ENABLED": str(
                self.subscription_websocket_enabled
            ).lower(),
            "HAPI_FHIR_BULK_EXPORT_ENABLED": str(self.bulk_export_enabled).lower(),
            "SPRING_DATASOURCE_URL": self.db_url,
            "SPRING_DATASOURCE_USERNAME": self.db_username,
            "SPRING_DATASOURCE_PASSWORD": self.db_password,
        }
