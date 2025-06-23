/**
 * Schema Validation
 * Comprehensive schema validation for complex data structures
 */

import Ajv, { JSONSchemaType, ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
import addKeywords from 'ajv-keywords';
import { InputSanitizer } from './sanitizer';
import { TypeValidator } from './type-checking';
import { RegexValidator } from './regex-patterns';

/**
 * Schema validation options
 */
export interface SchemaValidationOptions {
  coerceTypes?: boolean;
  removeAdditional?: boolean | 'all' | 'failing';
  useDefaults?: boolean;
  strict?: boolean;
  validateFormats?: boolean;
  allErrors?: boolean;
  verbose?: boolean;
  sanitize?: boolean;
  customFormats?: Record<string, RegExp | ((data: string) => boolean)>;
  customKeywords?: Record<string, any>;
}

/**
 * Validation result
 */
export interface SchemaValidationResult {
  valid: boolean;
  errors?: Array<{
    field: string;
    message: string;
    keyword: string;
    params: any;
    schemaPath: string;
  }>;
  data?: any;
}

/**
 * Schema validator class
 */
export class SchemaValidator {
  private ajv: Ajv;
  private validators: Map<string, ValidateFunction> = new Map();

  constructor(options: SchemaValidationOptions = {}) {
    this.ajv = new Ajv({
      coerceTypes: options.coerceTypes ?? true,
      removeAdditional: options.removeAdditional ?? true,
      useDefaults: options.useDefaults ?? true,
      strict: options.strict ?? false,
      allErrors: options.allErrors ?? true,
      verbose: options.verbose ?? true
    });

    // Add formats
    if (options.validateFormats !== false) {
      addFormats(this.ajv);
      this.addHealthcareFormats();
    }

    // Add keywords
    addKeywords(this.ajv);
    this.addCustomKeywords();

    // Add custom formats
    if (options.customFormats) {
      for (const [name, format] of Object.entries(options.customFormats)) {
        this.ajv.addFormat(name, format);
      }
    }

    // Add custom keywords
    if (options.customKeywords) {
      for (const [name, keyword] of Object.entries(options.customKeywords)) {
        this.ajv.addKeyword({
          keyword: name,
          ...keyword
        });
      }
    }
  }

  /**
   * Add healthcare-specific formats
   */
  private addHealthcareFormats(): void {
    // Medical Record Number
    this.ajv.addFormat('mrn', /^[A-Z0-9]{6,20}$/);

    // National Provider Identifier
    this.ajv.addFormat('npi', /^[1-9]\d{9}$/);

    // DEA number
    this.ajv.addFormat('dea', /^[A-Z]{2}\d{7}$/);

    // ICD-10 code
    this.ajv.addFormat('icd10', /^[A-Z]\d{2}(?:\.\d{1,4})?$/);

    // CPT code
    this.ajv.addFormat('cpt', /^(?:\d{5}|[A-Z]\d{4})$/);

    // LOINC code
    this.ajv.addFormat('loinc', /^\d{1,5}-\d$/);

    // RxNorm code
    this.ajv.addFormat('rxnorm', /^\d{1,7}$/);

    // FHIR ID
    this.ajv.addFormat('fhir-id', /^[A-Za-z0-9\-\.]{1,64}$/);

    // Blood type
    this.ajv.addFormat('blood-type', /^(A|B|AB|O)[+-]$/);

    // Phone with extension
    this.ajv.addFormat('phone-ext', /^[+]?[(]?[0-9]{1,4}[)]?[-\s.]?[(]?[0-9]{1,4}[)]?[-\s.]?[0-9]{1,9}(?:\s?(?:x|ext\.?)\s?\d{1,5})?$/);
  }

  /**
   * Add custom keywords
   */
  private addCustomKeywords(): void {
    // Healthcare-specific validations
    this.ajv.addKeyword({
      keyword: 'validDosage',
      type: 'string',
      compile: function() {
        return function(data: string) {
          return /^\d+(?:\.\d{1,3})?\s*(?:mg|mcg|g|ml|l|unit|iu|mEq)$/i.test(data);
        };
      }
    });

    // Date range validation
    this.ajv.addKeyword({
      keyword: 'dateRange',
      type: 'object',
      compile: function() {
        return function(data: any) {
          if (!data.start || !data.end) return false;
          const start = new Date(data.start);
          const end = new Date(data.end);
          return start <= end;
        };
      }
    });

    // Conditional required
    this.ajv.addKeyword({
      keyword: 'requiredIf',
      type: 'object',
      schemaType: 'object',
      compile: function(schema: any) {
        return function(data: any, dataPath: any, parentData: any) {
          const { property, value, required } = schema;
          if (parentData[property] === value) {
            for (const field of required) {
              if (!data[field]) return false;
            }
          }
          return true;
        };
      }
    });

    // Cross-field validation
    this.ajv.addKeyword({
      keyword: 'consistentWith',
      type: 'string',
      schemaType: 'object',
      compile: function(schema: any) {
        return function(data: any, dataPath: any, parentData: any) {
          const { field, rule } = schema;
          const relatedValue = parentData[field];

          switch (rule) {
            case 'email-domain':
              return data.endsWith(relatedValue.split('@')[1]);
            case 'date-after':
              return new Date(data) > new Date(relatedValue);
            case 'date-before':
              return new Date(data) < new Date(relatedValue);
            default:
              return true;
          }
        };
      }
    });

    // Sanitization keyword
    this.ajv.addKeyword({
      keyword: 'sanitize',
      type: 'string',
      modifying: true,
      compile: function(schema: any) {
        return function(data: string, dataPath: any, parentData: any, property: any) {
          if (typeof data === 'string') {
            parentData[property] = InputSanitizer.sanitizeString(data, schema);
          }
          return true;
        };
      }
    });
  }

  /**
   * Compile and cache a schema
   */
  compileSchema(schemaId: string, schema: any): ValidateFunction {
    const validator = this.ajv.compile(schema);
    this.validators.set(schemaId, validator);
    return validator;
  }

  /**
   * Validate data against schema
   */
  validate(
    data: any,
    schema: any | string,
    options?: { sanitize?: boolean }
  ): SchemaValidationResult {
    // Get validator
    let validator: ValidateFunction;
    if (typeof schema === 'string') {
      validator = this.validators.get(schema);
      if (!validator) {
        return {
          valid: false,
          errors: [{
            field: '',
            message: `Schema '${schema}' not found`,
            keyword: 'schema',
            params: {},
            schemaPath: ''
          }]
        };
      }
    } else {
      validator = this.ajv.compile(schema);
    }

    // Sanitize data if requested
    let processedData = data;
    if (options?.sanitize) {
      processedData = this.sanitizeData(data);
    }

    // Validate
    const valid = validator(processedData);

    if (!valid) {
      const errors = validator.errors?.map(error => ({
        field: error.instancePath.replace(/^\//, '').replace(/\//g, '.'),
        message: error.message || 'Validation failed',
        keyword: error.keyword,
        params: error.params,
        schemaPath: error.schemaPath
      })) || [];

      return { valid: false, errors };
    }

    return { valid: true, data: processedData };
  }

  /**
   * Sanitize data recursively
   */
  private sanitizeData(data: any): any {
    if (typeof data === 'string') {
      return InputSanitizer.sanitizeString(data);
    }

    if (Array.isArray(data)) {
      return data.map(item => this.sanitizeData(item));
    }

    if (data && typeof data === 'object') {
      const sanitized: any = {};
      for (const [key, value] of Object.entries(data)) {
        sanitized[key] = this.sanitizeData(value);
      }
      return sanitized;
    }

    return data;
  }

  /**
   * Add schema to validator
   */
  addSchema(schemaId: string, schema: any): void {
    this.ajv.addSchema(schema, schemaId);
  }

  /**
   * Remove schema from validator
   */
  removeSchema(schemaId: string): void {
    this.ajv.removeSchema(schemaId);
    this.validators.delete(schemaId);
  }

  /**
   * Get compiled validator
   */
  getValidator(schemaId: string): ValidateFunction | undefined {
    return this.validators.get(schemaId);
  }
}

/**
 * Common JSON schemas
 */
export const CommonJSONSchemas = {
  // Email
  email: {
    type: 'string',
    format: 'email',
    maxLength: 254,
    transform: ['toLowerCase', 'trim']
  },

  // Phone number
  phone: {
    type: 'string',
    format: 'phone-ext',
    maxLength: 30
  },

  // UUID
  uuid: {
    type: 'string',
    format: 'uuid'
  },

  // URL
  url: {
    type: 'string',
    format: 'uri',
    maxLength: 2048
  },

  // Date
  date: {
    type: 'string',
    format: 'date'
  },

  // DateTime
  dateTime: {
    type: 'string',
    format: 'date-time'
  },

  // Time
  time: {
    type: 'string',
    format: 'time'
  },

  // Address
  address: {
    type: 'object',
    properties: {
      street: { type: 'string', maxLength: 100 },
      city: { type: 'string', maxLength: 50 },
      state: { type: 'string', pattern: '^[A-Z]{2}$' },
      postalCode: { type: 'string', pattern: '^\\d{5}(-\\d{4})?$' },
      country: { type: 'string', pattern: '^[A-Z]{2}$', default: 'US' }
    },
    required: ['street', 'city', 'state', 'postalCode'],
    additionalProperties: false
  },

  // Pagination
  pagination: {
    type: 'object',
    properties: {
      page: { type: 'integer', minimum: 1, default: 1 },
      limit: { type: 'integer', minimum: 1, maximum: 100, default: 20 },
      sort: { type: 'string', enum: ['asc', 'desc'], default: 'asc' },
      sortBy: { type: 'string' }
    },
    additionalProperties: false
  }
};

/**
 * Healthcare JSON schemas
 */
export const HealthcareJSONSchemas = {
  // Patient
  patient: {
    type: 'object',
    properties: {
      id: { type: 'string', format: 'fhir-id' },
      mrn: { type: 'string', format: 'mrn', sanitize: { uppercase: true } },
      firstName: { type: 'string', minLength: 1, maxLength: 50, sanitize: { trimWhitespace: true } },
      lastName: { type: 'string', minLength: 1, maxLength: 50, sanitize: { trimWhitespace: true } },
      middleName: { type: 'string', maxLength: 50, sanitize: { trimWhitespace: true } },
      dateOfBirth: { type: 'string', format: 'date' },
      gender: { type: 'string', enum: ['male', 'female', 'other', 'unknown'] },
      ssn: { type: 'string', pattern: '^\\d{3}-?\\d{2}-?\\d{4}$' },
      address: { $ref: '#/definitions/address' },
      phone: { type: 'string', format: 'phone-ext' },
      email: { type: 'string', format: 'email' },
      bloodType: { type: 'string', format: 'blood-type' },
      allergies: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            allergen: { type: 'string', minLength: 2, maxLength: 200 },
            reaction: { type: 'string', enum: ['mild', 'moderate', 'severe', 'anaphylaxis'] },
            onsetDate: { type: 'string', format: 'date' }
          },
          required: ['allergen', 'reaction']
        }
      },
      emergencyContact: {
        type: 'object',
        properties: {
          name: { type: 'string', minLength: 2, maxLength: 100 },
          relationship: { type: 'string' },
          phone: { type: 'string', format: 'phone-ext' }
        },
        required: ['name', 'phone']
      }
    },
    required: ['mrn', 'firstName', 'lastName', 'dateOfBirth', 'gender'],
    additionalProperties: false,
    definitions: {
      address: CommonJSONSchemas.address
    }
  },

  // Provider
  provider: {
    type: 'object',
    properties: {
      id: { type: 'string', format: 'fhir-id' },
      npi: { type: 'string', format: 'npi' },
      dea: { type: 'string', format: 'dea' },
      firstName: { type: 'string', minLength: 1, maxLength: 50 },
      lastName: { type: 'string', minLength: 1, maxLength: 50 },
      credentials: { type: 'string', maxLength: 20 },
      specialty: { type: 'string' },
      licenseNumber: { type: 'string', pattern: '^[A-Z]{2}\\d{4,10}$' },
      licenseState: { type: 'string', pattern: '^[A-Z]{2}$' },
      phone: { type: 'string', format: 'phone-ext' },
      email: { type: 'string', format: 'email' },
      organization: { type: 'string' }
    },
    required: ['npi', 'firstName', 'lastName', 'specialty', 'licenseNumber', 'licenseState'],
    additionalProperties: false
  },

  // Prescription
  prescription: {
    type: 'object',
    properties: {
      id: { type: 'string', format: 'fhir-id' },
      patientId: { type: 'string', format: 'fhir-id' },
      providerId: { type: 'string', format: 'fhir-id' },
      medicationName: { type: 'string', minLength: 2, maxLength: 200 },
      rxnorm: { type: 'string', format: 'rxnorm' },
      dosage: { type: 'string', validDosage: true },
      frequency: { type: 'string', maxLength: 100 },
      route: { type: 'string', enum: ['oral', 'topical', 'injection', 'inhalation', 'rectal', 'ophthalmic', 'otic'] },
      quantity: { type: 'integer', minimum: 1, maximum: 9999 },
      refills: { type: 'integer', minimum: 0, maximum: 12 },
      instructions: { type: 'string', maxLength: 500 },
      startDate: { type: 'string', format: 'date' },
      endDate: { type: 'string', format: 'date' },
      status: { type: 'string', enum: ['active', 'completed', 'cancelled', 'on_hold', 'expired'] },
      prescribedAt: { type: 'string', format: 'date-time' }
    },
    required: ['patientId', 'providerId', 'medicationName', 'dosage', 'frequency', 'quantity', 'status'],
    additionalProperties: false
  },

  // Lab Result
  labResult: {
    type: 'object',
    properties: {
      id: { type: 'string', format: 'fhir-id' },
      patientId: { type: 'string', format: 'fhir-id' },
      orderedBy: { type: 'string', format: 'fhir-id' },
      performedBy: { type: 'string' },
      testName: { type: 'string', minLength: 2, maxLength: 200 },
      loinc: { type: 'string', format: 'loinc' },
      value: { type: 'string', maxLength: 100 },
      unit: { type: 'string', maxLength: 20 },
      referenceRange: { type: 'string', maxLength: 100 },
      interpretation: { type: 'string', enum: ['normal', 'abnormal', 'critical', 'inconclusive'] },
      status: { type: 'string', enum: ['pending', 'preliminary', 'final', 'amended', 'cancelled'] },
      collectionDate: { type: 'string', format: 'date-time' },
      resultDate: { type: 'string', format: 'date-time' },
      notes: { type: 'string', maxLength: 1000 }
    },
    required: ['patientId', 'orderedBy', 'testName', 'value', 'status', 'collectionDate'],
    additionalProperties: false
  },

  // Vital Signs
  vitalSigns: {
    type: 'object',
    properties: {
      patientId: { type: 'string', format: 'fhir-id' },
      recordedBy: { type: 'string', format: 'fhir-id' },
      recordedAt: { type: 'string', format: 'date-time' },
      bloodPressure: {
        type: 'object',
        properties: {
          systolic: { type: 'integer', minimum: 50, maximum: 300 },
          diastolic: { type: 'integer', minimum: 30, maximum: 200 }
        },
        required: ['systolic', 'diastolic']
      },
      heartRate: { type: 'integer', minimum: 30, maximum: 300 },
      respiratoryRate: { type: 'integer', minimum: 5, maximum: 60 },
      temperature: {
        type: 'object',
        properties: {
          value: { type: 'number', minimum: 32, maximum: 45 },
          unit: { type: 'string', enum: ['celsius', 'fahrenheit'] }
        },
        required: ['value', 'unit']
      },
      oxygenSaturation: { type: 'integer', minimum: 0, maximum: 100 },
      weight: {
        type: 'object',
        properties: {
          value: { type: 'number', minimum: 0, maximum: 1000 },
          unit: { type: 'string', enum: ['kg', 'lb'] }
        },
        required: ['value', 'unit']
      },
      height: {
        type: 'object',
        properties: {
          value: { type: 'number', minimum: 0, maximum: 300 },
          unit: { type: 'string', enum: ['cm', 'in'] }
        },
        required: ['value', 'unit']
      },
      bmi: { type: 'number', minimum: 10, maximum: 100 }
    },
    required: ['patientId', 'recordedBy', 'recordedAt'],
    additionalProperties: false
  },

  // Appointment
  appointment: {
    type: 'object',
    properties: {
      id: { type: 'string', format: 'fhir-id' },
      patientId: { type: 'string', format: 'fhir-id' },
      providerId: { type: 'string', format: 'fhir-id' },
      scheduledStart: { type: 'string', format: 'date-time' },
      scheduledEnd: { type: 'string', format: 'date-time' },
      actualStart: { type: 'string', format: 'date-time' },
      actualEnd: { type: 'string', format: 'date-time' },
      type: { type: 'string', enum: ['routine', 'follow_up', 'urgent', 'emergency', 'telemedicine'] },
      status: { type: 'string', enum: ['scheduled', 'confirmed', 'arrived', 'in_progress', 'completed', 'cancelled', 'no_show'] },
      reason: { type: 'string', maxLength: 200 },
      notes: { type: 'string', maxLength: 1000 },
      location: { type: 'string', maxLength: 200 }
    },
    required: ['patientId', 'providerId', 'scheduledStart', 'scheduledEnd', 'type', 'status'],
    additionalProperties: false,
    dateRange: { start: 'scheduledStart', end: 'scheduledEnd' }
  }
};

