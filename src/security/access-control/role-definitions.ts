/**
 * System Role Definitions
 * Defines the built-in roles and their hierarchy for Haven Health Passport
 */

import { Role, Permission, PermissionType } from './rbac-types';

// System roles that cannot be modified
export const SYSTEM_ROLES = {
  SUPER_ADMIN: 'super_admin',
  SYSTEM_ADMIN: 'system_admin',
  HEALTHCARE_ADMIN: 'healthcare_admin',
  PHYSICIAN: 'physician',
  NURSE: 'nurse',
  PHARMACIST: 'pharmacist',
  LAB_TECHNICIAN: 'lab_technician',
  BILLING_SPECIALIST: 'billing_specialist',
  PATIENT: 'patient',
  EMERGENCY_RESPONDER: 'emergency_responder',
  AUDITOR: 'auditor',
  GUEST: 'guest'
} as const;

// Role hierarchy definition
export const roleHierarchy: Record<string, string[]> = {
  [SYSTEM_ROLES.SUPER_ADMIN]: [], // Top level, no parents
  [SYSTEM_ROLES.SYSTEM_ADMIN]: [SYSTEM_ROLES.SUPER_ADMIN],
  [SYSTEM_ROLES.HEALTHCARE_ADMIN]: [SYSTEM_ROLES.SYSTEM_ADMIN],
  [SYSTEM_ROLES.PHYSICIAN]: [SYSTEM_ROLES.HEALTHCARE_ADMIN],
  [SYSTEM_ROLES.NURSE]: [SYSTEM_ROLES.HEALTHCARE_ADMIN],
  [SYSTEM_ROLES.PHARMACIST]: [SYSTEM_ROLES.HEALTHCARE_ADMIN],
  [SYSTEM_ROLES.LAB_TECHNICIAN]: [SYSTEM_ROLES.HEALTHCARE_ADMIN],
  [SYSTEM_ROLES.BILLING_SPECIALIST]: [SYSTEM_ROLES.HEALTHCARE_ADMIN],
  [SYSTEM_ROLES.EMERGENCY_RESPONDER]: [], // Special role, no hierarchy
  [SYSTEM_ROLES.AUDITOR]: [], // Special role, no hierarchy
  [SYSTEM_ROLES.PATIENT]: [], // Base role, no hierarchy
  [SYSTEM_ROLES.GUEST]: [SYSTEM_ROLES.PATIENT] // Limited patient access
};

