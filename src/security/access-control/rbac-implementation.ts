/**
 * RBAC Implementation
 * Core implementation of Role-Based Access Control for Haven Health Passport
 */

import {
  Role,
  Permission,
  PermissionType,
  UserRoleAssignment,
  AccessDecision,
  PolicyContext,
  ResourceScope,
  AccessControlAuditEntry,
  PermissionCondition,
  AssignmentCondition,
  RoleConstraint
} from './rbac-types';
import {
  SYSTEM_ROLES,
  roleHierarchy,
  createSystemRoles
} from './role-definitions';
import {
  permissionMatrix,
  hasPermission,
  ResourceType,
  ActionType,
  requiresApproval
} from './permission-matrix';
import { v4 as uuidv4 } from 'uuid';

/**
 * RBAC Manager - Core implementation for role-based access control
 */
export class RBACManager {
  private roles: Map<string, Role>;
  private userRoleAssignments: Map<string, UserRoleAssignment[]>;
  private auditLog: AccessControlAuditEntry[];
  private policyCache: Map<string, AccessDecision>;
  private delegationRules: Map<string, DelegationRule[]>;
  private emergencyAccessLog: EmergencyAccess[];
  private approvalWorkflows: Map<string, ApprovalWorkflow>;

  constructor() {
    this.roles = new Map();
    this.userRoleAssignments = new Map();
    this.auditLog = [];
    this.policyCache = new Map();
    this.delegationRules = new Map();
    this.emergencyAccessLog = [];
    this.approvalWorkflows = new Map();

    this.initializeSystemRoles();
    this.initializeApprovalWorkflows();
  }

  /**
   * Initialize system roles from definitions
   */
  private initializeSystemRoles(): void {
    const systemRoles = createSystemRoles();
    systemRoles.forEach(role => {
      this.roles.set(role.id, role);
    });
  }

  /**
   * Initialize approval workflows for sensitive operations
   */
  private initializeApprovalWorkflows(): void {
    // Define approval workflows for different scenarios
    this.approvalWorkflows.set('emergency_access', {
      id: 'emergency_access',
      name: 'Emergency Access Approval',
      steps: [
        {
          approverRole: SYSTEM_ROLES.HEALTHCARE_ADMIN,
          timeout: 300000, // 5 minutes
          autoApprove: false
        }
      ],
      escalation: {
        timeout: 600000, // 10 minutes
        escalateTo: SYSTEM_ROLES.SYSTEM_ADMIN
      }
    });

    this.approvalWorkflows.set('role_elevation', {
      id: 'role_elevation',
      name: 'Role Elevation Approval',
      steps: [
        {
          approverRole: SYSTEM_ROLES.SYSTEM_ADMIN,
          timeout: 86400000, // 24 hours
          autoApprove: false
        }
      ]
    });

    this.approvalWorkflows.set('data_export', {
      id: 'data_export',
      name: 'Sensitive Data Export',
      steps: [
        {
          approverRole: SYSTEM_ROLES.HEALTHCARE_ADMIN,
          timeout: 3600000, // 1 hour
          autoApprove: false
        },
        {
          approverRole: SYSTEM_ROLES.AUDITOR,
          timeout: 3600000, // 1 hour
          autoApprove: false
        }
      ]
    });
  }

