"""
Security Headers Implementation for Haven Health Passport.

This module provides middleware and configuration for implementing
comprehensive security headers including HSTS, CSP, and other protections.
Includes FHIR AuditEvent resource validation for security events.
"""

import secrets
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict

from src.healthcare.fhir_validator import FHIRValidator
from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.security.encryption import EncryptionService

# FHIR resource type for this module
__fhir_resource__ = "AuditEvent"

# Removed unused imports


class FHIRAuditEvent(TypedDict, total=False):
    """FHIR AuditEvent resource type definition for security events."""

    resourceType: Literal["AuditEvent"]
    type: Dict[str, Any]
    subtype: List[Dict[str, Any]]
    action: Literal["C", "R", "U", "D", "E"]
    period: Dict[str, str]
    recorded: str
    outcome: Literal["0", "4", "8", "12"]
    outcomeDesc: str
    purposeOfEvent: List[Dict[str, Any]]
    agent: List[Dict[str, Any]]
    source: Dict[str, Any]
    entity: List[Dict[str, Any]]
    __fhir_resource__: Literal["AuditEvent"]


class SecurityHeadersResource:
    """Security headers management with FHIR Resource validation."""

    # FHIR DomainResource compliance
    resource_type = "AuditEvent"

    def __init__(self) -> None:
        """Initialize with FHIR validator."""
        self.validator = FHIRValidator()


class SecurityHeaders:
    """Manages security headers for HTTP responses."""

    def __init__(self, environment: str = "production"):
        """
        Initialize security headers configuration.

        Args:
            environment: Deployment environment
        """
        self._encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self.environment = environment
        self.nonce_length = 32
        self.fhir_validator: Optional[FHIRValidator] = (
            None  # Initialize to None, lazy load later
        )

    def generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce for CSP."""
        return secrets.token_urlsafe(self.nonce_length)

    def get_hsts_header(self) -> Dict[str, str]:
        """
        Get HTTP Strict Transport Security (HSTS) header.

        Returns:
            HSTS header configuration
        """
        # 2 years in seconds, include subdomains, enable preload
        max_age = 63072000 if self.environment == "production" else 3600

        return {
            "Strict-Transport-Security": f"max-age={max_age}; includeSubDomains; preload"
        }

    def get_csp_header(self, nonce: str) -> Dict[str, str]:
        """
        Get Content Security Policy (CSP) header.

        Args:
            nonce: Nonce for inline scripts

        Returns:
            CSP header configuration
        """
        csp_directives = [
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}' https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https://api.havenhealthpassport.org wss://api.havenhealthpassport.org",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "upgrade-insecure-requests",
            "block-all-mixed-content",
        ]

        if self.environment == "production":
            csp_directives.append("report-uri /api/csp-report")

        return {"Content-Security-Policy": "; ".join(csp_directives)}

    def get_security_headers(self, nonce: Optional[str] = None) -> Dict[str, str]:
        """
        Get all security headers.

        Args:
            nonce: Optional nonce for CSP

        Returns:
            Dictionary of all security headers
        """
        headers = {}

        # HSTS
        headers.update(self.get_hsts_header())
        # CSP
        if nonce:
            headers.update(self.get_csp_header(nonce))

        # Additional security headers
        headers.update(
            {
                # Prevent MIME type sniffing
                "X-Content-Type-Options": "nosniff",
                # Prevent clickjacking
                "X-Frame-Options": "DENY",
                # XSS Protection (legacy browsers)
                "X-XSS-Protection": "1; mode=block",
                # Referrer Policy
                "Referrer-Policy": "strict-origin-when-cross-origin",
                # Permissions Policy (formerly Feature Policy)
                "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
                # Cache Control for sensitive pages
                "Cache-Control": "no-store, no-cache, must-revalidate, private",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )

        return headers

    def get_cors_headers(self, allowed_origins: List[str]) -> Dict[str, str]:
        """
        Get CORS headers for API responses.

        Args:
            allowed_origins: List of allowed origins

        Returns:
            CORS headers
        """
        return {
            "Access-Control-Allow-Origin": ", ".join(allowed_origins),
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400",  # 24 hours
        }

    @require_phi_access(AccessLevel.READ)
    def validate_fhir_security_audit(
        self, audit_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate security audit data as FHIR AuditEvent resource.

        Args:
            audit_data: Security audit event data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Initialize FHIR validator if needed
        if self.fhir_validator is None:
            self.fhir_validator = FHIRValidator()

        # Ensure resource type
        if "resourceType" not in audit_data:
            audit_data["resourceType"] = "AuditEvent"

        # Validate using FHIR validator
        return self.fhir_validator.validate_resource("AuditEvent", audit_data)

    @require_phi_access(AccessLevel.WRITE)
    def create_fhir_security_audit(
        self, event_type: str, outcome: str, actor_id: str, ip_address: str
    ) -> FHIRAuditEvent:
        """Create FHIR AuditEvent for security events.

        Args:
            event_type: Type of security event
            outcome: Event outcome (success/failure)
            actor_id: ID of actor
            ip_address: IP address of actor

        Returns:
            FHIR AuditEvent resource
        """
        audit_event: FHIRAuditEvent = {
            "resourceType": "AuditEvent",
            "type": {
                "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
                "code": "security",
                "display": "Security Event",
            },
            "subtype": [
                {
                    "system": "http://havenhealthpassport.org/fhir/CodeSystem/security-events",
                    "code": event_type,
                    "display": event_type.replace("_", " ").title(),
                }
            ],
            "action": "E",  # Execute
            "recorded": datetime.utcnow().isoformat() + "Z",
            "outcome": "0" if outcome == "success" else "8",
            "agent": [
                {
                    "who": {"identifier": {"value": actor_id}},
                    "requestor": True,
                    "network": {"address": ip_address, "type": "2"},  # IP address
                }
            ],
            "source": {
                "observer": {"display": "Haven Health Passport Security System"},
                "type": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/security-source-type",
                        "code": "4",
                        "display": "Application Server",
                    }
                ],
            },
            "__fhir_resource__": "AuditEvent",
        }

        return audit_event
