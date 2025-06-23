/**
 * Allowlist Configuration
 * Defines allowed values for various input types
 */

/**
 * Allowlist definitions for different input types
 */
export const Allowlists = {
  // Medical codes
  medicalCodes: {
    icd10: /^[A-Z]\d{2}(?:\.\d{1,2})?$/,
    cpt: /^\d{5}$/,
    ndc: /^\d{5}-\d{4}-\d{2}$/,
    loinc: /^\d{1,5}-\d$/,
    rxnorm: /^\d{1,7}$/,
    snomed: /^\d{6,18}$/
  },

  // Document types
  documentTypes: [
    'lab_result',
    'prescription',
    'discharge_summary',
    'consultation_note',
    'procedure_report',
    'imaging_report',
    'pathology_report',
    'progress_note',
    'history_physical',
    'operative_report',
    'emergency_record',
    'immunization_record',
    'allergy_list',
    'medication_list',
    'problem_list'
  ],

  // Allowed file extensions
  fileExtensions: {
    documents: ['.pdf', '.doc', '.docx', '.txt', '.rtf'],
    images: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'],
    medical_images: ['.dcm', '.nii', '.nii.gz'],
    data: ['.json', '.xml', '.csv', '.hl7', '.fhir']
  },

  // MIME types
  mimeTypes: {
    documents: [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'text/rtf'
    ],
    images: [
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/bmp',
      'image/svg+xml'
    ],
    medical: [
      'application/dicom',
      'application/hl7-v2+er7',
      'application/fhir+json',
      'application/fhir+xml'
    ]
  },

  // Language codes (ISO 639-1)
  languages: [
    'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko',
    'ar', 'hi', 'bn', 'pa', 'ur', 'fa', 'tr', 'vi', 'th', 'sw',
    'ha', 'yo', 'am', 'om', 'so', 'zu', 'ig', 'ne', 'si', 'my'
  ],

  // Country codes (ISO 3166-1 alpha-2)
  countries: [
    'US', 'CA', 'MX', 'GB', 'FR', 'DE', 'IT', 'ES', 'PT', 'NL',
    'BE', 'CH', 'AT', 'PL', 'RO', 'GR', 'TR', 'RU', 'UA', 'IN',
    'CN', 'JP', 'KR', 'AU', 'NZ', 'ZA', 'EG', 'NG', 'KE', 'ET',
    'BR', 'AR', 'CO', 'PE', 'CL', 'VE', 'EC', 'BO', 'PY', 'UY'
  ],

  // Time zones
  timeZones: Intl.supportedValuesOf('timeZone'),

  // Blood types
  bloodTypes: ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],

  // Genders (FHIR compliant)
  genders: ['male', 'female', 'other', 'unknown'],

  // Marital status (FHIR compliant)
  maritalStatus: [
    'single',
    'married',
    'divorced',
    'widowed',
    'separated',
    'registered_partnership',
    'unknown'
  ],

  // Appointment status
  appointmentStatus: [
    'scheduled',
    'confirmed',
    'arrived',
    'in_progress',
    'completed',
    'cancelled',
    'no_show',
    'rescheduled'
  ],

  // Prescription status
  prescriptionStatus: [
    'active',
    'completed',
    'cancelled',
    'on_hold',
    'expired',
    'draft'
  ],

  // Lab result status
  labResultStatus: [
    'pending',
    'in_progress',
    'completed',
    'verified',
    'amended',
    'cancelled',
    'error'
  ],

  // Urgency levels
  urgencyLevels: [
    'routine',
    'urgent',
    'emergency',
    'stat'
  ],

  // Allergy severity
  allergySeverity: [
    'mild',
    'moderate',
    'severe',
    'life_threatening'
  ],

  // Reaction types
  reactionTypes: [
    'allergy',
    'intolerance',
    'side_effect',
    'interaction',
    'unknown'
  ],

  // Vaccine codes (sample list)
  vaccineCodes: [
    'COVID-19',
    'Influenza',
    'MMR',
    'DTaP',
    'Hepatitis_A',
    'Hepatitis_B',
    'HPV',
    'Meningococcal',
    'Pneumococcal',
    'Rotavirus',
    'Varicella',
    'Zoster',
    'Tdap',
    'Polio'
  ],

  // Healthcare specialties
  specialties: [
    'cardiology',
    'dermatology',
    'emergency_medicine',
    'family_medicine',
    'gastroenterology',
    'general_surgery',
    'hematology',
    'infectious_disease',
    'internal_medicine',
    'nephrology',
    'neurology',
    'obstetrics_gynecology',
    'oncology',
    'ophthalmology',
    'orthopedics',
    'otolaryngology',
    'pathology',
    'pediatrics',
    'psychiatry',
    'pulmonology',
    'radiology',
    'rheumatology',
    'urology'
  ],

  // Insurance types
  insuranceTypes: [
    'private',
    'medicare',
    'medicaid',
    'military',
    'workers_compensation',
    'self_pay',
    'charity',
    'other'
  ],

  // Relationship types (for emergency contacts)
  relationshipTypes: [
    'spouse',
    'parent',
    'child',
    'sibling',
    'grandparent',
    'grandchild',
    'friend',
    'guardian',
    'partner',
    'other'
  ],

  // HTTP methods
  httpMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'],

  // Content types for API
  apiContentTypes: [
    'application/json',
    'application/xml',
    'application/fhir+json',
    'application/fhir+xml',
    'multipart/form-data'
  ],

  // Allowed domains for external resources
  trustedDomains: [
    'hl7.org',
    'fhir.org',
    'who.int',
    'cdc.gov',
    'nih.gov',
    'ncbi.nlm.nih.gov',
    'pubmed.ncbi.nlm.nih.gov'
  ],

  // Allowed protocols
  allowedProtocols: ['https:', 'http:', 'ftp:'],

  // Date formats
  dateFormats: [
    'YYYY-MM-DD',
    'MM/DD/YYYY',
    'DD/MM/YYYY',
    'YYYY-MM-DD HH:mm:ss',
    'ISO8601'
  ],

  // Phone number patterns by country
  phonePatterns: {
    US: /^\+1[2-9]\d{2}[2-9]\d{6}$/,
    UK: /^\+44[1-9]\d{9,10}$/,
    CA: /^\+1[2-9]\d{2}[2-9]\d{6}$/,
    AU: /^\+61[2-9]\d{8}$/,
    IN: /^\+91[6-9]\d{9}$/,
    DEFAULT: /^\+\d{1,3}\d{4,14}$/
  },

  // Email domains for healthcare providers
  healthcareEmailDomains: [
    'hospital.org',
    'clinic.org',
    'health.org',
    'medical.org',
    'healthcare.org'
  ],

  // Allowed HTML tags for rich text fields
  allowedHTMLTags: [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'td', 'th'
  ],

  // Allowed HTML attributes
  allowedHTMLAttributes: {
    'table': ['class'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'blockquote': ['cite']
  }
};