/**
 * Schema registry for managing schemas
 */
export class SchemaRegistry {
  private static schemas: Map<string, any> = new Map();
  private static validator: SchemaValidator = new SchemaValidator();

  /**
   * Register a schema
   */
  static register(name: string, schema: any): void {
    this.schemas.set(name, schema);
    this.validator.addSchema(name, schema);
  }

  /**
   * Get a schema
   */
  static get(name: string): any | undefined {
    return this.schemas.get(name);
  }

  /**
   * Validate against a registered schema
   */
  static validate(data: any, schemaName: string): SchemaValidationResult {
    return this.validator.validate(data, schemaName);
  }

  /**
   * List all registered schemas
   */
  static list(): string[] {
    return Array.from(this.schemas.keys());
  }

  /**
   * Initialize with default schemas
   */
  static initialize(): void {
    // Register common schemas
    for (const [name, schema] of Object.entries(CommonJSONSchemas)) {
      this.register(`common.${name}`, schema);
    }

    // Register healthcare schemas
    for (const [name, schema] of Object.entries(HealthcareJSONSchemas)) {
      this.register(`healthcare.${name}`, schema);
    }
  }
}

// Initialize schema registry
SchemaRegistry.initialize();

// Export convenience functions
export const createValidator = (options?: SchemaValidationOptions) => new SchemaValidator(options);
export const validateSchema = (data: any, schema: any) => new SchemaValidator().validate(data, schema);
export const registerSchema = SchemaRegistry.register.bind(SchemaRegistry);
export const validateWithRegistry = SchemaRegistry.validate.bind(SchemaRegistry);
