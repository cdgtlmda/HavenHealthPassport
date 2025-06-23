"""FHIR Authorization Module.

This module implements role-based access control (RBAC) and fine-grained
authorization for FHIR resources in the Haven Health Passport system.
Includes encrypted access tokens and permission validation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.healthcare.fhir_validator import FHIRValidator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class FHIRAuthorizationResource(BaseModel):
    """FHIR Authorization resource type."""

    resourceType: Literal["Consent", "Contract", "Permission"] = "Consent"


class FHIRRole(str, Enum):
    """FHIR system roles."""

    PATIENT = "patient"
    PRACTITIONER = "practitioner"
    ADMIN = "admin"
    CAREGIVER = "caregiver"
    RESEARCHER = "researcher"
    EMERGENCY_RESPONDER = "emergency_responder"
    PUBLIC_HEALTH = "public_health"
    REFUGEE_OFFICER = "refugee_officer"


class ResourcePermission(str, Enum):
    """Resource-level permissions."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SEARCH = "search"
    HISTORY = "history"
    CREATE = "create"
    UPDATE = "update"
    PATCH = "patch"
    VREAD = "vread"  # Version read


class ResourceScope(BaseModel):
    """Defines scope of resource access."""

    resource_type: str
    permissions: List[ResourcePermission]
    conditions: Optional[Dict[str, Any]] = None

    class Config:
        """Pydantic configuration for ResourceScope."""

        use_enum_values = True


class RoleDefinition(BaseModel):
    """Defines a role with its permissions."""

    role: FHIRRole
    name: str
    description: str
    resource_scopes: List[ResourceScope]
    is_system_role: bool = True
    priority: int = 0  # Higher priority overrides lower


# Default role definitions
DEFAULT_ROLES = {
    FHIRRole.PATIENT: RoleDefinition(
        role=FHIRRole.PATIENT,
        name="Patient",
        description="Patient with access to their own health records",
        resource_scopes=[
            ResourceScope(
                resource_type="Patient",
                permissions=[ResourcePermission.READ, ResourcePermission.UPDATE],
                conditions={"owner": "self"},
            ),
            ResourceScope(
                resource_type="Observation",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"patient": "self"},
            ),
            ResourceScope(
                resource_type="Condition",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"patient": "self"},
            ),
            ResourceScope(
                resource_type="MedicationRequest",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"patient": "self"},
            ),
            ResourceScope(
                resource_type="Procedure",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"patient": "self"},
            ),
            ResourceScope(
                resource_type="DocumentReference",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.CREATE,
                    ResourcePermission.SEARCH,
                ],
                conditions={"patient": "self"},
            ),
            ResourceScope(
                resource_type="AllergyIntolerance",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"patient": "self"},
            ),
            ResourceScope(
                resource_type="Immunization",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"patient": "self"},
            ),
        ],
    ),
    FHIRRole.PRACTITIONER: RoleDefinition(
        role=FHIRRole.PRACTITIONER,
        name="Healthcare Practitioner",
        description="Healthcare provider with access to patient records",
        resource_scopes=[
            ResourceScope(
                resource_type="Patient",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.UPDATE,
                    ResourcePermission.SEARCH,
                ],
            ),
            ResourceScope(
                resource_type="Observation",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.CREATE,
                    ResourcePermission.UPDATE,
                    ResourcePermission.SEARCH,
                ],
            ),
            ResourceScope(
                resource_type="Condition",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.CREATE,
                    ResourcePermission.UPDATE,
                    ResourcePermission.SEARCH,
                ],
            ),
            ResourceScope(
                resource_type="MedicationRequest",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.CREATE,
                    ResourcePermission.UPDATE,
                    ResourcePermission.DELETE,
                    ResourcePermission.SEARCH,
                ],
            ),
            ResourceScope(
                resource_type="Procedure",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.CREATE,
                    ResourcePermission.UPDATE,
                    ResourcePermission.SEARCH,
                ],
            ),
        ],
        priority=10,
    ),
    FHIRRole.ADMIN: RoleDefinition(
        role=FHIRRole.ADMIN,
        name="System Administrator",
        description="Full system access",
        resource_scopes=[
            ResourceScope(
                resource_type="*",
                permissions=[
                    ResourcePermission.READ,
                    ResourcePermission.WRITE,
                    ResourcePermission.DELETE,
                    ResourcePermission.CREATE,
                    ResourcePermission.UPDATE,
                    ResourcePermission.SEARCH,
                    ResourcePermission.HISTORY,
                ],
            )
        ],
        priority=100,
    ),
    FHIRRole.EMERGENCY_RESPONDER: RoleDefinition(
        role=FHIRRole.EMERGENCY_RESPONDER,
        name="Emergency Responder",
        description="Emergency access to critical health information",
        resource_scopes=[
            ResourceScope(
                resource_type="Patient",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
            ),
            ResourceScope(
                resource_type="AllergyIntolerance",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
            ),
            ResourceScope(
                resource_type="Condition",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"severity": ["severe", "critical"]},
            ),
            ResourceScope(
                resource_type="MedicationRequest",
                permissions=[ResourcePermission.READ, ResourcePermission.SEARCH],
                conditions={"status": "active"},
            ),
        ],
        priority=20,
    ),
}


