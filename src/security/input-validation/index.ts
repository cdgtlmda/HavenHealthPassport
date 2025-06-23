/**
 * Input Validation Module
 * Comprehensive input validation and security for Haven Health Passport
 */

// Export sanitization
export * from './sanitizer';
export {
  InputSanitizer,
  ContextualSanitizer,
  sanitize,
  sanitizeEmail,
  sanitizeURL,
  sanitizeJSON,
  sanitizeFilename,
  sanitizeMRN,
  sanitizeFHIRId
} from './sanitizer';

// Export allowlists
export * from './allowlists';
export {
  Allowlists,
  AllowlistValidator,
  DynamicAllowlistManager,
  isAllowed,
  validateMedicalCode,
  validateFileExtension,
  validateMimeType,
  validatePhoneNumber,
  isTrustedDomain
} from './allowlists';

// Export regex patterns
export * from './regex-patterns';
export {
  HealthcarePatterns,
  PersonalInfoPatterns,
  SecurityPatterns,
  FilePatterns,
  DateTimePatterns,
  FinancialPatterns,
  LocalePatterns,
  RegexValidator,
  PatternManager,
  validate as validateRegex,
  validateWithError,
  checkPasswordStrength,
  validateHealthcareCode
} from './regex-patterns';

// Export length limits
export * from './length-limits';
export {
  LengthLimits,
  LengthValidator,
  DynamicLengthManager,
  LengthRecommendations,
  validateLength,
  validateByType,
  truncate,
  pad,
  getByteLength
} from './length-limits';

// Export type checking
export * from './type-checking';
export {
  TypeValidator,
  SchemaValidator,
  isType,
  validateType,
  coerceType,
  validateSchema
} from './type-checking';

// Export encoding validation
export * from './encoding-validation';
export {
  EncodingValidator,
  EncodingUtils,
  detectEncoding,
  validateEncoding,
  convertEncoding,
  sanitizeForEncoding,
  normalizeLineEndings,
  escapeHTML,
  escapeXML,
  escapeJSON,
  escapeCSV,
  normalizeUnicode,
  removeZeroWidth
} from './encoding-validation';

// Export file upload security
export * from './file-upload-security';
export {
  FileUploadSecurity,
  MimeTypeValidator,
  DefaultFileUploadConfigs,
  createFileUploadSecurity,
  validateMimeExtension,
  getExpectedExtensions,
  getExpectedMimeTypes
} from './file-upload-security';

// Export API validation
export * from './api-validation';
export {
  APIValidator,
  CommonSchemas,
  HealthcareSchemas,
  SchemaBuilder,
  validate as validateAPI,
  createSchema,
  sanitizeRequest
} from './api-validation';

// Export schema validation
export * from './schema-validation';
export {
  SchemaValidator as JSONSchemaValidator,
  SchemaRegistry,
  CommonJSONSchemas,
  HealthcareJSONSchemas,
  createValidator,
  validateSchema as validateJSONSchema,
  registerSchema,
  validateWithRegistry
} from './schema-validation';

// Export rate limiting
export * from './rate-limiting';
export {
  RateLimiter,
  SlidingWindowRateLimiter,
  TokenBucketRateLimiter,
  DistributedRateLimiter,
  RateLimitPresets,
  createRateLimiter,
  createSlidingWindowLimiter,
  createTokenBucketLimiter,
  createDistributedLimiter
} from './rate-limiting';

// Export request throttling
export * from './request-throttling';
export {
  RequestThrottler,
  CircuitBreaker,
  BackpressureHandler,
  ThrottleStrategies,
  HealthcareThrottleConfigs,
  createThrottler,
  createCircuitBreaker,
  createBackpressureHandler
} from './request-throttling';

// Export abuse detection
export * from './abuse-detection';
export {
  AbuseDetector,
  HoneypotMiddleware,
  createAbuseDetector,
  createHoneypot
} from './abuse-detection';

/**
 * Pre-configured validation middleware for common use cases
 */
