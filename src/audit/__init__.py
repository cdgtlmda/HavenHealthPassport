"""
Audit Trail Module for Healthcare Standards Compliance.

Provides HIPAA-compliant audit logging and reporting
"""

from .audit_middleware import AuditMiddleware
from .audit_reports import AuditReportGenerator
from .audit_service import AuditEvent, AuditEventType, AuditLog, AuditTrailService

__all__ = [
    "AuditTrailService",
    "AuditEvent",
    "AuditEventType",
    "AuditLog",
    "AuditMiddleware",
    "AuditReportGenerator",
]

__version__ = "1.0.0"
