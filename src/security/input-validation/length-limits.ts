/**
 * Length Limits Configuration
 * Defines maximum and minimum lengths for various input types
 */

/**
 * Length limit definitions
 */
export const LengthLimits = {
  // Personal information
  personalInfo: {
    firstName: { min: 1, max: 50 },
    lastName: { min: 1, max: 50 },
    middleName: { min: 0, max: 50 },
    fullName: { min: 2, max: 150 },
    email: { min: 5, max: 254 }, // RFC 5321
    phoneNumber: { min: 10, max: 15 }, // E.164 format
    ssn: { min: 9, max: 11 }, // With or without dashes
    dateOfBirth: { min: 10, max: 10 }, // YYYY-MM-DD
    gender: { min: 1, max: 20 },
    maritalStatus: { min: 1, max: 30 }
  },

  // Address information
  address: {
    streetLine1: { min: 3, max: 100 },
    streetLine2: { min: 0, max: 100 },
    city: { min: 2, max: 50 },
    state: { min: 2, max: 50 },
    postalCode: { min: 3, max: 20 },
    country: { min: 2, max: 2 }, // ISO 3166-1 alpha-2
    fullAddress: { min: 10, max: 500 }
  },

  // Healthcare identifiers
  healthcareIds: {
    mrn: { min: 6, max: 20 },
    npi: { min: 10, max: 10 },
    dea: { min: 9, max: 9 },
    medicalLicense: { min: 6, max: 15 },
    insurancePolicy: { min: 6, max: 20 },
    insuranceGroup: { min: 4, max: 15 },
    patientId: { min: 1, max: 64 }, // FHIR ID
    encounterId: { min: 1, max: 64 },
    organizationId: { min: 1, max: 64 }
  },

  // Medical codes
  medicalCodes: {
    icd10: { min: 3, max: 8 },
    cpt: { min: 5, max: 5 },
    loinc: { min: 3, max: 10 },
    rxnorm: { min: 1, max: 8 },
    snomed: { min: 6, max: 18 },
    ndc: { min: 10, max: 14 },
    hcpcs: { min: 5, max: 5 }
  },

  // Clinical data
  clinicalData: {
    diagnosis: { min: 3, max: 500 },
    chiefComplaint: { min: 3, max: 500 },
    medications: { min: 2, max: 200 },
    allergies: { min: 2, max: 200 },
    procedures: { min: 3, max: 300 },
    labResults: { min: 1, max: 100 },
    vitalSigns: { min: 1, max: 20 },
    clinicalNotes: { min: 10, max: 10000 },
    dischargeSummary: { min: 100, max: 20000 },
    prescriptionInstructions: { min: 5, max: 500 }
  },

  // Authentication and security
  security: {
    username: { min: 3, max: 50 },
    password: { min: 8, max: 128 },
    pin: { min: 4, max: 8 },
    totpCode: { min: 6, max: 6 },
    apiKey: { min: 32, max: 64 },
    sessionToken: { min: 16, max: 256 },
    csrfToken: { min: 32, max: 64 },
    jwtToken: { min: 20, max: 8192 }, // Can be quite long
    securityQuestion: { min: 10, max: 200 },
    securityAnswer: { min: 2, max: 100 }
  },

  // File and content
  files: {
    filename: { min: 1, max: 255 },
    fileExtension: { min: 1, max: 10 },
    mimeType: { min: 3, max: 100 },
    filePath: { min: 1, max: 4096 }, // OS dependent
    description: { min: 0, max: 1000 },
    contentType: { min: 3, max: 100 },
    base64Data: { min: 1, max: 10485760 }, // 10MB base64
    fileSize: { min: 1, max: 52428800 } // 50MB in bytes
  },

  // Communication
  communication: {
    emailSubject: { min: 1, max: 200 },
    emailBody: { min: 1, max: 50000 },
    smsMessage: { min: 1, max: 160 },
    pushNotification: { min: 1, max: 250 },
    chatMessage: { min: 1, max: 1000 },
    comment: { min: 1, max: 5000 },
    feedback: { min: 10, max: 2000 }
  },

  // API and integration
  api: {
    endpoint: { min: 1, max: 2048 },
    queryParam: { min: 1, max: 100 },
    headerName: { min: 1, max: 100 },
    headerValue: { min: 0, max: 8192 },
    jsonKey: { min: 1, max: 100 },
    jsonValue: { min: 0, max: 100000 },
    xmlTag: { min: 1, max: 100 },
    xmlContent: { min: 0, max: 100000 }
  },

  // Appointment and scheduling
  scheduling: {
    appointmentReason: { min: 3, max: 200 },
    appointmentNotes: { min: 0, max: 1000 },
    duration: { min: 1, max: 480 }, // Minutes
    recurringPattern: { min: 3, max: 100 },
    timezone: { min: 3, max: 50 },
    location: { min: 3, max: 200 }
  },

  // Financial
  financial: {
    amount: { min: 1, max: 15 }, // Including decimal
    currency: { min: 3, max: 3 }, // ISO 4217
    accountNumber: { min: 4, max: 17 },
    routingNumber: { min: 9, max: 9 },
    creditCard: { min: 13, max: 19 },
    cvv: { min: 3, max: 4 },
    billingCode: { min: 1, max: 20 },
    invoiceNumber: { min: 1, max: 50 }
  },

  // Search and filtering
  search: {
    searchQuery: { min: 1, max: 200 },
    filterValue: { min: 1, max: 100 },
    sortField: { min: 1, max: 50 },
    pageSize: { min: 1, max: 1000 },
    offset: { min: 0, max: 1000000 }
  },

  // General text fields
  text: {
    shortText: { min: 1, max: 100 },
    mediumText: { min: 1, max: 500 },
    longText: { min: 1, max: 5000 },
    veryLongText: { min: 1, max: 50000 },
    title: { min: 1, max: 200 },
    label: { min: 1, max: 50 },
    placeholder: { min: 1, max: 100 },
    errorMessage: { min: 1, max: 500 },
    helpText: { min: 1, max: 1000 }
  }
};

