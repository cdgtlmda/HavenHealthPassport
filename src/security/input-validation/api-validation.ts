/**
 * API Validation
 * Comprehensive API request and response validation
 */

import Joi from 'joi';
import { Request, Response, NextFunction } from 'express';
import { InputSanitizer } from './sanitizer';
import { LengthValidator } from './length-limits';
import { TypeValidator } from './type-checking';
import { AllowlistValidator } from './allowlists';
import { RegexValidator } from './regex-patterns';

/**
 * API validation options
 */
export interface APIValidationOptions {
  sanitize?: boolean;
  stripUnknown?: boolean;
  allowUnknown?: boolean;
  abortEarly?: boolean;
  context?: any;
  presence?: 'required' | 'optional' | 'forbidden';
  convert?: boolean;
  validateHeaders?: boolean;
  validateQuery?: boolean;
  validateParams?: boolean;
  validateBody?: boolean;
  validateResponse?: boolean;
  maxDepth?: number;
  maxKeys?: number;
  customValidators?: Record<string, (value: any) => boolean>;
}

/**
 * Validation error details
 */
export interface ValidationError {
  field: string;
  message: string;
  value?: any;
  type: string;
  context?: any;
}

/**
 * API validator class
 */
export class APIValidator {
  private static readonly DEFAULT_OPTIONS: APIValidationOptions = {
    sanitize: true,
    stripUnknown: true,
    allowUnknown: false,
    abortEarly: false,
    convert: true,
    validateHeaders: true,
    validateQuery: true,
    validateParams: true,
    validateBody: true,
    validateResponse: false,
    maxDepth: 10,
    maxKeys: 1000
  };

  /**
   * Create validation middleware
   */
  static validate(schema: {
    headers?: Joi.Schema;
    query?: Joi.Schema;
    params?: Joi.Schema;
    body?: Joi.Schema;
    response?: Joi.Schema;
  }, options: APIValidationOptions = {}) {
    const opts = { ...this.DEFAULT_OPTIONS, ...options };

    return async (req: Request, res: Response, next: NextFunction) => {
      const errors: ValidationError[] = [];

      try {
        // Check request depth and size
        if (opts.maxDepth) {
          const depth = this.getObjectDepth(req.body);
          if (depth > opts.maxDepth) {
            errors.push({
              field: 'body',
              message: `Request exceeds maximum depth of ${opts.maxDepth}`,
              type: 'depth',
              value: depth
            });
          }
        }

        if (opts.maxKeys) {
          const keys = this.countKeys(req.body);
          if (keys > opts.maxKeys) {
            errors.push({
              field: 'body',
              message: `Request exceeds maximum key count of ${opts.maxKeys}`,
              type: 'size',
              value: keys
            });
          }
        }

        // Validate headers
        if (opts.validateHeaders && schema.headers) {
          const headerErrors = await this.validateSection(
            req.headers,
            schema.headers,
            'headers',
            opts
          );
          errors.push(...headerErrors);
        }

        // Validate query parameters
        if (opts.validateQuery && schema.query) {
          const queryErrors = await this.validateSection(
            req.query,
            schema.query,
            'query',
            opts
          );
          errors.push(...queryErrors);
        }

        // Validate URL parameters
        if (opts.validateParams && schema.params) {
          const paramErrors = await this.validateSection(
            req.params,
            schema.params,
            'params',
            opts
          );
          errors.push(...paramErrors);
        }

        // Validate request body
        if (opts.validateBody && schema.body) {
          const bodyErrors = await this.validateSection(
            req.body,
            schema.body,
            'body',
            opts
          );
          errors.push(...bodyErrors);
        }

        // If errors found, return validation error response
        if (errors.length > 0) {
          return res.status(400).json({
            error: 'Validation failed',
            details: errors
          });
        }

        // If response validation is enabled, override res.json
        if (opts.validateResponse && schema.response) {
          const originalJson = res.json.bind(res);
          res.json = function(data: any) {
            const responseErrors = APIValidator.validateSection(
              data,
              schema.response!,
              'response',
              opts
            );

            if (responseErrors.length > 0) {
              console.error('Response validation failed:', responseErrors);
              return originalJson({
                error: 'Internal server error',
                message: 'Response validation failed'
              });
            }

            return originalJson(data);
          };
        }

        next();
      } catch (error) {
        console.error('Validation error:', error);
        res.status(500).json({
          error: 'Internal server error',
          message: 'Validation failed'
        });
      }
    };
  }