  /**
   * Check access permission based on context
   */
  async checkAccess(context: PolicyContext): Promise<AccessDecision> {
    const startTime = Date.now();

    // Check cache first
    const cacheKey = this.generateCacheKey(context);
    const cachedDecision = this.policyCache.get(cacheKey);
    if (cachedDecision && this.isCacheValid(cachedDecision)) {
      return cachedDecision;
    }

    try {
      // Get user's effective roles including hierarchy
      const effectiveRoles = await this.getEffectiveRoles(context.user.id);

      // Check if any role has the required permission
      let allowed = false;
      const appliedPolicies: string[] = [];
      const missingPermissions: PermissionType[] = [];

      for (const roleId of effectiveRoles) {
        const role = this.roles.get(roleId);
        if (!role) continue;

        // Check role constraints
        if (!this.checkRoleConstraints(role, context)) {
          appliedPolicies.push(`role_constraint_failed:${roleId}`);
          continue;
        }

        // Check if role has the permission
        const hasPermission = role.permissions.some(p => p.type === context.action);
        if (hasPermission) {
          // Check permission conditions
          const permission = role.permissions.find(p => p.type === context.action)!;
          if (this.checkPermissionConditions(permission, context)) {
            allowed = true;
            appliedPolicies.push(`role_permission:${roleId}:${context.action}`);
            break;
          } else {
            appliedPolicies.push(`permission_condition_failed:${roleId}:${context.action}`);
          }
        } else {
          missingPermissions.push(context.action);
        }
      }

      // Check attribute-based access control (ABAC)
      if (!allowed) {
        allowed = await this.checkAttributeBasedAccess(context, appliedPolicies);
      }

      // Check for emergency override
      if (!allowed && context.user.attributes?.emergencyOverride) {
        allowed = await this.handleEmergencyAccess(context, appliedPolicies);
      }

      const decision: AccessDecision = {
        allowed,
        reason: allowed ? 'Access granted' : 'Access denied',
        requiredPermissions: [context.action],
        missingPermissions: allowed ? [] : missingPermissions,
        appliedPolicies
      };

      // Cache the decision
      this.policyCache.set(cacheKey, decision);

      // Audit the access check
      await this.auditAccessCheck(context, decision, Date.now() - startTime);

      return decision;

    } catch (error) {
      console.error('Error checking access:', error);
      return {
        allowed: false,
        reason: 'Error during access check',
        requiredPermissions: [context.action],
        missingPermissions: [context.action],
        appliedPolicies: ['error']
      };
    }
  }

  /**
   * Get effective roles including hierarchy
   */
  private async getEffectiveRoles(userId: string): Promise<string[]> {
    const assignments = this.userRoleAssignments.get(userId) || [];
    const effectiveRoles = new Set<string>();

    for (const assignment of assignments) {
      // Check if assignment is still valid
      if (!this.isAssignmentValid(assignment)) continue;

      // Add the assigned role
      effectiveRoles.add(assignment.roleId);

      // Add parent roles from hierarchy
      this.addParentRoles(assignment.roleId, effectiveRoles);
    }

    return Array.from(effectiveRoles);
  }

  /**
   * Add parent roles based on hierarchy
   */
  private addParentRoles(roleId: string, effectiveRoles: Set<string>): void {
    const parentRoles = roleHierarchy[roleId] || [];
    for (const parentRole of parentRoles) {
      if (!effectiveRoles.has(parentRole)) {
        effectiveRoles.add(parentRole);
        this.addParentRoles(parentRole, effectiveRoles);
      }
    }
  }

  /**
   * Check if role assignment is still valid
   */
  private isAssignmentValid(assignment: UserRoleAssignment): boolean {
    // Check expiration
    if (assignment.expiresAt && assignment.expiresAt < new Date()) {
      return false;
    }

    // Check conditions
    if (assignment.conditions) {
      for (const condition of assignment.conditions) {
        if (!this.checkAssignmentCondition(condition, assignment)) {
          return false;
        }
      }
    }

    return true;
  }

  /**
   * Check assignment conditions
   */
  private checkAssignmentCondition(
    condition: AssignmentCondition,
    assignment: UserRoleAssignment
  ): boolean {
    switch (condition.type) {
      case 'temporal':
        return this.checkTemporalCondition(condition.config);
      case 'contextual':
        return this.checkContextualCondition(condition.config);
      case 'approval':
        return this.checkApprovalCondition(condition.config, assignment);
      default:
        return false;
    }
  }

