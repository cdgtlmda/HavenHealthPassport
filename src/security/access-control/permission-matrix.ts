/**
 * Permission Matrix
 * Defines the detailed permission mapping for resources and actions
 */

import { PermissionType, ResourceScope } from './rbac-types';
import { SYSTEM_ROLES } from './role-definitions';

// Resource types in the system
export enum ResourceType {
  PATIENT_RECORD = 'patient_record',
  PRESCRIPTION = 'prescription',
  LAB_RESULT = 'lab_result',
  APPOINTMENT = 'appointment',
  BILLING_RECORD = 'billing_record',
  INSURANCE_CLAIM = 'insurance_claim',
  PROVIDER_PROFILE = 'provider_profile',
  ORGANIZATION = 'organization',
  AUDIT_LOG = 'audit_log',
  SYSTEM_CONFIG = 'system_config'
}

// Action types
export enum ActionType {
  CREATE = 'create',
  READ = 'read',
  UPDATE = 'update',
  DELETE = 'delete',
  SHARE = 'share',
  APPROVE = 'approve',
  EXPORT = 'export',
  ARCHIVE = 'archive'
}

// Permission matrix entry
export interface PermissionMatrixEntry {
  role: string;
  resource: ResourceType;
  actions: ActionType[];
  conditions?: {
    ownership?: 'own' | 'team' | 'organization' | 'any';
    timeConstraint?: {
      type: 'business_hours' | 'emergency' | 'always';
      config?: any;
    };
    requiresApproval?: boolean;
    dataClassification?: 'public' | 'internal' | 'confidential' | 'restricted';
  };
}
// Define the permission matrix
export const permissionMatrix: PermissionMatrixEntry[] = [
  // Super Admin - Full access
  {
    role: SYSTEM_ROLES.SUPER_ADMIN,
    resource: ResourceType.PATIENT_RECORD,
    actions: [ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.DELETE,
              ActionType.SHARE, ActionType.EXPORT, ActionType.ARCHIVE],
    conditions: {
      ownership: 'any',
      timeConstraint: { type: 'always' }
    }
  },
  {
    role: SYSTEM_ROLES.SUPER_ADMIN,
    resource: ResourceType.SYSTEM_CONFIG,
    actions: [ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.DELETE],
    conditions: {
      ownership: 'any',
      timeConstraint: { type: 'always' }
    }
  },

  // Physician - Patient care access
  {
    role: SYSTEM_ROLES.PHYSICIAN,
    resource: ResourceType.PATIENT_RECORD,
    actions: [ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.SHARE],
    conditions: {
      ownership: 'team', // Patients under their care
      timeConstraint: { type: 'business_hours' },
      dataClassification: 'confidential'
    }
  },
  {
    role: SYSTEM_ROLES.PHYSICIAN,
    resource: ResourceType.PRESCRIPTION,
    actions: [ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.APPROVE],
    conditions: {
      ownership: 'own', // Their own prescriptions
      timeConstraint: { type: 'business_hours' }
    }
  },
  {
    role: SYSTEM_ROLES.PHYSICIAN,
    resource: ResourceType.LAB_RESULT,
    actions: [ActionType.READ, ActionType.APPROVE],
    conditions: {
      ownership: 'team',      timeConstraint: { type: 'business_hours' }
    }
  },

  // Nurse - Limited patient care access
  {
    role: SYSTEM_ROLES.NURSE,
    resource: ResourceType.PATIENT_RECORD,
    actions: [ActionType.READ, ActionType.UPDATE],
    conditions: {
      ownership: 'team',
      timeConstraint: { type: 'business_hours' },
      dataClassification: 'confidential'
    }
  },
  {
    role: SYSTEM_ROLES.NURSE,
    resource: ResourceType.PRESCRIPTION,
    actions: [ActionType.READ],
    conditions: {
      ownership: 'team',
      timeConstraint: { type: 'business_hours' }
    }
  },

  // Patient - Own records only
  {
    role: SYSTEM_ROLES.PATIENT,
    resource: ResourceType.PATIENT_RECORD,
    actions: [ActionType.READ, ActionType.SHARE, ActionType.EXPORT],
    conditions: {
      ownership: 'own',
      timeConstraint: { type: 'always' }
    }
  },
  {
    role: SYSTEM_ROLES.PATIENT,
    resource: ResourceType.PRESCRIPTION,
    actions: [ActionType.READ],
    conditions: {
      ownership: 'own',
      timeConstraint: { type: 'always' }
    }
  },
  {
    role: SYSTEM_ROLES.PATIENT,
    resource: ResourceType.LAB_RESULT,
    actions: [ActionType.READ, ActionType.EXPORT],
    conditions: {
      ownership: 'own',      timeConstraint: { type: 'always' }
    }
  },

  // Emergency Responder - Override access
  {
    role: SYSTEM_ROLES.EMERGENCY_RESPONDER,
    resource: ResourceType.PATIENT_RECORD,
    actions: [ActionType.READ],
    conditions: {
      ownership: 'any',
      timeConstraint: {
        type: 'emergency',
        config: { maxDuration: 3600000, requiresJustification: true }
      },
      requiresApproval: false, // No approval needed in emergency
      dataClassification: 'restricted'
    }
  },
  {
    role: SYSTEM_ROLES.EMERGENCY_RESPONDER,
    resource: ResourceType.PRESCRIPTION,
    actions: [ActionType.READ],
    conditions: {
      ownership: 'any',
      timeConstraint: { type: 'emergency' }
    }
  },

  // Auditor - Read-only access
  {
    role: SYSTEM_ROLES.AUDITOR,
    resource: ResourceType.AUDIT_LOG,
    actions: [ActionType.READ, ActionType.EXPORT],
    conditions: {
      ownership: 'any',
      timeConstraint: { type: 'business_hours' },
      requiresApproval: true
    }
  },
  {
    role: SYSTEM_ROLES.AUDITOR,
    resource: ResourceType.PATIENT_RECORD,
    actions: [ActionType.READ],
    conditions: {
      ownership: 'any',
      timeConstraint: { type: 'business_hours' },
      requiresApproval: true,
      dataClassification: 'confidential'
    }
  }];

