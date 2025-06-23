/**
 * Security Headers Implementation
 * Core security headers configuration and middleware
 */

import { Request, Response, NextFunction } from 'express';
import { CSPBuilder, CSPConfig } from './csp-implementation';

/**
 * Security headers configuration
 */
export interface SecurityHeadersConfig {
  // CSP configuration
  csp?: CSPConfig | false;

  // Frame options
  frameOptions?: 'DENY' | 'SAMEORIGIN' | { allow: string } | false;

  // Content type options
  contentTypeOptions?: 'nosniff' | false;

  // XSS protection
  xssProtection?: '0' | '1' | '1; mode=block' | false;

  // HSTS configuration
  hsts?: {
    maxAge: number;
    includeSubDomains?: boolean;
    preload?: boolean;
  } | false;

  // Referrer policy
  referrerPolicy?:
    | 'no-referrer'
    | 'no-referrer-when-downgrade'
    | 'origin'
    | 'origin-when-cross-origin'
    | 'same-origin'
    | 'strict-origin'
    | 'strict-origin-when-cross-origin'
    | 'unsafe-url'
    | false;

  // Feature policy / Permissions policy
  permissionsPolicy?: {
    [feature: string]: string[];
  } | false;

  // Cross-origin policies
  crossOriginOpenerPolicy?: 'unsafe-none' | 'same-origin-allow-popups' | 'same-origin' | false;
  crossOriginEmbedderPolicy?: 'unsafe-none' | 'require-corp' | false;
  crossOriginResourcePolicy?: 'same-site' | 'same-origin' | 'cross-origin' | false;

  // Additional headers
  customHeaders?: Record<string, string>;

  // Remove headers
  removeHeaders?: string[];

  // Report endpoints
  reportingEndpoints?: {
    [name: string]: string;
  };
}

/**
 * Security headers middleware
 */
export class SecurityHeaders {
  private config: SecurityHeadersConfig;
  private cspBuilder?: CSPBuilder;

  constructor(config: SecurityHeadersConfig = {}) {
    this.config = {
      // Secure defaults
      frameOptions: 'DENY',
      contentTypeOptions: 'nosniff',
      xssProtection: '1; mode=block',
      hsts: {
        maxAge: 31536000, // 1 year
        includeSubDomains: true,
        preload: true
      },
      referrerPolicy: 'strict-origin-when-cross-origin',
      crossOriginOpenerPolicy: 'same-origin',
      crossOriginEmbedderPolicy: 'require-corp',
      crossOriginResourcePolicy: 'same-origin',
      ...config
    };

    // Initialize CSP if not disabled
    if (this.config.csp !== false) {
      this.cspBuilder = new CSPBuilder(this.config.csp);
    }
  }

  /**
   * Express middleware
   */
  middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      // Apply CSP
      if (this.cspBuilder) {
        const cspMiddleware = this.cspBuilder.middleware();
        cspMiddleware(req, res, () => {});
      }

      // X-Frame-Options
      if (this.config.frameOptions !== false) {
        if (typeof this.config.frameOptions === 'string') {
          res.setHeader('X-Frame-Options', this.config.frameOptions);
        } else if (this.config.frameOptions?.allow) {
          res.setHeader('X-Frame-Options', `ALLOW-FROM ${this.config.frameOptions.allow}`);
        }
      }

      // X-Content-Type-Options
      if (this.config.contentTypeOptions !== false) {
        res.setHeader('X-Content-Type-Options', this.config.contentTypeOptions!);
      }

      // X-XSS-Protection
      if (this.config.xssProtection !== false) {
        res.setHeader('X-XSS-Protection', this.config.xssProtection!);
      }

      // Strict-Transport-Security
      if (this.config.hsts !== false) {
        const hsts = this.config.hsts!;
        let value = `max-age=${hsts.maxAge}`;
        if (hsts.includeSubDomains) value += '; includeSubDomains';
        if (hsts.preload) value += '; preload';
        res.setHeader('Strict-Transport-Security', value);
      }

      // Referrer-Policy
      if (this.config.referrerPolicy !== false) {
        res.setHeader('Referrer-Policy', this.config.referrerPolicy!);
      }

      // Permissions-Policy (formerly Feature-Policy)
      if (this.config.permissionsPolicy !== false && this.config.permissionsPolicy) {
        const policies = Object.entries(this.config.permissionsPolicy)
          .map(([feature, allowList]) => `${feature}=(${allowList.join(' ')})`)
          .join(', ');
        res.setHeader('Permissions-Policy', policies);
      }

      // Cross-Origin-Opener-Policy
      if (this.config.crossOriginOpenerPolicy !== false) {
        res.setHeader('Cross-Origin-Opener-Policy', this.config.crossOriginOpenerPolicy!);
      }

      // Cross-Origin-Embedder-Policy
      if (this.config.crossOriginEmbedderPolicy !== false) {
        res.setHeader('Cross-Origin-Embedder-Policy', this.config.crossOriginEmbedderPolicy!);
      }