/**
 * Allowlist validator class
 */
export class AllowlistValidator {
  /**
   * Check if value is in allowlist
   */
  static isAllowed(value: any, allowlist: any[] | RegExp): boolean {
    if (Array.isArray(allowlist)) {
      return allowlist.includes(value);
    } else if (allowlist instanceof RegExp) {
      return allowlist.test(String(value));
    }
    return false;
  }

  /**
   * Validate medical code
   */
  static validateMedicalCode(code: string, codeType: keyof typeof Allowlists.medicalCodes): boolean {
    const pattern = Allowlists.medicalCodes[codeType];
    return pattern ? pattern.test(code) : false;
  }

  /**
   * Validate file extension
   */
  static validateFileExtension(filename: string, category: keyof typeof Allowlists.fileExtensions): boolean {
    const extensions = Allowlists.fileExtensions[category];
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
    return extensions.includes(ext);
  }

  /**
   * Validate MIME type
   */
  static validateMimeType(mimeType: string, category: keyof typeof Allowlists.mimeTypes): boolean {
    const allowedTypes = Allowlists.mimeTypes[category];
    return allowedTypes.includes(mimeType.toLowerCase());
  }

  /**
   * Validate phone number
   */
  static validatePhoneNumber(phone: string, countryCode: string = 'DEFAULT'): boolean {
    const pattern = Allowlists.phonePatterns[countryCode as keyof typeof Allowlists.phonePatterns]
                    || Allowlists.phonePatterns.DEFAULT;
    return pattern.test(phone);
  }

  /**
   * Validate trusted domain
   */
  static isTrustedDomain(url: string): boolean {
    try {
      const urlObj = new URL(url);
      return Allowlists.trustedDomains.some(domain =>
        urlObj.hostname === domain || urlObj.hostname.endsWith('.' + domain)
      );
    } catch {
      return false;
    }
  }

  /**
   * Get allowed values for a category
   */
  static getAllowedValues(category: keyof typeof Allowlists): any[] | RegExp | object {
    return Allowlists[category];
  }

  /**
   * Validate enum value
   */
  static validateEnum<T extends keyof typeof Allowlists>(
    value: any,
    category: T
  ): value is typeof Allowlists[T][number] {
    const allowedValues = Allowlists[category];
    if (Array.isArray(allowedValues)) {
      return allowedValues.includes(value);
    }
    return false;
  }
}

/**
 * Dynamic allowlist manager for runtime configuration
 */
export class DynamicAllowlistManager {
  private static customAllowlists: Map<string, Set<any>> = new Map();

  /**
   * Add custom allowlist
   */
  static addCustomAllowlist(name: string, values: any[]): void {
    this.customAllowlists.set(name, new Set(values));
  }

  /**
   * Add value to custom allowlist
   */
  static addToAllowlist(name: string, value: any): void {
    const allowlist = this.customAllowlists.get(name) || new Set();
    allowlist.add(value);
    this.customAllowlists.set(name, allowlist);
  }

  /**
   * Remove value from custom allowlist
   */
  static removeFromAllowlist(name: string, value: any): void {
    const allowlist = this.customAllowlists.get(name);
    if (allowlist) {
      allowlist.delete(value);
    }
  }

  /**
   * Check if value is in custom allowlist
   */
  static isInCustomAllowlist(name: string, value: any): boolean {
    const allowlist = this.customAllowlists.get(name);
    return allowlist ? allowlist.has(value) : false;
  }

  /**
   * Get custom allowlist
   */
  static getCustomAllowlist(name: string): any[] {
    const allowlist = this.customAllowlists.get(name);
    return allowlist ? Array.from(allowlist) : [];
  }
}

// Export for convenience
export const isAllowed = AllowlistValidator.isAllowed;
export const validateMedicalCode = AllowlistValidator.validateMedicalCode;
export const validateFileExtension = AllowlistValidator.validateFileExtension;
export const validateMimeType = AllowlistValidator.validateMimeType;
export const validatePhoneNumber = AllowlistValidator.validatePhoneNumber;
export const isTrustedDomain = AllowlistValidator.isTrustedDomain;