  /**
   * Check role constraints
   */
  private checkRoleConstraints(role: Role, context: PolicyContext): boolean {
    if (!role.constraints) return true;

    for (const constraint of role.constraints) {
      switch (constraint.type) {
        case 'time':
          if (!this.checkTimeConstraint(constraint.config, context)) return false;
          break;
        case 'location':
          if (!this.checkLocationConstraint(constraint.config, context)) return false;
          break;
        case 'resource_limit':
          if (!this.checkResourceLimitConstraint(constraint.config, context)) return false;
          break;
        case 'approval_required':
          if (!this.checkApprovalConstraint(constraint.config, context)) return false;
          break;
      }
    }

    return true;
  }

  /**
   * Check permission conditions
   */
  private checkPermissionConditions(
    permission: Permission,
    context: PolicyContext
  ): boolean {
    if (!permission.conditions) return true;

    for (const condition of permission.conditions) {
      if (!this.evaluatePermissionCondition(condition, context)) {
        return false;
      }
    }

    return true;
  }

  /**
   * Evaluate a single permission condition
   */
  private evaluatePermissionCondition(
    condition: PermissionCondition,
    context: PolicyContext
  ): boolean {
    const value = this.getValueFromContext(condition.field, context);

    switch (condition.operator) {
      case 'equals':
        return value === condition.value;
      case 'not_equals':
        return value !== condition.value;
      case 'in':
        return Array.isArray(condition.value) && condition.value.includes(value);
      case 'not_in':
        return Array.isArray(condition.value) && !condition.value.includes(value);
      case 'contains':
        return typeof value === 'string' && value.includes(condition.value);
      default:
        return false;
    }
  }

  /**
   * Get value from context based on field path
   */
  private getValueFromContext(field: string, context: PolicyContext): any {
    const parts = field.split('.');
    let value: any = context;

    for (const part of parts) {
      value = value?.[part];
      if (value === undefined) break;
    }

    return value;
  }

  /**
   * Check attribute-based access control
   */
  private async checkAttributeBasedAccess(
    context: PolicyContext,
    appliedPolicies: string[]
  ): Promise<boolean> {
    // Check user attributes against resource attributes
    const userDepartment = context.user.attributes?.department;
    const resourceDepartment = context.resource.attributes?.department;

    if (userDepartment && resourceDepartment && userDepartment === resourceDepartment) {
      appliedPolicies.push('abac:department_match');
      return true;
    }

    // Check data classification
    const userClearance = context.user.attributes?.clearanceLevel || 0;
    const resourceClassification = context.resource.attributes?.classificationLevel || 0;

    if (userClearance >= resourceClassification) {
      appliedPolicies.push('abac:clearance_sufficient');
      return true;
    }

    return false;
  }

  /**
   * Handle emergency access (break-glass)
   */
  private async handleEmergencyAccess(
    context: PolicyContext,
    appliedPolicies: string[]
  ): Promise<boolean> {
    // Check if user has emergency responder role
    const userRoles = await this.getEffectiveRoles(context.user.id);
    if (!userRoles.includes(SYSTEM_ROLES.EMERGENCY_RESPONDER)) {
      return false;
    }

    // Create emergency access record
    const emergencyAccess: EmergencyAccess = {
      id: uuidv4(),
      userId: context.user.id,
      resourceType: context.resource.type,
      resourceId: context.resource.id,
      action: context.action,
      timestamp: new Date(),
      justification: context.user.attributes?.emergencyJustification || 'Emergency access',
      expiresAt: new Date(Date.now() + 3600000) // 1 hour
    };

    this.emergencyAccessLog.push(emergencyAccess);
    appliedPolicies.push('emergency_access:break_glass');

    // Trigger notification to administrators
    await this.notifyEmergencyAccess(emergencyAccess);

    return true;
  }

