/**
 * Regex Validation Patterns
 * Comprehensive regex patterns for input validation
 */

/**
 * Healthcare-specific regex patterns
 */
export const HealthcarePatterns = {
  // Medical Record Number (MRN) - alphanumeric, 6-20 characters
  mrn: /^[A-Z0-9]{6,20}$/,

  // National Provider Identifier (NPI) - 10 digits
  npi: /^[1-9]\d{9}$/,

  // Drug Enforcement Administration (DEA) number
  dea: /^[A-Z]{2}\d{7}$/,

  // Social Security Number (SSN) - with or without dashes
  ssn: /^(?:\d{3}-\d{2}-\d{4}|\d{9})$/,

  // Medicare Beneficiary Identifier (MBI)
  mbi: /^[1-9][A-Z][A-Z0-9]\d[A-Z][A-Z0-9]\d[A-Z]{2}\d{2}$/,

  // ICD-10 diagnosis code
  icd10: /^[A-Z]\d{2}(?:\.\d{1,4})?$/,

  // CPT procedure code
  cpt: /^(?:\d{5}|[A-Z]\d{4})$/,

  // LOINC lab code
  loinc: /^\d{1,5}-\d$/,

  // RxNorm medication code
  rxnorm: /^\d{1,7}$/,

  // SNOMED CT code
  snomed: /^\d{6,18}$/,

  // NDC drug code (10 or 11 digits in 3 segments)
  ndc: /^(?:\d{4,5}-\d{3,4}-\d{1,2}|\d{5}-\d{4}-\d{2})$/,

  // Blood pressure reading
  bloodPressure: /^[1-9]\d{1,2}\/[1-9]\d{1,2}$/,

  // Heart rate (30-300 bpm)
  heartRate: /^(?:3[0-9]|[4-9]\d|[1-2]\d{2}|300)$/,

  // Temperature (Fahrenheit, 90.0-110.0)
  temperatureF: /^(?:9[0-9](?:\.\d)?|10[0-9](?:\.\d)?|110(?:\.0)?)$/,

  // Temperature (Celsius, 32.0-43.0)
  temperatureC: /^(?:3[2-9](?:\.\d)?|4[0-3](?:\.\d)?)$/,

  // Dosage (number with optional decimal and unit)
  dosage: /^\d+(?:\.\d{1,3})?\s*(?:mg|mcg|g|ml|l|unit|iu|mEq)$/i,

  // Medical license number (state-specific, general pattern)
  medicalLicense: /^[A-Z]{2}\d{4,10}$/,

  // Insurance policy number
  insurancePolicy: /^[A-Z0-9]{6,20}$/,

  // Insurance group number
  insuranceGroup: /^[A-Z0-9]{4,15}$/
};

/**
 * Personal information patterns
 */
