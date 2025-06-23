"""FHIR Authorization Configuration Module.

This module integrates the FHIR authorization handler with the server configuration,
providing a complete authorization setup for the Haven Health Passport FHIR server.
All PHI data is encrypted and access is controlled through role-based permissions.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.healthcare.fhir_authorization import (
    AuthorizationPolicy,
    ResourcePermission,
    get_authorization_handler,
)
from src.healthcare.fhir_server_config import FHIRServerConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FHIRAuthorizationConfig(BaseSettings):
    """FHIR Authorization Configuration Settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Authorization Enable/Disable
    authorization_enabled: bool = Field(default=True)

    # Authorization Mode
    authorization_mode: str = Field(
        default="rbac",  # Options: "rbac", "abac", "combined"
    )

    # Role-Based Access Control Settings
    rbac_enabled: bool = Field(default=True)

    # Attribute-Based Access Control Settings
    abac_enabled: bool = Field(default=True)

    # Consent Management
    consent_based_access: bool = Field(default=True)
    default_consent_policy: str = Field(
        default="opt-in",  # Options: "opt-in", "opt-out"
    )

    # Emergency Access
    emergency_access_enabled: bool = Field(default=True)
    emergency_access_duration_hours: int = Field(default=24)
    emergency_access_requires_justification: bool = Field(default=True)

    # Audit Settings
    authorization_audit_enabled: bool = Field(default=True)
    audit_failed_attempts: bool = Field(default=True)
    audit_success_attempts: bool = Field(default=True)

    # Performance Settings
    cache_authorization_decisions: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=300)  # 5 minutes

    # Default Roles
    auto_assign_patient_role: bool = Field(
        default=True, alias="FHIR_AUTO_ASSIGN_PATIENT_ROLE"
    )
    default_new_user_roles: List[str] = Field(
        default=["patient"], alias="FHIR_DEFAULT_USER_ROLES"
    )

    # Resource-specific Settings
    patient_data_isolation: bool = Field(
        default=True, alias="FHIR_PATIENT_DATA_ISOLATION"
    )
    practitioner_org_isolation: bool = Field(
        default=True, alias="FHIR_PRACTITIONER_ORG_ISOLATION"
    )

    # Policy Enforcement
    enforce_minimum_necessary: bool = Field(
        default=True, alias="FHIR_ENFORCE_MINIMUM_NECESSARY"
    )
    enforce_purpose_of_use: bool = Field(
        default=True, alias="FHIR_ENFORCE_PURPOSE_OF_USE"
    )

    # Cross-border Access
    enable_cross_border_access: bool = Field(
        default=True, alias="FHIR_CROSS_BORDER_ACCESS"
    )
    require_data_sovereignty_check: bool = Field(
        default=True, alias="FHIR_DATA_SOVEREIGNTY_CHECK"
    )