  /**
   * Assign role to user
   */
  async assignRole(
    userId: string,
    roleId: string,
    assignedBy: string,
    options?: {
      expiresAt?: Date;
      scope?: ResourceScope;
      delegated?: boolean;
      conditions?: AssignmentCondition[];
    }
  ): Promise<UserRoleAssignment> {
    // Validate role exists
    if (!this.roles.has(roleId)) {
      throw new Error(`Role ${roleId} does not exist`);
    }

    // Check if assigner has permission to assign roles
    const assignerContext: PolicyContext = {
      user: { id: assignedBy, roles: [], attributes: {} },
      resource: { type: 'role', id: roleId, attributes: {} },
      action: PermissionType.USER_ROLES,
      environment: {
        time: new Date(),
        ipAddress: '0.0.0.0',
        sessionId: 'system'
      }
    };

    const canAssign = await this.checkAccess(assignerContext);
    if (!canAssign.allowed) {
      throw new Error('User does not have permission to assign roles');
    }

    // Check segregation of duties
    await this.checkSegregationOfDuties(userId, roleId);

    // Create assignment
    const assignment: UserRoleAssignment = {
      userId,
      roleId,
      assignedBy,
      assignedAt: new Date(),
      expiresAt: options?.expiresAt,
      scope: options?.scope,
      delegated: options?.delegated || false,
      conditions: options?.conditions
    };

    // Add to user's assignments
    const userAssignments = this.userRoleAssignments.get(userId) || [];
    userAssignments.push(assignment);
    this.userRoleAssignments.set(userId, userAssignments);

    // Audit role assignment
    await this.auditRoleAssignment(assignment);

    return assignment;
  }

  /**
   * Check segregation of duties
   */
  private async checkSegregationOfDuties(userId: string, newRoleId: string): Promise<void> {
    const currentRoles = await this.getEffectiveRoles(userId);

    // Define conflicting role pairs
    const conflictingRoles: Array<[string, string]> = [
      [SYSTEM_ROLES.AUDITOR, SYSTEM_ROLES.SYSTEM_ADMIN],
      [SYSTEM_ROLES.BILLING_SPECIALIST, SYSTEM_ROLES.PHYSICIAN],
      [SYSTEM_ROLES.PATIENT, SYSTEM_ROLES.HEALTHCARE_ADMIN]
    ];

    for (const [role1, role2] of conflictingRoles) {
      if (
        (currentRoles.includes(role1) && newRoleId === role2) ||
        (currentRoles.includes(role2) && newRoleId === role1)
      ) {
        throw new Error(`Role ${newRoleId} conflicts with existing role due to segregation of duties`);
      }
    }
  }

  /**
   * Delegate role to another user
   */
  async delegateRole(
    fromUserId: string,
    toUserId: string,
    roleId: string,
    expiresAt: Date
  ): Promise<UserRoleAssignment> {
    // Check if user has the role to delegate
    const userRoles = await this.getEffectiveRoles(fromUserId);
    if (!userRoles.includes(roleId)) {
      throw new Error('User does not have the role to delegate');
    }

    // Check if role allows delegation
    const role = this.roles.get(roleId);
    if (role?.isSystem && role.priority > 500) {
      throw new Error('High-privilege system roles cannot be delegated');
    }

    // Create delegated assignment
    return this.assignRole(toUserId, roleId, fromUserId, {
      expiresAt,
      delegated: true,
      conditions: [{
        type: 'approval',
        config: { approvedBy: fromUserId, delegated: true }
      }]
    });
  }

  /**
   * Revoke role from user
   */
  async revokeRole(userId: string, roleId: string, revokedBy: string): Promise<void> {
    const userAssignments = this.userRoleAssignments.get(userId) || [];
    const updatedAssignments = userAssignments.filter(a => a.roleId !== roleId);

    if (updatedAssignments.length === userAssignments.length) {
      throw new Error('User does not have the specified role');
    }

    this.userRoleAssignments.set(userId, updatedAssignments);

    // Audit role revocation
    await this.auditRoleRevocation(userId, roleId, revokedBy);
  }