  /**
   * Validate a section of the request
   */
  private static validateSection(
    data: any,
    schema: Joi.Schema,
    section: string,
    options: APIValidationOptions
  ): ValidationError[] {
    const errors: ValidationError[] = [];

    // Sanitize input if enabled
    if (options.sanitize) {
      data = this.sanitizeData(data);
    }

    // Validate with Joi
    const result = schema.validate(data, {
      abortEarly: options.abortEarly,
      stripUnknown: options.stripUnknown,
      allowUnknown: options.allowUnknown,
      convert: options.convert,
      presence: options.presence,
      context: options.context
    });

    if (result.error) {
      for (const detail of result.error.details) {
        errors.push({
          field: `${section}.${detail.path.join('.')}`,
          message: detail.message,
          value: detail.context?.value,
          type: detail.type
        });
      }
    }

    return errors;
  }

  /**
   * Sanitize data recursively
   */
  private static sanitizeData(data: any): any {
    if (typeof data === 'string') {
      return InputSanitizer.sanitizeString(data);
    }

    if (Array.isArray(data)) {
      return data.map(item => this.sanitizeData(item));
    }

    if (data && typeof data === 'object') {
      const sanitized: any = {};
      for (const [key, value] of Object.entries(data)) {
        const sanitizedKey = InputSanitizer.sanitizeString(key);
        sanitized[sanitizedKey] = this.sanitizeData(value);
      }
      return sanitized;
    }

    return data;
  }

  /**
   * Get object depth
   */
  private static getObjectDepth(obj: any, currentDepth: number = 0): number {
    if (!obj || typeof obj !== 'object') {
      return currentDepth;
    }

    let maxDepth = currentDepth;

    for (const value of Object.values(obj)) {
      if (value && typeof value === 'object') {
        const depth = this.getObjectDepth(value, currentDepth + 1);
        maxDepth = Math.max(maxDepth, depth);
      }
    }

    return maxDepth;
  }

  /**
   * Count total keys in object
   */
  private static countKeys(obj: any): number {
    if (!obj || typeof obj !== 'object') {
      return 0;
    }

    let count = Object.keys(obj).length;

    for (const value of Object.values(obj)) {
      if (value && typeof value === 'object') {
        count += this.countKeys(value);
      }
    }

    return count;
  }
}

/**
 * Common validation schemas
 */
export const CommonSchemas = {
  // ID validations
  id: Joi.string().alphanum().length(24).required(),
  uuid: Joi.string().uuid({ version: 'uuidv4' }).required(),

  // String validations
  email: Joi.string().email().lowercase().max(254).required(),
  phone: Joi.string().pattern(/^[+]?[(]?[0-9]{1,4}[)]?[-\s.]?[(]?[0-9]{1,4}[)]?[-\s.]?[0-9]{1,9}$/).required(),
  url: Joi.string().uri().required(),

  // Healthcare validations
  mrn: Joi.string().pattern(/^[A-Z0-9]{6,20}$/).required(),
  npi: Joi.string().pattern(/^[1-9]\d{9}$/).required(),
  icd10: Joi.string().pattern(/^[A-Z]\d{2}(?:\.\d{1,4})?$/).required(),

  // Pagination
  page: Joi.number().integer().min(1).default(1),
  limit: Joi.number().integer().min(1).max(100).default(20),
  sort: Joi.string().valid('asc', 'desc').default('asc'),

  // Date validations
  date: Joi.date().iso().required(),
  dateRange: Joi.object({
    start: Joi.date().iso().required(),
    end: Joi.date().iso().greater(Joi.ref('start')).required()
  }),

  // Common objects
  address: Joi.object({
    street: Joi.string().max(100).required(),
    city: Joi.string().max(50).required(),
    state: Joi.string().length(2).uppercase().required(),
    postalCode: Joi.string().pattern(/^\d{5}(-\d{4})?$/).required(),
    country: Joi.string().length(2).uppercase().default('US')
  }),

  // File upload
  file: Joi.object({
    fieldname: Joi.string().required(),
    originalname: Joi.string().max(255).required(),
    mimetype: Joi.string().required(),
    size: Joi.number().max(10 * 1024 * 1024).required() // 10MB
  })
};