class AuthorizationContext(BaseModel):
    """Context for authorization decisions."""

    user_id: str
    roles: List[FHIRRole]
    organization_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    emergency_access: bool = False
    consent_overrides: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration for AuthorizationContext."""

        use_enum_values = True


class AuthorizationRequest(BaseModel):
    """Request for authorization check."""

    context: AuthorizationContext
    resource_type: str
    action: ResourcePermission
    resource_id: Optional[str] = None
    resource_data: Optional[Dict[str, Any]] = None
    compartment: Optional[str] = None

    class Config:
        """Pydantic configuration for AuthorizationRequest."""

        use_enum_values = True


class AuthorizationDecision(BaseModel):
    """Authorization decision result."""

    allowed: bool
    reasons: List[str] = Field(default_factory=list)
    applicable_roles: List[FHIRRole] = Field(default_factory=list)
    conditions_applied: List[str] = Field(default_factory=list)
    audit_info: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration for AuthorizationDecision."""

        use_enum_values = True


class ResourceFilter(BaseModel):
    """Filter to apply to resource queries."""

    field: str
    operator: str  # eq, ne, gt, lt, in, contains
    value: Any


class AuthorizationPolicy(BaseModel):
    """Custom authorization policy."""

    id: str
    name: str
    description: str
    priority: int = 0
    enabled: bool = True
    conditions: Dict[str, Any]
    effect: str  # "allow" or "deny"
    resource_types: List[str]
    actions: List[ResourcePermission]

    class Config:
        """Pydantic configuration for AuthorizationPolicy."""

        use_enum_values = True


class ConsentRecord(BaseModel):
    """Patient consent record."""

    patient_id: str
    consented_actors: List[str] = Field(default_factory=list)
    consented_purposes: List[str] = Field(default_factory=list)
    excluded_resources: List[str] = Field(default_factory=list)
    time_period_start: Optional[datetime] = None
    time_period_end: Optional[datetime] = None
    active: bool = True