  /**
   * Perform access review for a user
   */
  async performAccessReview(userId: string): Promise<AccessReview> {
    const assignments = this.userRoleAssignments.get(userId) || [];
    const effectiveRoles = await this.getEffectiveRoles(userId);

    const review: AccessReview = {
      userId,
      reviewDate: new Date(),
      assignments: assignments.map(a => ({
        ...a,
        isValid: this.isAssignmentValid(a),
        recommendations: this.getAssignmentRecommendations(a)
      })),
      effectiveRoles,
      unusedRoles: await this.findUnusedRoles(userId),
      excessivePermissions: await this.findExcessivePermissions(userId),
      recommendations: []
    };

    // Generate recommendations
    if (review.unusedRoles.length > 0) {
      review.recommendations.push({
        type: 'remove_unused',
        roles: review.unusedRoles,
        reason: 'Roles have not been used in the last 90 days'
      });
    }

    if (review.excessivePermissions.length > 0) {
      review.recommendations.push({
        type: 'reduce_permissions',
        permissions: review.excessivePermissions,
        reason: 'User has permissions beyond their job requirements'
      });
    }

    return review;
  }

  /**
   * Find unused roles for a user
   */
  private async findUnusedRoles(userId: string): Promise<string[]> {
    const recentLogs = this.auditLog.filter(
      log => log.userId === userId &&
      log.timestamp > new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) // 90 days
    );

    const usedRoles = new Set(
      recentLogs
        .filter(log => log.decision.allowed)
        .flatMap(log => log.decision.appliedPolicies)
        .filter(policy => policy.startsWith('role_permission:'))
        .map(policy => policy.split(':')[1])
    );

