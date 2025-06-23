/**
 * Role-Based Access Control (RBAC) Types and Interfaces
 * Defines the structure for roles, permissions, and access control
 */

// Permission types for the system
export enum PermissionType {
  // Healthcare Records
  RECORD_VIEW = 'record:view',
  RECORD_CREATE = 'record:create',
  RECORD_UPDATE = 'record:update',
  RECORD_DELETE = 'record:delete',
  RECORD_SHARE = 'record:share',
  RECORD_EXPORT = 'record:export',

  // Patient Management
  PATIENT_VIEW = 'patient:view',
  PATIENT_CREATE = 'patient:create',
  PATIENT_UPDATE = 'patient:update',
  PATIENT_DELETE = 'patient:delete',
  PATIENT_CONSENT = 'patient:consent',

  // Healthcare Provider
  PROVIDER_VIEW = 'provider:view',
  PROVIDER_CREATE = 'provider:create',
  PROVIDER_UPDATE = 'provider:update',
  PROVIDER_DELETE = 'provider:delete',
  PROVIDER_VERIFY = 'provider:verify',

  // Prescription Management
  PRESCRIPTION_VIEW = 'prescription:view',
  PRESCRIPTION_CREATE = 'prescription:create',
  PRESCRIPTION_UPDATE = 'prescription:update',
  PRESCRIPTION_APPROVE = 'prescription:approve',
  PRESCRIPTION_DISPENSE = 'prescription:dispense',

  // Lab Results
  LAB_VIEW = 'lab:view',
  LAB_CREATE = 'lab:create',
  LAB_UPDATE = 'lab:update',
  LAB_APPROVE = 'lab:approve',

  // Billing and Insurance
  BILLING_VIEW = 'billing:view',
  BILLING_CREATE = 'billing:create',
  BILLING_UPDATE = 'billing:update',
  BILLING_PROCESS = 'billing:process',
  INSURANCE_VIEW = 'insurance:view',
  INSURANCE_UPDATE = 'insurance:update',
  // Emergency Access
  EMERGENCY_VIEW = 'emergency:view',
  EMERGENCY_OVERRIDE = 'emergency:override',
  EMERGENCY_GRANT = 'emergency:grant',

  // System Administration
  SYSTEM_CONFIG = 'system:config',
  SYSTEM_AUDIT = 'system:audit',
  SYSTEM_BACKUP = 'system:backup',
  SYSTEM_RESTORE = 'system:restore',

  // User Management
  USER_VIEW = 'user:view',
  USER_CREATE = 'user:create',
  USER_UPDATE = 'user:update',
  USER_DELETE = 'user:delete',
  USER_SUSPEND = 'user:suspend',
  USER_ROLES = 'user:roles',

  // Analytics and Reporting
  ANALYTICS_VIEW = 'analytics:view',
  ANALYTICS_EXPORT = 'analytics:export',
  REPORT_VIEW = 'report:view',
  REPORT_CREATE = 'report:create',

  // Blockchain Operations
  BLOCKCHAIN_READ = 'blockchain:read',
  BLOCKCHAIN_WRITE = 'blockchain:write',
  BLOCKCHAIN_VERIFY = 'blockchain:verify',

  // AI/ML Operations
  AI_QUERY = 'ai:query',
  AI_TRAIN = 'ai:train',
  AI_CONFIG = 'ai:config'
}

// Permission definition
export interface Permission {
  id: string;
  type: PermissionType;
  resource?: string;
  conditions?: PermissionCondition[];
  description: string;
}

// Permission conditions for fine-grained control
export interface PermissionCondition {
  field: string;
  operator: 'equals' | 'not_equals' | 'in' | 'not_in' | 'contains';
  value: any;
}
// Role definition
export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: Permission[];
  parentRoles?: string[]; // For role hierarchy
  constraints?: RoleConstraint[];
  isSystem: boolean; // System roles cannot be modified
  priority: number; // For conflict resolution
}

// Role constraints
export interface RoleConstraint {
  type: 'time' | 'location' | 'resource_limit' | 'approval_required';
  config: any;
}

// User role assignment
export interface UserRoleAssignment {
  userId: string;
  roleId: string;
  assignedBy: string;
  assignedAt: Date;
  expiresAt?: Date;
  scope?: ResourceScope;
  delegated: boolean;
  conditions?: AssignmentCondition[];
}

// Resource scope for role assignments
export interface ResourceScope {
  type: 'organization' | 'department' | 'team' | 'project' | 'patient_group';
  id: string;
  children?: boolean; // Include child resources
}

// Assignment conditions
export interface AssignmentCondition {
  type: 'temporal' | 'contextual' | 'approval';
  config: any;
}

// Access decision
export interface AccessDecision {
  allowed: boolean;
  reason?: string;
  requiredPermissions?: PermissionType[];
  missingPermissions?: PermissionType[];
  appliedPolicies?: string[];
}
// Policy evaluation context
export interface PolicyContext {
  user: {
    id: string;
    roles: string[];
    attributes: Record<string, any>;
  };
  resource: {
    type: string;
    id: string;
    attributes: Record<string, any>;
  };
  action: PermissionType;
  environment: {
    time: Date;
    ipAddress: string;
    location?: {
      country: string;
      region: string;
    };
    deviceId?: string;
    sessionId: string;
  };
}

// Audit log entry for access control
export interface AccessControlAuditEntry {
  id: string;
  timestamp: Date;
  userId: string;
  action: PermissionType;
  resource: {
    type: string;
    id: string;
  };
  decision: AccessDecision;
  context: PolicyContext;
  duration: number; // Time taken to evaluate in ms
}
