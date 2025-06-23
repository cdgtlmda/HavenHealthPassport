/**
 * CSP (Content Security Policy) Implementation
 * Comprehensive CSP configuration and management
 */

import { Request, Response, NextFunction } from 'express';
import { createHash, randomBytes } from 'crypto';

/**
 * CSP directive types
 */
export type CSPDirective =
  | 'default-src'
  | 'script-src'
  | 'style-src'
  | 'img-src'
  | 'connect-src'
  | 'font-src'
  | 'object-src'
  | 'media-src'
  | 'frame-src'
  | 'sandbox'
  | 'report-uri'
  | 'report-to'
  | 'child-src'
  | 'form-action'
  | 'frame-ancestors'
  | 'plugin-types'
  | 'base-uri'
  | 'manifest-src'
  | 'worker-src'
  | 'prefetch-src'
  | 'navigate-to';

/**
 * CSP source values
 */
export type CSPSource =
  | "'self'"
  | "'unsafe-inline'"
  | "'unsafe-eval'"
  | "'none'"
  | "'strict-dynamic'"
  | "'unsafe-hashes'"
  | "'report-sample'"
  | "'unsafe-allow-redirects'"
  | string;

/**
 * CSP configuration
 */
export interface CSPConfig {
  directives: Partial<Record<CSPDirective, CSPSource[]>>;
  reportOnly?: boolean;
  reportUri?: string;
  reportTo?: string;
  useNonce?: boolean;
  useHash?: boolean;
  upgradeInsecureRequests?: boolean;
  blockAllMixedContent?: boolean;
}

/**
 * CSP violation report
 */
export interface CSPViolationReport {
  'csp-report': {
    'document-uri': string;
    'referrer'?: string;
    'violated-directive': string;
    'effective-directive': string;
    'original-policy': string;
    'disposition': 'enforce' | 'report';
    'blocked-uri'?: string;
    'line-number'?: number;
    'column-number'?: number;
    'source-file'?: string;
    'status-code'?: number;
    'script-sample'?: string;
  };
}

/**
 * CSP builder class
 */
export class CSPBuilder {
  private config: CSPConfig;
  private nonces: Map<string, string> = new Map();

  constructor(config: CSPConfig = {}) {
    this.config = {
      directives: {
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'"],
        'img-src': ["'self'", 'data:', 'https:'],
        'connect-src': ["'self'"],
        'font-src': ["'self'"],
        'object-src': ["'none'"],
        'media-src': ["'self'"],
        'frame-src': ["'none'"],
        'base-uri': ["'self'"],
        'form-action': ["'self'"],
        'frame-ancestors': ["'none'"],
        'plugin-types': ["'none'"]
      },
      reportOnly: false,
      useNonce: true,
      useHash: false,
      upgradeInsecureRequests: true,
      blockAllMixedContent: true,
      ...config
    };

    // Merge directives
    if (config.directives) {
      this.config.directives = {
        ...this.config.directives,
        ...config.directives
      };
    }
  }

  /**
   * Generate nonce
   */
  generateNonce(): string {
    const nonce = randomBytes(16).toString('base64');
    return nonce;
  }

  /**
   * Generate hash for inline content
   */
  generateHash(content: string, algorithm: 'sha256' | 'sha384' | 'sha512' = 'sha256'): string {
    const hash = createHash(algorithm).update(content).digest('base64');
    return `'${algorithm}-${hash}'`;
  }

  /**
   * Add source to directive
   */
  addSource(directive: CSPDirective, source: CSPSource): this {
    if (!this.config.directives[directive]) {
      this.config.directives[directive] = [];
    }

    if (!this.config.directives[directive]!.includes(source)) {
      this.config.directives[directive]!.push(source);
    }

    return this;
  }

  /**
   * Remove source from directive
   */
  removeSource(directive: CSPDirective, source: CSPSource): this {
    if (this.config.directives[directive]) {
      this.config.directives[directive] =
        this.config.directives[directive]!.filter(s => s !== source);
    }

    return this;
  }

  /**
   * Set directive
   */
  setDirective(directive: CSPDirective, sources: CSPSource[]): this {
    this.config.directives[directive] = sources;
    return this;
  }

  /**
   * Build CSP string
   */
  build(nonce?: string): string {
    const parts: string[] = [];

    // Add upgrade-insecure-requests
    if (this.config.upgradeInsecureRequests) {
      parts.push('upgrade-insecure-requests');
    }

    // Add block-all-mixed-content
    if (this.config.blockAllMixedContent) {
      parts.push('block-all-mixed-content');
    }

    // Build directives
    for (const [directive, sources] of Object.entries(this.config.directives)) {
      if (sources && sources.length > 0) {
        let directiveSources = [...sources];

        // Add nonce to script-src and style-src if enabled
        if (nonce && this.config.useNonce) {
          if (directive === 'script-src' || directive === 'style-src') {
            directiveSources.push(`'nonce-${nonce}'`);
          }
        }

        parts.push(`${directive} ${directiveSources.join(' ')}`);
      }
    }

    // Add report-uri
    if (this.config.reportUri) {
      parts.push(`report-uri ${this.config.reportUri}`);
    }

    // Add report-to
    if (this.config.reportTo) {
      parts.push(`report-to ${this.config.reportTo}`);
    }

    return parts.join('; ');
  }