// Permission sets for each role
export const rolePermissions: Record<string, PermissionType[]> = {
  [SYSTEM_ROLES.SUPER_ADMIN]: [
    // All permissions
    ...Object.values(PermissionType)
  ],

  [SYSTEM_ROLES.SYSTEM_ADMIN]: [
    // System management
    PermissionType.SYSTEM_CONFIG,
    PermissionType.SYSTEM_AUDIT,    PermissionType.SYSTEM_BACKUP,
    PermissionType.SYSTEM_RESTORE,
    // User management
    PermissionType.USER_VIEW,
    PermissionType.USER_CREATE,
    PermissionType.USER_UPDATE,
    PermissionType.USER_DELETE,
    PermissionType.USER_SUSPEND,
    PermissionType.USER_ROLES,
    // Healthcare administration
    PermissionType.PROVIDER_VIEW,
    PermissionType.PROVIDER_CREATE,
    PermissionType.PROVIDER_UPDATE,
    PermissionType.PROVIDER_DELETE,
    PermissionType.PROVIDER_VERIFY,
    // Analytics
    PermissionType.ANALYTICS_VIEW,
    PermissionType.ANALYTICS_EXPORT,
    PermissionType.REPORT_VIEW,
    PermissionType.REPORT_CREATE
  ],

  [SYSTEM_ROLES.HEALTHCARE_ADMIN]: [
    // Provider management
    PermissionType.PROVIDER_VIEW,
    PermissionType.PROVIDER_CREATE,
    PermissionType.PROVIDER_UPDATE,
    PermissionType.PROVIDER_VERIFY,
    // User management (healthcare staff only)
    PermissionType.USER_VIEW,
    PermissionType.USER_CREATE,
    PermissionType.USER_UPDATE,
    PermissionType.USER_ROLES,
    // Healthcare operations
    PermissionType.PATIENT_VIEW,
    PermissionType.RECORD_VIEW,
    PermissionType.PRESCRIPTION_VIEW,
    PermissionType.LAB_VIEW,
    PermissionType.BILLING_VIEW,
    // Reports
    PermissionType.REPORT_VIEW,
    PermissionType.REPORT_CREATE
  ],

  [SYSTEM_ROLES.PHYSICIAN]: [
    // Patient care
    PermissionType.PATIENT_VIEW,
    PermissionType.PATIENT_CREATE,
    PermissionType.PATIENT_UPDATE,
    PermissionType.PATIENT_CONSENT,    // Medical records
    PermissionType.RECORD_VIEW,
    PermissionType.RECORD_CREATE,
    PermissionType.RECORD_UPDATE,
    PermissionType.RECORD_SHARE,
    PermissionType.RECORD_EXPORT,
    // Prescriptions
    PermissionType.PRESCRIPTION_VIEW,
    PermissionType.PRESCRIPTION_CREATE,
    PermissionType.PRESCRIPTION_UPDATE,
    PermissionType.PRESCRIPTION_APPROVE,
    // Lab orders
    PermissionType.LAB_VIEW,
    PermissionType.LAB_CREATE,
    PermissionType.LAB_UPDATE,
    // Emergency access
    PermissionType.EMERGENCY_VIEW,
    PermissionType.EMERGENCY_GRANT,
    // AI assistance
    PermissionType.AI_QUERY
  ],

  [SYSTEM_ROLES.NURSE]: [
    // Patient care
    PermissionType.PATIENT_VIEW,
    PermissionType.PATIENT_UPDATE,
    // Medical records
    PermissionType.RECORD_VIEW,
    PermissionType.RECORD_CREATE,
    PermissionType.RECORD_UPDATE,
    // Prescriptions (view only)
    PermissionType.PRESCRIPTION_VIEW,
    // Lab results
    PermissionType.LAB_VIEW,
    PermissionType.LAB_UPDATE,
    // Emergency access
    PermissionType.EMERGENCY_VIEW
  ],

  [SYSTEM_ROLES.PHARMACIST]: [
    // Patient info (limited)
    PermissionType.PATIENT_VIEW,
    // Prescriptions
    PermissionType.PRESCRIPTION_VIEW,
    PermissionType.PRESCRIPTION_UPDATE,
    PermissionType.PRESCRIPTION_DISPENSE,
    // Medical records (medication history)
    PermissionType.RECORD_VIEW
  ],
  [SYSTEM_ROLES.LAB_TECHNICIAN]: [
    // Lab operations
    PermissionType.LAB_VIEW,
    PermissionType.LAB_CREATE,
    PermissionType.LAB_UPDATE,
    PermissionType.LAB_APPROVE,
    // Patient info (limited)
    PermissionType.PATIENT_VIEW,
    // Medical records (lab-related)
    PermissionType.RECORD_VIEW
  ],

  [SYSTEM_ROLES.BILLING_SPECIALIST]: [
    // Billing operations
    PermissionType.BILLING_VIEW,
    PermissionType.BILLING_CREATE,
    PermissionType.BILLING_UPDATE,
    PermissionType.BILLING_PROCESS,
    // Insurance
    PermissionType.INSURANCE_VIEW,
    PermissionType.INSURANCE_UPDATE,
    // Patient info (billing-related)
    PermissionType.PATIENT_VIEW,
    // Medical records (billing codes)
    PermissionType.RECORD_VIEW
  ],

  [SYSTEM_ROLES.PATIENT]: [
    // Own records only
    PermissionType.RECORD_VIEW,
    PermissionType.RECORD_SHARE,
    PermissionType.RECORD_EXPORT,
    // Own patient info
    PermissionType.PATIENT_VIEW,
    PermissionType.PATIENT_UPDATE,
    PermissionType.PATIENT_CONSENT,
    // View prescriptions
    PermissionType.PRESCRIPTION_VIEW,
    // View lab results
    PermissionType.LAB_VIEW,
    // View billing
    PermissionType.BILLING_VIEW,
    PermissionType.INSURANCE_VIEW,
    // Emergency access grant
    PermissionType.EMERGENCY_GRANT
  ],

  [SYSTEM_ROLES.EMERGENCY_RESPONDER]: [    // Emergency access
    PermissionType.EMERGENCY_VIEW,
    PermissionType.EMERGENCY_OVERRIDE,
    // Critical patient info
    PermissionType.PATIENT_VIEW,
    PermissionType.RECORD_VIEW,
    PermissionType.PRESCRIPTION_VIEW
  ],

  [SYSTEM_ROLES.AUDITOR]: [
    // Read-only access to everything
    PermissionType.SYSTEM_AUDIT,
    PermissionType.USER_VIEW,
    PermissionType.PATIENT_VIEW,
    PermissionType.PROVIDER_VIEW,
    PermissionType.RECORD_VIEW,
    PermissionType.PRESCRIPTION_VIEW,
    PermissionType.LAB_VIEW,
    PermissionType.BILLING_VIEW,
    PermissionType.INSURANCE_VIEW,
    PermissionType.ANALYTICS_VIEW,
    PermissionType.REPORT_VIEW,
    PermissionType.BLOCKCHAIN_READ,
    PermissionType.BLOCKCHAIN_VERIFY
  ],

  [SYSTEM_ROLES.GUEST]: [
    // Minimal access
    PermissionType.PATIENT_VIEW, // Own profile only
    PermissionType.RECORD_VIEW  // Shared records only
  ]
};

