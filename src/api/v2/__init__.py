"""Haven Health Passport API v2 endpoints.

This module exports all v2 API routers for the core functionality
of the Haven Health Passport system.
"""

from .analysis_endpoints import router as analysis_endpoints
from .bulk_operations_endpoints import router as bulk_operations_endpoints
from .dashboard import router as dashboard
from .health_record_endpoints import router as health_record_endpoints
from .notification_endpoints import router as notification_endpoints
from .organization_endpoints import router as organization_endpoints
from .password_policy_endpoints import router as password_policy_endpoints
from .patient_endpoints import router as patient_endpoints
from .remediation_endpoints import router as remediation_endpoints
from .reports import router as report_endpoints
from .sync_endpoints import router as sync_endpoints
from .websocket_health import router as websocket_health

__all__ = [
    "patient_endpoints",
    "health_record_endpoints",
    "analysis_endpoints",
    "remediation_endpoints",
    "notification_endpoints",
    "websocket_health",
    "dashboard",
    "organization_endpoints",
    "bulk_operations_endpoints",
    "password_policy_endpoints",
    "report_endpoints",
    "sync_endpoints",
]
