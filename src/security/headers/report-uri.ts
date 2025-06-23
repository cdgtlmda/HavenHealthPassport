/**
 * Report URI Handler
 * Handles security violation reports from various sources
 */

import { Request, Response, Router } from 'express';
import { CSPViolationReport } from './csp-implementation';

/**
 * Report types
 */
export interface SecurityReport {
  type: 'csp' | 'ct' | 'nel' | 'deprecation' | 'intervention' | 'crash';
  timestamp: Date;
  userAgent?: string;
  url?: string;
  body: any;
}

/**
 * Report-To configuration
 */
export interface ReportToConfig {
  group: string;
  max_age: number;
  endpoints: Array<{
    url: string;
    priority?: number;
    weight?: number;
  }>;
  include_subdomains?: boolean;
}

/**
 * Report URI handler
 */
export class ReportUriHandler {
  private reports: SecurityReport[] = [];
  private maxReports: number = 10000;
  private reportHandlers: Map<string, (report: any) => void> = new Map();

  constructor(config?: { maxReports?: number }) {
    if (config?.maxReports) {
      this.maxReports = config.maxReports;
    }
  }

  /**
   * Register report handler
   */
  registerHandler(type: string, handler: (report: any) => void): void {
    this.reportHandlers.set(type, handler);
  }

  /**
   * Handle CSP violation report
   */
  handleCSPReport(req: Request, res: Response): void {
    const report = req.body as CSPViolationReport;

    this.storeReport({
      type: 'csp',
      timestamp: new Date(),
      userAgent: req.headers['user-agent'],
      url: report['csp-report']['document-uri'],
      body: report
    });

    // Call custom handler if registered
    const handler = this.reportHandlers.get('csp');
    if (handler) {
      handler(report);
    }

    res.status(204).end();
  }

  /**
   * Handle Network Error Logging report
   */
  handleNELReport(req: Request, res: Response): void {
    const reports = req.body;

    for (const report of reports) {
      this.storeReport({
        type: 'nel',
        timestamp: new Date(),
        userAgent: req.headers['user-agent'],
        url: report.url,
        body: report
      });
    }

    res.status(204).end();
  }

  /**
   * Handle generic report
   */
  handleGenericReport(req: Request, res: Response): void {
    const reports = Array.isArray(req.body) ? req.body : [req.body];

    for (const report of reports) {
      this.storeReport({
        type: report.type || 'unknown',
        timestamp: new Date(),
        userAgent: req.headers['user-agent'],
        url: report.url,
        body: report
      });
    }

    res.status(204).end();
  }

  /**
   * Store report
   */
  private storeReport(report: SecurityReport): void {
    this.reports.push(report);

    // Limit stored reports
    if (this.reports.length > this.maxReports) {
      this.reports = this.reports.slice(-this.maxReports);
    }

    // Log critical reports
    if (report.type === 'csp' && this.isCriticalCSPViolation(report.body)) {
      console.error('Critical CSP violation:', report);
    }
  }

  /**
   * Check if CSP violation is critical
   */
  private isCriticalCSPViolation(report: CSPViolationReport): boolean {
    const violation = report['csp-report'];

    // Check for script injection attempts
    if (violation['violated-directive'].startsWith('script-src') &&
        violation['blocked-uri']?.includes('javascript:')) {
      return true;
    }

    // Check for data exfiltration attempts
    if (violation['violated-directive'].startsWith('connect-src') &&
        !violation['blocked-uri']?.startsWith('https://')) {
      return true;
    }

    return false;
  }

  /**
   * Get reports
   */
  getReports(filter?: { type?: string; since?: Date }): SecurityReport[] {
    let filtered = this.reports;

    if (filter?.type) {
      filtered = filtered.filter(r => r.type === filter.type);
    }

    if (filter?.since) {
      filtered = filtered.filter(r => r.timestamp > filter.since);
    }

    return filtered;
  }

  /**
   * Generate Report-To header value
   */
  static generateReportTo(configs: ReportToConfig[]): string {
    return configs.map(config => JSON.stringify(config)).join(', ');
  }

  /**
   * Create Express router
   */
  router(): Router {
    const router = Router();

    // CSP reports
    router.post('/csp', (req, res) => this.handleCSPReport(req, res));

    // Network Error Logging
    router.post('/nel', (req, res) => this.handleNELReport(req, res));

    // Generic reports
    router.post('/generic', (req, res) => this.handleGenericReport(req, res));

    // Get reports (admin only)
    router.get('/reports', (req, res) => {
      // Add authentication check here
      const reports = this.getReports({
        type: req.query.type as string,
        since: req.query.since ? new Date(req.query.since as string) : undefined
      });

      res.json({
        count: reports.length,
        reports: reports.slice(0, 100) // Limit response
      });
    });

    return router;
  }
}

/**
 * Report-To configurations
 */
export const ReportToConfigs = {
  // Default configuration
  default: [
    {
      group: 'default',
      max_age: 86400,
      endpoints: [
        { url: 'https://api.havenhealth.com/security/reports/generic' }
      ]
    },
    {
      group: 'csp',
      max_age: 86400,
      endpoints: [
        { url: 'https://api.havenhealth.com/security/reports/csp' }
      ]
    },
    {
      group: 'network-errors',
      max_age: 86400,
      endpoints: [
        { url: 'https://api.havenhealth.com/security/reports/nel' }
      ]
    }
  ]
};

// Export convenience function
export const createReportHandler = (config?: any) => new ReportUriHandler(config);
