"""Healthcare Regulatory Compliance Module.

This module provides comprehensive regulatory compliance functionality
including GDPR, HIPAA, and international healthcare data protection standards.
"""

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access
from src.healthcare.regulatory.consent_management import (
    ConsentDuration,
    ConsentManager,
    ConsentMethod,
    ConsentScope,
    ConsentStatus,
    ConsentType,
)
from src.healthcare.regulatory.data_minimization import (
    CollectionJustification,
    DataField,
    DataMinimizationLevel,
    DataMinimizationManager,
    DataMinimizationPolicy,
)
from src.healthcare.regulatory.gdpr_compliance import (
    GDPRConsentManager,
    GDPRDataPortability,
    GDPRDataProtectionOfficer,
    GDPRErasure,
    GDPRLawfulBasis,
    GDPRRight,
    HIPAAMinimumNecessary,
    ProcessingPurpose,
)
from src.healthcare.regulatory.gdpr_configuration import GDPRConfiguration
from src.healthcare.regulatory.gdpr_consent_integration import GDPRConsentIntegration
from src.healthcare.regulatory.gdpr_data_portability import DataScope as DataCategory
from src.healthcare.regulatory.gdpr_data_portability import (
    ExportFormat as DataExportFormat,
)
from src.healthcare.regulatory.gdpr_data_portability import (
    GDPRDataPortability as GDPRDataPortabilityManager,
)
from src.healthcare.regulatory.gdpr_data_portability import (
    PortabilityStatus as TransferProtocol,
)
from src.healthcare.regulatory.hipaa_authorization_tracking import (
    AuthorizationStatus,
    AuthorizationType,
    HIPAAAuthorizationTracking,
)
from src.healthcare.regulatory.hipaa_breach_notification import (
    BreachSeverity,
    BreachType,
    HIPAABreachNotification,
    NotificationStatus,
)
from src.healthcare.regulatory.hipaa_compliance import (
    HIPAAAccessControl,
    HIPAAAuditLog,
    HIPAARequirement,
    PHIField,
)
from src.healthcare.regulatory.hipaa_deidentification import (
    DeIdentificationMethod,
    HIPAADeIdentification,
    IdentifierType,
)
from src.healthcare.regulatory.hipaa_encryption_standards import (
    EncryptionAlgorithm,
    EncryptionType,
    HIPAAEncryptionStandards,
    KeyStrength,
)
from src.healthcare.regulatory.hipaa_integrity_controls import (
    HIPAAIntegrityControls,
    IntegrityLevel,
    IntegrityMethod,
)
from src.healthcare.regulatory.hipaa_retention_policies import (
    DisposalMethod,
    HIPAARetentionPolicies,
    RecordType,
    RetentionBasis,
)
from src.healthcare.regulatory.hipaa_transmission_security import (
    DataClassification,
    EncryptionStandard,
    HIPAATransmissionSecurity,
    TransmissionProtocol,
)
from src.healthcare.regulatory.iso27001_controls import (
    ControlFamily,
    ControlPriority,
    ControlStatus,
    ISO27001Control,
    ISO27001Framework,
    RiskLevel,
)
from src.healthcare.regulatory.iso27001_implementation import (
    ISO27001ImplementationManager,
)
from src.healthcare.regulatory.iso27001_policies import (
    HealthcareSecurityPolicies,
    PolicyType,
)
from src.healthcare.regulatory.right_to_deletion_config import (
    DataCategory as DeletionDataCategory,
)
from src.healthcare.regulatory.right_to_deletion_config import (
    DeletionMethod,
    DeletionStatus,
    LegalBasis,
    RightToDeletionConfiguration,
)
from src.healthcare.regulatory.right_to_deletion_manager import (
    DeletionRequest,
    RightToDeletionManager,
)

__all__ = [
    # GDPR Components
    "GDPRLawfulBasis",
    "GDPRRight",
    "ProcessingPurpose",
    "GDPRConsentManager",
    "GDPRDataPortability",
    "GDPRErasure",
    "GDPRDataProtectionOfficer",
    "GDPRConfiguration",
    "GDPRDataPortabilityManager",
    "DataExportFormat",
    "DataCategory",
    "TransferProtocol",
    # Consent Management
    "ConsentType",
    "ConsentStatus",
    "ConsentScope",
    "ConsentDuration",
    "ConsentMethod",
    "ConsentManager",
    "GDPRConsentIntegration",
    # HIPAA Components
    "HIPAAAccessControl",
    "HIPAAAuditLog",
    "HIPAARequirement",
    "PHIField",
    "AccessLevel",
    "HIPAAMinimumNecessary",
    "HIPAAAuthorizationTracking",
    "AuthorizationType",
    "AuthorizationStatus",
    "HIPAABreachNotification",
    "BreachType",
    "BreachSeverity",
    "NotificationStatus",
    "HIPAADeIdentification",
    "DeIdentificationMethod",
    "IdentifierType",
    "HIPAAEncryptionStandards",
    "EncryptionType",
    "EncryptionAlgorithm",
    "KeyStrength",
    "HIPAAIntegrityControls",
    "IntegrityLevel",
    "IntegrityMethod",
    "HIPAARetentionPolicies",
    "RecordType",
    "RetentionBasis",
    "DisposalMethod",
    "HIPAATransmissionSecurity",
    "TransmissionProtocol",
    "DataClassification",
    "EncryptionStandard",
    # Right to Deletion
    "DeletionMethod",
    "DataCategory",
    "LegalBasis",
    "DeletionStatus",
    "RightToDeletionConfiguration",
    "RightToDeletionManager",
    "DeletionRequest",
    # Data Minimization
    "DataMinimizationLevel",
    "DataField",
    "CollectionJustification",
    "DataMinimizationPolicy",
    "DataMinimizationManager",
    # ISO 27001 Components
    "ControlFamily",
    "ControlStatus",
    "ControlPriority",
    "RiskLevel",
    "ISO27001Control",
    "ISO27001Framework",
    "PolicyType",
    "HealthcareSecurityPolicies",
    "ISO27001ImplementationManager",
]