/**
 * Schema builder for common patterns
 */
export class SchemaBuilder {
  private schema: any = {};

  /**
   * Add field to schema
   */
  field(name: string, validator: Joi.Schema): SchemaBuilder {
    this.schema[name] = validator;
    return this;
  }

  /**
   * Add required string field
   */
  requiredString(name: string, options?: {
    min?: number;
    max?: number;
    pattern?: RegExp;
    lowercase?: boolean;
    uppercase?: boolean;
    trim?: boolean;
  }): SchemaBuilder {
    let validator = Joi.string().required();

    if (options?.min) validator = validator.min(options.min);
    if (options?.max) validator = validator.max(options.max);
    if (options?.pattern) validator = validator.pattern(options.pattern);
    if (options?.lowercase) validator = validator.lowercase();
    if (options?.uppercase) validator = validator.uppercase();
    if (options?.trim) validator = validator.trim();

    this.schema[name] = validator;
    return this;
  }

  /**
   * Add optional string field
   */
  optionalString(name: string, options?: any): SchemaBuilder {
    this.requiredString(name, options);
    this.schema[name] = this.schema[name].optional();
    return this;
  }

  /**
   * Add required number field
   */
  requiredNumber(name: string, options?: {
    min?: number;
    max?: number;
    integer?: boolean;
    positive?: boolean;
    negative?: boolean;
  }): SchemaBuilder {
    let validator = Joi.number().required();

    if (options?.min !== undefined) validator = validator.min(options.min);
    if (options?.max !== undefined) validator = validator.max(options.max);
    if (options?.integer) validator = validator.integer();
    if (options?.positive) validator = validator.positive();
    if (options?.negative) validator = validator.negative();

    this.schema[name] = validator;
    return this;
  }

  /**
   * Add optional number field
   */
  optionalNumber(name: string, options?: any): SchemaBuilder {
    this.requiredNumber(name, options);
    this.schema[name] = this.schema[name].optional();
    return this;
  }

  /**
   * Add required boolean field
   */
  requiredBoolean(name: string): SchemaBuilder {
    this.schema[name] = Joi.boolean().required();
    return this;
  }

  /**
   * Add optional boolean field
   */
  optionalBoolean(name: string): SchemaBuilder {
    this.schema[name] = Joi.boolean().optional();
    return this;
  }

  /**
   * Add required array field
   */
  requiredArray(name: string, items: Joi.Schema, options?: {
    min?: number;
    max?: number;
    unique?: boolean;
  }): SchemaBuilder {
    let validator = Joi.array().items(items).required();

    if (options?.min !== undefined) validator = validator.min(options.min);
    if (options?.max !== undefined) validator = validator.max(options.max);
    if (options?.unique) validator = validator.unique();

    this.schema[name] = validator;
    return this;
  }

  /**
   * Add optional array field
   */
  optionalArray(name: string, items: Joi.Schema, options?: any): SchemaBuilder {
    this.requiredArray(name, items, options);
    this.schema[name] = this.schema[name].optional();
    return this;
  }

  /**
   * Add required object field
   */
  requiredObject(name: string, schema: any): SchemaBuilder {
    this.schema[name] = Joi.object(schema).required();
    return this;
  }

  /**
   * Add optional object field
   */
  optionalObject(name: string, schema: any): SchemaBuilder {
    this.schema[name] = Joi.object(schema).optional();
    return this;
  }

  /**
   * Add enum field
   */
  enum(name: string, values: any[], required: boolean = true): SchemaBuilder {
    let validator = Joi.valid(...values);
    if (required) validator = validator.required();
    else validator = validator.optional();

    this.schema[name] = validator;
    return this;
  }

  /**
   * Add custom validator
   */
  custom(name: string, validator: Joi.Schema): SchemaBuilder {
    this.schema[name] = validator;
    return this;
  }