export const PersonalInfoPatterns = {
  // Name (letters, spaces, hyphens, apostrophes)
  name: /^[a-zA-Z][a-zA-Z\s\-']{0,99}$/,

  // Email address (RFC 5322 simplified)
  email: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,

  // US phone number
  phoneUS: /^(?:\+1\s?)?\(?[2-9]\d{2}\)?[\s.-]?[2-9]\d{2}[\s.-]?\d{4}$/,

  // International phone number
  phoneIntl: /^\+[1-9]\d{1,3}\s?\d{4,14}$/,

  // US ZIP code (5 or 9 digits)
  zipUS: /^\d{5}(?:-\d{4})?$/,

  // Canadian postal code
  postalCA: /^[A-Z]\d[A-Z]\s?\d[A-Z]\d$/i,

  // UK postcode
  postcodeUK: /^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i,

  // Date of birth (YYYY-MM-DD)
  dateOfBirth: /^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/,

  // Age (0-150)
  age: /^(?:[1-9]?\d|1[0-4]\d|150)$/,

  // Street address
  streetAddress: /^[a-zA-Z0-9\s,.\-#']{3,100}$/,

  // City name
  city: /^[a-zA-Z][a-zA-Z\s\-']{1,50}$/,

  // State/Province code (2 letters)
  stateCode: /^[A-Z]{2}$/,

  // Country code (ISO 3166-1 alpha-2)
  countryCode: /^[A-Z]{2}$/
};

/**
 * Security and authentication patterns
 */
export const SecurityPatterns = {
  // Strong password (min 8 chars, uppercase, lowercase, number, special)
  strongPassword: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/,

  // Medium password (min 8 chars, mixed case and numbers)
  mediumPassword: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/,

  // PIN (4-8 digits)
  pin: /^\d{4,8}$/,

  // TOTP code (6 digits)
  totpCode: /^\d{6}$/,

  // UUID v4
  uuid: /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,

  // JWT token
  jwt: /^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$/,

  // API key (alphanumeric with hyphens, 32-64 chars)
  apiKey: /^[A-Za-z0-9\-_]{32,64}$/,

  // Session ID
  sessionId: /^[A-Za-z0-9]{16,64}$/,

  // CSRF token
  csrfToken: /^[A-Za-z0-9+/]{32,}={0,2}$/,

  // Base64 encoded string
  base64: /^[A-Za-z0-9+/]+=*$/,

  // Hex color code
  hexColor: /^#?[0-9A-Fa-f]{6}$/,

  // IP address (v4)
  ipv4: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,

  // IP address (v6)
  ipv6: /^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/
};

/**
 * File and data patterns
 */
export const FilePatterns = {
  // Filename (no path traversal)
  filename: /^[a-zA-Z0-9][a-zA-Z0-9\s._\-()]{0,254}$/,

  // File extension
  fileExtension: /^\.[a-zA-Z0-9]{1,10}$/,

  // MIME type
  mimeType: /^[a-zA-Z0-9][a-zA-Z0-9\/+.\-]{0,99}$/,

  // URL (simplified)
  url: /^https?:\/\/[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=]+$/,

  // Relative path (no .. allowed)
  relativePath: /^(?!.*\.\.)(?!\/)[a-zA-Z0-9\/_\-\.]+$/,

  // JSON property name
  jsonProperty: /^[a-zA-Z_$][a-zA-Z0-9_$]*$/,

  // XML tag name
  xmlTag: /^[a-zA-Z_:][a-zA-Z0-9_:\-.]*$/,

  // CSV header
  csvHeader: /^[a-zA-Z][a-zA-Z0-9_\s]{0,50}$/
};

/**
 * Time and date patterns
 */
export const DateTimePatterns = {
  // ISO 8601 date
  isoDate: /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/,

  // ISO 8601 datetime
  isoDateTime: /^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{3})?Z?$/,

  // Time (24-hour format)
  time24: /^(?:[01]\d|2[0-3]):[0-5]\d$/,

  // Time (12-hour format with AM/PM)
  time12: /^(?:0?[1-9]|1[0-2]):[0-5]\d\s?[AP]M$/i,

  // Month (01-12)
  month: /^(?:0[1-9]|1[0-2])$/,

  // Day of month (01-31)
  dayOfMonth: /^(?:0[1-9]|[12]\d|3[01])$/,

  // Year (1900-2099)
  year: /^(?:19|20)\d{2}$/,

  // Duration (ISO 8601)
  duration: /^P(?:\d+Y)?(?:\d+M)?(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$/,

  // Cron expression
  cron: /^(?:\*|(?:[0-9]|[1-5][0-9])|\*\/[0-9]+)\s+(?:\*|(?:[0-9]|[1-5][0-9])|\*\/[0-9]+)\s+(?:\*|(?:[0-9]|1[0-9]|2[0-3])|\*\/[0-9]+)\s+(?:\*|(?:[1-9]|[12][0-9]|3[01])|\*\/[0-9]+)\s+(?:\*|(?:[1-9]|1[0-2])|\*\/[0-9]+)\s+(?:\*|(?:[0-6])|\*\/[0-9]+)$/
};

/**
 * Financial patterns
 */
export const FinancialPatterns = {
  // Credit card number (basic Luhn check pattern)
  creditCard: /^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})$/,

  // CVV code
  cvv: /^\d{3,4}$/,

  // USD currency amount
  usdAmount: /^\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?$/,

  // Bank routing number (US)
  routingNumber: /^\d{9}$/,

  // Bank account number
  accountNumber: /^\d{4,17}$/,

  // IBAN
  iban: /^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$/,

  // SWIFT/BIC code
  swift: /^[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?$/
};

/**
 * Locale and internationalization patterns
 */
export const LocalePatterns = {
  // Language code (ISO 639-1)
  languageCode: /^[a-z]{2}$/,

  // Locale (language-country)
  locale: /^[a-z]{2}-[A-Z]{2}$/,

  // Currency code (ISO 4217)
  currencyCode: /^[A-Z]{3}$/,

  // Timezone (IANA format simplified)
  timezone: /^[A-Z][a-zA-Z_]+\/[A-Z][a-zA-Z_]+$/
};

/**
 * Regex validator class
 */
export class RegexValidator {
  /**
   * Validate input against pattern
   */
  static validate(input: string, pattern: RegExp): boolean {
    return pattern.test(input);
  }

  /**
   * Validate with custom error message
   */
  static validateWithError(
    input: string,
    pattern: RegExp,
    errorMessage: string
  ): { valid: boolean; error?: string } {
    const valid = pattern.test(input);
    return valid ? { valid } : { valid, error: errorMessage };
  }

  /**
   * Validate multiple patterns
   */
  static validateMultiple(
    input: string,
    patterns: Array<{ pattern: RegExp; name: string }>
  ): { valid: boolean; passed: string[]; failed: string[] } {
    const passed: string[] = [];
    const failed: string[] = [];

    for (const { pattern, name } of patterns) {
      if (pattern.test(input)) {
        passed.push(name);
      } else {
        failed.push(name);
      }
    }

    return {
      valid: failed.length === 0,
      passed,
      failed
    };
  }

  /**
   * Extract matches from input
   */
  static extractMatches(input: string, pattern: RegExp): string[] {
    const matches = input.match(new RegExp(pattern, 'g'));
    return matches || [];
  }

  /**
   * Replace based on pattern
   */
  static sanitizeByPattern(
    input: string,
    pattern: RegExp,
    replacement: string = ''
  ): string {
    return input.replace(new RegExp(pattern, 'g'), replacement);
  }

  /**
   * Check password strength
   */
  static checkPasswordStrength(password: string): {
    score: number;
    strength: 'weak' | 'medium' | 'strong';
    feedback: string[];
  } {
    let score = 0;
    const feedback: string[] = [];

    if (password.length >= 8) score++;
    else feedback.push('Password should be at least 8 characters');

    if (password.length >= 12) score++;

    if (/[a-z]/.test(password)) score++;
    else feedback.push('Add lowercase letters');

    if (/[A-Z]/.test(password)) score++;
    else feedback.push('Add uppercase letters');

    if (/\d/.test(password)) score++;
    else feedback.push('Add numbers');

    if (/[@$!%*?&]/.test(password)) score++;
    else feedback.push('Add special characters');

    if (!/(.)\1{2,}/.test(password)) score++;
    else feedback.push('Avoid repeating characters');

    const strength = score >= 6 ? 'strong' : score >= 4 ? 'medium' : 'weak';

    return { score, strength, feedback };
  }

  /**
   * Validate healthcare code
   */
  static validateHealthcareCode(
    code: string,
    codeType: keyof typeof HealthcarePatterns
  ): boolean {
    const pattern = HealthcarePatterns[codeType];
    return pattern ? pattern.test(code) : false;
  }

  /**
   * Create custom pattern
   */
  static createPattern(
    options: {
      minLength?: number;
      maxLength?: number;
      allowedChars?: string;
      requiredChars?: string[];
      disallowedChars?: string;
      startsWith?: string;
      endsWith?: string;
    }
  ): RegExp {
    let pattern = '^';

    if (options.startsWith) {
      pattern += options.startsWith;
    }

    if (options.allowedChars) {
      pattern += `[${options.allowedChars}]`;
      if (options.minLength && options.maxLength) {
        pattern += `{${options.minLength},${options.maxLength}}`;
      } else if (options.minLength) {
        pattern += `{${options.minLength},}`;
      } else if (options.maxLength) {
        pattern += `{0,${options.maxLength}}`;
      } else {
        pattern += '*';
      }
    }

    if (options.endsWith) {
      pattern += options.endsWith;
    }

    pattern += '$';

    // Add lookaheads for required characters
    if (options.requiredChars && options.requiredChars.length > 0) {
      const lookaheads = options.requiredChars.map(chars => `(?=.*[${chars}])`).join('');
      pattern = `^${lookaheads}${pattern.substring(1)}`;
    }

    return new RegExp(pattern);
  }
}

/**
 * Pattern collection manager
 */
export class PatternManager {
  private static customPatterns: Map<string, RegExp> = new Map();

  /**
   * Add custom pattern
   */
  static addPattern(name: string, pattern: RegExp): void {
    this.customPatterns.set(name, pattern);
  }

  /**
   * Get pattern by name
   */
  static getPattern(name: string): RegExp | undefined {
    // Check custom patterns first
    if (this.customPatterns.has(name)) {
      return this.customPatterns.get(name);
    }

    // Check built-in pattern collections
    const collections = [
      HealthcarePatterns,
      PersonalInfoPatterns,
      SecurityPatterns,
      FilePatterns,
      DateTimePatterns,
      FinancialPatterns,
      LocalePatterns
    ];

    for (const collection of collections) {
      if (name in collection) {
        return (collection as any)[name];
      }
    }

    return undefined;
  }

  /**
   * List all available patterns
   */
  static listPatterns(): string[] {
    const patterns: string[] = [];

    // Add custom patterns
    patterns.push(...Array.from(this.customPatterns.keys()));

    // Add built-in patterns
    const collections = [
      { name: 'Healthcare', patterns: HealthcarePatterns },
      { name: 'PersonalInfo', patterns: PersonalInfoPatterns },
      { name: 'Security', patterns: SecurityPatterns },
      { name: 'File', patterns: FilePatterns },
      { name: 'DateTime', patterns: DateTimePatterns },
      { name: 'Financial', patterns: FinancialPatterns },
      { name: 'Locale', patterns: LocalePatterns }
    ];

    for (const { name, patterns: collectionPatterns } of collections) {
      for (const key in collectionPatterns) {
        patterns.push(`${name}.${key}`);
      }
    }

    return patterns;
  }
}

// Export convenience functions
export const validate = RegexValidator.validate;
export const validateWithError = RegexValidator.validateWithError;
export const checkPasswordStrength = RegexValidator.checkPasswordStrength;
export const validateHealthcareCode = RegexValidator.validateHealthcareCode;
