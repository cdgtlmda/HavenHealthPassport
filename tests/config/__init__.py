"""Test Configuration Module.

Provides real test service configurations for medical-compliant testing
"""

from .real_test_config import RealTestConfig, real_test_config
from .test_database_schema import (
    AccessLog,
    AuditLog,
    Base,
    EmergencyAccess,
    EncryptionKey,
    HealthRecord,
    HIPAAAuditLog,
    Patient,
    PatientConsent,
    Provider,
    User,
    create_test_schema,
)

__all__ = [
    "RealTestConfig",
    "real_test_config",
    "Base",
    "Patient",
    "HealthRecord",
    "Provider",
    "AuditLog",
    "AccessLog",
    "EmergencyAccess",
    "EncryptionKey",
    "HIPAAAuditLog",
    "PatientConsent",
    "User",
    "create_test_schema",
]