    const assignedRoles = await this.getEffectiveRoles(userId);
    return assignedRoles.filter(role => !usedRoles.has(role));
  }

  /**
   * Find excessive permissions for a user
   */
  private async findExcessivePermissions(userId: string): Promise<PermissionType[]> {
    // This would typically involve analyzing usage patterns
    // For now, return empty array
    return [];
  }

  /**
   * Get assignment recommendations
   */
  private getAssignmentRecommendations(assignment: UserRoleAssignment): string[] {
    const recommendations: string[] = [];

    // Check if assignment is expiring soon
    if (assignment.expiresAt) {
      const daysUntilExpiry = Math.floor(
        (assignment.expiresAt.getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      );
      if (daysUntilExpiry < 30 && daysUntilExpiry > 0) {
        recommendations.push(`Role expires in ${daysUntilExpiry} days - review for renewal`);
      }
    }

    // Check if delegated role
    if (assignment.delegated) {
      recommendations.push('This is a delegated role - verify if still needed');
    }

    return recommendations;
  }

  /**
   * Implement automated remediation
   */
  async performAutomatedRemediation(): Promise<RemediationReport> {
    const report: RemediationReport = {
      timestamp: new Date(),
      actionsT
aken: number;
      expiredAssignments: number;
      revokedRoles: number;
      errors: string[];
    };

    const actions = {
      actionsTaken: 0,
      expiredAssignments: 0,
      revokedRoles: 0,
      errors: []
    };

    try {
      // Remove expired assignments
      for (const [userId, assignments] of this.userRoleAssignments.entries()) {
        const validAssignments = assignments.filter(a => {
          if (!this.isAssignmentValid(a)) {
            actions.expiredAssignments++;
            actions.actionsTaken++;
            return false;
          }
          return true;
        });
        this.userRoleAssignments.set(userId, validAssignments);
      }

      // Remove unused roles (optional, based on policy)
      for (const [userId, assignments] of this.userRoleAssignments.entries()) {
        const unusedRoles = await this.findUnusedRoles(userId);
        for (const roleId of unusedRoles) {
          try {
            await this.revokeRole(userId, roleId, 'system:automated_remediation');
            actions.revokedRoles++;
            actions.actionsTaken++;
          } catch (error) {
            actions.errors.push(`Failed to revoke unused role ${roleId} from user ${userId}`);
          }
        }
      }

      // Clear expired emergency access
      this.emergencyAccessLog = this.emergencyAccessLog.filter(
        access => access.expiresAt > new Date()
      );

    } catch (error) {
      actions.errors.push(`Remediation error: ${error.message}`);
    }

    return report;
  }

  /**
   * Create approval request
   */
  async createApprovalRequest(
    requestType: string,
    requestedBy: string,
    context: any
  ): Promise<ApprovalRequest> {
    const workflow = this.approvalWorkflows.get(requestType);
    if (!workflow) {
      throw new Error(`Unknown approval workflow: ${requestType}`);
    }

    const request: ApprovalRequest = {
      id: uuidv4(),
      type: requestType,
      requestedBy,
      requestedAt: new Date(),
      status: 'pending',
      workflow,
      context,
      currentStep: 0,
      approvals: []
    };

    // Store request (in real implementation, this would be persisted)
    // For now, we'll just return it
    return request;
  }

  /**
   * Process approval
   */
  async processApproval(
    requestId: string,
    approverId: string,
    decision: 'approve' | 'reject',
    comments?: string
  ): Promise<void> {
    // In real implementation, this would update the approval request
    // and potentially trigger the next step in the workflow
  }

  /**
   * Helper methods for constraints
   */
  private checkTimeConstraint(config: any, context: PolicyContext): boolean {
    const now = context.environment.time;

    if (config.allowedHours) {
      const hour = now.getHours();
      if (hour < config.allowedHours.start || hour > config.allowedHours.end) {
        return false;
      }
    }

    if (config.allowedDays) {
      const day = now.getDay();
      if (!config.allowedDays.includes(day)) {
        return false;
      }
    }

    if (config.maxDuration && context.environment.sessionId) {
      // Check session duration (would need session tracking)
      // For now, return true
    }

    return true;
  }

  private checkLocationConstraint(config: any, context: PolicyContext): boolean {
    if (!context.environment.location) return false;

    if (config.allowedCountries) {
      if (!config.allowedCountries.includes(context.environment.location.country)) {
        return false;
      }
    }

    if (config.allowedRegions) {
      if (!config.allowedRegions.includes(context.environment.location.region)) {
        return false;
      }
    }

    return true;
  }

  private checkResourceLimitConstraint(config: any, context: PolicyContext): boolean {
    // This would check resource usage limits
    // For example, number of records accessed, API calls made, etc.
    return true;
  }

  private checkApprovalConstraint(config: any, context: PolicyContext): boolean {
    // This would check if required approvals are in place
    return true;
  }

  private checkTemporalCondition(config: any): boolean {
    const now = new Date();

    if (config.validFrom && now < new Date(config.validFrom)) {
      return false;
    }

    if (config.validUntil && now > new Date(config.validUntil)) {
      return false;
    }

    return true;
  }

  private checkContextualCondition(config: any): boolean {
    // Check contextual conditions like device trust, network location, etc.
    return true;
  }

  private checkApprovalCondition(config: any, assignment: UserRoleAssignment): boolean {
    // Check if assignment has required approvals
    return config.approvedBy === assignment.assignedBy;
  }

  /**
   * Audit methods
   */
  private async auditAccessCheck(
    context: PolicyContext,
    decision: AccessDecision,
    duration: number
  ): Promise<void> {
    const auditEntry: AccessControlAuditEntry = {
      id: uuidv4(),
      timestamp: new Date(),
      userId: context.user.id,
      action: context.action,
      resource: {
        type: context.resource.type,
        id: context.resource.id
      },
      decision,
      context,
      duration
    };

    this.auditLog.push(auditEntry);

    // In production, this would be persisted to a database
    // and potentially sent to a SIEM system
  }

  private async auditRoleAssignment(assignment: UserRoleAssignment): Promise<void> {
    // Audit role assignment
    console.log('Role assigned:', assignment);
  }

  private async auditRoleRevocation(
    userId: string,
    roleId: string,
    revokedBy: string
  ): Promise<void> {
    // Audit role revocation
    console.log('Role revoked:', { userId, roleId, revokedBy });
  }

  private async notifyEmergencyAccess(access: EmergencyAccess): Promise<void> {
    // Send notifications to administrators
    console.log('Emergency access used:', access);
  }

  /**
   * Cache management
   */
  private generateCacheKey(context: PolicyContext): string {
    return `${context.user.id}:${context.action}:${context.resource.type}:${context.resource.id}`;
  }

  private isCacheValid(decision: AccessDecision): boolean {
    // In production, check cache TTL
    // For now, always consider cache valid
    return true;
  }

  /**
   * Export methods for reporting
   */
  exportAuditLog(startDate: Date, endDate: Date): AccessControlAuditEntry[] {
    return this.auditLog.filter(
      entry => entry.timestamp >= startDate && entry.timestamp <= endDate
    );
  }

  exportRoleAssignments(): Record<string, UserRoleAssignment[]> {
    const result: Record<string, UserRoleAssignment[]> = {};
    for (const [userId, assignments] of this.userRoleAssignments.entries()) {
      result[userId] = assignments;
    }
    return result;
  }

  exportEmergencyAccessLog(): EmergencyAccess[] {
    return [...this.emergencyAccessLog];
  }
}

