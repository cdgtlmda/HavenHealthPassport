/**
 * Security.txt Implementation
 * RFC 9116 compliant security.txt file generation
 */

import { Request, Response } from 'express';
import { createHash } from 'crypto';

/**
 * Security.txt configuration
 */
export interface SecurityTxtConfig {
  contact: string | string[];
  expires?: Date;
  encryption?: string | string[];
  acknowledgments?: string;
  preferredLanguages?: string | string[];
  canonical?: string | string[];
  policy?: string;
  hiring?: string;
  csaf?: string;
}

/**
 * Security.txt generator
 */
export class SecurityTxtGenerator {
  private config: SecurityTxtConfig;

  constructor(config: SecurityTxtConfig) {
    this.config = config;
  }

  /**
   * Generate security.txt content
   */
  generate(): string {
    const lines: string[] = [];

    // Add required contact field
    if (Array.isArray(this.config.contact)) {
      this.config.contact.forEach(contact => {
        lines.push(`Contact: ${contact}`);
      });
    } else {
      lines.push(`Contact: ${this.config.contact}`);
    }

    // Add expires field (recommended)
    if (this.config.expires) {
      lines.push(`Expires: ${this.config.expires.toISOString()}`);
    } else {
      // Default to 1 year from now
      const expires = new Date();
      expires.setFullYear(expires.getFullYear() + 1);
      lines.push(`Expires: ${expires.toISOString()}`);
    }

    // Add optional fields
    if (this.config.encryption) {
      if (Array.isArray(this.config.encryption)) {
        this.config.encryption.forEach(key => {
          lines.push(`Encryption: ${key}`);
        });
      } else {
        lines.push(`Encryption: ${this.config.encryption}`);
      }
    }

    if (this.config.acknowledgments) {
      lines.push(`Acknowledgments: ${this.config.acknowledgments}`);
    }

    if (this.config.preferredLanguages) {
      const languages = Array.isArray(this.config.preferredLanguages)
        ? this.config.preferredLanguages.join(', ')
        : this.config.preferredLanguages;
      lines.push(`Preferred-Languages: ${languages}`);
    }

    if (this.config.canonical) {
      if (Array.isArray(this.config.canonical)) {
        this.config.canonical.forEach(url => {
          lines.push(`Canonical: ${url}`);
        });
      } else {
        lines.push(`Canonical: ${this.config.canonical}`);
      }
    }

    if (this.config.policy) {
      lines.push(`Policy: ${this.config.policy}`);
    }

    if (this.config.hiring) {
      lines.push(`Hiring: ${this.config.hiring}`);
    }

    if (this.config.csaf) {
      lines.push(`CSAF: ${this.config.csaf}`);
    }

    return lines.join('\n') + '\n';
  }

  /**
   * Generate signed security.txt
   */
  generateSigned(privateKey: string): string {
    const content = this.generate();
    // In production, use proper PGP signing
    // This is a placeholder for demonstration
    const signature = createHash('sha256').update(content).digest('hex');
    return content + '\n' + `# Signature: ${signature}\n`;
  }

  /**
   * Express middleware
   */
  middleware() {
    const content = this.generate();

    return (req: Request, res: Response) => {
      res.type('text/plain');
      res.setHeader('Cache-Control', 'max-age=86400'); // 24 hours
      res.send(content);
    };
  }
}

/**
 * Healthcare-specific security.txt configurations
 */
export const HealthcareSecurityTxt = {
  // Standard configuration
  standard: {
    contact: [
      'mailto:security@havenhealth.com',
      'https://havenhealth.com/security/report'
    ],
    encryption: 'https://havenhealth.com/.well-known/pgp-key.txt',
    acknowledgments: 'https://havenhealth.com/security/acknowledgments',
    preferredLanguages: 'en, es, fr',
    canonical: 'https://havenhealth.com/.well-known/security.txt',
    policy: 'https://havenhealth.com/security/policy',
    hiring: 'https://havenhealth.com/careers/security'
  },

  // Minimal configuration
  minimal: {
    contact: 'mailto:security@havenhealth.com'
  }
};

// Export convenience function
export const createSecurityTxt = (config: SecurityTxtConfig) => new SecurityTxtGenerator(config);