      // Cross-Origin-Resource-Policy
      if (this.config.crossOriginResourcePolicy !== false) {
        res.setHeader('Cross-Origin-Resource-Policy', this.config.crossOriginResourcePolicy!);
      }

      // Reporting-Endpoints
      if (this.config.reportingEndpoints) {
        const endpoints = Object.entries(this.config.reportingEndpoints)
          .map(([name, url]) => `${name}="${url}"`)
          .join(', ');
        res.setHeader('Reporting-Endpoints', endpoints);
      }

      // Custom headers
      if (this.config.customHeaders) {
        for (const [name, value] of Object.entries(this.config.customHeaders)) {
          res.setHeader(name, value);
        }
      }

      // Remove headers
      if (this.config.removeHeaders) {
        for (const header of this.config.removeHeaders) {
          res.removeHeader(header);
        }
      }

      next();
    };
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<SecurityHeadersConfig>): void {
    this.config = { ...this.config, ...config };

    // Update CSP if needed
    if (config.csp !== undefined) {
      if (config.csp === false) {
        this.cspBuilder = undefined;
      } else {
        this.cspBuilder = new CSPBuilder(config.csp);
      }
    }
  }

  /**
   * Get current configuration
   */
  getConfig(): SecurityHeadersConfig {
    return { ...this.config };
  }
}

/**
 * Healthcare-specific security headers configurations
 */
export const HealthcareSecurityHeaders = {
  // Patient portal configuration
  patientPortal: {
    frameOptions: 'DENY' as const,
    contentTypeOptions: 'nosniff' as const,
    xssProtection: '1; mode=block' as const,
    hsts: {
      maxAge: 63072000, // 2 years
      includeSubDomains: true,
      preload: true
    },
    referrerPolicy: 'strict-origin' as const,
    permissionsPolicy: {
      'geolocation': ["'none'"],
      'camera': ["'none'"],
      'microphone': ["'none'"],
      'payment': ["'self'"],
      'usb': ["'none'"],
      'accelerometer': ["'none'"],
      'gyroscope': ["'none'"],
      'magnetometer': ["'none'"],
      'interest-cohort': ["'none'"]
    },
    crossOriginOpenerPolicy: 'same-origin' as const,
    crossOriginEmbedderPolicy: 'require-corp' as const,
    crossOriginResourcePolicy: 'same-origin' as const
  },

  // Provider application
  providerApp: {
    frameOptions: 'SAMEORIGIN' as const, // Allow for embedded viewers
    contentTypeOptions: 'nosniff' as const,
    xssProtection: '1; mode=block' as const,
    hsts: {
      maxAge: 31536000,
      includeSubDomains: true,
      preload: false
    },
    referrerPolicy: 'strict-origin-when-cross-origin' as const,
    permissionsPolicy: {
      'geolocation': ["'self'"], // For emergency location
      'camera': ["'self'"], // For telehealth
      'microphone': ["'self'"], // For telehealth
      'payment': ["'none'"],
      'usb': ["'self'"], // For medical devices
      'serial': ["'self'"], // For medical devices
      'bluetooth': ["'self'"] // For medical devices
    },
    crossOriginOpenerPolicy: 'same-origin-allow-popups' as const,
    crossOriginEmbedderPolicy: 'unsafe-none' as const, // For compatibility
    crossOriginResourcePolicy: 'cross-origin' as const
  },

  // API endpoints
  api: {
    frameOptions: 'DENY' as const,
    contentTypeOptions: 'nosniff' as const,
    xssProtection: '0' as const, // Disable for API
    hsts: {
      maxAge: 31536000,
      includeSubDomains: true,
      preload: true
    },
    referrerPolicy: 'no-referrer' as const,
    permissionsPolicy: false,
    crossOriginResourcePolicy: 'cross-origin' as const,
    customHeaders: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, private',
      'Pragma': 'no-cache',
      'Expires': '0'
    }
  },

  // Development configuration
  development: {
    frameOptions: 'SAMEORIGIN' as const,
    contentTypeOptions: 'nosniff' as const,
    xssProtection: '1; mode=block' as const,
    hsts: false, // Disable in development
    referrerPolicy: 'no-referrer-when-downgrade' as const,
    permissionsPolicy: {
      'geolocation': ["*"],
      'camera': ["*"],
      'microphone': ["*"]
    },
    crossOriginOpenerPolicy: 'unsafe-none' as const,
    crossOriginEmbedderPolicy: 'unsafe-none' as const,
    crossOriginResourcePolicy: 'cross-origin' as const
  }
};

/**
 * Nonce generator for inline scripts/styles
 */
export class NonceGenerator {
  private static nonces: Map<string, string> = new Map();

  /**
   * Generate nonce for request
   */
  static generate(req: Request): string {
    const requestId = req.headers['x-request-id'] as string ||
                     `${Date.now()}-${Math.random()}`;

    if (!this.nonces.has(requestId)) {
      const nonce = CSPBuilder.prototype.generateNonce();
      this.nonces.set(requestId, nonce);

      // Clean up old nonces
      setTimeout(() => this.nonces.delete(requestId), 60000); // 1 minute
    }

    return this.nonces.get(requestId)!;
  }

