/**
 * Access Certification Process
 * Implements periodic certification of user access rights
 */

import { v4 as uuidv4 } from 'uuid';
import {
  UserRoleAssignment,
  Role,
  PermissionType
} from './rbac-types';
import { rbacManager } from './rbac-implementation';
import { SYSTEM_ROLES } from './role-definitions';

/**
 * Access Certification Manager
 * Handles periodic certification campaigns for access review
 */
export class AccessCertificationManager {
  private campaigns: Map<string, CertificationCampaign>;
  private certifications: Map<string, Certification[]>;
  private certificationSchedule: CertificationSchedule[];

  constructor() {
    this.campaigns = new Map();
    this.certifications = new Map();
    this.certificationSchedule = [];
    this.initializeDefaultSchedule();
  }

  /**
   * Initialize default certification schedule
   */
  private initializeDefaultSchedule(): void {
    // Quarterly certification for high-privilege roles
    this.certificationSchedule.push({
      id: 'high_privilege_quarterly',
      name: 'High Privilege Access Review',
      frequency: 'quarterly',
      scope: {
        roles: [
          SYSTEM_ROLES.SUPER_ADMIN,
          SYSTEM_ROLES.SYSTEM_ADMIN,
          SYSTEM_ROLES.HEALTHCARE_ADMIN
        ],
        includeEmergencyAccess: true
      },
      reviewers: {
        primary: 'direct_manager',
        secondary: 'role_owner',
        escalation: SYSTEM_ROLES.SYSTEM_ADMIN
      },
      dueInDays: 14
    });

    // Semi-annual certification for healthcare roles
    this.certificationSchedule.push({
      id: 'healthcare_semiannual',
      name: 'Healthcare Access Review',
      frequency: 'semiannual',
      scope: {
        roles: [
          SYSTEM_ROLES.PHYSICIAN,
          SYSTEM_ROLES.NURSE,
          SYSTEM_ROLES.PHARMACIST,
          SYSTEM_ROLES.LAB_TECHNICIAN
        ],
        includeEmergencyAccess: false
      },
      reviewers: {
        primary: 'department_head',
        secondary: 'direct_manager',
        escalation: SYSTEM_ROLES.HEALTHCARE_ADMIN
      },
      dueInDays: 21
    });

    // Annual certification for all other roles
    this.certificationSchedule.push({
      id: 'standard_annual',
      name: 'Annual Access Review',
      frequency: 'annual',
      scope: {
        roles: 'all',
        excludeRoles: [
          SYSTEM_ROLES.PATIENT,
          SYSTEM_ROLES.GUEST
        ],
        includeEmergencyAccess: false
      },
      reviewers: {
        primary: 'direct_manager',
        secondary: 'role_owner',
        escalation: SYSTEM_ROLES.SYSTEM_ADMIN
      },
      dueInDays: 30
    });
  }

  /**
   * Create a new certification campaign
   */
  async createCampaign(
    scheduleId: string,
    initiatedBy: string
  ): Promise<CertificationCampaign> {
    const schedule = this.certificationSchedule.find(s => s.id === scheduleId);
    if (!schedule) {
      throw new Error(`Certification schedule ${scheduleId} not found`);
    }

    const campaign: CertificationCampaign = {
      id: uuidv4(),
      scheduleId,
      name: `${schedule.name} - ${new Date().toISOString().split('T')[0]}`,
      status: 'active',
      startDate: new Date(),
      dueDate: new Date(Date.now() + schedule.dueInDays * 24 * 60 * 60 * 1000),
      initiatedBy,
      scope: schedule.scope,
      reviewers: schedule.reviewers,
      statistics: {
        totalCertifications: 0,
        completedCertifications: 0,
        pendingCertifications: 0,
        revokedAccess: 0,
        modifiedAccess: 0
      }
    };

    // Generate certifications for the campaign
    const certifications = await this.generateCertifications(campaign);
    campaign.statistics.totalCertifications = certifications.length;
    campaign.statistics.pendingCertifications = certifications.length;

    this.campaigns.set(campaign.id, campaign);
    this.certifications.set(campaign.id, certifications);

    return campaign;
  }