/**
 * Length validator class
 */
export class LengthValidator {
  /**
   * Validate string length
   */
  static validate(
    value: string,
    minLength: number,
    maxLength: number
  ): { valid: boolean; error?: string } {
    const length = value.length;

    if (length < minLength) {
      return {
        valid: false,
        error: `Value must be at least ${minLength} characters long`
      };
    }

    if (length > maxLength) {
      return {
        valid: false,
        error: `Value must not exceed ${maxLength} characters`
      };
    }

    return { valid: true };
  }

  /**
   * Validate using predefined limits
   */
  static validateByType(
    value: string,
    category: keyof typeof LengthLimits,
    field: string
  ): { valid: boolean; error?: string } {
    const limits = (LengthLimits[category] as any)[field];

    if (!limits) {
      return {
        valid: false,
        error: `Unknown field type: ${category}.${field}`
      };
    }

    return this.validate(value, limits.min, limits.max);
  }

  /**
   * Truncate string to max length
   */
  static truncate(
    value: string,
    maxLength: number,
    suffix: string = '...'
  ): string {
    if (value.length <= maxLength) {
      return value;
    }

    const truncateLength = maxLength - suffix.length;
    return value.substring(0, truncateLength) + suffix;
  }

  /**
   * Pad string to min length
   */
  static pad(
    value: string,
    minLength: number,
    padChar: string = ' ',
    padStart: boolean = false
  ): string {
    if (value.length >= minLength) {
      return value;
    }

    const padLength = minLength - value.length;
    const padding = padChar.repeat(padLength);

    return padStart ? padding + value : value + padding;
  }

  /**
   * Get length limits for a field
   */
  static getLimits(
    category: keyof typeof LengthLimits,
    field: string
  ): { min: number; max: number } | undefined {
    return (LengthLimits[category] as any)[field];
  }