/**
 * Type definitions for additional features
 */
interface DelegationRule {
  fromRole: string;
  toRoles: string[];
  maxDuration: number;
  requiresApproval: boolean;
}

interface EmergencyAccess {
  id: string;
  userId: string;
  resourceType: string;
  resourceId: string;
  action: PermissionType;
  timestamp: Date;
  justification: string;
  expiresAt: Date;
}

interface ApprovalWorkflow {
  id: string;
  name: string;
  steps: ApprovalStep[];
  escalation?: {
    timeout: number;
    escalateTo: string;
  };
}

interface ApprovalStep {
  approverRole: string;
  timeout: number;
  autoApprove: boolean;
}

interface ApprovalRequest {
  id: string;
  type: string;
  requestedBy: string;
  requestedAt: Date;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  workflow: ApprovalWorkflow;
  context: any;
  currentStep: number;
  approvals: Approval[];
}

interface Approval {
  approverId: string;
  decision: 'approve' | 'reject';
  timestamp: Date;
  comments?: string;
}

interface AccessReview {
  userId: string;
  reviewDate: Date;
  assignments: Array<UserRoleAssignment & {
    isValid: boolean;
    recommendations: string[];
  }>;
  effectiveRoles: string[];
  unusedRoles: string[];
  excessivePermissions: PermissionType[];
  recommendations: ReviewRecommendation[];
}

interface ReviewRecommendation {
  type: 'remove_unused' | 'reduce_permissions' | 'update_constraints';
  roles?: string[];
  permissions?: PermissionType[];
  reason: string;
}

interface RemediationReport {
  timestamp: Date;
  actionsTaken: number;
  expiredAssignments: number;
  revokedRoles: number;
  errors: string[];
}

// Export the RBAC manager instance
export const rbacManager = new RBACManager();

// Export convenience functions
export async function checkAccess(context: PolicyContext): Promise<AccessDecision> {
  return rbacManager.checkAccess(context);
}

export async function assignRole(
  userId: string,
  roleId: string,
  assignedBy: string,
  options?: any
): Promise<UserRoleAssignment> {
  return rbacManager.assignRole(userId, roleId, assignedBy, options);
}

export async function delegateRole(
  fromUserId: string,
  toUserId: string,
  roleId: string,
  expiresAt: Date
): Promise<UserRoleAssignment> {
  return rbacManager.delegateRole(fromUserId, toUserId, roleId, expiresAt);
}

export async function revokeRole(
  userId: string,
  roleId: string,
  revokedBy: string
): Promise<void> {
  return rbacManager.revokeRole(userId, roleId, revokedBy);
}

export async function performAccessReview(userId: string): Promise<AccessReview> {
  return rbacManager.performAccessReview(userId);
}

export async function performAutomatedRemediation(): Promise<RemediationReport> {
  return rbacManager.performAutomatedRemediation();
}
