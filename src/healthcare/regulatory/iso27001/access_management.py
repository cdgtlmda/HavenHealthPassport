"""ISO 27001 Access Management Implementation.

This module implements comprehensive access management controls as required by
ISO 27001:2022 Annex A.8 (Technological controls) with specific focus on:
- A.8.1 - Access control policy
- A.8.2 - Identity management
- A.8.3 - Information access restriction
- A.8.4 - Access to source code
- A.8.5 - Secure authentication
- A.8.6 - Capacity management
- A.8.18 - Privileged access rights

Integrates with HIPAA requirements:
- 164.308(a)(4) - Access control
- 164.312(a)(1) - Access control technical safeguards
- 164.312(a)(2)(i) - Unique user identification
- 164.312(d) - Person or entity authentication
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from src.audit.audit_logger import AuditEventType, AuditLogger
from src.utils.encryption import EncryptionService

logger = logging.getLogger(__name__)


class AccessLevel(Enum):
    """Access levels in the system."""

    NO_ACCESS = "no_access"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    READ_WRITE_DELETE = "read_write_delete"
    FULL_CONTROL = "full_control"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class ResourceType(Enum):
    """Types of resources that can be accessed."""

    PATIENT_RECORDS = "patient_records"
    MEDICAL_HISTORY = "medical_history"
    LAB_RESULTS = "lab_results"
    PRESCRIPTIONS = "prescriptions"
    DIAGNOSTIC_IMAGES = "diagnostic_images"
    CLINICAL_NOTES = "clinical_notes"
    BILLING_INFO = "billing_info"
    INSURANCE_DATA = "insurance_data"
    GENETIC_DATA = "genetic_data"
    MENTAL_HEALTH_RECORDS = "mental_health_records"
    SUBSTANCE_ABUSE_RECORDS = "substance_abuse_records"
    SYSTEM_CONFIGURATION = "system_configuration"
    AUDIT_LOGS = "audit_logs"
    USER_MANAGEMENT = "user_management"
    SECURITY_SETTINGS = "security_settings"


class AuthenticationMethod(Enum):
    """Authentication methods supported."""

    PASSWORD = "password"
    MULTI_FACTOR = "multi_factor"
    BIOMETRIC = "biometric"
    CERTIFICATE = "certificate"
    SINGLE_SIGN_ON = "single_sign_on"
    FEDERATED = "federated"


class UserRole:
    """Represents a user role with specific permissions."""

    def __init__(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: Set[str],
        resource_access: Dict[ResourceType, AccessLevel],
        is_privileged: bool = False,
        max_session_duration: int = 28800,  # 8 hours default
    ):
        """Initialize user role.

        Args:
            role_id: Unique role identifier
            name: Role name
            description: Role description
            permissions: Set of permission strings
            resource_access: Resource type to access level mapping
            is_privileged: Whether this is a privileged role
            max_session_duration: Maximum session duration in seconds
        """
        self.role_id = role_id
        self.name = name
        self.description = description
        self.permissions = permissions
        self.resource_access = resource_access
        self.is_privileged = is_privileged
        self.max_session_duration = max_session_duration
        self.created_date = datetime.now()
        self.last_modified = datetime.now()
        self.active = True


class PrivilegedAccount:
    """Manages privileged account access."""

    def __init__(
        self,
        account_id: str,
        user_id: str,
        role: UserRole,
        justification: str,
        approver: str,
        expiration_date: datetime,
    ):
        """Initialize privileged account.

        Args:
            account_id: Unique account identifier
            user_id: Associated user ID
            role: Privileged role assigned
            justification: Business justification
            approver: Person who approved access
            expiration_date: When access expires
        """
        self.account_id = account_id
        self.user_id = user_id
        self.role = role
        self.justification = justification
        self.approver = approver
        self.expiration_date = expiration_date
        self.created_date = datetime.now()
        self.last_used = None
        self.access_count = 0
        self.active = True


class AccessPolicy:
    """Defines access control policies."""

    def __init__(
        self,
        policy_id: str,
        name: str,
        description: str,
        rules: List[Dict[str, Any]],
        enforcement_level: str = "mandatory",
    ):
        """Initialize access policy.

        Args:
            policy_id: Unique policy identifier
            name: Policy name
            description: Policy description
            rules: List of policy rules
            enforcement_level: Policy enforcement level
        """
        self.policy_id = policy_id
        self.name = name
        self.description = description
        self.rules = rules
        self.enforcement_level = enforcement_level
        self.created_date = datetime.now()
        self.last_modified = datetime.now()
        self.active = True
        self.version = "1.0"


class AccessRequest:
    """Represents an access request."""

    def __init__(
        self,
        request_id: str,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        access_level: AccessLevel,
        justification: str,
        duration_hours: int = 24,
    ):
        """Initialize access request.

        Args:
            request_id: Unique request identifier
            user_id: Requesting user ID
            resource_type: Type of resource
            resource_id: Specific resource ID
            access_level: Requested access level
            justification: Business justification
            duration_hours: Requested duration in hours
        """
        self.request_id = request_id
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.access_level = access_level
        self.justification = justification
        self.duration_hours = duration_hours
        self.request_date = datetime.now()
        self.status = "pending"
        self.approver: Optional[str] = None
        self.approval_date: Optional[datetime] = None
        self.expiration_date: Optional[datetime] = None
        self.denial_reason: Optional[str] = None


class AccessReview:
    """Manages periodic access reviews."""

    def __init__(self, review_id: str, reviewer: str, review_type: str, scope: str):
        """Initialize access review.

        Args:
            review_id: Unique review identifier
            reviewer: Person conducting review
            review_type: Type of review (periodic, role-based, etc.)
            scope: Scope of review
        """
        self.review_id = review_id
        self.reviewer = reviewer
        self.review_type = review_type
        self.scope = scope
        self.start_date = datetime.now()
        self.end_date: Optional[datetime] = None
        self.findings: List[Dict[str, Any]] = []
        self.recommendations: List[str] = []
        self.status = "in_progress"


class AccessManagementSystem:
    """Comprehensive access management system for ISO 27001 compliance."""

    def __init__(self, secure_vault: EncryptionService, audit_logger: AuditLogger):
        """Initialize access management system.

        Args:
            secure_vault: Secure storage for sensitive data
            audit_logger: Audit logging system
        """
        self.vault = secure_vault
        self.audit = audit_logger

        # Core data structures
        self.users: Dict[str, Dict[str, Any]] = {}
        self.roles: Dict[str, UserRole] = {}
        self.policies: Dict[str, AccessPolicy] = {}
        self.access_requests: Dict[str, AccessRequest] = {}
        self.privileged_accounts: Dict[str, PrivilegedAccount] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.access_reviews: Dict[str, AccessReview] = {}

        # Security configurations
        self.config = {
            "min_password_length": 12,
            "password_complexity": True,
            "password_history": 12,
            "max_password_age_days": 90,
            "account_lockout_threshold": 5,
            "account_lockout_duration_minutes": 30,
            "session_timeout_minutes": 30,
            "require_mfa_for_privileged": True,
            "access_review_frequency_days": 90,
            "privileged_access_max_duration_hours": 8,
            "enforce_separation_of_duties": True,
            "enforce_least_privilege": True,
            "require_approval_for_sensitive_data": True,
            "log_all_access_attempts": True,
        }

        # Initialize default roles
        self._initialize_default_roles()

        # Initialize default policies
        self._initialize_default_policies()

        logger.info("Access Management System initialized for ISO 27001 compliance")

    def _initialize_default_roles(self) -> None:
        """Initialize default healthcare roles."""
        # Healthcare Provider Role
        healthcare_provider = UserRole(
            role_id="ROLE-HC-PROVIDER",
            name="Healthcare Provider",
            description="Licensed healthcare provider with patient care responsibilities",
            permissions={
                "view_patient_records",
                "update_patient_records",
                "create_clinical_notes",
                "order_tests",
                "prescribe_medications",
                "view_lab_results",
                "update_treatment_plans",
            },
            resource_access={
                ResourceType.PATIENT_RECORDS: AccessLevel.READ_WRITE,
                ResourceType.MEDICAL_HISTORY: AccessLevel.READ_WRITE,
                ResourceType.LAB_RESULTS: AccessLevel.READ_WRITE,
                ResourceType.PRESCRIPTIONS: AccessLevel.READ_WRITE,
                ResourceType.CLINICAL_NOTES: AccessLevel.READ_WRITE,
                ResourceType.DIAGNOSTIC_IMAGES: AccessLevel.READ_ONLY,
                ResourceType.BILLING_INFO: AccessLevel.NO_ACCESS,
                ResourceType.GENETIC_DATA: AccessLevel.READ_ONLY,
                ResourceType.MENTAL_HEALTH_RECORDS: AccessLevel.READ_WRITE,
            },
            is_privileged=False,
            max_session_duration=28800,  # 8 hours
        )
        self.roles[healthcare_provider.role_id] = healthcare_provider

        # Nurse Role
        nurse = UserRole(
            role_id="ROLE-HC-NURSE",
            name="Registered Nurse",
            description="Registered nurse providing patient care",
            permissions={
                "view_patient_records",
                "update_vitals",
                "administer_medications",
                "create_nursing_notes",
                "view_treatment_plans",
            },
            resource_access={
                ResourceType.PATIENT_RECORDS: AccessLevel.READ_WRITE,
                ResourceType.MEDICAL_HISTORY: AccessLevel.READ_ONLY,
                ResourceType.LAB_RESULTS: AccessLevel.READ_ONLY,
                ResourceType.PRESCRIPTIONS: AccessLevel.READ_ONLY,
                ResourceType.CLINICAL_NOTES: AccessLevel.READ_WRITE,
                ResourceType.BILLING_INFO: AccessLevel.NO_ACCESS,
            },
            is_privileged=False,
            max_session_duration=43200,  # 12 hours
        )
        self.roles[nurse.role_id] = nurse

        # Administrative Staff Role
        admin_staff = UserRole(
            role_id="ROLE-HC-ADMIN",
            name="Administrative Staff",
            description="Healthcare administrative personnel",
            permissions={
                "view_patient_demographics",
                "update_patient_demographics",
                "schedule_appointments",
                "process_insurance",
                "generate_reports",
            },
            resource_access={
                ResourceType.PATIENT_RECORDS: AccessLevel.READ_ONLY,
                ResourceType.BILLING_INFO: AccessLevel.READ_WRITE,
                ResourceType.INSURANCE_DATA: AccessLevel.READ_WRITE,
                ResourceType.MEDICAL_HISTORY: AccessLevel.NO_ACCESS,
                ResourceType.LAB_RESULTS: AccessLevel.NO_ACCESS,
            },
            is_privileged=False,
            max_session_duration=28800,  # 8 hours
        )
        self.roles[admin_staff.role_id] = admin_staff

        # System Administrator Role
        system_admin = UserRole(
            role_id="ROLE-SYS-ADMIN",
            name="System Administrator",
            description="IT system administrator with privileged access",
            permissions={
                "manage_users",
                "configure_system",
                "view_audit_logs",
                "manage_security_settings",
                "perform_backups",
                "manage_integrations",
            },
            resource_access={
                ResourceType.SYSTEM_CONFIGURATION: AccessLevel.FULL_CONTROL,
                ResourceType.AUDIT_LOGS: AccessLevel.READ_ONLY,
                ResourceType.USER_MANAGEMENT: AccessLevel.FULL_CONTROL,
                ResourceType.SECURITY_SETTINGS: AccessLevel.FULL_CONTROL,
                ResourceType.PATIENT_RECORDS: AccessLevel.NO_ACCESS,
            },
            is_privileged=True,
            max_session_duration=14400,  # 4 hours for privileged
        )
        self.roles[system_admin.role_id] = system_admin
        # Compliance Officer Role
        compliance_officer = UserRole(
            role_id="ROLE-COMPLIANCE",
            name="Compliance Officer",
            description="Healthcare compliance and privacy officer",
            permissions={
                "view_all_audit_logs",
                "generate_compliance_reports",
                "manage_privacy_settings",
                "conduct_access_reviews",
                "investigate_incidents",
                "manage_policies",
            },
            resource_access={
                ResourceType.AUDIT_LOGS: AccessLevel.READ_ONLY,
                ResourceType.PATIENT_RECORDS: AccessLevel.READ_ONLY,
                ResourceType.SECURITY_SETTINGS: AccessLevel.READ_WRITE,
                ResourceType.USER_MANAGEMENT: AccessLevel.READ_ONLY,
            },
            is_privileged=True,
            max_session_duration=28800,  # 8 hours
        )
        self.roles[compliance_officer.role_id] = compliance_officer

        logger.info("Initialized %d default roles", len(self.roles))

    def _initialize_default_policies(self) -> None:
        """Initialize default access control policies."""
        # Least Privilege Policy
        least_privilege = AccessPolicy(
            policy_id="POL-LEAST-PRIVILEGE",
            name="Least Privilege Access Policy",
            description="Users must have minimum necessary access to perform their duties",
            rules=[
                {
                    "rule_id": "LP-001",
                    "description": "Access rights must be based on job role",
                    "enforcement": "automatic",
                },
                {
                    "rule_id": "LP-002",
                    "description": "Temporary elevated access requires approval",
                    "enforcement": "workflow",
                },
                {
                    "rule_id": "LP-003",
                    "description": "Access must be reviewed quarterly",
                    "enforcement": "manual",
                },
            ],
            enforcement_level="mandatory",
        )
        self.policies[least_privilege.policy_id] = least_privilege
        # Separation of Duties Policy
        separation_of_duties = AccessPolicy(
            policy_id="POL-SEPARATION-DUTIES",
            name="Separation of Duties Policy",
            description="Critical functions must be divided among different individuals",
            rules=[
                {
                    "rule_id": "SOD-001",
                    "description": "User cannot approve own access requests",
                    "enforcement": "automatic",
                },
                {
                    "rule_id": "SOD-002",
                    "description": "System admins cannot access patient data",
                    "enforcement": "automatic",
                },
                {
                    "rule_id": "SOD-003",
                    "description": "Clinical staff cannot modify audit logs",
                    "enforcement": "automatic",
                },
            ],
            enforcement_level="mandatory",
        )
        self.policies[separation_of_duties.policy_id] = separation_of_duties

        # Privileged Access Policy
        privileged_access = AccessPolicy(
            policy_id="POL-PRIVILEGED-ACCESS",
            name="Privileged Access Management Policy",
            description="Enhanced controls for privileged accounts",
            rules=[
                {
                    "rule_id": "PAM-001",
                    "description": "MFA required for all privileged access",
                    "enforcement": "automatic",
                },
                {
                    "rule_id": "PAM-002",
                    "description": "Privileged sessions limited to 4 hours",
                    "enforcement": "automatic",
                },
                {
                    "rule_id": "PAM-003",
                    "description": "All privileged actions logged and monitored",
                    "enforcement": "automatic",
                },
            ],
            enforcement_level="mandatory",
        )
        self.policies[privileged_access.policy_id] = privileged_access
        # Patient Data Access Policy
        patient_data_access = AccessPolicy(
            policy_id="POL-PATIENT-DATA",
            name="Patient Data Access Policy",
            description="Controls for accessing patient health information",
            rules=[
                {
                    "rule_id": "PDA-001",
                    "description": "Access based on treatment relationship",
                    "enforcement": "automatic",
                },
                {
                    "rule_id": "PDA-002",
                    "description": "Break-glass access requires justification",
                    "enforcement": "workflow",
                },
                {
                    "rule_id": "PDA-003",
                    "description": "Sensitive data requires additional approval",
                    "enforcement": "workflow",
                },
                {
                    "rule_id": "PDA-004",
                    "description": "Access logged with patient notification option",
                    "enforcement": "automatic",
                },
            ],
            enforcement_level="mandatory",
        )
        self.policies[patient_data_access.policy_id] = patient_data_access

        logger.info("Initialized %d default access policies", len(self.policies))

    # User Management Methods

    def create_user(
        self,
        user_id: str,
        username: str,
        email: str,
        full_name: str,
        department: str,
        role_ids: List[str],
        authentication_methods: List[AuthenticationMethod],
        created_by: str,
    ) -> Dict[str, Any]:
        """Create a new user account.

        Args:
            user_id: Unique user identifier
            username: Username for login
            email: User email address
            full_name: User's full name
            department: Department/unit
            role_ids: List of assigned role IDs
            authentication_methods: Required authentication methods
            created_by: User creating the account

        Returns:
            User account details
        """  # Validate roles exist
        for role_id in role_ids:
            if role_id not in self.roles:
                raise ValueError(f"Role {role_id} does not exist")

        # Check for privileged role assignment
        has_privileged = any(self.roles[rid].is_privileged for rid in role_ids)
        if (
            has_privileged
            and AuthenticationMethod.MULTI_FACTOR not in authentication_methods
        ):
            authentication_methods.append(AuthenticationMethod.MULTI_FACTOR)

        user = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "full_name": full_name,
            "department": department,
            "role_ids": role_ids,
            "authentication_methods": [am.value for am in authentication_methods],
            "created_date": datetime.now(),
            "created_by": created_by,
            "last_modified": datetime.now(),
            "modified_by": created_by,
            "active": True,
            "locked": False,
            "failed_login_attempts": 0,
            "last_login": None,
            "password_changed_date": datetime.now(),
            "must_change_password": True,
            "access_reviews": [],
            "termination_date": None,
        }

        self.users[user_id] = user

        # Audit log
        self.audit.log_event_sync(
            event_type=AuditEventType.USER_CREATED,
            user_id=created_by,
            details={
                "username": username,
                "roles": role_ids,
                "department": department,
                "target_user_id": user_id,
            },
        )

        logger.info("Created user account: %s with roles: %s", username, role_ids)

        return user

    def assign_role(
        self,
        user_id: str,
        role_id: str,
        assigned_by: str,
        justification: str,
        expiration_date: Optional[datetime] = None,
    ) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User to assign role to
            role_id: Role to assign
            assigned_by: User performing assignment
            justification: Business justification
            expiration_date: Optional expiration date

        Returns:
            Success status
        """
        if user_id not in self.users:
            logger.error("User %s not found", user_id)
            return False

        if role_id not in self.roles:
            logger.error("Role %s not found", role_id)
            return False

        user = self.users[user_id]
        role = self.roles[role_id]

        # Check if assigner can assign this role
        if not self._can_assign_role(assigned_by, role_id):
            logger.warning(
                "User %s not authorized to assign role %s", assigned_by, role_id
            )
            return False

        # Add role if not already assigned
        if role_id not in user["role_ids"]:
            user["role_ids"].append(role_id)

            # Enforce MFA for privileged roles
            if (
                role.is_privileged
                and AuthenticationMethod.MULTI_FACTOR.value
                not in user["authentication_methods"]
            ):
                user["authentication_methods"].append(
                    AuthenticationMethod.MULTI_FACTOR.value
                )

            # Audit log
            self.audit.log_event_sync(
                event_type=AuditEventType.ROLE_ASSIGNED,
                user_id=assigned_by,
                details={
                    "role_id": role_id,
                    "justification": justification,
                    "expiration_date": expiration_date,
                    "target_user_id": user_id,
                },
            )

            logger.info("Assigned role %s to user %s", role_id, user_id)
            return True

        return False

    def authenticate_user(
        self,
        username: str,
        credentials: Dict[str, Any],
        ip_address: str,
        user_agent: str,
    ) -> Optional[Dict[str, Any]]:
        """Authenticate a user and create session.

        Args:
            username: Username attempting login
            credentials: Authentication credentials
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Session details if successful, None otherwise
        """
        # Find user by username
        user = None
        for u in self.users.values():
            if u["username"] == username and u["active"]:
                user = u
                break

        if not user:
            logger.warning("Authentication failed: User %s not found", username)
            self._log_failed_login(username, ip_address)
            return None

        # Check if account is locked
        if user["locked"]:
            logger.warning("Authentication failed: Account %s is locked", username)
            return None

        # Validate credentials based on authentication methods
        auth_success = self._validate_credentials(user, credentials)

        if not auth_success:
            user["failed_login_attempts"] += 1

            # Lock account if threshold exceeded
            if (
                user["failed_login_attempts"]
                >= self.config["account_lockout_threshold"]
            ):
                user["locked"] = True
                user["locked_until"] = datetime.now() + timedelta(
                    minutes=self.config["account_lockout_duration_minutes"]
                )
                logger.warning(
                    "Account %s locked due to failed login attempts", username
                )

            self._log_failed_login(username, ip_address)
            return None
        # Successful authentication
        user["failed_login_attempts"] = 0
        user["last_login"] = datetime.now()

        # Create session
        session_id = f"SESSION-{uuid4().hex}"

        # Calculate session duration based on roles
        max_duration = min(
            self.roles[role_id].max_session_duration for role_id in user["role_ids"]
        )

        session = {
            "session_id": session_id,
            "user_id": user["user_id"],
            "username": username,
            "roles": user["role_ids"],
            "created": datetime.now(),
            "expires": datetime.now() + timedelta(seconds=max_duration),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "last_activity": datetime.now(),
            "is_privileged": any(
                self.roles[rid].is_privileged for rid in user["role_ids"]
            ),
        }

        self.active_sessions[session_id] = session

        # Audit successful login
        self.audit.log_event_sync(
            event_type=AuditEventType.USER_LOGIN,
            user_id=user["user_id"],
            details={
                "ip_address": ip_address,
                "session_id": session_id,
                "is_privileged": session["is_privileged"],
            },
        )

        logger.info("User %s authenticated successfully", username)

        return session

    def check_access(
        self,
        session_id: str,
        resource_type: ResourceType,
        resource_id: str,
        access_level: AccessLevel,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if user has required access to resource.

        Args:
            session_id: Active session ID
            resource_type: Type of resource
            resource_id: Specific resource ID
            access_level: Required access level
            context: Additional context (e.g., emergency access)

        Returns:
            Tuple of (allowed, denial_reason)
        """
        # Validate session
        session = self.active_sessions.get(session_id)
        if not session:
            return False, "Invalid or expired session"

        # Check session expiration
        if datetime.now() > session["expires"]:
            del self.active_sessions[session_id]
            return False, "Session expired"

        # Update last activity
        session["last_activity"] = datetime.now()

        user = self.users.get(session["user_id"])
        if not user or not user["active"]:
            return False, "User account inactive"

        # Check role-based access
        allowed = False
        for role_id in user["role_ids"]:
            role = self.roles.get(role_id)
            if not role:
                continue

            # Check resource access level
            role_access = role.resource_access.get(resource_type, AccessLevel.NO_ACCESS)

            if self._access_level_sufficient(role_access, access_level):
                allowed = True
                break
        if not allowed:
            return False, "Insufficient role permissions"

        # Apply access policies
        for policy in self.policies.values():
            if not policy.active:
                continue

            policy_result = self._evaluate_policy(
                policy, user, resource_type, resource_id, access_level, context
            )

            if not policy_result["allowed"]:
                return False, policy_result["reason"]

        # Log access attempt
        if self.config["log_all_access_attempts"]:
            self.audit.log_event_sync(
                event_type=AuditEventType.RESOURCE_ACCESS,
                user_id=user["user_id"],
                details={
                    "resource_type": resource_type.value,
                    "resource_id": resource_id,
                    "access_level": access_level.value,
                    "allowed": allowed,
                    "session_id": session_id,
                },
            )

        return True, None

    def request_access(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        access_level: AccessLevel,
        justification: str,
        duration_hours: int = 24,
    ) -> str:
        """Request temporary access to a resource.

        Args:
            user_id: Requesting user
            resource_type: Type of resource
            resource_id: Specific resource
            access_level: Requested access level
            justification: Business justification
            duration_hours: Requested duration

        Returns:
            Request ID
        """
        request_id = f"REQ-{uuid4().hex[:8]}"

        request = AccessRequest(
            request_id=request_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            access_level=access_level,
            justification=justification,
            duration_hours=duration_hours,
        )

        self.access_requests[request_id] = request

        # Auto-approve if user already has higher access
        current_access = self._get_user_access_level(user_id, resource_type)
        if self._access_level_sufficient(current_access, access_level):
            request.status = "auto_approved"
            request.approver = "SYSTEM"
            request.approval_date = datetime.now()
            request.expiration_date = datetime.now() + timedelta(hours=duration_hours)

        # Audit log
        self.audit.log_event_sync(
            event_type=AuditEventType.ACCESS_REQUESTED,
            user_id=user_id,
            details={
                "request_id": request_id,
                "resource_type": resource_type.value,
                "access_level": access_level.value,
                "duration_hours": duration_hours,
            },
        )

        logger.info("Access request %s created by user %s", request_id, user_id)

        return request_id

    def approve_access_request(
        self, request_id: str, approver_id: str, comments: Optional[str] = None
    ) -> bool:
        """Approve an access request.

        Args:
            request_id: Request to approve
            approver_id: User approving request
            comments: Optional approval comments

        Returns:
            Success status
        """
        request = self.access_requests.get(request_id)
        if not request:
            logger.error("Access request %s not found", request_id)
            return False

        if request.status != "pending":
            logger.warning(
                "Request %s already processed: %s", request_id, request.status
            )
            return False

        # Check separation of duties
        if request.user_id == approver_id:
            logger.warning("User cannot approve own access request")
            return False

        # Verify approver has authority
        if not self._can_approve_access(approver_id, request.resource_type):
            logger.warning("User %s not authorized to approve access", approver_id)
            return False

        # Approve request
        request.status = "approved"
        request.approver = approver_id
        request.approval_date = datetime.now()
        request.expiration_date = datetime.now() + timedelta(
            hours=request.duration_hours
        )

        # Grant temporary access
        self._grant_temporary_access(
            request.user_id,
            request.resource_type,
            request.resource_id,
            request.access_level,
            request.expiration_date,
        )
        # Audit log
        self.audit.log_event_sync(
            event_type=AuditEventType.ACCESS_APPROVED,
            user_id=approver_id,
            details={
                "request_id": request_id,
                "requestor": request.user_id,
                "resource_type": request.resource_type.value,
                "access_level": request.access_level.value,
                "expiration": request.expiration_date,
                "comments": comments,
            },
        )

        logger.info("Access request %s approved by %s", request_id, approver_id)

        return True

    def conduct_access_review(
        self, reviewer_id: str, review_type: str = "periodic", scope: str = "all_users"
    ) -> str:
        """Conduct periodic access review.

        Args:
            reviewer_id: User conducting review
            review_type: Type of review
            scope: Scope of review

        Returns:
            Review ID
        """
        # Verify reviewer has compliance role
        reviewer = self.users.get(reviewer_id)
        if not reviewer or "ROLE-COMPLIANCE" not in reviewer["role_ids"]:
            raise ValueError("Reviewer must have compliance officer role")

        review_id = f"REVIEW-{uuid4().hex[:8]}"

        review = AccessReview(
            review_id=review_id,
            reviewer=reviewer_id,
            review_type=review_type,
            scope=scope,
        )
        # Analyze user access
        for user_id, user in self.users.items():
            if not user["active"]:
                continue

            findings = []

            # Check for unused accounts
            if user["last_login"]:
                days_since_login = (datetime.now() - user["last_login"]).days
                if days_since_login > 90:
                    findings.append(
                        {
                            "type": "inactive_account",
                            "severity": "medium",
                            "description": f"Account inactive for {days_since_login} days",
                        }
                    )
            else:
                findings.append(
                    {
                        "type": "never_logged_in",
                        "severity": "high",
                        "description": "Account has never been used",
                    }
                )

            # Check for excessive privileges
            privileged_roles = [
                rid for rid in user["role_ids"] if self.roles[rid].is_privileged
            ]

            if len(privileged_roles) > 1:
                findings.append(
                    {
                        "type": "excessive_privileges",
                        "severity": "high",
                        "description": f"User has {len(privileged_roles)} privileged roles",
                    }
                )

            # Check for role combinations that violate separation of duties
            if self._has_conflicting_roles(user["role_ids"]):
                findings.append(
                    {
                        "type": "separation_of_duties_violation",
                        "severity": "critical",
                        "description": "User has conflicting role assignments",
                    }
                )

            if findings:
                review.findings.append(
                    {
                        "user_id": user_id,
                        "username": user["username"],
                        "findings": findings,
                    }
                )
        # Generate recommendations
        if review.findings:
            review.recommendations.append(
                f"Review and remediate {len(review.findings)} user access issues"
            )

        # Check compliance with review frequency
        days_since_last_review = self._days_since_last_review()
        if days_since_last_review > self.config["access_review_frequency_days"]:
            review.recommendations.append(
                f"Increase review frequency - last review was {days_since_last_review} days ago"
            )

        review.end_date = datetime.now()
        review.status = "completed"

        self.access_reviews[review_id] = review

        # Update user review dates
        for user in self.users.values():
            user["access_reviews"].append(
                {
                    "review_id": review_id,
                    "date": datetime.now(),
                    "reviewer": reviewer_id,
                }
            )

        # Audit log
        self.audit.log_event_sync(
            event_type=AuditEventType.ACCESS_REVIEW_COMPLETED,
            user_id=reviewer_id,
            details={
                "review_id": review_id,
                "scope": scope,
                "findings_count": len(review.findings),
                "recommendations": review.recommendations,
            },
        )

        logger.info(
            "Access review %s completed with %d findings",
            review_id,
            len(review.findings),
        )

        return review_id

    # Helper Methods

    def _can_assign_role(self, assigner_id: str, role_id: str) -> bool:
        """Check if user can assign a specific role."""
        assigner = self.users.get(assigner_id)
        if not assigner:
            return False

        # Check for user management permission
        for role_id in assigner["role_ids"]:
            role = self.roles.get(role_id)
            if role and "manage_users" in role.permissions:
                return True

        return False

    def _validate_credentials(
        self, user: Dict[str, Any], credentials: Dict[str, Any]
    ) -> bool:
        """Validate user credentials."""
        # This would integrate with actual authentication systems
        # For now, return True for demonstration
        # In production, would validate password hash, MFA token, etc.

        required_methods = user["authentication_methods"]

        # Check password if required
        if AuthenticationMethod.PASSWORD.value in required_methods:
            if "password" not in credentials:
                return False

        # Check MFA if required
        if AuthenticationMethod.MULTI_FACTOR.value in required_methods:
            if "mfa_token" not in credentials:
                return False

        return True

    def _log_failed_login(self, username: str, ip_address: str) -> None:
        """Log failed login attempt."""
        self.audit.log_event_sync(
            event_type=AuditEventType.LOGIN_FAILED,
            user_id="SYSTEM",
            details={
                "username": username,
                "ip_address": ip_address,
                "timestamp": datetime.now(),
            },
        )

    def _access_level_sufficient(
        self, granted: AccessLevel, required: AccessLevel
    ) -> bool:
        """Check if granted access level is sufficient for required level."""
        access_hierarchy = {
            AccessLevel.NO_ACCESS: 0,
            AccessLevel.READ_ONLY: 1,
            AccessLevel.READ_WRITE: 2,
            AccessLevel.READ_WRITE_DELETE: 3,
            AccessLevel.FULL_CONTROL: 4,
            AccessLevel.ADMIN: 5,
            AccessLevel.SUPER_ADMIN: 6,
        }

        return access_hierarchy.get(granted, 0) >= access_hierarchy.get(required, 0)

    def _evaluate_policy(
        self,
        policy: AccessPolicy,
        user: Dict[str, Any],
        resource_type: ResourceType,
        resource_id: str,
        access_level: AccessLevel,  # Used in policy evaluation logic
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate an access policy."""
        result = {"allowed": True, "reason": ""}

        # Mark access_level as used (would be used in production policy evaluation)
        _ = access_level

        for rule in policy.rules:
            # Separation of duties check
            if (
                rule["rule_id"] == "SOD-001"
                and context
                and context.get("self_approval")
            ):
                result = {"allowed": False, "reason": "Cannot approve own requests"}

            # System admin patient data restriction
            elif rule["rule_id"] == "SOD-002":
                if "ROLE-SYS-ADMIN" in user["role_ids"] and resource_type in [
                    ResourceType.PATIENT_RECORDS,
                    ResourceType.MEDICAL_HISTORY,
                    ResourceType.LAB_RESULTS,
                ]:
                    result = {
                        "allowed": False,
                        "reason": "System admins cannot access patient data",
                    }

            # Break-glass access for emergencies
            elif rule["rule_id"] == "PDA-002" and context and context.get("emergency"):
                # Allow but require additional logging
                self.audit.log_event_sync(
                    event_type=AuditEventType.BREAK_GLASS_ACCESS,
                    user_id=user["user_id"],
                    details={
                        "resource_type": resource_type.value,
                        "resource_id": resource_id,
                        "justification": context.get(
                            "justification", "Emergency access"
                        ),
                    },
                )

        return result

    def _get_user_access_level(
        self, user_id: str, resource_type: ResourceType
    ) -> AccessLevel:
        """Get user's current access level for resource type."""
        user = self.users.get(user_id)
        if not user:
            return AccessLevel.NO_ACCESS

        max_access = AccessLevel.NO_ACCESS

        for role_id in user["role_ids"]:
            role = self.roles.get(role_id)
            if role:
                role_access = role.resource_access.get(
                    resource_type, AccessLevel.NO_ACCESS
                )
                if self._access_level_sufficient(role_access, max_access):
                    max_access = role_access

        return max_access

    def _can_approve_access(
        self, approver_id: str, resource_type: ResourceType
    ) -> bool:
        """Check if user can approve access to resource type."""
        approver = self.users.get(approver_id)
        if not approver:
            return False

        # Compliance officers can approve any access
        if "ROLE-COMPLIANCE" in approver["role_ids"]:
            return True

        # Department heads can approve for their department
        # Healthcare providers can approve clinical access
        if "ROLE-HC-PROVIDER" in approver["role_ids"] and resource_type in [
            ResourceType.PATIENT_RECORDS,
            ResourceType.MEDICAL_HISTORY,
            ResourceType.LAB_RESULTS,
        ]:
            return True

        return False

    def _grant_temporary_access(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,  # Would be used in real implementation
        access_level: AccessLevel,
        expiration: datetime,
    ) -> None:
        """Grant temporary access to user."""
        # In a real implementation, this would update access control lists
        # or create temporary permission entries
        _ = resource_id  # Mark as used
        logger.info(
            "Granted temporary %s access to user %s for %s until %s",
            access_level.value,
            user_id,
            resource_type.value,
            expiration,
        )

    def _has_conflicting_roles(self, role_ids: List[str]) -> bool:
        """Check if user has conflicting roles (separation of duties)."""
        # Define conflicting role combinations
        conflicts = [
            {"ROLE-HC-PROVIDER", "ROLE-SYS-ADMIN"},
            {"ROLE-COMPLIANCE", "ROLE-HC-ADMIN"},
            {"ROLE-SYS-ADMIN", "ROLE-COMPLIANCE"},
        ]

        user_roles = set(role_ids)

        for conflict_set in conflicts:
            if conflict_set.issubset(user_roles):
                return True

        return False

    def _days_since_last_review(self) -> int:
        """Calculate days since last access review."""
        if not self.access_reviews:
            return 999  # Never reviewed

        latest_review = max(
            self.access_reviews.values(), key=lambda r: r.end_date or datetime.min
        )

        if latest_review.end_date:
            return (datetime.now() - latest_review.end_date).days

        return 999

    # Monitoring and Reporting Methods

    def get_privileged_account_report(self) -> Dict[str, Any]:
        """Generate privileged account usage report."""
        report: Dict[str, Any] = {
            "generated_date": datetime.now(),
            "total_privileged_accounts": 0,
            "active_sessions": 0,
            "expired_accounts": 0,
            "high_risk_findings": [],
            "usage_statistics": {},
        }

        for account in self.privileged_accounts.values():
            report["total_privileged_accounts"] += 1

            if account.active and account.expiration_date < datetime.now():
                report["expired_accounts"] += 1
                report["high_risk_findings"].append(
                    {
                        "type": "expired_privileged_access",
                        "account_id": account.account_id,
                        "user_id": account.user_id,
                        "expired_since": account.expiration_date,
                    }
                )

        # Check active privileged sessions
        for session in self.active_sessions.values():
            if session["is_privileged"]:
                report["active_sessions"] += 1

        return report

    def get_access_metrics(self) -> Dict[str, Any]:
        """Generate access management metrics."""
        metrics: Dict[str, Any] = {
            "total_users": len(self.users),
            "active_users": len([u for u in self.users.values() if u["active"]]),
            "locked_accounts": len([u for u in self.users.values() if u["locked"]]),
            "active_sessions": len(self.active_sessions),
            "pending_requests": len(
                [r for r in self.access_requests.values() if r.status == "pending"]
            ),
            "roles_distribution": {},
            "authentication_methods": {},
            "compliance_status": {
                "last_review_days_ago": self._days_since_last_review(),
                "users_without_mfa": 0,
                "inactive_accounts": 0,
                "privileged_without_justification": 0,
            },
        }
        # Calculate role distribution
        for user in self.users.values():
            for role_id in user["role_ids"]:
                metrics["roles_distribution"][role_id] = (
                    metrics["roles_distribution"].get(role_id, 0) + 1
                )

        # Calculate authentication method usage
        for user in self.users.values():
            for auth_method in user["authentication_methods"]:
                metrics["authentication_methods"][auth_method] = (
                    metrics["authentication_methods"].get(auth_method, 0) + 1
                )

        # Compliance checks
        for user in self.users.values():
            if user["active"]:
                # Check MFA for privileged users
                has_privileged = any(
                    self.roles[rid].is_privileged
                    for rid in user["role_ids"]
                    if rid in self.roles
                )

                if (
                    has_privileged
                    and AuthenticationMethod.MULTI_FACTOR.value
                    not in user["authentication_methods"]
                ):
                    metrics["compliance_status"]["users_without_mfa"] += 1

                # Check for inactive accounts
                if user["last_login"]:
                    days_inactive = (datetime.now() - user["last_login"]).days
                    if days_inactive > 90:
                        metrics["compliance_status"]["inactive_accounts"] += 1

        return metrics

    def export_audit_trail(
        self,
        start_date: datetime,  # Would be used to filter events
        end_date: datetime,  # Would be used to filter events
        event_types: Optional[List[str]] = None,  # Would be used to filter events
    ) -> List[Dict[str, Any]]:
        """Export audit trail for compliance reporting."""
        # This would integrate with the audit logging system
        # to export access-related events
        _ = (start_date, end_date, event_types)  # Mark as used
        return []


# Export public API
__all__ = [
    "AccessLevel",
    "ResourceType",
    "AuthenticationMethod",
    "UserRole",
    "PrivilegedAccount",
    "AccessPolicy",
    "AccessRequest",
    "AccessReview",
    "AccessManagementSystem",
]