  /**
   * Generate certifications for a campaign
   */
  private async generateCertifications(
    campaign: CertificationCampaign
  ): Promise<Certification[]> {
    const certifications: Certification[] = [];
    const roleAssignments = rbacManager.exportRoleAssignments();

    for (const [userId, assignments] of Object.entries(roleAssignments)) {
      for (const assignment of assignments) {
        // Check if assignment is in scope
        if (!this.isAssignmentInScope(assignment, campaign.scope)) {
          continue;
        }

        // Determine reviewer
        const reviewer = await this.determineReviewer(
          userId,
          assignment,
          campaign.reviewers
        );

        const certification: Certification = {
          id: uuidv4(),
          campaignId: campaign.id,
          userId,
          roleId: assignment.roleId,
          assignment,
          reviewer,
          status: 'pending',
          createdAt: new Date(),
          dueDate: campaign.dueDate,
          riskScore: await this.calculateRiskScore(userId, assignment),
          recommendations: await this.generateRecommendations(userId, assignment)
        };

        certifications.push(certification);
      }
    }

    // Check for emergency access
    if (campaign.scope.includeEmergencyAccess) {
      const emergencyAccess = rbacManager.exportEmergencyAccessLog();
      for (const access of emergencyAccess) {
        const certification: Certification = {
          id: uuidv4(),
          campaignId: campaign.id,
          userId: access.userId,
          roleId: SYSTEM_ROLES.EMERGENCY_RESPONDER,
          emergencyAccess: access,
          reviewer: campaign.reviewers.escalation,
          status: 'pending',
          createdAt: new Date(),
          dueDate: campaign.dueDate,
          riskScore: 'high', // Emergency access is always high risk
          recommendations: ['Review emergency access justification', 'Verify continued need']
        };

        certifications.push(certification);
      }
    }

    return certifications;
  }

  /**
   * Check if assignment is in scope for campaign
   */
  private isAssignmentInScope(
    assignment: UserRoleAssignment,
    scope: CertificationScope
  ): boolean {
    if (scope.roles === 'all') {
      return !scope.excludeRoles?.includes(assignment.roleId);
    }

    return scope.roles.includes(assignment.roleId);
  }

  /**
   * Determine reviewer for certification
   */
  private async determineReviewer(
    userId: string,
    assignment: UserRoleAssignment,
    reviewers: ReviewerConfig
  ): Promise<string> {
    // In a real implementation, this would look up organizational hierarchy
    // For now, return the escalation reviewer
    return reviewers.escalation;
  }

  /**
   * Calculate risk score for an assignment
   */
  private async calculateRiskScore(
    userId: string,
    assignment: UserRoleAssignment
  ): Promise<RiskScore> {
    let score = 0;

    // Check role privilege level
    const role = await this.getRoleDetails(assignment.roleId);
    if (role.priority > 700) score += 40;
    else if (role.priority > 500) score += 25;
    else score += 10;

    // Check if delegated
    if (assignment.delegated) score += 15;

    // Check assignment age
    const ageInDays = Math.floor(
      (Date.now() - assignment.assignedAt.getTime()) / (1000 * 60 * 60 * 24)
    );
    if (ageInDays > 365) score += 20;
    else if (ageInDays > 180) score += 10;

    // Check usage patterns
    const accessReview = await rbacManager.performAccessReview(userId);
    if (accessReview.unusedRoles.includes(assignment.roleId)) score += 30;

    // Determine risk level
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  }

