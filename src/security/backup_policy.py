"""
Backup Policy Configuration for Haven Health Passport.

This module defines backup policies and schedules for different
types of data in the system.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.healthcare.hipaa_access_control import AccessLevel, require_phi_access

# FHIR Resource type imports
if TYPE_CHECKING:
    pass


class BackupType(Enum):
    """Types of backups."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupFrequency(Enum):
    """Backup frequency options."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BackupPolicy:
    """Defines a backup policy for a specific data type."""

    def __init__(
        self,
        name: str,
        backup_type: BackupType,
        frequency: BackupFrequency,
        retention_days: int,
        fhir_resources: Optional[List[str]] = None,
    ):
        """
        Initialize backup policy.

        Args:
            name: Policy name
            backup_type: Type of backup
            frequency: Backup frequency
            retention_days: How long to retain backups
            fhir_resources: FHIR resource types covered by this policy
        """
        self.name = name
        self.backup_type = backup_type
        self.frequency = frequency
        self.retention_days = retention_days
        self.encryption_required = True
        self.compression_enabled = True
        self.fhir_resources = fhir_resources or []
        self.validate_fhir_on_backup = True
        self.fhir_bundle_format = True  # Backup as FHIR Bundle


# Predefined backup policies for Haven Health Passport
BACKUP_POLICIES = {
    "patient_data": BackupPolicy(
        name="Patient Data Backup",
        backup_type=BackupType.FULL,
        frequency=BackupFrequency.DAILY,
        retention_days=2555,  # 7 years for HIPAA
        fhir_resources=["Patient", "RelatedPerson", "Person"],
    ),
    "medical_records": BackupPolicy(
        name="Medical Records Backup",
        backup_type=BackupType.INCREMENTAL,
        frequency=BackupFrequency.HOURLY,
        retention_days=2555,  # 7 years for HIPAA
        fhir_resources=[
            "Observation",
            "Condition",
            "Procedure",
            "MedicationRequest",
            "DiagnosticReport",
            "Immunization",
            "AllergyIntolerance",
        ],
    ),
    "audit_logs": BackupPolicy(
        name="Audit Logs Backup",
        backup_type=BackupType.FULL,
        frequency=BackupFrequency.DAILY,
        retention_days=365,  # 1 year
        fhir_resources=["AuditEvent"],
    ),
    "system_config": BackupPolicy(
        name="System Configuration Backup",
        backup_type=BackupType.SNAPSHOT,
        frequency=BackupFrequency.WEEKLY,
        retention_days=90,
    ),
    "blockchain_data": BackupPolicy(
        name="Blockchain Data Backup",
        backup_type=BackupType.FULL,
        frequency=BackupFrequency.DAILY,
        retention_days=999999,  # Permanent
    ),
    "fhir_bundle": BackupPolicy(
        name="FHIR Bundle Backup",
        backup_type=BackupType.FULL,
        frequency=BackupFrequency.DAILY,
        retention_days=2555,  # 7 years for HIPAA
        fhir_resources=["Bundle"],
    ),
}


def get_backup_schedule(policy: BackupPolicy) -> str:
    """
    Convert backup policy to cron expression.

    Args:
        policy: Backup policy

    Returns:
        Cron expression for the backup schedule
    """
    schedules = {
        BackupFrequency.HOURLY: "0 * * * *",  # Every hour
        BackupFrequency.DAILY: "0 2 * * *",  # 2 AM daily
        BackupFrequency.WEEKLY: "0 2 * * 0",  # 2 AM Sunday
        BackupFrequency.MONTHLY: "0 2 1 * *",  # 2 AM first of month
    }

    return schedules.get(policy.frequency, "0 2 * * *")


@require_phi_access(AccessLevel.READ)
def validate_fhir_backup_content(
    backup_data: Dict[str, Any], policy: BackupPolicy
) -> bool:
    """
    Validate FHIR resources in backup data.

    Args:
        backup_data: Data to be backed up
        policy: Backup policy being applied

    Returns:
        True if all FHIR resources are valid
    """
    if not policy.validate_fhir_on_backup:
        return True

    # Check if data contains FHIR resources
    if "resourceType" in backup_data:
        # Single FHIR resource
        resource_type = backup_data.get("resourceType")
        if policy.fhir_resources and resource_type not in policy.fhir_resources:
            return False

    elif "entry" in backup_data and backup_data.get("resourceType") == "Bundle":
        # FHIR Bundle
        for entry in backup_data.get("entry", []):
            resource = entry.get("resource", {})
            resource_type = resource.get("resourceType")
            if policy.fhir_resources and resource_type not in policy.fhir_resources:
                return False

    return True


@require_phi_access(AccessLevel.READ)
def create_fhir_backup_bundle(
    resources: List[Dict[str, Any]], policy: BackupPolicy
) -> Dict[str, Any]:
    """
    Create a FHIR Bundle for backup.

    Args:
        resources: List of FHIR resources to backup
        policy: Backup policy being applied

    Returns:
        FHIR Bundle containing all resources
    """
    entries: List[Dict[str, Any]] = []

    bundle: Dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "meta": {
            "tag": [
                {
                    "system": "http://havenhealthpassport.org/backup",
                    "code": policy.name,
                    "display": f"Backup Policy: {policy.name}",
                }
            ]
        },
        "entry": entries,
    }

    for resource in resources:
        if validate_fhir_backup_content(resource, policy):
            entries.append(
                {
                    "resource": resource,
                    "fullUrl": f"urn:uuid:{resource.get('id', 'unknown')}",
                }
            )

    bundle["total"] = len(entries)

    return bundle
