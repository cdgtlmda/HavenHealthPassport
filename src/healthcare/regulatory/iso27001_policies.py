"""ISO 27001 Healthcare Security Policies.

This module implements specific security policies required for ISO 27001
compliance in healthcare environments, including templates and procedures.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict
from uuid import uuid4

from src.healthcare.fhir_validator import FHIRValidator

# FHIR resource type for this module
__fhir_resource__ = "DocumentReference"

logger = logging.getLogger(__name__)


class FHIRDocumentReference(TypedDict, total=False):
    """FHIR DocumentReference resource type definition for policies."""

    resourceType: Literal["DocumentReference"]
    id: str
    masterIdentifier: Dict[str, Any]
    identifier: List[Dict[str, Any]]
    status: Literal["current", "superseded", "entered-in-error"]
    docStatus: Literal["preliminary", "final", "amended", "entered-in-error"]
    type: Dict[str, Any]
    category: List[Dict[str, Any]]
    subject: Dict[str, str]
    date: str
    author: List[Dict[str, Any]]
    authenticator: Dict[str, str]
    custodian: Dict[str, str]
    relatesTo: List[Dict[str, Any]]
    description: str
    securityLabel: List[Dict[str, Any]]
    content: List[Dict[str, Any]]
    context: Dict[str, Any]
    __fhir_resource__: Literal["DocumentReference"]


class PolicyType(Enum):
    """Types of security policies."""

    INFORMATION_SECURITY = "information_security"
    ACCESS_CONTROL = "access_control"
    DATA_CLASSIFICATION = "data_classification"
    ACCEPTABLE_USE = "acceptable_use"
    INCIDENT_RESPONSE = "incident_response"
    BUSINESS_CONTINUITY = "business_continuity"
    RISK_MANAGEMENT = "risk_management"
    ASSET_MANAGEMENT = "asset_management"
    PHYSICAL_SECURITY = "physical_security"
    NETWORK_SECURITY = "network_security"
    ENCRYPTION = "encryption"
    BACKUP_RECOVERY = "backup_recovery"
    CHANGE_MANAGEMENT = "change_management"
    VENDOR_MANAGEMENT = "vendor_management"
    TRAINING_AWARENESS = "training_awareness"


class HealthcareSecurityPolicies:
    """Healthcare-specific security policies for ISO 27001."""

    def __init__(self) -> None:
        """Initialize healthcare security policies."""
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.procedures: Dict[str, Dict[str, Any]] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._initialize_policy_templates()
        self.fhir_validator: Optional[FHIRValidator] = (
            None  # Will be initialized when needed
        )

    def _initialize_policy_templates(self) -> None:
        """Initialize healthcare policy templates."""
        # Information Security Policy
        self.templates["information_security"] = {
            "title": "Healthcare Information Security Policy",
            "version": "2.0",
            "sections": {
                "1_purpose": {
                    "title": "Purpose",
                    "content": [
                        "Establish information security requirements for protecting patient data",
                        "Ensure compliance with HIPAA, GDPR, and ISO 27001",
                        "Define roles and responsibilities for information security",
                        "Protect confidentiality, integrity, and availability of healthcare information",
                    ],
                },
                "2_scope": {
                    "title": "Scope",
                    "content": [
                        "All healthcare information systems and applications",
                        "All personnel handling patient data",
                        "Third-party service providers and business associates",
                        "All locations where patient data is processed or stored",
                    ],
                },
                "3_policy_statements": {
                    "title": "Policy Statements",
                    "content": {
                        "3.1": "Patient data must be classified and protected according to sensitivity",
                        "3.2": "Access to patient data shall be based on minimum necessary principle",
                        "3.3": "All patient data must be encrypted in transit and at rest",
                        "3.4": "Security incidents must be reported immediately",
                        "3.5": "Regular security assessments must be conducted",
                        "3.6": "All staff must complete annual security awareness training",
                    },
                },
                "4_responsibilities": {
                    "title": "Responsibilities",
                    "content": {
                        "CEO": "Overall accountability for information security",
                        "CISO": "Develop and maintain security program",
                        "IT_Department": "Implement technical security controls",
                        "Clinical_Staff": "Follow security procedures when accessing patient data",
                        "All_Employees": "Report security incidents and comply with policies",
                    },
                },
                "5_compliance": {
                    "title": "Compliance",
                    "content": [
                        "Non-compliance may result in disciplinary action",
                        "Regular audits will verify compliance",
                        "Exceptions must be documented and approved by CISO",
                    ],
                },
            },
            "related_standards": ["ISO 27001", "HIPAA", "GDPR"],
            "review_frequency": "annual",
        }

        # Access Control Policy
        self.templates["access_control"] = {
            "title": "Healthcare Access Control Policy",
            "version": "2.0",
            "sections": {
                "1_purpose": {
                    "title": "Purpose",
                    "content": [
                        "Control access to patient health information",
                        "Implement role-based access control (RBAC)",
                        "Ensure compliance with minimum necessary standard",
                        "Prevent unauthorized access to sensitive data",
                    ],
                },
                "2_access_requirements": {
                    "title": "Access Requirements",
                    "content": {
                        "2.1_user_registration": [
                            "Formal request and approval process",
                            "Identity verification required",
                            "Background checks for privileged access",
                            "Signed confidentiality agreement",
                        ],
                        "2.2_authentication": [
                            "Unique user identification required",
                            "Strong password policy (min 12 characters)",
                            "Multi-factor authentication for remote access",
                            "Biometric authentication for high-security areas",
                        ],
                        "2.3_authorization": [
                            "Role-based access control implementation",
                            "Principle of least privilege",
                            "Regular access reviews (quarterly)",
                            "Automatic de-provisioning upon termination",
                        ],
                    },
                },
                "3_access_controls": {
                    "title": "Access Control Measures",
                    "content": {
                        "3.1_physical": [
                            "Badge access to secure areas",
                            "Visitor management system",
                            "Clean desk policy",
                            "Locked storage for sensitive documents",
                        ],
                        "3.2_logical": [
                            "Network segmentation",
                            "Application-level access controls",
                            "Database encryption",
                            "Session timeout after 15 minutes",
                        ],
                        "3.3_privileged": [
                            "Privileged access management (PAM) system",
                            "Just-in-time access provisioning",
                            "Session recording for admin activities",
                            "Quarterly privileged access reviews",
                        ],
                    },
                },
                "4_monitoring": {
                    "title": "Access Monitoring",
                    "content": [
                        "Real-time access monitoring and alerting",
                        "Daily review of access logs",
                        "Monthly access pattern analysis",
                        "Immediate investigation of anomalies",
                    ],
                },
            },
            "controls_mapping": ["A.8.1", "A.8.2", "A.8.5"],
            "review_frequency": "annual",
        }

        # Incident Response Policy
        self.templates["incident_response"] = {
            "title": "Healthcare Security Incident Response Policy",
            "version": "2.0",
            "sections": {
                "1_purpose": {
                    "title": "Purpose",
                    "content": [
                        "Establish procedures for security incident response",
                        "Minimize impact of security incidents",
                        "Ensure HIPAA breach notification compliance",
                        "Preserve evidence for investigation",
                    ],
                },
                "2_incident_types": {
                    "title": "Incident Categories",
                    "content": {
                        "2.1_data_breach": "Unauthorized access or disclosure of patient data",
                        "2.2_malware": "Ransomware, viruses, or other malicious software",
                        "2.3_physical": "Theft or loss of devices containing patient data",
                        "2.4_system": "System compromise or unauthorized changes",
                        "2.5_insider": "Inappropriate access by authorized users",
                    },
                },
                "3_response_procedures": {
                    "title": "Response Procedures",
                    "content": {
                        "3.1_detection": [
                            "Automated monitoring and alerting",
                            "User reporting mechanisms",
                            "Regular security scans",
                            "Third-party notifications",
                        ],
                        "3.2_triage": [
                            "Initial assessment within 15 minutes",
                            "Severity classification (Critical/High/Medium/Low)",
                            "Immediate escalation for critical incidents",
                            "Incident response team activation",
                        ],
                        "3.3_containment": [
                            "Isolate affected systems",
                            "Disable compromised accounts",
                            "Preserve evidence",
                            "Prevent further damage",
                        ],
                        "3.4_eradication": [
                            "Remove malicious code",
                            "Patch vulnerabilities",
                            "Reset compromised credentials",
                            "Verify system integrity",
                        ],
                        "3.5_recovery": [
                            "Restore from clean backups",
                            "Rebuild compromised systems",
                            "Verify functionality",
                            "Monitor for recurrence",
                        ],
                        "3.6_lessons_learned": [
                            "Post-incident review within 48 hours",
                            "Root cause analysis",
                            "Update procedures",
                            "Share findings with team",
                        ],
                    },
                },
                "4_breach_notification": {
                    "title": "Breach Notification Requirements",
                    "content": {
                        "4.1_risk_assessment": [
                            "Determine if PHI was compromised",
                            "Assess harm to individuals",
                            "Document assessment process",
                            "Legal counsel consultation",
                        ],
                        "4.2_notification_timeline": {
                            "individuals": "Without unreasonable delay, max 60 days",
                            "OCR": "Within 60 days",
                            "media": "Within 60 days if >500 individuals",
                            "business_associates": "Immediately",
                        },
                        "4.3_notification_content": [
                            "Description of breach",
                            "Types of information involved",
                            "Steps individuals should take",
                            "Organization's response actions",
                            "Contact information",
                        ],
                    },
                },
                "5_incident_response_team": {
                    "title": "Incident Response Team",
                    "content": {
                        "team_lead": "CISO or designated security manager",
                        "technical_lead": "Senior IT security analyst",
                        "legal_counsel": "Healthcare compliance attorney",
                        "communications": "Public relations manager",
                        "clinical_representative": "Chief Medical Officer delegate",
                        "HR_representative": "For insider threat incidents",
                    },
                },
            },
            "related_procedures": [
                "Forensics",
                "Evidence Preservation",
                "Communication",
            ],
            "review_frequency": "semi-annual",
        }

        # Data Classification Policy
        self.templates["data_classification"] = {
            "title": "Healthcare Data Classification Policy",
            "version": "2.0",
            "sections": {
                "1_purpose": {
                    "title": "Purpose",
                    "content": [
                        "Classify healthcare data based on sensitivity",
                        "Define protection requirements for each classification",
                        "Ensure appropriate handling of patient information",
                        "Support compliance with privacy regulations",
                    ],
                },
                "2_classification_levels": {
                    "title": "Data Classification Levels",
                    "content": {
                        "2.1_restricted": {
                            "description": "Highly sensitive patient data",
                            "examples": [
                                "Genetic information",
                                "Mental health records",
                                "Substance abuse treatment",
                                "HIV/AIDS status",
                                "Sexual health data",
                            ],
                            "controls": [
                                "Encryption at rest and in transit",
                                "Access on strict need-to-know basis",
                                "Audit all access",
                                "Additional consent required",
                            ],
                        },
                        "2.2_confidential": {
                            "description": "Standard patient health information",
                            "examples": [
                                "Medical records",
                                "Diagnoses and treatment plans",
                                "Lab results",
                                "Prescription information",
                                "Insurance information",
                            ],
                            "controls": [
                                "Encryption required",
                                "Role-based access control",
                                "Regular access reviews",
                                "Standard HIPAA protections",
                            ],
                        },
                        "2.3_internal": {
                            "description": "Non-patient sensitive data",
                            "examples": [
                                "Employee records",
                                "Financial data",
                                "Strategic plans",
                                "Security configurations",
                            ],
                            "controls": [
                                "Access based on job function",
                                "Encryption for transmission",
                                "Secure storage",
                                "Non-disclosure agreements",
                            ],
                        },
                        "2.4_public": {
                            "description": "Information for public distribution",
                            "examples": [
                                "Marketing materials",
                                "General health education",
                                "Public announcements",
                                "De-identified statistics",
                            ],
                            "controls": [
                                "Approval before publication",
                                "Verify no PHI included",
                                "Standard handling",
                                "Public website posting allowed",
                            ],
                        },
                    },
                },
                "3_handling_requirements": {
                    "title": "Data Handling Requirements",
                    "content": {
                        "3.1_labeling": [
                            "Clear classification marking required",
                            "Electronic files must include metadata",
                            "Physical documents marked prominently",
                            "Email subject line classification tags",
                        ],
                        "3.2_storage": {
                            "restricted": "Encrypted database with access logging",
                            "confidential": "Encrypted storage, secure facilities",
                            "internal": "Access-controlled systems",
                            "public": "Standard storage acceptable",
                        },
                        "3.3_transmission": {
                            "restricted": "End-to-end encryption, secure channels only",
                            "confidential": "Encrypted transmission required",
                            "internal": "Secure corporate network or VPN",
                            "public": "Standard transmission acceptable",
                        },
                        "3.4_disposal": {
                            "restricted": "Certified destruction with certificate",
                            "confidential": "Secure shredding or wiping",
                            "internal": "Standard secure disposal",
                            "public": "Standard recycling acceptable",
                        },
                    },
                },
                "4_responsibilities": {
                    "title": "Responsibilities",
                    "content": {
                        "data_owners": "Classify data appropriately",
                        "users": "Handle according to classification",
                        "IT_security": "Implement technical controls",
                        "compliance": "Monitor and audit compliance",
                    },
                },
            },
            "review_frequency": "annual",
        }

    def create_policy(
        self, policy_type: PolicyType, customizations: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a security policy from template.

        Args:
            policy_type: Type of policy to create
            customizations: Custom content to merge

        Returns:
            Policy ID
        """
        template = self.templates.get(policy_type.value)
        if not template:
            raise ValueError(f"No template for policy type: {policy_type.value}")

        policy_id = f"POL-{policy_type.value.upper()}-{uuid4().hex[:8]}"

        # Create policy from template
        policy = {
            "policy_id": policy_id,
            "type": policy_type.value,
            "title": template["title"],
            "version": template["version"],
            "effective_date": datetime.now(),
            "next_review_date": datetime.now() + timedelta(days=365),
            "status": "draft",
            "content": template["sections"],
            "metadata": {
                "created_date": datetime.now(),
                "created_by": "system",
                "template_version": template["version"],
                "related_standards": template.get("related_standards", []),
                "review_frequency": template.get("review_frequency", "annual"),
            },
        }

        # Apply customizations
        if customizations:
            policy = self._merge_customizations(policy, customizations)

        self.policies[policy_id] = policy
        logger.info("Created policy: %s - %s", policy_id, policy["title"])

        return policy_id

    def create_procedure(
        self,
        procedure_name: str,
        policy_id: str,
        steps: List[Dict[str, Any]],
        roles: Dict[str, str],
    ) -> str:
        """Create a procedure linked to a policy.

        Args:
            procedure_name: Name of procedure
            policy_id: Related policy ID
            steps: Procedure steps
            roles: Roles and responsibilities

        Returns:
            Procedure ID
        """
        procedure_id = f"PROC-{uuid4().hex[:8]}"

        procedure = {
            "procedure_id": procedure_id,
            "name": procedure_name,
            "policy_id": policy_id,
            "version": "1.0",
            "effective_date": datetime.now(),
            "steps": steps,
            "roles": roles,
            "tools_required": [],
            "references": [],
            "status": "active",
        }

        self.procedures[procedure_id] = procedure
        logger.info("Created procedure: %s - %s", procedure_id, procedure_name)

        return procedure_id

    def approve_policy(
        self, policy_id: str, approver: str, comments: Optional[str] = None
    ) -> bool:
        """Approve a policy for implementation.

        Args:
            policy_id: Policy to approve
            approver: Person approving
            comments: Approval comments

        Returns:
            Success status
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return False

        policy["status"] = "approved"
        policy["metadata"]["approved_by"] = approver
        policy["metadata"]["approved_date"] = datetime.now()
        if comments:
            policy["metadata"]["approval_comments"] = comments

        logger.info("Policy approved: %s by %s", policy_id, approver)
        return True

    def review_policy(
        self, policy_id: str, reviewer: str, changes_required: bool, findings: List[str]
    ) -> Dict[str, Any]:
        """Review a policy for continued effectiveness.

        Args:
            policy_id: Policy to review
            reviewer: Person reviewing
            changes_required: Whether changes needed
            findings: Review findings

        Returns:
            Review results
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return {"error": "Policy not found"}

        review = {
            "review_id": f"REV-{uuid4().hex[:8]}",
            "policy_id": policy_id,
            "reviewer": reviewer,
            "review_date": datetime.now(),
            "changes_required": changes_required,
            "findings": findings,
            "previous_version": policy["version"],
        }

        # Update policy metadata
        if "reviews" not in policy["metadata"]:
            policy["metadata"]["reviews"] = []
        policy["metadata"]["reviews"].append(review)

        # Update next review date
        if policy["metadata"]["review_frequency"] == "annual":
            policy["next_review_date"] = datetime.now() + timedelta(days=365)
        elif policy["metadata"]["review_frequency"] == "semi-annual":
            policy["next_review_date"] = datetime.now() + timedelta(days=180)

        return review

    def distribute_policy(
        self,
        policy_id: str,
        distribution_list: List[str],
        require_acknowledgment: bool = True,
    ) -> Dict[str, Any]:
        """Distribute policy to staff.

        Args:
            policy_id: Policy to distribute
            distribution_list: List of recipients
            require_acknowledgment: Whether acknowledgment required

        Returns:
            Distribution tracking info
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return {"error": "Policy not found"}

        distribution = {
            "distribution_id": f"DIST-{uuid4().hex[:8]}",
            "policy_id": policy_id,
            "policy_title": policy["title"],
            "distribution_date": datetime.now(),
            "recipients": distribution_list,
            "require_acknowledgment": require_acknowledgment,
            "acknowledgments": {},
            "completion_status": "in_progress",
        }

        # In production, would send notifications
        logger.info(
            "Distributed policy %s to %d recipients", policy_id, len(distribution_list)
        )

        return distribution

    def get_policy_compliance_status(self, policy_id: str) -> Dict[str, Any]:
        """Get compliance status for a policy.

        Args:
            policy_id: Policy ID

        Returns:
            Compliance status
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return {"error": "Policy not found"}

        status = {
            "policy_id": policy_id,
            "policy_title": policy["title"],
            "status": policy["status"],
            "version": policy["version"],
            "effective_date": policy["effective_date"],
            "next_review_date": policy["next_review_date"],
            "compliance_metrics": {
                "acknowledgment_rate": 0,  # Would calculate from distributions
                "training_completion": 0,  # Would check training records
                "audit_findings": [],  # Would pull from audit system
                "incidents_related": 0,  # Would check incident system
            },
            "is_current": policy["next_review_date"] > datetime.now(),
            "days_until_review": (policy["next_review_date"] - datetime.now()).days,
        }

        return status

    def generate_policy_package(self, organization_name: str) -> Dict[str, Any]:
        """Generate complete policy package for organization.

        Args:
            organization_name: Name of organization

        Returns:
            Policy package
        """
        package: Dict[str, Any] = {
            "package_id": f"PKG-{uuid4().hex[:8]}",
            "organization": organization_name,
            "generated_date": datetime.now(),
            "iso_standard": "ISO 27001:2022",
            "healthcare_standards": ["HIPAA", "GDPR"],
            "policies": {},
            "procedures": {},
            "total_policies": 0,
            "total_procedures": 0,
        }

        # Create essential policies
        essential_policies = [
            PolicyType.INFORMATION_SECURITY,
            PolicyType.ACCESS_CONTROL,
            PolicyType.INCIDENT_RESPONSE,
            PolicyType.DATA_CLASSIFICATION,
        ]

        for policy_type in essential_policies:
            policy_id = self.create_policy(policy_type)
            self.approve_policy(policy_id, "CISO", "Auto-approved for package")
            if isinstance(package["policies"], dict):
                package["policies"][policy_type.value] = self.policies[policy_id]
            if isinstance(package["total_policies"], int):
                package["total_policies"] += 1

        # Create sample procedures
        sample_procedures = [
            {
                "name": "User Access Provisioning",
                "policy": PolicyType.ACCESS_CONTROL,
                "steps": [
                    {"step": 1, "action": "Submit access request form"},
                    {"step": 2, "action": "Manager approval"},
                    {"step": 3, "action": "Security review"},
                    {"step": 4, "action": "Account creation"},
                    {"step": 5, "action": "Access verification"},
                ],
            },
            {
                "name": "Security Incident Response",
                "policy": PolicyType.INCIDENT_RESPONSE,
                "steps": [
                    {"step": 1, "action": "Detect and report incident"},
                    {"step": 2, "action": "Initial triage"},
                    {"step": 3, "action": "Contain incident"},
                    {"step": 4, "action": "Investigate"},
                    {"step": 5, "action": "Remediate"},
                    {"step": 6, "action": "Document lessons learned"},
                ],
            },
        ]

        for proc in sample_procedures:
            # Find policy ID
            proc_policy_id: Optional[str] = None
            for pid, pol in self.policies.items():
                if (
                    "type" in pol
                    and "policy" in proc
                    and hasattr(proc["policy"], "value")
                    and pol["type"] == proc["policy"].value
                ):
                    proc_policy_id = pid
                    break

            if proc_policy_id:
                proc_id = self.create_procedure(
                    procedure_name=str(proc["name"]) if "name" in proc else "",
                    policy_id=proc_policy_id,
                    steps=(
                        proc["steps"]
                        if "steps" in proc and isinstance(proc["steps"], list)
                        else []
                    ),
                    roles={"all_staff": "Follow procedure"},
                )
                if isinstance(package["procedures"], dict) and isinstance(
                    proc["name"], str
                ):
                    package["procedures"][proc["name"]] = self.procedures[proc_id]
                if isinstance(package["total_procedures"], int):
                    package["total_procedures"] += 1

        return package

    def validate_fhir_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate policy document as FHIR DocumentReference resource.

        Args:
            document_data: Document data to validate

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Initialize FHIR validator if needed
        if self.fhir_validator is None:
            self.fhir_validator = FHIRValidator()

        # Ensure resource type
        if "resourceType" not in document_data:
            document_data["resourceType"] = "DocumentReference"

        # Validate using FHIR validator
        return self.fhir_validator.validate_resource("DocumentReference", document_data)

    def create_fhir_document_reference(
        self, policy_id: str, policy_type: PolicyType
    ) -> FHIRDocumentReference:
        """Create FHIR DocumentReference for a security policy.

        Args:
            policy_id: Policy identifier
            policy_type: Type of policy

        Returns:
            FHIR DocumentReference resource
        """
        policy = self.policies.get(policy_id, {})

        document_ref: FHIRDocumentReference = {
            "resourceType": "DocumentReference",
            "id": policy_id,
            "status": "current",
            "docStatus": "final" if policy.get("approved") else "preliminary",
            "type": {
                "coding": [
                    {
                        "system": "http://havenhealthpassport.org/fhir/CodeSystem/policy-types",
                        "code": policy_type.value,
                        "display": policy_type.value.replace("_", " ").title(),
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "69764-9",
                            "display": "Document type",
                        }
                    ],
                    "text": "Security Policy",
                }
            ],
            "date": policy.get("created_date", datetime.now()).isoformat(),
            "description": f"ISO 27001 {policy_type.value.replace('_', ' ').title()} Policy",
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "title": policy.get("title", ""),
                        "creation": policy.get(
                            "created_date", datetime.now()
                        ).isoformat(),
                    }
                }
            ],
            "__fhir_resource__": "DocumentReference",
        }

        # Add author if available
        if author := policy.get("created_by"):
            document_ref["author"] = [{"display": author}]

        # Add authenticator if approved
        if approver := policy.get("approved_by"):
            document_ref["authenticator"] = {"display": approver}

        return document_ref

    def _merge_customizations(
        self, policy: Dict[str, Any], customizations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge customizations into policy.

        Args:
            policy: Base policy
            customizations: Custom content

        Returns:
            Merged policy
        """
        # Deep merge logic would go here
        # For now, simple update
        policy.update(customizations)
        return policy


def validate_fhir(fhir_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate FHIR data for ISO 27001 policy documents.

    Args:
        fhir_data: FHIR data to validate

    Returns:
        Validation results
    """
    errors = []
    warnings = []

    # Check resource type
    if fhir_data.get("resourceType") != "DocumentReference":
        errors.append("Resource type must be DocumentReference for policy documents")

    # Check required fields
    required_fields = ["status", "type", "content"]
    for field in required_fields:
        if field not in fhir_data:
            errors.append(f"Required field '{field}' is missing")

    # Validate status
    if "status" in fhir_data:
        valid_statuses = ["current", "superseded", "entered-in-error"]
        if fhir_data["status"] not in valid_statuses:
            errors.append(f"Invalid status: {fhir_data['status']}")

    # Validate docStatus
    if "docStatus" in fhir_data:
        valid_doc_statuses = ["preliminary", "final", "amended", "entered-in-error"]
        if fhir_data["docStatus"] not in valid_doc_statuses:
            errors.append(f"Invalid docStatus: {fhir_data['docStatus']}")

    # Check for security labels
    if "securityLabel" not in fhir_data:
        warnings.append("Security labels are recommended for policy documents")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# Export public API
__all__ = ["PolicyType", "HealthcareSecurityPolicies", "validate_fhir"]
