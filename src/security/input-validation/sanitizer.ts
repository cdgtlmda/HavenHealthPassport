/**
 * Input Sanitizer
 * Core sanitization functionality for all input types
 */

import DOMPurify from 'isomorphic-dompurify';
import validator from 'validator';
import { createHash } from 'crypto';

/**
 * Sanitization options for different contexts
 */
export interface SanitizationOptions {
  allowHTML?: boolean;
  allowedTags?: string[];
  allowedAttributes?: Record<string, string[]>;
  stripScripts?: boolean;
  stripStyles?: boolean;
  stripComments?: boolean;
  maxLength?: number;
  encoding?: string;
  trimWhitespace?: boolean;
  normalizeWhitespace?: boolean;
  toLowerCase?: boolean;
  toUpperCase?: boolean;
}

/**
 * Input sanitizer class
 */
export class InputSanitizer {
  private static readonly DEFAULT_OPTIONS: SanitizationOptions = {
    allowHTML: false,
    stripScripts: true,
    stripStyles: true,
    stripComments: true,
    trimWhitespace: true,
    normalizeWhitespace: true,
    encoding: 'utf-8'
  };

  // Dangerous patterns that should always be removed
  private static readonly DANGEROUS_PATTERNS = [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript:/gi,
    /on\w+\s*=/gi,
    /<iframe/gi,
    /<embed/gi,
    /<object/gi,
    /eval\(/gi,
    /expression\(/gi,
    /vbscript:/gi,
    /onclick/gi,
    /onerror/gi,
    /onload/gi,
    /&#x/gi,
    /&#0/gi
  ];

  /**
   * Sanitize string input
   */
  static sanitizeString(
    input: string,
    options: SanitizationOptions = {}
  ): string {
    const opts = { ...this.DEFAULT_OPTIONS, ...options };
    let sanitized = input;

    // Basic string sanitization
    if (opts.trimWhitespace) {
      sanitized = sanitized.trim();
    }

    if (opts.normalizeWhitespace) {
      sanitized = sanitized.replace(/\s+/g, ' ');
    }

    if (opts.toLowerCase) {
      sanitized = sanitized.toLowerCase();
    } else if (opts.toUpperCase) {
      sanitized = sanitized.toUpperCase();
    }

    // Remove dangerous patterns
    for (const pattern of this.DANGEROUS_PATTERNS) {
      sanitized = sanitized.replace(pattern, '');
    }

    // HTML sanitization
    if (opts.allowHTML) {
      const purifyConfig: any = {
        ALLOWED_TAGS: opts.allowedTags || [],
        ALLOWED_ATTR: opts.allowedAttributes || {},
        FORBID_TAGS: opts.stripScripts ? ['script', 'style'] : [],
        FORBID_ATTR: ['onerror', 'onload', 'onclick'],
        KEEP_CONTENT: true,
        SANITIZE_DOM: true
      };
      sanitized = DOMPurify.sanitize(sanitized, purifyConfig);
    } else {
      // Strip all HTML if not allowed
      sanitized = this.stripHTML(sanitized);
    }

    // Length validation
    if (opts.maxLength && sanitized.length > opts.maxLength) {
      sanitized = sanitized.substring(0, opts.maxLength);
    }

    // Encoding normalization
    sanitized = this.normalizeEncoding(sanitized, opts.encoding);

    return sanitized;
  }

  /**
   * Sanitize email input
   */
  static sanitizeEmail(email: string): string {
    let sanitized = email.toLowerCase().trim();

    // Remove any HTML or script tags
    sanitized = this.stripHTML(sanitized);

    // Normalize email
    sanitized = validator.normalizeEmail(sanitized, {
      all_lowercase: true,
      gmail_remove_dots: true,
      gmail_remove_subaddress: false,
      gmail_convert_googlemaildotcom: true,
      outlookdotcom_remove_subaddress: false,
      yahoo_remove_subaddress: false,
      icloud_remove_subaddress: false
    }) || '';

    // Additional email-specific sanitization
    sanitized = sanitized.replace(/[<>]/g, '');

    return sanitized;
  }

  /**
   * Sanitize phone number
   */
  static sanitizePhoneNumber(phone: string, locale: string = 'en-US'): string {
    // Remove all non-numeric characters except + for international
    let sanitized = phone.replace(/[^\d+]/g, '');

    // Ensure it starts with + for international or is a valid length
    if (sanitized.startsWith('+')) {
      // International format
      if (sanitized.length < 8 || sanitized.length > 15) {
        throw new Error('Invalid phone number length');
      }
    } else {
      // Assume local format, add country code if needed
      // This would be customized based on locale
      if (locale === 'en-US' && sanitized.length === 10) {
        sanitized = '+1' + sanitized;
      }
    }

    return sanitized;
  }

  /**
   * Sanitize URL
   */
  static sanitizeURL(url: string): string {
    let sanitized = url.trim();

    // Remove any potentially dangerous protocols
    const dangerousProtocols = [
      'javascript:',
      'data:',
      'vbscript:',
      'file:',
      'about:'
    ];

    for (const protocol of dangerousProtocols) {
      if (sanitized.toLowerCase().startsWith(protocol)) {
        return '';
      }
    }

    // Ensure URL encoding for special characters
    try {
      const urlObj = new URL(sanitized);

      // Only allow http, https, and ftp protocols
      if (!['http:', 'https:', 'ftp:'].includes(urlObj.protocol)) {
        return '';
      }

      // Encode the URL properly
      sanitized = urlObj.toString();
    } catch (e) {
      // If not a valid URL, return empty
      return '';
    }

    return sanitized;
  }

  /**
   * Sanitize JSON input
   */
  static sanitizeJSON(jsonString: string): object | null {
    try {
      // First, basic string sanitization
      let sanitized = jsonString.trim();

      // Remove any BOM characters
      sanitized = sanitized.replace(/^\uFEFF/, '');

      // Parse JSON
      const parsed = JSON.parse(sanitized);

      // Recursively sanitize all string values in the object
      return this.sanitizeObject(parsed);
    } catch (e) {
      return null;
    }
  }

  /**
   * Sanitize object recursively
   */
  static sanitizeObject(obj: any): any {
    if (obj === null || obj === undefined) {
      return obj;
    }

    if (typeof obj === 'string') {
      return this.sanitizeString(obj);
    }

    if (Array.isArray(obj)) {
      return obj.map(item => this.sanitizeObject(item));
    }

    if (typeof obj === 'object') {
      const sanitized: any = {};
      for (const [key, value] of Object.entries(obj)) {
        // Sanitize the key as well
        const sanitizedKey = this.sanitizeString(key, {
          allowHTML: false,
          maxLength: 255
        });
        sanitized[sanitizedKey] = this.sanitizeObject(value);
      }
      return sanitized;
    }

    return obj;
  }

  /**
   * Sanitize SQL input (parameterized queries should be used instead)
   */
  static sanitizeSQL(input: string): string {
    // This is a backup - always use parameterized queries!
    let sanitized = input;

    // Escape single quotes
    sanitized = sanitized.replace(/'/g, "''");

    // Remove SQL comment markers
    sanitized = sanitized.replace(/--/g, '');
    sanitized = sanitized.replace(/\/\*/g, '');
    sanitized = sanitized.replace(/\*\//g, '');

    // Remove common SQL injection patterns
    const sqlPatterns = [
      /union\s+select/gi,
      /drop\s+table/gi,
      /insert\s+into/gi,
      /delete\s+from/gi,
      /update\s+set/gi,
      /exec(\s|\()/gi,
      /execute(\s|\()/gi,
      /xp_cmdshell/gi,
      /sp_executesql/gi
    ];

    for (const pattern of sqlPatterns) {
      sanitized = sanitized.replace(pattern, '');
    }

    return sanitized;
  }

  /**
   * Sanitize filename
   */
  static sanitizeFilename(filename: string): string {
    // Remove path traversal attempts
    let sanitized = filename.replace(/\.\./g, '');
    sanitized = sanitized.replace(/[\/\\]/g, '');

    // Remove special characters that could be problematic
    sanitized = sanitized.replace(/[<>:"|?*\x00-\x1f]/g, '');

    // Limit length
    const maxLength = 255;
    if (sanitized.length > maxLength) {
      const extension = sanitized.substring(sanitized.lastIndexOf('.'));
      const nameWithoutExt = sanitized.substring(0, sanitized.lastIndexOf('.'));
      sanitized = nameWithoutExt.substring(0, maxLength - extension.length) + extension;
    }

    // Ensure it doesn't start with a dot (hidden file)
    if (sanitized.startsWith('.')) {
      sanitized = sanitized.substring(1);
    }

    // If empty after sanitization, provide a default
    if (!sanitized) {
      sanitized = 'unnamed_file';
    }

    return sanitized;
  }

  /**
   * Sanitize command line arguments
   */
  static sanitizeCommandArg(arg: string): string {
    // Remove shell metacharacters
    const shellMetacharacters = /[;&|`$<>\\!"'(){}\[\]#~*?]/g;
    let sanitized = arg.replace(shellMetacharacters, '');

    // Remove newlines and carriage returns
    sanitized = sanitized.replace(/[\r\n]/g, '');

    // Limit length
    const maxLength = 1000;
    if (sanitized.length > maxLength) {
      sanitized = sanitized.substring(0, maxLength);
    }

    return sanitized;
  }

  /**
   * Sanitize NoSQL query input
   */
  static sanitizeNoSQL(input: any): any {
    if (typeof input === 'string') {
      // Remove MongoDB operators
      const mongoOperators = /\$\w+/g;
      return input.replace(mongoOperators, '');
    }

    if (typeof input === 'object' && input !== null) {
      const sanitized: any = Array.isArray(input) ? [] : {};

      for (const [key, value] of Object.entries(input)) {
        // Skip keys that start with $
        if (typeof key === 'string' && key.startsWith('$')) {
          continue;
        }

        if (Array.isArray(input)) {
          sanitized.push(this.sanitizeNoSQL(value));
        } else {
          sanitized[key] = this.sanitizeNoSQL(value);
        }
      }

      return sanitized;
    }

    return input;
  }

  /**
   * Sanitize medical record number (MRN)
   */
  static sanitizeMRN(mrn: string): string {
    // Remove any non-alphanumeric characters
    let sanitized = mrn.replace(/[^a-zA-Z0-9]/g, '');

    // Convert to uppercase for consistency
    sanitized = sanitized.toUpperCase();

    // Limit length (typical MRN length)
    const maxLength = 20;
    if (sanitized.length > maxLength) {
      sanitized = sanitized.substring(0, maxLength);
    }

    return sanitized;
  }

  /**
   * Sanitize FHIR resource ID
   */
  static sanitizeFHIRId(id: string): string {
    // FHIR IDs must match [A-Za-z0-9\-\.]{1,64}
    let sanitized = id.replace(/[^A-Za-z0-9\-\.]/g, '');

    // Limit to 64 characters
    if (sanitized.length > 64) {
      sanitized = sanitized.substring(0, 64);
    }

    // Cannot start or end with dash or period
    sanitized = sanitized.replace(/^[\-\.]/, '').replace(/[\-\.]$/, '');

    return sanitized;
  }

  /**
   * Strip HTML from string
   */
  private static stripHTML(html: string): string {
    // Use DOMPurify with no allowed tags
    return DOMPurify.sanitize(html, { ALLOWED_TAGS: [] });
  }

  /**
   * Normalize encoding
   */
  private static normalizeEncoding(input: string, encoding?: string): string {
    try {
      // Convert to buffer and back to ensure proper encoding
      const buffer = Buffer.from(input, encoding as BufferEncoding || 'utf-8');
      return buffer.toString('utf-8');
    } catch (e) {
      // If encoding fails, return original
      return input;
    }
  }

  /**
   * Create content hash for integrity checking
   */
  static createContentHash(content: string): string {
    return createHash('sha256').update(content).digest('hex');
  }

  /**
   * Verify content integrity
   */
  static verifyContentIntegrity(content: string, hash: string): boolean {
    const currentHash = this.createContentHash(content);
    return currentHash === hash;
  }
}

/**
 * Context-specific sanitizers
 */
export class ContextualSanitizer {
  /**
   * Sanitize healthcare-specific inputs
   */
  static sanitizeHealthcareInput(input: string, type: 'diagnosis' | 'medication' | 'procedure'): string {
    let sanitized = InputSanitizer.sanitizeString(input, {
      allowHTML: false,
      maxLength: type === 'diagnosis' ? 500 : 255,
      trimWhitespace: true
    });

    // Remove any numeric codes that might be injection attempts
    if (type === 'diagnosis') {
      // Preserve ICD codes but remove SQL-like patterns
      sanitized = sanitized.replace(/(\b(?!ICD|CPT)[A-Z]{2,}\d+)/gi, '');
    }

    return sanitized;
  }

  /**
   * Sanitize patient name
   */
  static sanitizePatientName(name: string): string {
    return InputSanitizer.sanitizeString(name, {
      allowHTML: false,
      maxLength: 100,
      trimWhitespace: true,
      // Allow letters, spaces, hyphens, and apostrophes
    }).replace(/[^a-zA-Z\s\-']/g, '');
  }

  /**
   * Sanitize address
   */
  static sanitizeAddress(address: string): string {
    return InputSanitizer.sanitizeString(address, {
      allowHTML: false,
      maxLength: 500,
      trimWhitespace: true
    }).replace(/[<>]/g, '');
  }
}

// Export convenience functions
export const sanitize = InputSanitizer.sanitizeString.bind(InputSanitizer);
export const sanitizeEmail = InputSanitizer.sanitizeEmail.bind(InputSanitizer);
export const sanitizeURL = InputSanitizer.sanitizeURL.bind(InputSanitizer);
export const sanitizeJSON = InputSanitizer.sanitizeJSON.bind(InputSanitizer);
export const sanitizeFilename = InputSanitizer.sanitizeFilename.bind(InputSanitizer);
export const sanitizeMRN = InputSanitizer.sanitizeMRN.bind(InputSanitizer);
export const sanitizeFHIRId = InputSanitizer.sanitizeFHIRId.bind(InputSanitizer);