  /**
   * Build the schema
   */
  build(): Joi.Schema {
    return Joi.object(this.schema);
  }
}

/**
 * Healthcare-specific schemas
 */
export const HealthcareSchemas = {
  // Patient schema
  patient: new SchemaBuilder()
    .requiredString('firstName', { min: 1, max: 50 })
    .requiredString('lastName', { min: 1, max: 50 })
    .optionalString('middleName', { max: 50 })
    .requiredString('dateOfBirth')
    .enum('gender', ['male', 'female', 'other', 'unknown'])
    .requiredString('mrn', { pattern: /^[A-Z0-9]{6,20}$/ })
    .optionalString('ssn', { pattern: /^\d{3}-?\d{2}-?\d{4}$/ })
    .requiredObject('address', CommonSchemas.address)
    .requiredString('phone')
    .requiredString('email')
    .optionalString('emergencyContact')
    .optionalString('emergencyPhone')
    .build(),

  // Prescription schema
  prescription: new SchemaBuilder()
    .requiredString('patientId')
    .requiredString('providerId')
    .requiredString('medicationName')
    .requiredString('dosage')
    .requiredString('frequency')
    .requiredNumber('quantity', { min: 1, integer: true })
    .requiredNumber('refills', { min: 0, integer: true })
    .requiredString('instructions', { max: 500 })
    .optionalString('rxnorm')
    .requiredString('startDate')
    .optionalString('endDate')
    .enum('status', ['active', 'completed', 'cancelled', 'on_hold'])
    .build(),

  // Lab result schema
  labResult: new SchemaBuilder()
    .requiredString('patientId')
    .requiredString('orderedBy')
    .requiredString('testName')
    .requiredString('loinc')
    .requiredString('value')
    .requiredString('unit')
    .requiredString('referenceRange')
    .enum('status', ['normal', 'abnormal', 'critical'])
    .requiredString('collectionDate')
    .requiredString('resultDate')
    .optionalString('notes', { max: 1000 })
    .build(),

  // Appointment schema
  appointment: new SchemaBuilder()
    .requiredString('patientId')
    .requiredString('providerId')
    .requiredString('dateTime')
    .requiredNumber('duration', { min: 15, max: 480, integer: true })
    .enum('type', ['routine', 'follow_up', 'urgent', 'emergency'])
    .requiredString('reason', { max: 200 })
    .optionalString('notes', { max: 1000 })
    .enum('status', ['scheduled', 'confirmed', 'arrived', 'completed', 'cancelled', 'no_show'])
    .build()
};

/**
 * Request sanitizer middleware
 */
export function sanitizeRequest(options?: {
  sanitizeQuery?: boolean;
  sanitizeParams?: boolean;
  sanitizeBody?: boolean;
  sanitizeHeaders?: boolean;
}) {
  const opts = {
    sanitizeQuery: true,
    sanitizeParams: true,
    sanitizeBody: true,
    sanitizeHeaders: false,
    ...options
  };

  return (req: Request, res: Response, next: NextFunction) => {
    try {
      if (opts.sanitizeQuery && req.query) {
        req.query = APIValidator['sanitizeData'](req.query);
      }

      if (opts.sanitizeParams && req.params) {
        req.params = APIValidator['sanitizeData'](req.params);
      }

      if (opts.sanitizeBody && req.body) {
        req.body = APIValidator['sanitizeData'](req.body);
      }

      if (opts.sanitizeHeaders && req.headers) {
        // Be careful with headers - some should not be sanitized
        const safeHeaders = ['x-custom-header', 'x-api-version'];
        for (const header of safeHeaders) {
          if (req.headers[header] && typeof req.headers[header] === 'string') {
            req.headers[header] = InputSanitizer.sanitizeString(req.headers[header] as string);
          }
        }
      }

      next();
    } catch (error) {
      console.error('Sanitization error:', error);
      res.status(500).json({ error: 'Internal server error' });
    }
  };
}

// Export convenience functions
export const validate = APIValidator.validate.bind(APIValidator);
export const createSchema = () => new SchemaBuilder();
