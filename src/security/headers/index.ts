/**
 * Security Headers Module
 * Comprehensive security headers implementation for Haven Health Passport
 */

// Export CSP implementation
export * from './csp-implementation';
export {
  CSPBuilder,
  CSPConfig,
  CSPDirective,
  CSPSource,
  CSPViolationReport,
  CSPPresets,
  CSPUtils,
  HealthcareCSPConfigs,
  createCSP,
  parseCSP,
  mergeCSP,
  validateCSP
} from './csp-implementation';

// Export main security headers
export * from './security-headers';
export {
  SecurityHeaders,
  SecurityHeadersConfig,
  SecurityHeadersValidator,
  SecurityHeadersPresets,
  HealthcareSecurityHeaders,
  NonceGenerator,
  createSecurityHeaders,
  validateHeaders,
  generateSecurityReport
} from './security-headers';

// Export permissions policy
export * from './permissions-policy';
export {
  PermissionsPolicyBuilder,
  PermissionsPolicyConfig,
  PermissionFeature,
  PermissionValue,
  HealthcarePermissionsPolicies,
  createPermissionsPolicy
} from './permissions-policy';

// Export security.txt
export * from './security-txt';
export {
  SecurityTxtGenerator,
  SecurityTxtConfig,
  HealthcareSecurityTxt,
  createSecurityTxt
} from './security-txt';

// Export report URI handler
export * from './report-uri';
export {
  ReportUriHandler,
  SecurityReport,
  ReportToConfig,
  ReportToConfigs,
  createReportHandler
} from './report-uri';

import { Request, Response, NextFunction, Application } from 'express';
import { SecurityHeaders, SecurityHeadersConfig } from './security-headers';
import { CSPBuilder } from './csp-implementation';
import { SecurityTxtGenerator } from './security-txt';
import { ReportUriHandler } from './report-uri';

/**
 * Complete security headers setup
 */
export interface SecurityHeadersSetup {
  headers?: SecurityHeadersConfig;
  csp?: any;
  securityTxt?: any;
  reportUri?: string;
  enableReporting?: boolean;
}

/**
 * Apply complete security headers to Express app
 */
export function applySecurityHeaders(
  app: Application,
  config: SecurityHeadersSetup = {}
): void {
  // Create security headers middleware
  const securityHeaders = new SecurityHeaders(config.headers);

  // Apply to all routes
  app.use(securityHeaders.middleware());

  // Setup security.txt
  if (config.securityTxt) {
    const securityTxt = new SecurityTxtGenerator(config.securityTxt);
    app.get('/.well-known/security.txt', securityTxt.middleware());
    app.get('/security.txt', (req, res) => {
      res.redirect(301, '/.well-known/security.txt');
    });
  }

  // Setup report URI endpoint
  if (config.enableReporting && config.reportUri) {
    const reportHandler = new ReportUriHandler();
    app.use(config.reportUri, reportHandler.router());
  }
}

/**
 * Healthcare-specific complete setup
 */
export const HealthcareSecuritySetup = {
  // Patient portal setup
  patientPortal: {
    headers: HealthcareSecurityHeaders.patientPortal,
    csp: HealthcareCSPConfigs.patientPortal,
    securityTxt: HealthcareSecurityTxt.standard,
    reportUri: '/api/security/reports',
    enableReporting: true
  },

  // Provider app setup
  providerApp: {
    headers: HealthcareSecurityHeaders.providerApp,
    csp: HealthcareCSPConfigs.providerApp,
    securityTxt: HealthcareSecurityTxt.standard,
    reportUri: '/api/security/reports',
    enableReporting: true
  },

  // API setup
  api: {
    headers: HealthcareSecurityHeaders.api,
    csp: false, // No CSP for API
    securityTxt: HealthcareSecurityTxt.minimal,
    reportUri: '/api/security/reports',
    enableReporting: true
  }
};

/**
 * Middleware to remove sensitive headers
 */
export function removeSensitiveHeaders(): (req: Request, res: Response, next: NextFunction) => void {
  return (req: Request, res: Response, next: NextFunction) => {
    // Remove headers that might leak information
    res.removeHeader('X-Powered-By');
    res.removeHeader('Server');
    res.removeHeader('X-AspNet-Version');
    res.removeHeader('X-AspNetMvc-Version');
    next();
  };
}

/**
 * Middleware to add security headers for file downloads
 */
export function downloadSecurityHeaders(): (req: Request, res: Response, next: NextFunction) => void {
  return (req: Request, res: Response, next: NextFunction) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Download-Options', 'noopen');
    res.setHeader('Content-Disposition', 'attachment');
    next();
  };
}

/**
 * Best practices guide
 */
export const SecurityHeadersBestPractices = {
  csp: [
    "Start with a report-only policy to identify issues",
    "Use 'strict-dynamic' for scripts instead of 'unsafe-inline'",
    "Implement nonces for inline scripts and styles",
    "Regularly review CSP violation reports",
    "Keep source lists as restrictive as possible"
  ],

  hsts: [
    "Start with a lower max-age and gradually increase",
    "Include subdomains once you're confident",
    "Submit to HSTS preload list for maximum security",
    "Ensure all subdomains support HTTPS before enabling includeSubDomains"
  ],

  general: [
    "Test security headers in staging before production",
    "Monitor for broken functionality after implementation",
    "Keep security headers up to date with standards",
    "Document any exceptions or special cases",
    "Regular security header audits"
  ],

  healthcare: [
    "Be careful with frame-ancestors for embedded viewers",
    "Allow necessary permissions for medical devices",
    "Implement strict CSP for patient data pages",
    "Use report-uri to monitor policy violations",
    "Consider regulatory requirements for security headers"
  ]
};

/**
 * Security headers checklist
 */
export const SecurityHeadersChecklist = {
  required: [
    'Content-Security-Policy',
    'X-Content-Type-Options',
    'X-Frame-Options',
    'Strict-Transport-Security'
  ],

  recommended: [
    'Referrer-Policy',
    'Permissions-Policy',
    'Cross-Origin-Opener-Policy',
    'Cross-Origin-Embedder-Policy',
    'Cross-Origin-Resource-Policy'
  ],

  optional: [
    'Report-To',
    'NEL (Network Error Logging)',
    'Expect-CT',
    'Public-Key-Pins (deprecated)'
  ]
};

// Export convenience function for quick setup
export function quickSecurityHeaders(type: 'strict' | 'balanced' | 'api' = 'balanced') {
  return SecurityHeadersPresets[type].middleware();
}

// Export version
export const VERSION = '1.0.0';