export const ValidationPresets = {
  // Healthcare API validation
  healthcareAPI: {
    sanitizer: sanitizeRequest(),
    validator: APIValidator.validate({
      headers: CommonSchemas.object({
        'x-api-key': CommonSchemas.apiKey,
        'x-user-id': CommonSchemas.uuid
      }),
      query: CommonSchemas.object({
        page: CommonSchemas.page,
        limit: CommonSchemas.limit,
        sort: CommonSchemas.sort
      })
    }),
    rateLimiter: createRateLimiter(RateLimitPresets.healthcare.patientLookup),
    throttler: createThrottler(HealthcareThrottleConfigs.patientData),
    abuseDetector: createAbuseDetector({
      enableBehavioralAnalysis: true,
      enableContentAnalysis: true,
      maxFailedLogins: 3
    })
  },

  // File upload validation
  fileUpload: {
    documents: createFileUploadSecurity(DefaultFileUploadConfigs.documents),
    images: createFileUploadSecurity(DefaultFileUploadConfigs.images),
    medicalImages: createFileUploadSecurity(DefaultFileUploadConfigs.medicalImages)
  },

  // Authentication endpoints
  authentication: {
    rateLimiter: createRateLimiter(RateLimitPresets.auth.login),
    validator: APIValidator.validate({
      body: CommonSchemas.object({
        email: CommonSchemas.email,
        password: CommonSchemas.string().min(8).max(128)
      })
    }),
    abuseDetector: createAbuseDetector({
      maxFailedLogins: 5,
      maxFailedLoginWindow: 15 * 60 * 1000
    })
  }
};

/**
 * Comprehensive input validation middleware
 */
export function createComprehensiveValidator(options: {
  sanitize?: boolean;
  validateSchema?: any;
  rateLimit?: any;
  throttle?: any;
  detectAbuse?: boolean;
} = {}) {
  const middlewares = [];

  // Add sanitization
  if (options.sanitize !== false) {
    middlewares.push(sanitizeRequest());
  }

  // Add schema validation
  if (options.validateSchema) {
    middlewares.push(APIValidator.validate(options.validateSchema));
  }

  // Add rate limiting
  if (options.rateLimit) {
    middlewares.push(createRateLimiter(options.rateLimit).middleware());
  }

  // Add throttling
  if (options.throttle) {
    middlewares.push(createThrottler(options.throttle).middleware());
  }

  // Add abuse detection
  if (options.detectAbuse !== false) {
    middlewares.push(createAbuseDetector().middleware());
  }

  return middlewares;
}

/**
 * Healthcare-specific validators
 */
export const HealthcareValidators = {
  // Validate patient data
  validatePatient: (data: any) => {
    const schema = HealthcareJSONSchemas.patient;
    return new JSONSchemaValidator().validate(data, schema);
  },

  // Validate prescription
  validatePrescription: (data: any) => {
    const schema = HealthcareJSONSchemas.prescription;
    return new JSONSchemaValidator().validate(data, schema);
  },

  // Validate lab result
  validateLabResult: (data: any) => {
    const schema = HealthcareJSONSchemas.labResult;
    return new JSONSchemaValidator().validate(data, schema);
  },

  // Validate medical codes
  validateMedicalCodes: (codes: { type: string; value: string }[]) => {
    const results = codes.map(({ type, value }) => ({
      type,
      value,
      valid: validateMedicalCode(value, type as any)
    }));

    return {
      valid: results.every(r => r.valid),
      results
    };
  }
};

/**
 * Security best practices guide
 */
export const SecurityBestPractices = {
  inputValidation: [
    'Always sanitize user input before processing',
    'Use allowlists instead of blocklists where possible',
    'Validate input length to prevent buffer overflows',
    'Check data types and enforce strict typing',
    'Normalize encoding to prevent encoding attacks',
    'Validate file uploads thoroughly including magic numbers'
  ],

  rateLimiting: [
    'Implement rate limiting on all public endpoints',
    'Use sliding window for better accuracy',
    'Consider token bucket for burst handling',
    'Implement distributed rate limiting for scalability',
    'Set different limits for authenticated vs anonymous users'
  ],

  abuseDetection: [
    'Monitor for suspicious patterns in real-time',
    'Implement honeypots to detect automated attacks',
    'Use device fingerprinting to track suspicious devices',
    'Block geographic regions if not serving those areas',
    'Implement progressive blocking (warn, throttle, block)'
  ],

  healthcare: [
    'Validate all medical codes against official registries',
    'Sanitize PHI (Protected Health Information) carefully',
    'Implement field-level encryption for sensitive data',
    'Log all access to patient records for HIPAA compliance',
    'Validate prescriptions against drug interaction databases'
  ]
};

// Export version for compatibility checking
export const VERSION = '1.0.0';
