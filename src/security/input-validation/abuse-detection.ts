/**
 * Abuse Detection
 * Comprehensive abuse detection and prevention system
 */

import { Request, Response, NextFunction } from 'express';
import { createHash } from 'crypto';
import geoip from 'geoip-lite';
import { UAParser } from 'ua-parser-js';

/**
 * Abuse detection configuration
 */
export interface AbuseDetectionConfig {
  // Thresholds
  maxFailedLogins?: number;
  maxFailedLoginWindow?: number;
  maxRequestsPerIP?: number;
  maxRequestsPerUser?: number;
  maxRequestsWindow?: number;

  // Behavioral analysis
  enableBehavioralAnalysis?: boolean;
  suspiciousPatterns?: SuspiciousPattern[];

  // Geographic restrictions
  blockedCountries?: string[];
  allowedCountries?: string[];
  enforceGeoBlocking?: boolean;

  // Device fingerprinting
  enableFingerprinting?: boolean;
  maxDevicesPerUser?: number;

  // Content analysis
  enableContentAnalysis?: boolean;
  maliciousPatterns?: RegExp[];

  // Actions
  blockDuration?: number;
  alertThreshold?: number;
  onAbuse?: (type: string, details: AbuseDetails) => void;
  onBlock?: (reason: string, details: AbuseDetails) => void;
}

/**
 * Abuse details
 */
export interface AbuseDetails {
  ip: string;
  userId?: string;
  userAgent?: string;
  fingerprint?: string;
  country?: string;
  timestamp: Date;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  evidence: any;
}

/**
 * Suspicious pattern definition
 */
export interface SuspiciousPattern {
  name: string;
  description: string;
  detector: (req: Request, history: RequestHistory) => boolean;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

/**
 * Request history for behavioral analysis
 */
export interface RequestHistory {
  requests: Array<{
    timestamp: Date;
    path: string;
    method: string;
    statusCode?: number;
    responseTime?: number;
    size?: number;
  }>;
  failedLogins: number;
  successfulLogins: number;
  uniquePaths: Set<string>;
  avgResponseTime: number;
}

/**
 * Abuse detector class
 */
export class AbuseDetector {
  private config: AbuseDetectionConfig;
  private blockedIPs: Map<string, { until: Date; reason: string }> = new Map();
  private blockedUsers: Map<string, { until: Date; reason: string }> = new Map();
  private requestHistory: Map<string, RequestHistory> = new Map();
  private deviceFingerprints: Map<string, Set<string>> = new Map();
  private suspiciousActivity: Map<string, AbuseDetails[]> = new Map();

  constructor(config: AbuseDetectionConfig = {}) {
    this.config = {
      maxFailedLogins: 5,
      maxFailedLoginWindow: 15 * 60 * 1000, // 15 minutes
      maxRequestsPerIP: 1000,
      maxRequestsPerUser: 5000,
      maxRequestsWindow: 60 * 60 * 1000, // 1 hour
      enableBehavioralAnalysis: true,
      enableFingerprinting: true,
      maxDevicesPerUser: 5,
      enableContentAnalysis: true,
      enforceGeoBlocking: false,
      blockDuration: 60 * 60 * 1000, // 1 hour
      alertThreshold: 10,
      ...config
    };

    // Add default suspicious patterns
    if (!this.config.suspiciousPatterns) {
      this.config.suspiciousPatterns = this.getDefaultPatterns();
    }

    // Add default malicious patterns
    if (!this.config.maliciousPatterns) {
      this.config.maliciousPatterns = this.getDefaultMaliciousPatterns();
    }

    // Clean up expired blocks periodically
    setInterval(() => this.cleanupExpiredBlocks(), 60000); // Every minute
  }