  /**
   * Get nonce for request
   */
  static get(req: Request): string | undefined {
    const requestId = req.headers['x-request-id'] as string;
    return requestId ? this.nonces.get(requestId) : undefined;
  }

  /**
   * Express middleware
   */
  static middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      const nonce = NonceGenerator.generate(req);
      res.locals.nonce = nonce;
      next();
    };
  }
}

/**
 * Security headers validator
 */
export class SecurityHeadersValidator {
  /**
   * Validate security headers
   */
  static validate(headers: Record<string, string>): {
    score: number;
    missing: string[];
    insecure: string[];
    recommendations: string[];
  } {
    let score = 100;
    const missing: string[] = [];
    const insecure: string[] = [];
    const recommendations: string[] = [];

    // Check for required headers
    const requiredHeaders = [
      'X-Content-Type-Options',
      'X-Frame-Options',
      'X-XSS-Protection',
      'Strict-Transport-Security',
      'Content-Security-Policy'
    ];

    for (const header of requiredHeaders) {
      if (!headers[header.toLowerCase()]) {
        missing.push(header);
        score -= 10;
      }
    }

    // Check for insecure values
    if (headers['x-frame-options'] === 'ALLOWALL') {
      insecure.push('X-Frame-Options: ALLOWALL is insecure');
      score -= 20;
    }

    if (headers['content-security-policy']?.includes("'unsafe-inline'") &&
        headers['content-security-policy']?.includes("'unsafe-eval'")) {
      insecure.push("CSP with both 'unsafe-inline' and 'unsafe-eval' is very insecure");
      score -= 30;
    }

    // Recommendations
    if (!headers['referrer-policy']) {
      recommendations.push('Consider adding Referrer-Policy header');
      score -= 5;
    }

    if (!headers['permissions-policy'] && !headers['feature-policy']) {
      recommendations.push('Consider adding Permissions-Policy header');
      score -= 5;
    }

    if (!headers['cross-origin-opener-policy']) {
      recommendations.push('Consider adding Cross-Origin-Opener-Policy header');
      score -= 5;
    }

    return {
      score: Math.max(0, score),
      missing,
      insecure,
      recommendations
    };
  }

  /**
   * Generate security report
   */
  static generateReport(headers: Record<string, string>): string {
    const validation = this.validate(headers);

    let report = `Security Headers Report\n`;
    report += `Score: ${validation.score}/100\n\n`;

    if (validation.missing.length > 0) {
      report += `Missing Headers:\n`;
      validation.missing.forEach(h => report += `  - ${h}\n`);
      report += '\n';
    }

    if (validation.insecure.length > 0) {
      report += `Security Issues:\n`;
      validation.insecure.forEach(i => report += `  - ${i}\n`);
      report += '\n';
    }

    if (validation.recommendations.length > 0) {
      report += `Recommendations:\n`;
      validation.recommendations.forEach(r => report += `  - ${r}\n`);
    }

    return report;
  }
}

/**
 * Security headers presets
 */
export const SecurityHeadersPresets = {
  // Maximum security
  strict: new SecurityHeaders({
    frameOptions: 'DENY',
    contentTypeOptions: 'nosniff',
    xssProtection: '1; mode=block',
    hsts: {
      maxAge: 63072000,
      includeSubDomains: true,
      preload: true
    },
    referrerPolicy: 'no-referrer',
    permissionsPolicy: {
      'geolocation': ["'none'"],
      'camera': ["'none'"],
      'microphone': ["'none'"],
      'payment': ["'none'"],
      'usb': ["'none'"]
    },
    crossOriginOpenerPolicy: 'same-origin',
    crossOriginEmbedderPolicy: 'require-corp',
    crossOriginResourcePolicy: 'same-origin'
  }),

  // Balanced security
  balanced: new SecurityHeaders({
    frameOptions: 'SAMEORIGIN',
    contentTypeOptions: 'nosniff',
    xssProtection: '1; mode=block',
    hsts: {
      maxAge: 31536000,
      includeSubDomains: true
    },
    referrerPolicy: 'strict-origin-when-cross-origin',
    crossOriginOpenerPolicy: 'same-origin-allow-popups'
  }),

  // API security
  api: new SecurityHeaders({
    frameOptions: 'DENY',
    contentTypeOptions: 'nosniff',
    xssProtection: '0',
    hsts: {
      maxAge: 31536000,
      includeSubDomains: true,
      preload: true
    },
    referrerPolicy: 'no-referrer',
    customHeaders: {
      'Cache-Control': 'no-store',
      'Pragma': 'no-cache'
    }
  })
};

// Export convenience functions
export const createSecurityHeaders = (config?: SecurityHeadersConfig) => new SecurityHeaders(config);
export const validateHeaders = SecurityHeadersValidator.validate;
export const generateSecurityReport = SecurityHeadersValidator.generateReport;