class FHIRAuthorizationConfigurator:
    """Configures and manages FHIR authorization for the server.

    Integrates authorization handler with server configuration.
    """

    def __init__(
        self,
        auth_config: Optional[FHIRAuthorizationConfig] = None,
        server_config: Optional[FHIRServerConfig] = None,
    ):
        """Initialize authorization configurator.

        Args:
            auth_config: Authorization configuration
            server_config: Server configuration
        """
        self.auth_config = auth_config or FHIRAuthorizationConfig()
        self.server_config = server_config or FHIRServerConfig()
        self.authorization_handler = get_authorization_handler()
        self._configure_authorization()

    def _configure_authorization(self) -> None:
        """Configure authorization handler based on settings."""
        logger.info("Configuring FHIR authorization...")

        # Enable/disable audit
        self.authorization_handler.set_audit_enabled(
            self.auth_config.authorization_audit_enabled
        )

        # Configure default policies
        self._configure_default_policies()

        # Configure emergency access policies
        if self.auth_config.emergency_access_enabled:
            self._configure_emergency_access_policies()

        # Configure consent policies
        if self.auth_config.consent_based_access:
            self._configure_consent_policies()

        logger.info("FHIR authorization configuration complete")

    def _configure_default_policies(self) -> None:
        """Configure default authorization policies."""
        # Patient data isolation policy
        if self.auth_config.patient_data_isolation:
            policy = AuthorizationPolicy(
                id="patient-isolation",
                name="Patient Data Isolation",
                description="Ensure patients can only access their own records",
                priority=90,
                enabled=True,
                conditions={"is_patient_data": True},
                effect="deny",
                resource_types=["*"],
                actions=[ResourcePermission.READ, ResourcePermission.WRITE],
            )
            self.authorization_handler.add_policy(policy)

        # Practitioner organization isolation
        if self.auth_config.practitioner_org_isolation:
            policy = AuthorizationPolicy(
                id="practitioner-org-isolation",
                name="Practitioner Organization Isolation",
                description="Practitioners can only access data within their organization",
                priority=80,
                enabled=True,
                conditions={"match_organization": True},
                effect="allow",
                resource_types=["*"],
                actions=[ResourcePermission.READ, ResourcePermission.WRITE],
            )
            self.authorization_handler.add_policy(policy)

        # Minimum necessary policy
        if self.auth_config.enforce_minimum_necessary:
            policy = AuthorizationPolicy(
                id="minimum-necessary",
                name="Minimum Necessary Access",
                description="Enforce HIPAA minimum necessary standard",
                priority=70,
                enabled=True,
                conditions={"check_minimum_necessary": True},
                effect="allow",
                resource_types=["*"],
                actions=[ResourcePermission.READ],
            )
            self.authorization_handler.add_policy(policy)

    def _configure_emergency_access_policies(self) -> None:
        """Configure emergency access policies."""
        policy = AuthorizationPolicy(
            id="emergency-access",
            name="Emergency Access Override",
            description="Allow emergency access to critical health information",
            priority=95,
            enabled=True,
            conditions={
                "emergency_access": True,
                "max_duration_hours": self.auth_config.emergency_access_duration_hours,
                "requires_justification": self.auth_config.emergency_access_requires_justification,
            },
            effect="allow",
            resource_types=[
                "Patient",
                "AllergyIntolerance",
                "Condition",
                "MedicationRequest",
                "Immunization",
            ],
            actions=[ResourcePermission.READ, ResourcePermission.SEARCH],
        )
        self.authorization_handler.add_policy(policy)

    def _configure_consent_policies(self) -> None:
        """Configure consent-based access policies."""
        policy = AuthorizationPolicy(
            id="consent-based-access",
            name="Patient Consent Enforcement",
            description="Enforce patient consent for data access",
            priority=85,
            enabled=True,
            conditions={
                "check_consent": True,
                "default_policy": self.auth_config.default_consent_policy,
            },
            effect="deny",  # Deny if no consent
            resource_types=["*"],
            actions=[ResourcePermission.READ, ResourcePermission.WRITE],
        )
        self.authorization_handler.add_policy(policy)

    def get_server_authorization_config(self) -> Dict[str, Any]:
        """Get authorization configuration for FHIR server.

        Returns:
            Configuration dictionary for server setup
        """
        return {
            "authorization": {
                "enabled": self.auth_config.authorization_enabled,
                "mode": self.auth_config.authorization_mode,
                "rbac": {
                    "enabled": self.auth_config.rbac_enabled,
                    "default_roles": self.auth_config.default_new_user_roles,
                    "auto_assign_patient_role": self.auth_config.auto_assign_patient_role,
                },
                "abac": {
                    "enabled": self.auth_config.abac_enabled,
                    "policies": len(self.authorization_handler.custom_policies),
                },
                "consent": {
                    "enabled": self.auth_config.consent_based_access,
                    "default_policy": self.auth_config.default_consent_policy,
                },
                "emergency_access": {
                    "enabled": self.auth_config.emergency_access_enabled,
                    "duration_hours": self.auth_config.emergency_access_duration_hours,
                    "requires_justification": self.auth_config.emergency_access_requires_justification,
                },
                "audit": {
                    "enabled": self.auth_config.authorization_audit_enabled,
                    "audit_failures": self.auth_config.audit_failed_attempts,
                    "audit_success": self.auth_config.audit_success_attempts,
                },
                "cache": {
                    "enabled": self.auth_config.cache_authorization_decisions,
                    "ttl_seconds": self.auth_config.cache_ttl_seconds,
                },
                "enforcement": {
                    "minimum_necessary": self.auth_config.enforce_minimum_necessary,
                    "purpose_of_use": self.auth_config.enforce_purpose_of_use,
                    "patient_isolation": self.auth_config.patient_data_isolation,
                    "org_isolation": self.auth_config.practitioner_org_isolation,
                },
                "cross_border": {
                    "enabled": self.auth_config.enable_cross_border_access,
                    "sovereignty_check": self.auth_config.require_data_sovereignty_check,
                },
            }
        }

    def configure_hapi_fhir_interceptors(self) -> Dict[str, Any]:
        """Generate HAPI FHIR interceptor configuration.

        Returns:
            Interceptor configuration for HAPI FHIR
        """
        interceptors = []

        if self.auth_config.authorization_enabled:
            # Authorization interceptor
            interceptors.append(
                {
                    "class": "ca.uhn.fhir.rest.server.interceptor.auth.AuthorizationInterceptor",
                    "config": {"rules": self._generate_hapi_auth_rules()},
                }
            )

        if self.auth_config.consent_based_access:
            # Consent interceptor
            interceptors.append(
                {
                    "class": "ca.uhn.fhir.rest.server.interceptor.consent.ConsentInterceptor",
                    "config": {
                        "defaultPolicy": self.auth_config.default_consent_policy
                    },
                }
            )

        if self.auth_config.authorization_audit_enabled:
            # Audit interceptor
            interceptors.append(
                {
                    "class": "ca.uhn.fhir.rest.server.interceptor.audit.AuditingInterceptor",
                    "config": {
                        "auditFailures": self.auth_config.audit_failed_attempts,
                        "auditSuccess": self.auth_config.audit_success_attempts,
                    },
                }
            )

        return {"interceptors": interceptors}

    def _generate_hapi_auth_rules(self) -> List[Dict[str, Any]]:
        """Generate HAPI FHIR authorization rules from our configuration.

        Returns:
            List of authorization rules for HAPI
        """
        rules = []

        # Convert role definitions to HAPI rules
        for role, role_def in self.authorization_handler.roles.items():
            for scope in role_def.resource_scopes:
                rule = {
                    "type": "rule",
                    "name": f"{role.value}_{scope.resource_type}",
                    "resourceType": scope.resource_type,
                    "permissions": [perm.value for perm in scope.permissions],
                    "role": role.value,
                }

                if scope.conditions:
                    rule["conditions"] = (
                        list(scope.conditions.values())
                        if isinstance(scope.conditions, dict)
                        else scope.conditions
                    )

                rules.append(rule)

        return rules

    def update_server_config_with_auth(self) -> None:
        """Update server configuration with authorization settings."""
        # Enable authentication in server config
        self.server_config.auth_enabled = self.auth_config.authorization_enabled

        # Add authorization configuration to server metadata
        server_metadata = self.server_config.get_server_metadata()
        server_metadata["authorization"] = self.get_server_authorization_config()

        logger.info("Updated server configuration with authorization settings")

    def validate_configuration(self) -> List[str]:
        """Validate authorization configuration.

        Returns:
            List of validation warnings/errors
        """
        warnings = []

        # Check if auth is enabled but no auth mechanism configured
        if (
            self.auth_config.authorization_enabled
            and not self.server_config.auth_enabled
        ):
            warnings.append("Authorization enabled but authentication is disabled")

        # Check role configuration
        if self.auth_config.rbac_enabled and not self.authorization_handler.roles:
            warnings.append("RBAC enabled but no roles defined")

        # Check policy configuration
        if (
            self.auth_config.abac_enabled
            and not self.authorization_handler.custom_policies
        ):
            warnings.append("ABAC enabled but no custom policies defined")

        # Check emergency access configuration
        if (
            self.auth_config.emergency_access_enabled
            and not self.auth_config.emergency_access_requires_justification
        ):
            warnings.append(
                "Emergency access enabled without justification requirement"
            )

        # Check consent configuration
        if (
            self.auth_config.consent_based_access
            and self.auth_config.default_consent_policy == "opt-out"
        ):
            warnings.append(
                "Default consent policy is opt-out - ensure GDPR compliance"
            )

        return warnings


# Singleton instance
_configurator: Optional[FHIRAuthorizationConfigurator] = None


def get_authorization_configurator() -> FHIRAuthorizationConfigurator:
    """Get singleton authorization configurator instance."""
    global _configurator  # pylint: disable=global-statement
    if _configurator is None:
        _configurator = FHIRAuthorizationConfigurator()
    return _configurator


def configure_fhir_authorization(
    auth_config: Optional[FHIRAuthorizationConfig] = None,
    server_config: Optional[FHIRServerConfig] = None,
) -> FHIRAuthorizationConfigurator:
    """Configure FHIR authorization with custom settings.

    Args:
        auth_config: Authorization configuration
        server_config: Server configuration

    Returns:
        Configured authorization configurator
    """
    global _configurator  # pylint: disable=global-statement
    _configurator = FHIRAuthorizationConfigurator(auth_config, server_config)
    return _configurator