class FHIRAuthorizationHandler:
    """Main authorization handler for FHIR resources.

    Implements role-based and attribute-based access control.
    """

    def __init__(self) -> None:
        """Initialize authorization handler."""
        self.roles = DEFAULT_ROLES.copy()
        self.custom_policies: List[AuthorizationPolicy] = []
        self.consent_records: Dict[str, ConsentRecord] = {}
        self._audit_enabled = True
        self.fhir_validator = FHIRValidator()

    def add_role(self, role_definition: RoleDefinition) -> None:
        """Add or update a role definition."""
        self.roles[role_definition.role] = role_definition
        logger.info(f"Added/updated role: {role_definition.role}")

    def add_policy(self, policy: AuthorizationPolicy) -> None:
        """Add a custom authorization policy."""
        self.custom_policies.append(policy)
        self.custom_policies.sort(key=lambda p: p.priority, reverse=True)
        logger.info(f"Added policy: {policy.name}")

    def add_consent(self, consent: ConsentRecord) -> None:
        """Add or update patient consent."""
        self.consent_records[consent.patient_id] = consent
        logger.info(f"Updated consent for patient: {consent.patient_id}")

    def set_audit_enabled(self, enabled: bool) -> None:
        """Enable or disable audit logging."""
        self._audit_enabled = enabled

    def check_authorization(
        self, request: AuthorizationRequest
    ) -> AuthorizationDecision:
        """Check authorization for request.

        Evaluates roles, policies, and consent to make authorization decision.
        """
        decision = AuthorizationDecision(
            allowed=False, reasons=[], applicable_roles=[], conditions_applied=[]
        )

        try:
            # Check custom deny policies first
            deny_decision = self._check_deny_policies(request)
            if deny_decision:
                return deny_decision

            # Check role-based permissions
            role_decision = self._check_role_permissions(request)
            if role_decision.allowed:
                decision = role_decision

            # Check custom allow policies
            policy_decision = self._check_allow_policies(request)
            if policy_decision.allowed:
                decision = policy_decision

            # Check patient consent if applicable
            if decision.allowed and self._is_patient_data(request):
                consent_decision = self._check_patient_consent(request)
                if not consent_decision.allowed:
                    decision = consent_decision

            # Apply emergency access override if needed
            if not decision.allowed and request.context.emergency_access:
                decision = self._check_emergency_access(request)

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Authorization check failed: {str(e)}")
            decision.allowed = False
            decision.reasons = decision.reasons + [f"Authorization error: {str(e)}"]

        # Audit the decision
        if self._audit_enabled:
            self._audit_decision(request, decision)

        return decision

    def _check_role_permissions(
        self, request: AuthorizationRequest
    ) -> AuthorizationDecision:
        """Check if user roles allow the requested action."""
        decision = AuthorizationDecision(
            allowed=False, reasons=[], applicable_roles=[], conditions_applied=[]
        )

        for role in request.context.roles:
            if role not in self.roles:
                continue

            role_def = self.roles[role]
            decision.applicable_roles = decision.applicable_roles + [role]

            for scope in role_def.resource_scopes:
                if self._matches_resource_scope(request, scope):
                    if request.action in scope.permissions:
                        if self._check_conditions(request, scope.conditions):
                            decision.allowed = True
                            decision.reasons = decision.reasons + [
                                f"Allowed by role '{role_def.name}' for {request.resource_type}"
                            ]
                            return decision

        decision.reasons = decision.reasons + ["No matching role permissions found"]
        return decision

    def _matches_resource_scope(
        self, request: AuthorizationRequest, scope: ResourceScope
    ) -> bool:
        """Check if request matches resource scope."""
        if scope.resource_type == "*":
            return True
        return request.resource_type == scope.resource_type

    def _check_conditions(
        self, request: AuthorizationRequest, conditions: Optional[Dict[str, Any]]
    ) -> bool:
        """Evaluate conditions for resource access."""
        if not conditions:
            return True

        for key, value in conditions.items():
            if key == "owner" and value == "self":
                if not self._is_resource_owner(request):
                    return False
            elif key == "patient" and value == "self":
                if not self._is_patient_resource(request):
                    return False
            elif request.resource_data:
                resource_value = request.resource_data.get(key)
                if isinstance(value, list):
                    if resource_value not in value:
                        return False
                elif resource_value != value:
                    return False

        return True

    def _is_resource_owner(self, request: AuthorizationRequest) -> bool:
        """Check if user is owner of the resource."""
        if not request.resource_data:
            return False

        # For Patient resource, check if user ID matches patient ID
        if request.resource_type == "Patient":
            patient_id = request.resource_data.get("id")
            return patient_id == request.context.user_id

        return False

    def _is_patient_resource(self, request: AuthorizationRequest) -> bool:
        """Check if user is the patient referenced in the resource."""
        if not request.resource_data:
            return False

        # Check patient reference in resource
        patient_ref = request.resource_data.get("patient", {})
        if isinstance(patient_ref, dict):
            patient_id = patient_ref.get("reference", "").rsplit("/", maxsplit=1)[-1]
        else:
            patient_id = str(patient_ref).rsplit("/", maxsplit=1)[-1]

        return bool(patient_id == request.context.user_id)

    def _check_deny_policies(
        self, request: AuthorizationRequest
    ) -> Optional[AuthorizationDecision]:
        """Check custom deny policies."""
        for policy in self.custom_policies:
            if not policy.enabled or policy.effect != "deny":
                continue

            if self._matches_policy(request, policy):
                decision = AuthorizationDecision(
                    allowed=False, reasons=[f"Denied by policy: {policy.name}"]
                )
                return decision

        return None

    def _check_allow_policies(
        self, request: AuthorizationRequest
    ) -> AuthorizationDecision:
        """Check custom allow policies."""
        decision = AuthorizationDecision(
            allowed=False, reasons=[], applicable_roles=[], conditions_applied=[]
        )

        for policy in self.custom_policies:
            if not policy.enabled or policy.effect != "allow":
                continue

            if self._matches_policy(request, policy):
                decision.allowed = True
                decision.reasons.append(f"Allowed by policy: {policy.name}")
                return decision

        return decision

    def _matches_policy(
        self, request: AuthorizationRequest, policy: AuthorizationPolicy
    ) -> bool:
        """Check if request matches policy conditions."""
        # Check resource type
        if (
            request.resource_type not in policy.resource_types
            and "*" not in policy.resource_types
        ):
            return False

        # Check action
        if request.action not in policy.actions:
            return False

        # Check additional conditions
        return self._check_conditions(request, policy.conditions)

    def _is_patient_data(self, request: AuthorizationRequest) -> bool:
        """Check if resource contains patient data."""
        patient_resources = [
            "Patient",
            "Observation",
            "Condition",
            "MedicationRequest",
            "Procedure",
            "DocumentReference",
            "AllergyIntolerance",
            "Immunization",
            "CarePlan",
            "Goal",
            "CareTeam",
        ]
        return request.resource_type in patient_resources

    def _check_patient_consent(
        self, request: AuthorizationRequest
    ) -> AuthorizationDecision:
        """Check patient consent for data access."""
        decision = AuthorizationDecision(
            allowed=True, reasons=[], applicable_roles=[], conditions_applied=[]
        )

        # Extract patient ID from resource
        patient_id = self._extract_patient_id(request)
        if not patient_id:
            return decision

        consent = self.consent_records.get(patient_id)
        if not consent or not consent.active:
            return decision

        # Check if actor is consented
        if request.context.user_id not in consent.consented_actors:
            # Check organization-level consent
            if request.context.organization_id not in consent.consented_actors:
                decision.allowed = False
                decision.reasons = decision.reasons + [
                    "Access denied: No patient consent"
                ]
                return decision

        # Check excluded resources
        if request.resource_type in consent.excluded_resources:
            decision.allowed = False
            decision.reasons = decision.reasons + [
                f"Access denied: {request.resource_type} excluded by patient"
            ]

        # Check time period
        now = datetime.utcnow()
        if consent.time_period_start and now < consent.time_period_start:
            decision.allowed = False
            decision.reasons = decision.reasons + [
                "Access denied: Consent not yet active"
            ]
        elif consent.time_period_end and now > consent.time_period_end:
            decision.allowed = False
            decision.reasons = decision.reasons + ["Access denied: Consent expired"]

        return decision

    def _extract_patient_id(self, request: AuthorizationRequest) -> Optional[str]:
        """Extract patient ID from resource data."""
        if not request.resource_data:
            return None

        # Direct patient resource
        if request.resource_type == "Patient":
            return request.resource_data.get("id")

        # Resources with patient reference
        patient_ref = request.resource_data.get("patient", {})
        if isinstance(patient_ref, dict):
            ref_str: str = patient_ref.get("reference", "")
            return ref_str.split("/")[-1] if ref_str else None
        elif isinstance(patient_ref, str):
            return patient_ref.split("/")[-1]

        # Subject reference (some resources use subject instead of patient)
        subject_ref = request.resource_data.get("subject", {})
        if isinstance(subject_ref, dict):
            ref = subject_ref.get("reference", "")
            if "Patient/" in ref:
                parts = ref.split("/")
                return parts[-1] if parts else None

        return None

    def _check_emergency_access(
        self, request: AuthorizationRequest
    ) -> AuthorizationDecision:
        """Check if emergency access should be granted."""
        decision = AuthorizationDecision(
            allowed=False, reasons=[], applicable_roles=[], conditions_applied=[]
        )

        # Emergency access only for specific resource types
        emergency_resources = [
            "Patient",
            "AllergyIntolerance",
            "Condition",
            "MedicationRequest",
            "Immunization",
        ]

        if request.resource_type not in emergency_resources:
            decision.reasons = decision.reasons + [
                "Emergency access not available for this resource type"
            ]
            return decision

        # Emergency access only for read operations
        if request.action not in [ResourcePermission.READ, ResourcePermission.SEARCH]:
            decision.reasons = decision.reasons + [
                "Emergency access only allows read operations"
            ]
            return decision

        decision.allowed = True
        decision.reasons = decision.reasons + ["Emergency access granted"]
        decision.conditions_applied = decision.conditions_applied + [
            "emergency_override"
        ]

        return decision

    def _audit_decision(
        self, request: AuthorizationRequest, decision: AuthorizationDecision
    ) -> None:
        """Audit authorization decision."""
        audit_entry = {
            "timestamp": decision.timestamp.isoformat(),
            "user_id": request.context.user_id,
            "roles": request.context.roles,
            "resource_type": request.resource_type,
            "resource_id": request.resource_id,
            "action": request.action,
            "decision": "allowed" if decision.allowed else "denied",
            "reasons": decision.reasons,
            "session_id": request.context.session_id,
            "ip_address": request.context.ip_address,
            "emergency_access": request.context.emergency_access,
        }

        decision.audit_info = audit_entry
        logger.info(f"Authorization audit: {audit_entry}")

    def get_resource_filters(
        self, context: AuthorizationContext, resource_type: str
    ) -> List[ResourceFilter]:
        """Get filters to apply to resource queries based on user authorization.

        This ensures users only see resources they're authorized to access.
        """
        filters = []

        # For patients, filter to their own records
        if FHIRRole.PATIENT in context.roles:
            if resource_type == "Patient":
                filters.append(
                    ResourceFilter(field="_id", operator="eq", value=context.user_id)
                )
            else:
                filters.append(
                    ResourceFilter(
                        field="patient.reference",
                        operator="eq",
                        value=f"Patient/{context.user_id}",
                    )
                )

        # For practitioners, apply organization filters if needed
        elif FHIRRole.PRACTITIONER in context.roles and context.organization_id:
            filters.append(
                ResourceFilter(
                    field="organization.reference",
                    operator="eq",
                    value=f"Organization/{context.organization_id}",
                )
            )

        return filters

    def validate_fhir_consent(self, consent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR Consent resource.

        Args:
            consent_data: FHIR Consent resource data

        Returns:
            Validation result with 'valid', 'errors', and 'warnings' keys
        """
        # Use base FHIR validator for Consent resources
        return self.fhir_validator.validate_resource("Consent", consent_data)


# Singleton instance
_authorization_handler = FHIRAuthorizationHandler()


def get_authorization_handler() -> FHIRAuthorizationHandler:
    """Get the singleton authorization handler instance."""
    return _authorization_handler