  /**
   * Create middleware
   */
  middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      // Generate nonce if enabled
      let nonce: string | undefined;
      if (this.config.useNonce) {
        nonce = this.generateNonce();
        // Store nonce in res.locals for use in templates
        res.locals.cspNonce = nonce;
      }

      // Build CSP header
      const cspHeader = this.build(nonce);

      // Set appropriate header
      const headerName = this.config.reportOnly ?
        'Content-Security-Policy-Report-Only' :
        'Content-Security-Policy';

      res.setHeader(headerName, cspHeader);

      next();
    };
  }

  /**
   * Handle CSP violation reports
   */
  static reportHandler() {
    return async (req: Request, res: Response) => {
      const report = req.body as CSPViolationReport;

      // Log violation
      console.warn('CSP Violation:', {
        documentUri: report['csp-report']['document-uri'],
        violatedDirective: report['csp-report']['violated-directive'],
        blockedUri: report['csp-report']['blocked-uri'],
        sourceFile: report['csp-report']['source-file'],
        lineNumber: report['csp-report']['line-number'],
        columnNumber: report['csp-report']['column-number'],
        scriptSample: report['csp-report']['script-sample']
      });

      // Store in database or send to monitoring service
      // await storeCSPViolation(report);

      res.status(204).end();
    };
  }
}

/**
 * Healthcare-specific CSP configurations
 */
export const HealthcareCSPConfigs = {
  // Strict configuration for patient portals
  patientPortal: {
    directives: {
      'default-src': ["'self'"],
      'script-src': ["'self'", "'strict-dynamic'"],
      'style-src': ["'self'", "'unsafe-inline'"], // For dynamic styles
      'img-src': ["'self'", 'data:', 'https://medical-images.example.com'],
      'connect-src': ["'self'", 'https://api.havenhealth.com', 'wss://api.havenhealth.com'],
      'font-src': ["'self'", 'https://fonts.gstatic.com'],
      'object-src': ["'none'"],
      'media-src': ["'self'"],
      'frame-src': ["'none'"],
      'base-uri': ["'self'"],
      'form-action': ["'self'"],
      'frame-ancestors': ["'none'"],
      'manifest-src': ["'self'"],
      'worker-src': ["'self'"]
    },
    reportUri: '/api/security/csp-report',
    useNonce: true,
    upgradeInsecureRequests: true,
    blockAllMixedContent: true
  },

  // Configuration for provider applications
  providerApp: {
    directives: {
      'default-src': ["'self'"],
      'script-src': ["'self'", "'strict-dynamic'", "blob:"], // For PDF viewers
      'style-src': ["'self'", "'unsafe-inline'"],
      'img-src': ["'self'", 'data:', 'https:', 'blob:'],
      'connect-src': ["'self'", 'https://api.havenhealth.com', 'wss://api.havenhealth.com'],
      'font-src': ["'self'", 'https://fonts.gstatic.com'],
      'object-src': ["'self'"], // For PDF embedding
      'media-src': ["'self'", 'blob:'],
      'frame-src': ["'self'", 'https://telehealth.havenhealth.com'],
      'base-uri': ["'self'"],
      'form-action': ["'self'"],
      'frame-ancestors': ["'self'"],
      'worker-src': ["'self'", 'blob:']
    },
    reportUri: '/api/security/csp-report',
    useNonce: true,
    upgradeInsecureRequests: true
  },

  // Configuration for admin interfaces
  adminInterface: {
    directives: {
      'default-src': ["'self'"],
      'script-src': ["'self'", "'strict-dynamic'"],
      'style-src': ["'self'", "'unsafe-inline'"],
      'img-src': ["'self'", 'data:'],
      'connect-src': ["'self'"],
      'font-src': ["'self'"],
      'object-src': ["'none'"],
      'media-src': ["'none'"],
      'frame-src': ["'none'"],
      'base-uri': ["'self'"],
      'form-action': ["'self'"],
      'frame-ancestors': ["'none'"]
    },
    reportUri: '/api/security/csp-report',
    useNonce: true,
    upgradeInsecureRequests: true,
    blockAllMixedContent: true
  },

  // Development configuration (more permissive)
  development: {
    directives: {
      'default-src': ["'self'"],
      'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "http://localhost:*"],
      'style-src': ["'self'", "'unsafe-inline'", "http://localhost:*"],
      'img-src': ["'self'", 'data:', 'http:', 'https:'],
      'connect-src': ["'self'", 'http://localhost:*', 'ws://localhost:*'],
      'font-src': ["'self'", 'data:', 'http:', 'https:'],
      'object-src': ["'self'"],
      'media-src': ["'self'"],
      'frame-src': ["'self'", "http://localhost:*"],
      'form-action': ["'self'"],
      'frame-ancestors': ["'self'", "http://localhost:*"]
    },
    reportOnly: true,
    reportUri: '/api/security/csp-report'
  }
};

