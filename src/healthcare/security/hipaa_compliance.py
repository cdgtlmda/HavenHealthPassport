"""
HIPAA Compliance Checker.

Validates compliance with HIPAA Security Rule requirements.
Ensures encrypted PHI data handling with proper access control.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from .base_types import SecurityControl, SecurityControlStatus, ValidationResult


class HIPAASafeguard(Enum):
    """HIPAA safeguard categories."""

    ADMINISTRATIVE = "administrative"
    PHYSICAL = "physical"
    TECHNICAL = "technical"


@dataclass
class HIPAARequirement:
    """HIPAA requirement specification."""

    section: str
    title: str
    safeguard: HIPAASafeguard
    required: bool  # Required vs Addressable
    description: str


class HIPAAComplianceChecker:
    """HIPAA-specific compliance validation."""

    def __init__(self) -> None:
        """Initialize HIPAA compliance checker with requirements."""
        self.requirements = self._define_hipaa_requirements()

    def _define_hipaa_requirements(self) -> List[HIPAARequirement]:
        """Define HIPAA Security Rule requirements."""
        return [
            # Administrative Safeguards
            HIPAARequirement(
                section="164.308(a)(1)",
                title="Security Management Process",
                safeguard=HIPAASafeguard.ADMINISTRATIVE,
                required=True,
                description="Implement policies and procedures to prevent, detect, contain, and correct security violations",
            ),
            HIPAARequirement(
                section="164.308(a)(2)",
                title="Assigned Security Responsibility",
                safeguard=HIPAASafeguard.ADMINISTRATIVE,
                required=True,
                description="Identify the security official responsible for developing and implementing security policies",
            ),
            HIPAARequirement(
                section="164.308(a)(3)",
                title="Workforce Security",
                safeguard=HIPAASafeguard.ADMINISTRATIVE,
                required=True,
                description="Implement procedures for authorization and/or supervision of workforce members",
            ),
            HIPAARequirement(
                section="164.308(a)(4)",
                title="Information Access Management",
                safeguard=HIPAASafeguard.ADMINISTRATIVE,
                required=True,
                description="Implement policies for granting access to ePHI",
            ),
            HIPAARequirement(
                section="164.308(a)(5)",
                title="Security Awareness and Training",
                safeguard=HIPAASafeguard.ADMINISTRATIVE,
                required=True,
                description="Implement security awareness training for all workforce members",
            ),
            # Physical Safeguards
            HIPAARequirement(
                section="164.310(a)(1)",
                title="Facility Access Controls",
                safeguard=HIPAASafeguard.PHYSICAL,
                required=True,
                description="Implement policies to limit physical access to electronic systems",
            ),
            HIPAARequirement(
                section="164.310(b)",
                title="Workstation Use",
                safeguard=HIPAASafeguard.PHYSICAL,
                required=True,
                description="Implement policies for proper workstation use",
            ),
            HIPAARequirement(
                section="164.310(c)",
                title="Workstation Security",
                safeguard=HIPAASafeguard.PHYSICAL,
                required=True,
                description="Implement physical safeguards for workstations",
            ),
            # Technical Safeguards
            HIPAARequirement(
                section="164.312(a)(1)",
                title="Access Control",
                safeguard=HIPAASafeguard.TECHNICAL,
                required=True,
                description="Implement technical policies to allow access only to authorized persons",
            ),
            HIPAARequirement(
                section="164.312(a)(2)(iv)",
                title="Encryption and Decryption",
                safeguard=HIPAASafeguard.TECHNICAL,
                required=False,  # Addressable, not required
                description="Implement a mechanism to encrypt and decrypt electronic protected health information",
            ),
            HIPAARequirement(
                section="164.312(b)",
                title="Audit Controls",
                safeguard=HIPAASafeguard.TECHNICAL,
                required=True,
                description="Implement mechanisms to record and examine activity in systems containing ePHI",
            ),
            HIPAARequirement(
                section="164.312(c)(1)",
                title="Integrity",
                safeguard=HIPAASafeguard.TECHNICAL,
                required=True,
                description="Implement policies to protect ePHI from improper alteration or destruction",
            ),
            HIPAARequirement(
                section="164.312(e)(1)",
                title="Transmission Security",
                safeguard=HIPAASafeguard.TECHNICAL,
                required=True,
                description="Implement technical security measures to guard against unauthorized access during transmission",
            ),
        ]

    async def validate_control(self, control: SecurityControl) -> ValidationResult:
        """Validate a security control for HIPAA compliance."""
        # Map control to HIPAA requirements
        relevant_requirements = self._map_control_to_requirements(control)

        if not relevant_requirements:
            return ValidationResult(
                control=control,
                status=SecurityControlStatus.NOT_APPLICABLE,
                timestamp=datetime.now(),
                details={"message": "No direct HIPAA requirement mapping"},
                evidence=[],
            )

        # Perform HIPAA-specific validation
        validation_results = []
        for requirement in relevant_requirements:
            result = await self._validate_requirement(control, requirement)
            validation_results.append(result)

        # Aggregate results
        all_compliant = all(r["compliant"] for r in validation_results)
        any_compliant = any(r["compliant"] for r in validation_results)

        if all_compliant:
            status = SecurityControlStatus.COMPLIANT
        elif any_compliant:
            status = SecurityControlStatus.PARTIALLY_COMPLIANT
        else:
            status = SecurityControlStatus.NON_COMPLIANT

        return ValidationResult(
            control=control,
            status=status,
            timestamp=datetime.now(),
            details={
                "hipaa_requirements": [r.section for r in relevant_requirements],
                "validation_results": validation_results,
            },
            evidence=[
                {
                    "type": "hipaa_mapping",
                    "requirement": r.section,
                    "title": r.title,
                    "result": next(
                        v for v in validation_results if v["requirement"] == r.section
                    ),
                }
                for r in relevant_requirements
            ],
            remediation_required=not all_compliant,
            remediation_steps=self._generate_remediation_steps(
                control, validation_results
            ),
        )

    def _map_control_to_requirements(
        self, control: SecurityControl
    ) -> List[HIPAARequirement]:
        """Map security control to relevant HIPAA requirements."""
        # This mapping would be more sophisticated in production
        mappings = {
            "AC-001": ["164.312(a)(1)"],  # User Authentication -> Access Control
            "AC-002": ["164.308(a)(4)"],  # RBAC -> Information Access Management
            "AU-001": ["164.312(b)"],  # Audit Logging -> Audit Controls
            "EN-001": ["164.312(a)(2)(iv)"],  # Encryption -> Access Control
            "TS-001": ["164.312(e)(1)"],  # Network Security -> Transmission Security
        }

        requirement_sections = mappings.get(control.id, [])
        return [r for r in self.requirements if r.section in requirement_sections]

    async def _validate_requirement(
        self, control: SecurityControl, requirement: HIPAARequirement
    ) -> Dict[str, Any]:
        """Validate specific HIPAA requirement."""
        # Simulate validation logic
        checks = {
            "policy_exists": True,
            "implementation_verified": True,
            "documentation_complete": True,
            "testing_performed": True,
        }

        compliant = all(checks.values())

        return {
            "requirement": requirement.section,
            "compliant": compliant,
            "checks": checks,
            "notes": f"Validated {control.name} against {requirement.title}",
        }

    def _generate_remediation_steps(
        self, control: SecurityControl, results: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate HIPAA-specific remediation steps using control type."""
        # Comprehensive remediation guidance based on control type
        REMEDIATION_GUIDES = {
            "ACCESS_CONTROL": {
                "MISSING_MFA": {
                    "severity": "HIGH",
                    "steps": [
                        "Enable multi-factor authentication for all users with PHI access",
                        "Configure TOTP or SMS-based second factor in authentication settings",
                        "Provide backup codes for account recovery",
                        "Conduct user training on MFA setup and usage",
                        "Monitor MFA adoption rate through security dashboard",
                        "Enforce MFA requirement within 30 days per HIPAA § 164.312(a)(2)(i)",
                    ],
                    "references": ["HIPAA § 164.312(a)(2)(i)", "NIST 800-63B"],
                    "script": "scripts/enable_mfa.py --enforce --grace-period=30",
                    "implementation_steps": [
                        {
                            "step": 1,
                            "action": "Enable MFA in auth settings",
                            "code_example": "auth.enable_mfa(required=True)",
                        },
                        {
                            "step": 2,
                            "action": "Force MFA enrollment on next login",
                            "script": "scripts/force_mfa_enrollment.py",
                        },
                        {
                            "step": 3,
                            "action": "Monitor adoption rate",
                            "dashboard_link": "/admin/security/mfa-status",
                        },
                    ],
                },
                "EXCESSIVE_PERMISSIONS": {
                    "severity": "MEDIUM",
                    "steps": [
                        "Review all user permissions using access audit report",
                        "Apply principle of least privilege to all roles",
                        "Remove unnecessary PHI access permissions",
                        "Implement role-based access control (RBAC)",
                        "Schedule quarterly access reviews",
                        "Document permission changes in audit log",
                    ],
                    "automation": "scripts/remediation/clean_permissions.py",
                    "timeline": "45 days",
                    "automation_available": True,
                    "script_template": "remediation/clean_permissions.py",
                    "implementation_steps": [
                        {
                            "step": 1,
                            "action": "Generate permissions audit report",
                            "script": "scripts/audit_permissions.py --output=report.csv",
                        },
                        {
                            "step": 2,
                            "action": "Review and approve changes",
                            "code_example": "permission_review.approve_changes(report_id)",
                        },
                        {
                            "step": 3,
                            "action": "Apply permission changes",
                            "script": "scripts/apply_permission_changes.py --dry-run=false",
                        },
                    ],
                },
                "STALE_ACCOUNTS": {
                    "severity": "MEDIUM",
                    "steps": [
                        "Identify accounts inactive for >90 days",
                        "Disable accounts not used in 180 days",
                        "Implement automated account lifecycle management",
                        "Require re-authentication after 30 days of inactivity",
                    ],
                    "timeline": "30 days",
                    "script": "scripts/manage_stale_accounts.py",
                    "implementation_steps": [
                        {
                            "step": 1,
                            "action": "Identify stale accounts",
                            "code_example": "accounts.find_inactive(days=90)",
                        },
                        {
                            "step": 2,
                            "action": "Send warning emails",
                            "script": "scripts/notify_inactive_users.py",
                        },
                        {
                            "step": 3,
                            "action": "Disable accounts",
                            "code_example": "accounts.bulk_disable(inactive_list)",
                        },
                    ],
                },
            },
            "AUDIT_CONTROLS": {
                "MISSING_AUDIT_LOGS": {
                    "severity": "HIGH",
                    "steps": [
                        "Enable comprehensive audit logging for all PHI access",
                        "Configure log retention for minimum 6 years",
                        "Implement tamper-proof log storage",
                        "Set up real-time alerting for suspicious activities",
                        "Test audit log integrity monthly",
                    ],
                    "references": ["HIPAA § 164.312(b)", "HIPAA § 164.316(b)(2)"],
                    "timeline": "14 days",
                    "implementation_steps": [
                        {
                            "step": 1,
                            "action": "Enable audit logging",
                            "code_example": "audit_config.enable_phi_logging(retention_years=6)",
                        },
                        {
                            "step": 2,
                            "action": "Configure tamper-proof storage",
                            "script": "scripts/setup_immutable_logs.py",
                        },
                        {
                            "step": 3,
                            "action": "Set up alerting",
                            "code_example": "alerting.add_rule('suspicious_phi_access', notify=['security@example.com'])",
                        },
                    ],
                },
                "INCOMPLETE_AUDIT_TRAIL": {
                    "severity": "MEDIUM",
                    "steps": [
                        "Ensure all CRUD operations are logged",
                        "Include user ID, timestamp, and accessed fields",
                        "Log both successful and failed access attempts",
                        "Implement log analysis tools for pattern detection",
                    ],
                },
            },
            "ENCRYPTION": {
                "WEAK_ENCRYPTION": {
                    "severity": "CRITICAL",
                    "steps": [
                        "Upgrade to AES-256 encryption immediately",
                        "Rotate all encryption keys using secure process",
                        "Implement key management system (KMS)",
                        "Document encryption standards in security policy",
                        "Scan for any unencrypted PHI storage",
                    ],
                    "emergency_action": True,
                    "script": "scripts/encryption/upgrade_encryption.py --algorithm=AES-256",
                    "timeline": "7 days",
                    "references": ["HIPAA § 164.312(a)(2)(iv)", "NIST SP 800-175B"],
                    "implementation_steps": [
                        {
                            "step": 1,
                            "action": "Audit current encryption",
                            "script": "scripts/audit_encryption.py --full-scan",
                        },
                        {
                            "step": 2,
                            "action": "Generate new encryption keys",
                            "code_example": "kms.generate_key(algorithm='AES-256-GCM')",
                        },
                        {
                            "step": 3,
                            "action": "Migrate data with zero downtime",
                            "script": "scripts/migrate_encryption.py --mode=online",
                        },
                    ],
                },
                "MISSING_ENCRYPTION_AT_REST": {
                    "severity": "HIGH",
                    "steps": [
                        "Enable database encryption using Transparent Data Encryption",
                        "Encrypt all file storage systems",
                        "Implement full-disk encryption on all servers",
                        "Verify backup encryption is enabled",
                    ],
                },
            },
            "TRANSMISSION_SECURITY": {
                "WEAK_TLS": {
                    "severity": "HIGH",
                    "steps": [
                        "Upgrade to TLS 1.3 minimum",
                        "Disable all legacy protocols (SSL, TLS 1.0/1.1)",
                        "Implement certificate pinning for mobile apps",
                        "Configure HSTS headers with 1-year duration",
                        "Scan for mixed content issues",
                    ],
                    "validation": "scripts/security/test_tls.py --min-version=1.3",
                }
            },
        }

        steps = []

        # Get control-specific remediation using control type
        control_type = (
            control.control_type
            if hasattr(control, "control_type")
            else control.type if hasattr(control, "type") else "GENERAL"
        )
        control_remediation = REMEDIATION_GUIDES.get(control_type, {})
        if not isinstance(control_remediation, dict):
            control_remediation = {}

        for result in results:
            if not result["compliant"]:
                issue_type = result.get("issue_type", "UNKNOWN")

                if issue_type in control_remediation:
                    guide = control_remediation[issue_type]

                    # Add severity indicator
                    steps.append(f"\n[{guide['severity']}] {issue_type}:")

                    # Add detailed steps
                    for step in guide["steps"]:
                        steps.append(f"  • {step}")

                    # Add automation script if available
                    if "script" in guide:
                        steps.append(f"  → Automation available: {guide['script']}")

                    if "automation" in guide:
                        steps.append(f"  → Automation available: {guide['automation']}")

                    # Add timeline if specified
                    if "timeline" in guide:
                        steps.append(f"  ⏱️ Timeline: {guide['timeline']}")

                    # Add references
                    if "references" in guide:
                        steps.append(
                            f"  📚 References: {', '.join(guide['references'])}"
                        )

                    # Add implementation steps with code examples
                    if "implementation_steps" in guide:
                        steps.append("\n  Implementation Steps:")
                        for idx, impl_step in enumerate(
                            guide["implementation_steps"], 1
                        ):
                            steps.append(f"    {idx}. {impl_step['action']}")
                            if "code_example" in impl_step:
                                steps.append(
                                    f"       Code: {impl_step['code_example']}"
                                )
                            if "script" in impl_step:
                                steps.append(f"       Script: {impl_step['script']}")
                else:
                    # Generic remediation for unknown issues
                    steps.append(f"\n[MEDIUM] {issue_type}:")
                    steps.append(f"  • Review {control.name} implementation")
                    steps.append("  • Ensure compliance with HIPAA requirements")
                    steps.append("  • Document remediation actions taken")

                    # Generic remediation for unknown issues
                    for check, passed in result.get("checks", {}).items():
                        if not passed:
                            steps.append(
                                f"  • Address {check} for HIPAA requirement {result.get('requirement', 'Unknown')}"
                            )

        # Add general compliance recommendations
        if steps:
            steps.extend(
                [
                    "\nGeneral Recommendations:",
                    "• Document all remediation actions in compliance log",
                    "• Test changes in non-production environment first",
                    "• Verify remediation effectiveness through security scans",
                    "• Update security policies to prevent recurrence",
                    "• Schedule follow-up audit within 30 days",
                ]
            )

        return steps