  /**
   * Validate array length
   */
  static validateArrayLength(
    array: any[],
    minLength: number,
    maxLength: number
  ): { valid: boolean; error?: string } {
    const length = array.length;

    if (length < minLength) {
      return {
        valid: false,
        error: `Array must contain at least ${minLength} items`
      };
    }

    if (length > maxLength) {
      return {
        valid: false,
        error: `Array must not exceed ${maxLength} items`
      };
    }

    return { valid: true };
  }

  /**
   * Validate object size (number of properties)
   */
  static validateObjectSize(
    obj: object,
    minSize: number,
    maxSize: number
  ): { valid: boolean; error?: string } {
    const size = Object.keys(obj).length;

    if (size < minSize) {
      return {
        valid: false,
        error: `Object must have at least ${minSize} properties`
      };
    }

    if (size > maxSize) {
      return {
        valid: false,
        error: `Object must not exceed ${maxSize} properties`
      };
    }

    return { valid: true };
  }

  /**
   * Calculate actual byte length (for UTF-8)
   */
  static getByteLength(value: string): number {
    return Buffer.byteLength(value, 'utf8');
  }

  /**
   * Validate byte length
   */
  static validateByteLength(
    value: string,
    maxBytes: number
  ): { valid: boolean; error?: string; actualBytes?: number } {
    const bytes = this.getByteLength(value);

    if (bytes > maxBytes) {
      return {
        valid: false,
        error: `Value exceeds maximum byte limit of ${maxBytes}`,
        actualBytes: bytes
      };
    }

    return { valid: true, actualBytes: bytes };
  }
}

/**
 * Dynamic length limits manager
 */
export class DynamicLengthManager {
  private static customLimits: Map<string, { min: number; max: number }> = new Map();

  /**
   * Set custom length limit
   */
  static setLimit(
    key: string,
    min: number,
    max: number
  ): void {
    this.customLimits.set(key, { min, max });
  }

  /**
   * Get custom length limit
   */
  static getLimit(key: string): { min: number; max: number } | undefined {
    return this.customLimits.get(key);
  }

  /**
   * Validate using custom limit
   */
  static validateCustom(
    value: string,
    key: string
  ): { valid: boolean; error?: string } {
    const limits = this.customLimits.get(key);

    if (!limits) {
      return {
        valid: false,
        error: `No custom limits defined for key: ${key}`
      };
    }

    return LengthValidator.validate(value, limits.min, limits.max);
  }

  /**
   * Remove custom limit
   */
  static removeLimit(key: string): void {
    this.customLimits.delete(key);
  }

  /**
   * Clear all custom limits
   */
  static clearLimits(): void {
    this.customLimits.clear();
  }
}

/**
 * Length recommendations based on context
 */
export const LengthRecommendations = {
  // User experience recommendations
  ux: {
    errorMessage: { ideal: 50, acceptable: 100 },
    helpText: { ideal: 75, acceptable: 150 },
    buttonLabel: { ideal: 20, acceptable: 30 },
    tooltipText: { ideal: 100, acceptable: 200 },
    placeholder: { ideal: 30, acceptable: 50 }
  },

  // Performance recommendations
  performance: {
    searchQuery: { ideal: 50, acceptable: 100 },
    apiEndpoint: { ideal: 100, acceptable: 200 },
    cacheKey: { ideal: 50, acceptable: 100 },
    indexedField: { ideal: 30, acceptable: 50 }
  },

  // Security recommendations
  security: {
    password: { ideal: 16, acceptable: 12 },
    apiKey: { ideal: 64, acceptable: 32 },
    sessionToken: { ideal: 128, acceptable: 64 }
  }
};

// Export convenience functions
export const validateLength = LengthValidator.validate;
export const validateByType = LengthValidator.validateByType;
export const truncate = LengthValidator.truncate;
export const pad = LengthValidator.pad;
export const getByteLength = LengthValidator.getByteLength;