/**
 * CSP presets for common scenarios
 */
export const CSPPresets = {
  // Maximum security
  strict: new CSPBuilder({
    directives: {
      'default-src': ["'none'"],
      'script-src': ["'self'"],
      'style-src': ["'self'"],
      'img-src': ["'self'"],
      'connect-src': ["'self'"],
      'font-src': ["'self'"],
      'object-src': ["'none'"],
      'media-src': ["'none'"],
      'frame-src': ["'none'"],
      'base-uri': ["'none'"],
      'form-action': ["'self'"],
      'frame-ancestors': ["'none'"],
      'sandbox': ['allow-forms', 'allow-same-origin', 'allow-scripts']
    }
  }),

  // API only (no UI)
  api: new CSPBuilder({
    directives: {
      'default-src': ["'none'"],
      'frame-ancestors': ["'none'"]
    }
  }),

  // Single Page Application
  spa: new CSPBuilder({
    directives: {
      'default-src': ["'self'"],
      'script-src': ["'self'", "'strict-dynamic'"],
      'style-src': ["'self'", "'unsafe-inline'"],
      'img-src': ["'self'", 'data:', 'https:'],
      'connect-src': ["'self'"],
      'font-src': ["'self'"],
      'object-src': ["'none'"],
      'media-src': ["'self'"],
      'frame-src': ["'none'"],
      'base-uri': ["'self'"],
      'form-action': ["'self'"],
      'frame-ancestors': ["'none'"],
      'manifest-src': ["'self'"],
      'worker-src': ["'self'"]
    }
  })
};

/**
 * CSP utilities
 */
export class CSPUtils {
  /**
   * Parse CSP string to configuration
   */
  static parse(cspString: string): CSPConfig {
    const config: CSPConfig = { directives: {} };

    const directives = cspString.split(';').map(d => d.trim());

    for (const directive of directives) {
      const parts = directive.split(' ');
      const directiveName = parts[0] as CSPDirective;

      if (directiveName === 'upgrade-insecure-requests') {
        config.upgradeInsecureRequests = true;
      } else if (directiveName === 'block-all-mixed-content') {
        config.blockAllMixedContent = true;
      } else if (directiveName === 'report-uri') {
        config.reportUri = parts[1];
      } else if (directiveName === 'report-to') {
        config.reportTo = parts[1];
      } else if (parts.length > 1) {
        config.directives[directiveName] = parts.slice(1) as CSPSource[];
      }
    }

    return config;
  }

  /**
   * Merge multiple CSP configurations
   */
  static merge(...configs: CSPConfig[]): CSPConfig {
    const merged: CSPConfig = { directives: {} };

    for (const config of configs) {
      // Merge boolean flags
      merged.reportOnly = config.reportOnly || merged.reportOnly;
      merged.useNonce = config.useNonce ?? merged.useNonce;
      merged.useHash = config.useHash ?? merged.useHash;
      merged.upgradeInsecureRequests = config.upgradeInsecureRequests ?? merged.upgradeInsecureRequests;
      merged.blockAllMixedContent = config.blockAllMixedContent ?? merged.blockAllMixedContent;

      // Merge strings
      merged.reportUri = config.reportUri || merged.reportUri;
      merged.reportTo = config.reportTo || merged.reportTo;

      // Merge directives
      for (const [directive, sources] of Object.entries(config.directives)) {
        if (!merged.directives[directive as CSPDirective]) {
          merged.directives[directive as CSPDirective] = [];
        }

        const mergedSources = merged.directives[directive as CSPDirective]!;
        for (const source of sources || []) {
          if (!mergedSources.includes(source)) {
            mergedSources.push(source);
          }
        }
      }
    }

    return merged;
  }

  /**
   * Validate CSP configuration
   */
  static validate(config: CSPConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check for dangerous combinations
    if (config.directives['script-src']?.includes("'unsafe-inline'") &&
        config.directives['script-src']?.includes("'unsafe-eval'")) {
      errors.push("Using both 'unsafe-inline' and 'unsafe-eval' is highly insecure");
    }

    // Check for missing important directives
    if (!config.directives['default-src']) {
      errors.push("Missing 'default-src' directive");
    }

    // Check for overly permissive policies
    if (config.directives['default-src']?.includes("*")) {
      errors.push("Using wildcard (*) in default-src is not recommended");
    }

    // Validate report-uri format
    if (config.reportUri && !config.reportUri.startsWith('/') && !config.reportUri.startsWith('http')) {
      errors.push("Invalid report-uri format");
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Generate inline script hash
   */
  static generateScriptHash(script: string): string {
    return `'sha256-${createHash('sha256').update(script).digest('base64')}'`;
  }

  /**
   * Generate inline style hash
   */
  static generateStyleHash(style: string): string {
    return `'sha256-${createHash('sha256').update(style).digest('base64')}'`;
  }
}

// Export convenience functions
export const createCSP = (config?: CSPConfig) => new CSPBuilder(config);
export const parseCSP = CSPUtils.parse;
export const mergeCSP = CSPUtils.merge;
export const validateCSP = CSPUtils.validate;