  /**
   * Main middleware
   */
  middleware() {
    return async (req: Request, res: Response, next: NextFunction) => {
      const ip = this.getClientIP(req);
      const userId = this.getUserId(req);
      const fingerprint = this.generateFingerprint(req);

      // Check if IP is blocked
      if (this.isBlocked(ip, 'ip')) {
        const block = this.blockedIPs.get(ip)!;
        return res.status(403).json({
          error: 'Access denied',
          reason: block.reason,
          until: block.until
        });
      }

      // Check if user is blocked
      if (userId && this.isBlocked(userId, 'user')) {
        const block = this.blockedUsers.get(userId)!;
        return res.status(403).json({
          error: 'Access denied',
          reason: block.reason,
          until: block.until
        });
      }

      // Check geographic restrictions
      if (this.config.enforceGeoBlocking) {
        const geoCheck = this.checkGeographicRestrictions(ip);
        if (!geoCheck.allowed) {
          this.recordAbuse('geo_restriction', {
            ip,
            userId,
            country: geoCheck.country,
            timestamp: new Date(),
            type: 'geo_restriction',
            severity: 'medium',
            evidence: { country: geoCheck.country }
          });

          return res.status(403).json({
            error: 'Access denied',
            reason: 'Geographic restriction'
          });
        }
      }

      // Update request history
      this.updateRequestHistory(ip, req);

      // Check for abuse patterns
      const abuseCheck = await this.detectAbuse(req);
      if (abuseCheck.detected) {
        this.handleAbuse(abuseCheck.type, abuseCheck.details);

        if (abuseCheck.shouldBlock) {
          return res.status(403).json({
            error: 'Access denied',
            reason: 'Suspicious activity detected'
          });
        }
      }

      // Monitor response
      const startTime = Date.now();
      const originalEnd = res.end;

      res.end = function(...args: any[]) {
        const responseTime = Date.now() - startTime;
        const history = this.requestHistory.get(ip);

        if (history && history.requests.length > 0) {
          const lastRequest = history.requests[history.requests.length - 1];
          lastRequest.statusCode = res.statusCode;
          lastRequest.responseTime = responseTime;

          // Check for failed login attempts
          if (req.path.includes('login') && res.statusCode === 401) {
            history.failedLogins++;
            this.checkFailedLogins(ip, userId);
          } else if (req.path.includes('login') && res.statusCode === 200) {
            history.successfulLogins++;
          }
        }

        return originalEnd.apply(this, args);
      }.bind(this);

      next();
    };
  }

  /**
   * Detect abuse patterns
   */
  private async detectAbuse(req: Request): Promise<{
    detected: boolean;
    type?: string;
    details?: AbuseDetails;
    shouldBlock?: boolean;
  }> {
    const ip = this.getClientIP(req);
    const userId = this.getUserId(req);
    const history = this.requestHistory.get(ip) || this.createNewHistory();

    // Check request rate
    const rateCheck = this.checkRequestRate(ip, userId);
    if (rateCheck.exceeded) {
      return {
        detected: true,
        type: 'rate_limit_abuse',
        details: {
          ip,
          userId,
          timestamp: new Date(),
          type: 'rate_limit_abuse',
          severity: 'high',
          evidence: rateCheck
        },
        shouldBlock: true
      };
    }

    // Check behavioral patterns
    if (this.config.enableBehavioralAnalysis) {
      for (const pattern of this.config.suspiciousPatterns!) {
        if (pattern.detector(req, history)) {
          const details: AbuseDetails = {
            ip,
            userId,
            userAgent: req.headers['user-agent'],
            timestamp: new Date(),
            type: pattern.name,
            severity: pattern.severity,
            evidence: { pattern: pattern.name }
          };

          return {
            detected: true,
            type: pattern.name,
            details,
            shouldBlock: pattern.severity === 'critical'
          };
        }
      }
    }

    // Check content for malicious patterns
    if (this.config.enableContentAnalysis) {
      const contentCheck = this.checkMaliciousContent(req);
      if (contentCheck.detected) {
        return {
          detected: true,
          type: 'malicious_content',
          details: {
            ip,
            userId,
            timestamp: new Date(),
            type: 'malicious_content',
            severity: 'critical',
            evidence: contentCheck
          },
          shouldBlock: true
        };
      }
    }

    // Check device fingerprinting
    if (this.config.enableFingerprinting && userId) {
      const fingerprintCheck = this.checkDeviceFingerprint(userId, req);
      if (fingerprintCheck.suspicious) {
        return {
          detected: true,
          type: 'device_anomaly',
          details: {
            ip,
            userId,
            fingerprint: fingerprintCheck.fingerprint,
            timestamp: new Date(),
            type: 'device_anomaly',
            severity: 'medium',
            evidence: fingerprintCheck
          },
          shouldBlock: false
        };
      }
    }

    return { detected: false };
  }

