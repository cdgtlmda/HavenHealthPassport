/**
 * Access Control Module
 * Exports all RBAC components for the Haven Health Passport system
 */

// Export types
export * from './rbac-types';
export * from './role-definitions';
export * from './permission-matrix';

// Export implementation
export {
  RBACManager,
  rbacManager,
  checkAccess,
  assignRole,
  delegateRole,
  revokeRole,
  performAccessReview,
  performAutomatedRemediation
} from './rbac-implementation';

// Export certification
export {
  AccessCertificationManager,
  certificationManager
} from './access-certification';

// Convenience exports for common operations
export { SYSTEM_ROLES } from './role-definitions';
export { PermissionType } from './rbac-types';
export { ResourceType, ActionType } from './permission-matrix';

/**
 * Quick start guide for using the RBAC system:
 *
 * 1. Check access:
 *    const decision = await checkAccess({
 *      user: { id: 'user123', roles: [], attributes: {} },
 *      resource: { type: 'patient_record', id: 'record456', attributes: {} },
 *      action: PermissionType.RECORD_VIEW,
 *      environment: { time: new Date(), ipAddress: '192.168.1.1', sessionId: 'session123' }
 *    });
 *
 * 2. Assign role:
 *    const assignment = await assignRole('user123', SYSTEM_ROLES.PHYSICIAN, 'admin123', {
 *      expiresAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000) // 1 year
 *    });
 *
 * 3. Perform access review:
 *    const review = await performAccessReview('user123');
 *
 * 4. Create certification campaign:
 *    const campaign = await certificationManager.createCampaign('high_privilege_quarterly', 'admin123');
 */

// Initialize RBAC on module load
console.log('Haven Health Passport RBAC system initialized');