  /**
   * Generate recommendations for certification
   */
  private async generateRecommendations(
    userId: string,
    assignment: UserRoleAssignment
  ): Promise<string[]> {
    const recommendations: string[] = [];
    const accessReview = await rbacManager.performAccessReview(userId);

    // Check if role is unused
    if (accessReview.unusedRoles.includes(assignment.roleId)) {
      recommendations.push('Role has not been used in 90 days - consider removal');
    }

    // Check if assignment is expiring
    if (assignment.expiresAt) {
      const daysUntilExpiry = Math.floor(
        (assignment.expiresAt.getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      );
      if (daysUntilExpiry < 60) {
        recommendations.push(`Assignment expires in ${daysUntilExpiry} days`);
      }
    }

    // Check if delegated
    if (assignment.delegated) {
      recommendations.push('This is a delegated role - verify if delegation is still needed');
    }

    // Check for segregation of duties
    const otherRoles = accessReview.effectiveRoles.filter(r => r !== assignment.roleId);
    if (this.checkForConflicts(assignment.roleId, otherRoles)) {
      recommendations.push('Potential segregation of duties conflict detected');
    }

    return recommendations;
  }

  /**
   * Process certification decision
   */
  async processCertification(
    certificationId: string,
    reviewerId: string,
    decision: CertificationDecision
  ): Promise<void> {
    const certification = this.findCertification(certificationId);
    if (!certification) {
      throw new Error(`Certification ${certificationId} not found`);
    }

    // Validate reviewer
    if (certification.reviewer !== reviewerId) {
      throw new Error('Reviewer not authorized for this certification');
    }

    // Update certification
    certification.status = 'completed';
    certification.decision = decision;
    certification.reviewedAt = new Date();
    certification.reviewedBy = reviewerId;

    // Process the decision
    switch (decision.action) {
      case 'approve':
        // No action needed, access continues
        break;

      case 'revoke':
        await rbacManager.revokeRole(
          certification.userId,
          certification.roleId,
          reviewerId
        );
        this.updateCampaignStatistics(certification.campaignId, 'revoked');
        break;

      case 'modify':
        if (decision.modifications) {
          await this.applyModifications(
            certification.userId,
            certification.assignment!,
            decision.modifications
          );
          this.updateCampaignStatistics(certification.campaignId, 'modified');
        }
        break;
    }

    // Update campaign statistics
    this.updateCampaignStatistics(certification.campaignId, 'completed');
  }

  /**
   * Apply modifications to an assignment
   */
  private async applyModifications(
    userId: string,
    assignment: UserRoleAssignment,
    modifications: AccessModification
  ): Promise<void> {
    // Revoke existing assignment
    await rbacManager.revokeRole(userId, assignment.roleId, 'certification_process');

    // Create new assignment with modifications
    await rbacManager.assignRole(
      userId,
      assignment.roleId,
      'certification_process',
      {
        expiresAt: modifications.newExpiration || assignment.expiresAt,
        scope: modifications.newScope || assignment.scope,
        conditions: modifications.newConditions || assignment.conditions
      }
    );
  }

  /**
   * Update campaign statistics
   */
  private updateCampaignStatistics(
    campaignId: string,
    action: 'completed' | 'revoked' | 'modified'
  ): void {
    const campaign = this.campaigns.get(campaignId);
    if (!campaign) return;

    switch (action) {
      case 'completed':
        campaign.statistics.completedCertifications++;
        campaign.statistics.pendingCertifications--;
        break;
      case 'revoked':
        campaign.statistics.revokedAccess++;
        break;
      case 'modified':
        campaign.statistics.modifiedAccess++;
        break;
    }

    // Check if campaign is complete
    if (campaign.statistics.pendingCertifications === 0) {
      campaign.status = 'completed';
      campaign.completedDate = new Date();
    }
  }

  /**
   * Get campaign status report
   */
  getCampaignReport(campaignId: string): CampaignReport {
    const campaign = this.campaigns.get(campaignId);
    if (!campaign) {
      throw new Error(`Campaign ${campaignId} not found`);
    }

    const certifications = this.certifications.get(campaignId) || [];

    return {
      campaign,
      progress: {
        total: campaign.statistics.totalCertifications,
        completed: campaign.statistics.completedCertifications,
        pending: campaign.statistics.pendingCertifications,
        percentComplete: Math.round(
          (campaign.statistics.completedCertifications / campaign.statistics.totalCertifications) * 100
        )
      },
      riskAnalysis: {
        high: certifications.filter(c => c.riskScore === 'high').length,
        medium: certifications.filter(c => c.riskScore === 'medium').length,
        low: certifications.filter(c => c.riskScore === 'low').length
      },
      overdue: certifications.filter(
        c => c.status === 'pending' && c.dueDate < new Date()
      ).length
    };
  }

  /**
   * Send reminders for pending certifications
   */
  async sendReminders(): Promise<void> {
    for (const [campaignId, certifications] of this.certifications.entries()) {
      const campaign = this.campaigns.get(campaignId);
      if (!campaign || campaign.status !== 'active') continue;

      for (const cert of certifications) {
        if (cert.status !== 'pending') continue;

        const daysUntilDue = Math.floor(
          (cert.dueDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24)
        );

        // Send reminders at specific intervals
        if ([7, 3, 1].includes(daysUntilDue) || daysUntilDue < 0) {
          await this.sendCertificationReminder(cert, daysUntilDue);
        }
      }
    }
  }

  /**
   * Helper methods
   */
  private findCertification(certificationId: string): Certification | undefined {
    for (const certs of this.certifications.values()) {
      const cert = certs.find(c => c.id === certificationId);
      if (cert) return cert;
    }
    return undefined;
  }

  private async getRoleDetails(roleId: string): Promise<Role> {
    // This would fetch role details from rbacManager
    // For now, return a mock
    return {
      id: roleId,
      name: roleId,
      description: '',
      permissions: [],
      isSystem: true,
      priority: 500
    };
  }

  private checkForConflicts(roleId: string, otherRoles: string[]): boolean {
    // Check for segregation of duties conflicts
    const conflicts: Array<[string, string]> = [
      [SYSTEM_ROLES.AUDITOR, SYSTEM_ROLES.SYSTEM_ADMIN],
      [SYSTEM_ROLES.BILLING_SPECIALIST, SYSTEM_ROLES.PHYSICIAN]
    ];

    for (const [role1, role2] of conflicts) {
      if (
        (roleId === role1 && otherRoles.includes(role2)) ||
        (roleId === role2 && otherRoles.includes(role1))
      ) {
        return true;
      }
    }

    return false;
  }

  private async sendCertificationReminder(
    certification: Certification,
    daysUntilDue: number
  ): Promise<void> {
    // In real implementation, this would send email/notification
    console.log(`Reminder sent for certification ${certification.id}: ${daysUntilDue} days until due`);
  }
}

/**
 * Type definitions for certification process
 */
interface CertificationCampaign {
  id: string;
  scheduleId: string;
  name: string;
  status: 'active' | 'completed' | 'cancelled';
  startDate: Date;
  dueDate: Date;
  completedDate?: Date;
  initiatedBy: string;
  scope: CertificationScope;
  reviewers: ReviewerConfig;
  statistics: {
    totalCertifications: number;
    completedCertifications: number;
    pendingCertifications: number;
    revokedAccess: number;
    modifiedAccess: number;
  };
}

interface CertificationSchedule {
  id: string;
  name: string;
  frequency: 'quarterly' | 'semiannual' | 'annual';
  scope: CertificationScope;
  reviewers: ReviewerConfig;
  dueInDays: number;
}

interface CertificationScope {
  roles: string[] | 'all';
  excludeRoles?: string[];
  includeEmergencyAccess: boolean;
}

interface ReviewerConfig {
  primary: string;
  secondary: string;
  escalation: string;
}

interface Certification {
  id: string;
  campaignId: string;
  userId: string;
  roleId: string;
  assignment?: UserRoleAssignment;
  emergencyAccess?: any;
  reviewer: string;
  status: 'pending' | 'completed';
  createdAt: Date;
  dueDate: Date;
  reviewedAt?: Date;
  reviewedBy?: string;
  decision?: CertificationDecision;
  riskScore: RiskScore;
  recommendations: string[];
}

type RiskScore = 'high' | 'medium' | 'low';

interface CertificationDecision {
  action: 'approve' | 'revoke' | 'modify';
  comments?: string;
  modifications?: AccessModification;
}

interface AccessModification {
  newExpiration?: Date;
  newScope?: any;
  newConditions?: any[];
}

interface CampaignReport {
  campaign: CertificationCampaign;
  progress: {
    total: number;
    completed: number;
    pending: number;
    percentComplete: number;
  };
  riskAnalysis: {
    high: number;
    medium: number;
    low: number;
  };
  overdue: number;
}

// Export certification manager instance
export const certificationManager = new AccessCertificationManager();