  /**
   * Get default suspicious patterns
   */
  private getDefaultPatterns(): SuspiciousPattern[] {
    return [
      {
        name: 'path_scanning',
        description: 'Scanning for common vulnerable paths',
        severity: 'high',
        detector: (req, history) => {
          const suspiciousPaths = [
            '/admin', '/wp-admin', '/phpmyadmin', '/.env',
            '/.git', '/config', '/backup', '/sql', '/db',
            '/api/v1/users', '/api/v1/admin'
          ];

          const recentPaths = history.requests
            .slice(-20)
            .map(r => r.path);

          const suspiciousCount = recentPaths.filter(path =>
            suspiciousPaths.some(sp => path.includes(sp))
          ).length;

          return suspiciousCount > 5;
        }
      },
      {
        name: 'rapid_sequential_requests',
        description: 'Too many requests in rapid succession',
        severity: 'medium',
        detector: (req, history) => {
          const recentRequests = history.requests.slice(-10);
          if (recentRequests.length < 10) return false;

          const timeSpan = recentRequests[9].timestamp.getTime() -
                          recentRequests[0].timestamp.getTime();

          return timeSpan < 1000; // 10 requests in 1 second
        }
      },
      {
        name: 'parameter_fuzzing',
        description: 'Testing with malformed parameters',
        severity: 'high',
        detector: (req, history) => {
          const params = { ...req.query, ...req.body };
          const fuzzyPatterns = [
            /['"<>]/,                    // SQL/XSS characters
            /\.\.[\/\\]/,                // Path traversal
            /\${.*}/,                    // Template injection
            /{{.*}}/,                    // Template injection
            /%00/,                       // Null byte
            /\x00-\x1f/                  // Control characters
          ];

          for (const value of Object.values(params)) {
            if (typeof value === 'string') {
              for (const pattern of fuzzyPatterns) {
                if (pattern.test(value)) return true;
              }
            }
          }

          return false;
        }
      },
      {
        name: 'credential_stuffing',
        description: 'Multiple login attempts with different credentials',
        severity: 'critical',
        detector: (req, history) => {
          if (!req.path.includes('login')) return false;

          const recentLogins = history.requests
            .filter(r => r.path.includes('login'))
            .slice(-10);

          return recentLogins.length >= 5 &&
                 history.failedLogins > history.successfulLogins * 2;
        }
      },
      {
        name: 'api_abuse',
        description: 'Excessive API calls',
        severity: 'medium',
        detector: (req, history) => {
          const apiRequests = history.requests
            .filter(r => r.path.startsWith('/api'))
            .length;

          return apiRequests > 100;
        }
      }
    ];
  }

  /**
   * Get default malicious patterns
   */
  private getDefaultMaliciousPatterns(): RegExp[] {
    return [
      // SQL Injection
      /(\b(union|select|insert|update|delete|drop|exec|execute)\b.*\b(from|where|table|database)\b)/i,
      /(';|";|--;|\/\*|\*\/)/,

      // XSS
      /<script[^>]*>[\s\S]*?<\/script>/gi,
      /javascript:\s*[^"'`]*/gi,
      /on\w+\s*=\s*["'][^"']*["']/gi,

      // Command Injection
      /(\||;|&|`|\$\(|\${)/,
      /(nc|netcat|bash|sh|cmd|powershell)\s+-/i,

      // LDAP Injection
      /[()&|*]/,

      // XML Injection
      /<!ENTITY.*>/,
      /<!\[CDATA\[.*\]\]>/,

      // Path Traversal
      /\.\.[\/\\]|\.\.;/,

      // Server-Side Includes
      /<!--#(include|exec|echo|config)/i
    ];
  }

  /**
   * Check request rate
   */
  private checkRequestRate(ip: string, userId?: string): {
    exceeded: boolean;
    current: number;
    limit: number;
    window: string;
  } {
    const history = this.requestHistory.get(ip);
    if (!history) {
      return { exceeded: false, current: 0, limit: this.config.maxRequestsPerIP!, window: '1h' };
    }

    const now = Date.now();
    const windowStart = now - this.config.maxRequestsWindow!;
    const recentRequests = history.requests.filter(r =>
      r.timestamp.getTime() > windowStart
    ).length;

    const limit = userId ? this.config.maxRequestsPerUser! : this.config.maxRequestsPerIP!;

    return {
      exceeded: recentRequests > limit,
      current: recentRequests,
      limit,
      window: '1h'
    };
  }

  /**
   * Check failed login attempts
   */
  private checkFailedLogins(ip: string, userId?: string): void {
    const history = this.requestHistory.get(ip);
    if (!history) return;

    const now = Date.now();
    const windowStart = now - this.config.maxFailedLoginWindow!;
    const recentFailures = history.requests.filter(r =>
      r.path.includes('login') &&
      r.statusCode === 401 &&
      r.timestamp.getTime() > windowStart
    ).length;

    if (recentFailures >= this.config.maxFailedLogins!) {
      const details: AbuseDetails = {
        ip,
        userId,
        timestamp: new Date(),
        type: 'failed_login',
        severity: 'high',
        evidence: { failedAttempts: recentFailures }
      };

      this.handleAbuse('failed_login', details);

      // Block the IP/user
      this.block(ip, 'ip', 'Too many failed login attempts');
      if (userId) {
        this.block(userId, 'user', 'Too many failed login attempts');
      }
    }
  }

  /**
   * Check malicious content
   */
  private checkMaliciousContent(req: Request): {
    detected: boolean;
    pattern?: string;
    location?: string;
  } {
    const checkString = (str: string, location: string) => {
      for (const pattern of this.config.maliciousPatterns!) {
        if (pattern.test(str)) {
          return { detected: true, pattern: pattern.toString(), location };
        }
      }
      return { detected: false };
    };

    // Check URL
    const urlCheck = checkString(req.originalUrl, 'url');
    if (urlCheck.detected) return urlCheck;

    // Check headers
    for (const [header, value] of Object.entries(req.headers)) {
      if (typeof value === 'string') {
        const headerCheck = checkString(value, `header:${header}`);
        if (headerCheck.detected) return headerCheck;
      }
    }

    // Check body
    if (req.body) {
      const bodyStr = JSON.stringify(req.body);
      const bodyCheck = checkString(bodyStr, 'body');
      if (bodyCheck.detected) return bodyCheck;
    }

    return { detected: false };
  }

  /**
   * Check device fingerprint
   */
  private checkDeviceFingerprint(userId: string, req: Request): {
    suspicious: boolean;
    fingerprint: string;
    reason?: string;
  } {
    const fingerprint = this.generateFingerprint(req);

    if (!this.deviceFingerprints.has(userId)) {
      this.deviceFingerprints.set(userId, new Set([fingerprint]));
      return { suspicious: false, fingerprint };
    }

    const userFingerprints = this.deviceFingerprints.get(userId)!;

    if (!userFingerprints.has(fingerprint)) {
      userFingerprints.add(fingerprint);

      if (userFingerprints.size > this.config.maxDevicesPerUser!) {
        return {
          suspicious: true,
          fingerprint,
          reason: 'Too many devices'
        };
      }

      return {
        suspicious: true,
        fingerprint,
        reason: 'New device'
      };
    }

    return { suspicious: false, fingerprint };
  }

  /**
   * Check geographic restrictions
   */
  private checkGeographicRestrictions(ip: string): {
    allowed: boolean;
    country?: string;
  } {
    const geo = geoip.lookup(ip);
    const country = geo?.country;

    if (!country) {
      return { allowed: true }; // Allow if can't determine
    }

    if (this.config.blockedCountries?.includes(country)) {
      return { allowed: false, country };
    }

    if (this.config.allowedCountries &&
        !this.config.allowedCountries.includes(country)) {
      return { allowed: false, country };
    }

    return { allowed: true, country };
  }

  /**
   * Generate device fingerprint
   */
  private generateFingerprint(req: Request): string {
    const ua = new UAParser(req.headers['user-agent']);
    const browser = ua.getBrowser();
    const os = ua.getOS();
    const device = ua.getDevice();

    const components = [
      browser.name || 'unknown',
      browser.version || 'unknown',
      os.name || 'unknown',
      os.version || 'unknown',
      device.type || 'desktop',
      device.vendor || 'unknown',
      req.headers['accept-language'] || 'unknown',
      req.headers['accept-encoding'] || 'unknown'
    ];

    return createHash('sha256')
      .update(components.join('|'))
      .digest('hex');
  }

  /**
   * Handle detected abuse
   */
  private handleAbuse(type: string, details: AbuseDetails): void {
    // Record abuse
    this.recordAbuse(type, details);

    // Call custom handler
    if (this.config.onAbuse) {
      this.config.onAbuse(type, details);
    }

    // Check if should alert
    const key = `${details.ip}:${type}`;
    const incidents = this.suspiciousActivity.get(key) || [];

    if (incidents.length >= this.config.alertThreshold!) {
      console.error(`ABUSE ALERT: ${type} from ${details.ip}`, details);
    }
  }

  /**
   * Record abuse incident
   */
  private recordAbuse(type: string, details: AbuseDetails): void {
    const key = `${details.ip}:${type}`;

    if (!this.suspiciousActivity.has(key)) {
      this.suspiciousActivity.set(key, []);
    }

    this.suspiciousActivity.get(key)!.push(details);

    // Keep only recent incidents
    const recentIncidents = this.suspiciousActivity.get(key)!
      .filter(incident =>
        incident.timestamp.getTime() > Date.now() - 24 * 60 * 60 * 1000
      );

    this.suspiciousActivity.set(key, recentIncidents);
  }

  /**
   * Block IP or user
   */
  private block(identifier: string, type: 'ip' | 'user', reason: string): void {
    const until = new Date(Date.now() + this.config.blockDuration!);
    const blockInfo = { until, reason };

    if (type === 'ip') {
      this.blockedIPs.set(identifier, blockInfo);
    } else {
      this.blockedUsers.set(identifier, blockInfo);
    }

    if (this.config.onBlock) {
      this.config.onBlock(reason, {
        ip: type === 'ip' ? identifier : '',
        userId: type === 'user' ? identifier : '',
        timestamp: new Date(),
        type: 'block',
        severity: 'critical',
        evidence: { reason, until }
      });
    }
  }

  /**
   * Check if blocked
   */
  private isBlocked(identifier: string, type: 'ip' | 'user'): boolean {
    const map = type === 'ip' ? this.blockedIPs : this.blockedUsers;
    const block = map.get(identifier);

    if (!block) return false;

    if (block.until.getTime() < Date.now()) {
      map.delete(identifier);
      return false;
    }

    return true;
  }

  /**
   * Update request history
   */
  private updateRequestHistory(ip: string, req: Request): void {
    if (!this.requestHistory.has(ip)) {
      this.requestHistory.set(ip, this.createNewHistory());
    }

    const history = this.requestHistory.get(ip)!;

    history.requests.push({
      timestamp: new Date(),
      path: req.path,
      method: req.method
    });

    history.uniquePaths.add(req.path);

    // Keep only recent history
    const cutoff = Date.now() - 24 * 60 * 60 * 1000; // 24 hours
    history.requests = history.requests.filter(r =>
      r.timestamp.getTime() > cutoff
    );
  }

  /**
   * Create new history object
   */
  private createNewHistory(): RequestHistory {
    return {
      requests: [],
      failedLogins: 0,
      successfulLogins: 0,
      uniquePaths: new Set(),
      avgResponseTime: 0
    };
  }

  /**
   * Get client IP
   */
  private getClientIP(req: Request): string {
    return (req.ip ||
            req.headers['x-forwarded-for'] ||
            req.headers['x-real-ip'] ||
            req.socket.remoteAddress ||
            'unknown') as string;
  }

  /**
   * Get user ID from request
   */
  private getUserId(req: Request): string | undefined {
    return (req as any).user?.id ||
           (req as any).userId ||
           req.headers['x-user-id'] as string;
  }

  /**
   * Clean up expired blocks
   */
  private cleanupExpiredBlocks(): void {
    const now = Date.now();

    // Clean IP blocks
    for (const [ip, block] of this.blockedIPs.entries()) {
      if (block.until.getTime() < now) {
        this.blockedIPs.delete(ip);
      }
    }

    // Clean user blocks
    for (const [userId, block] of this.blockedUsers.entries()) {
      if (block.until.getTime() < now) {
        this.blockedUsers.delete(userId);
      }
    }
  }

  /**
   * Get abuse statistics
   */
  getStatistics() {
    const stats = {
      blockedIPs: this.blockedIPs.size,
      blockedUsers: this.blockedUsers.size,
      totalSuspiciousActivity: 0,
      activityByType: {} as Record<string, number>,
      recentIncidents: [] as AbuseDetails[]
    };

    for (const [key, incidents] of this.suspiciousActivity.entries()) {
      const type = key.split(':')[1];
      stats.activityByType[type] = (stats.activityByType[type] || 0) + incidents.length;
      stats.totalSuspiciousActivity += incidents.length;

      // Get recent incidents
      const recent = incidents.slice(-10);
      stats.recentIncidents.push(...recent);
    }

    // Sort recent incidents by timestamp
    stats.recentIncidents.sort((a, b) =>
      b.timestamp.getTime() - a.timestamp.getTime()
    );

    return stats;
  }

  /**
   * Unblock IP or user
   */
  unblock(identifier: string, type: 'ip' | 'user'): void {
    if (type === 'ip') {
      this.blockedIPs.delete(identifier);
    } else {
      this.blockedUsers.delete(identifier);
    }
  }

  /**
   * Clear all blocks
   */
  clearAllBlocks(): void {
    this.blockedIPs.clear();
    this.blockedUsers.clear();
  }
}

/**
 * Honeypot middleware
 */
export class HoneypotMiddleware {
  private honeypotPaths: string[];
  private honeypotFields: string[];
  private onTrigger?: (req: Request, type: string) => void;

  constructor(config: {
    paths?: string[];
    fields?: string[];
    onTrigger?: (req: Request, type: string) => void;
  } = {}) {
    this.honeypotPaths = config.paths || [
      '/admin/config.php',
      '/wp-login.php',
      '/.env',
      '/api/debug',
      '/phpmyadmin'
    ];

    this.honeypotFields = config.fields || [
      'email_confirm',
      'phone_confirm',
      'website',
      'honeypot'
    ];

    this.onTrigger = config.onTrigger;
  }

  middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      // Check honeypot paths
      if (this.honeypotPaths.includes(req.path)) {
        if (this.onTrigger) {
          this.onTrigger(req, 'path');
        }

        // Log and block
        console.warn(`Honeypot triggered: ${req.path} from ${req.ip}`);

        // Return fake response to confuse attacker
        return res.status(200).send('<!-- Success -->');
      }

      // Check honeypot fields in forms
      if (req.body) {
        for (const field of this.honeypotFields) {
          if (req.body[field]) {
            if (this.onTrigger) {
              this.onTrigger(req, 'field');
            }

            console.warn(`Honeypot field triggered: ${field} from ${req.ip}`);

            // Return success to confuse bots
            return res.status(200).json({ success: true });
          }
        }
      }

      next();
    };
  }
}

// Export convenience functions
export const createAbuseDetector = (config?: AbuseDetectionConfig) => new AbuseDetector(config);
export const createHoneypot = (config?: any) => new HoneypotMiddleware(config);