// Create role objects
export function createSystemRoles(): Role[] {
  return Object.entries(SYSTEM_ROLES).map(([key, roleId]) => ({
    id: roleId,
    name: key.replace(/_/g, ' ').toLowerCase()
      .replace(/\b\w/g, c => c.toUpperCase()),
    description: getRoleDescription(roleId),
    permissions: rolePermissions[roleId].map(type => ({
      id: `${roleId}_${type}`,
      type,
      description: getPermissionDescription(type)
    })),
    parentRoles: roleHierarchy[roleId] || [],
    isSystem: true,
    priority: getRolePriority(roleId),
    constraints: getRoleConstraints(roleId)
  }));
}
// Helper functions
function getRoleDescription(roleId: string): string {
  const descriptions: Record<string, string> = {
    [SYSTEM_ROLES.SUPER_ADMIN]: 'Full system access with no restrictions',
    [SYSTEM_ROLES.SYSTEM_ADMIN]: 'System administration and configuration',
    [SYSTEM_ROLES.HEALTHCARE_ADMIN]: 'Healthcare organization administration',
    [SYSTEM_ROLES.PHYSICIAN]: 'Licensed physician with full patient care access',
    [SYSTEM_ROLES.NURSE]: 'Registered nurse with patient care access',
    [SYSTEM_ROLES.PHARMACIST]: 'Licensed pharmacist with prescription access',
    [SYSTEM_ROLES.LAB_TECHNICIAN]: 'Laboratory technician with lab result access',
    [SYSTEM_ROLES.BILLING_SPECIALIST]: 'Billing and insurance specialist',
    [SYSTEM_ROLES.PATIENT]: 'Patient with access to own health records',
    [SYSTEM_ROLES.EMERGENCY_RESPONDER]: 'Emergency responder with override access',
    [SYSTEM_ROLES.AUDITOR]: 'Compliance auditor with read-only access',
    [SYSTEM_ROLES.GUEST]: 'Guest with minimal access to shared records'
  };
  return descriptions[roleId] || 'Custom role';
}

function getRolePriority(roleId: string): number {
  const priorities: Record<string, number> = {
    [SYSTEM_ROLES.SUPER_ADMIN]: 1000,
    [SYSTEM_ROLES.SYSTEM_ADMIN]: 900,
    [SYSTEM_ROLES.HEALTHCARE_ADMIN]: 800,
    [SYSTEM_ROLES.PHYSICIAN]: 700,
    [SYSTEM_ROLES.NURSE]: 600,
    [SYSTEM_ROLES.PHARMACIST]: 500,
    [SYSTEM_ROLES.LAB_TECHNICIAN]: 400,
    [SYSTEM_ROLES.BILLING_SPECIALIST]: 300,
    [SYSTEM_ROLES.EMERGENCY_RESPONDER]: 950, // High priority for emergencies
    [SYSTEM_ROLES.AUDITOR]: 850, // High priority for compliance
    [SYSTEM_ROLES.PATIENT]: 200,
    [SYSTEM_ROLES.GUEST]: 100
  };
  return priorities[roleId] || 0;
}

function getRoleConstraints(roleId: string): any[] {
  // Add specific constraints for certain roles
  if (roleId === SYSTEM_ROLES.EMERGENCY_RESPONDER) {
    return [{
      type: 'time',
      config: { maxDuration: 3600000 } // 1 hour max
    }];
  }
  return [];
}
function getPermissionDescription(type: PermissionType): string {
  // This would typically come from a localization file
  return type.replace(/_/g, ' ').toLowerCase();
}