// Helper function to check if a role has permission for an action on a resource
export function hasPermission(
  role: string,
  resource: ResourceType,
  action: ActionType,
  context?: {
    ownership?: string;
    isEmergency?: boolean;
    isBusinessHours?: boolean;
  }
): boolean {
  const entries = permissionMatrix.filter(
    entry => entry.role === role && entry.resource === resource
  );

  for (const entry of entries) {
    if (!entry.actions.includes(action)) continue;

    // Check conditions
    if (entry.conditions) {
      if (entry.conditions.ownership && context?.ownership !== entry.conditions.ownership) {
        continue;
      }

      if (entry.conditions.timeConstraint) {
        const { type } = entry.conditions.timeConstraint;
        if (type === 'business_hours' && !context?.isBusinessHours) continue;
        if (type === 'emergency' && !context?.isEmergency) continue;
      }
    }

    return true;
  }

  return false;
}

// Get all permissions for a role
export function getRolePermissions(role: string): PermissionMatrixEntry[] {
  return permissionMatrix.filter(entry => entry.role === role);
}

// Get required approval for an action
export function requiresApproval(
  role: string,
  resource: ResourceType,
  action: ActionType
): boolean {  const entry = permissionMatrix.find(
    e => e.role === role && e.resource === resource && e.actions.includes(action)
  );

  return entry?.conditions?.requiresApproval || false;
}

// Export permission matrix for visualization
export function exportPermissionMatrix(): any {
  const matrix: any = {};

  for (const entry of permissionMatrix) {
    if (!matrix[entry.role]) {
      matrix[entry.role] = {};
    }

    if (!matrix[entry.role][entry.resource]) {
      matrix[entry.role][entry.resource] = {
        actions: [],
        conditions: entry.conditions
      };
    }

    matrix[entry.role][entry.resource].actions.push(...entry.actions);
  }

  return matrix;
}
