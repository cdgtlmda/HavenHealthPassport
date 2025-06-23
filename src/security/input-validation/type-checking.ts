/**
 * Type Checking and Validation
 * Runtime type checking for input validation
 */

/**
 * Type definitions for validation
 */
export type ValidationType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'object'
  | 'array'
  | 'date'
  | 'email'
  | 'url'
  | 'uuid'
  | 'json'
  | 'base64'
  | 'hex'
  | 'alphanumeric'
  | 'alpha'
  | 'numeric'
  | 'integer'
  | 'float'
  | 'positive'
  | 'negative'
  | 'percentage'
  | 'creditCard'
  | 'phone'
  | 'postalCode'
  | 'ipAddress'
  | 'macAddress'
  | 'domain'
  | 'slug'
  | 'jwt'
  | 'dataUri'
  | 'mimeType'
  | 'semver'
  | 'latitude'
  | 'longitude'
  | 'port'
  | 'mongoId'
  | 'md5'
  | 'sha1'
  | 'sha256'
  | 'sha512'
  | 'isbn'
  | 'issn'
  | 'isin'
  | 'iban'
  | 'bic'
  | 'locale'
  | 'currency'
  | 'fqdn';

/**
 * Type validation options
 */
export interface TypeValidationOptions {
  required?: boolean;
  nullable?: boolean;
  allowEmpty?: boolean;
  coerce?: boolean;
  strict?: boolean;
  customValidator?: (value: any) => boolean;
  customError?: string;
}

/**
 * Type validator class
 */
export class TypeValidator {
  /**
   * Check if value is of specified type
   */
  static isType(value: any, type: ValidationType, options: TypeValidationOptions = {}): boolean {
    // Handle null/undefined
    if (value === null || value === undefined) {
      return options.nullable === true;
    }

    // Handle empty values
    if (value === '' && !options.allowEmpty) {
      return false;
    }

    // Coerce types if requested
    if (options.coerce) {
      value = this.coerceType(value, type);
    }

    // Perform type checking
    switch (type) {
      case 'string':
        return typeof value === 'string';

      case 'number':
        return typeof value === 'number' && !isNaN(value);

      case 'boolean':
        return typeof value === 'boolean';

      case 'object':
        return typeof value === 'object' && value !== null && !Array.isArray(value);

      case 'array':
        return Array.isArray(value);

      case 'date':
        return value instanceof Date && !isNaN(value.getTime());

      case 'email':
        return this.isEmail(value);

      case 'url':
        return this.isURL(value);

      case 'uuid':
        return this.isUUID(value);

      case 'json':
        return this.isJSON(value);

      case 'base64':
        return this.isBase64(value);

      case 'hex':
        return this.isHex(value);

      case 'alphanumeric':
        return this.isAlphanumeric(value);

      case 'alpha':
        return this.isAlpha(value);

      case 'numeric':
        return this.isNumeric(value);

      case 'integer':
        return this.isInteger(value);

      case 'float':
        return this.isFloat(value);

      case 'positive':
        return this.isPositive(value);

      case 'negative':
        return this.isNegative(value);

      case 'percentage':
        return this.isPercentage(value);

      case 'creditCard':
        return this.isCreditCard(value);

      case 'phone':
        return this.isPhone(value);

      case 'postalCode':
        return this.isPostalCode(value);

      case 'ipAddress':
        return this.isIPAddress(value);

      case 'macAddress':
        return this.isMACAddress(value);

      case 'domain':
        return this.isDomain(value);

      case 'slug':
        return this.isSlug(value);

      case 'jwt':
        return this.isJWT(value);

      case 'dataUri':
        return this.isDataURI(value);

      case 'mimeType':
        return this.isMimeType(value);

      case 'semver':
        return this.isSemVer(value);

      case 'latitude':
        return this.isLatitude(value);

      case 'longitude':
        return this.isLongitude(value);

      case 'port':
        return this.isPort(value);

      case 'mongoId':
        return this.isMongoId(value);

      case 'md5':
        return this.isMD5(value);

      case 'sha1':
        return this.isSHA1(value);

      case 'sha256':
        return this.isSHA256(value);

      case 'sha512':
        return this.isSHA512(value);

      case 'isbn':
        return this.isISBN(value);

      case 'issn':
        return this.isISSN(value);

      case 'isin':
        return this.isISIN(value);

      case 'iban':
        return this.isIBAN(value);

      case 'bic':
        return this.isBIC(value);

      case 'locale':
        return this.isLocale(value);

      case 'currency':
        return this.isCurrency(value);

      case 'fqdn':
        return this.isFQDN(value);

      default:
        return false;
    }
  }

  /**
   * Validate with detailed error message
   */
  static validate(
    value: any,
    type: ValidationType,
    options: TypeValidationOptions = {}
  ): { valid: boolean; error?: string; coerced?: any } {
    // Check if required
    if (options.required && (value === null || value === undefined || value === '')) {
      return {
        valid: false,
        error: options.customError || `Value is required`
      };
    }

    // Perform type validation
    const valid = this.isType(value, type, options);

    if (!valid) {
      return {
        valid: false,
        error: options.customError || `Value must be a valid ${type}`
      };
    }

    // Custom validation
    if (options.customValidator && !options.customValidator(value)) {
      return {
        valid: false,
        error: options.customError || `Value failed custom validation`
      };
    }

    // Return success with coerced value if applicable
    const result: any = { valid: true };
    if (options.coerce) {
      result.coerced = this.coerceType(value, type);
    }

    return result;
  }

  /**
   * Coerce value to type
   */
  static coerceType(value: any, type: ValidationType): any {
    switch (type) {
      case 'string':
        return String(value);

      case 'number':
      case 'integer':
      case 'float':
        return Number(value);

      case 'boolean':
        return Boolean(value);

      case 'date':
        return new Date(value);

      case 'array':
        return Array.isArray(value) ? value : [value];

      case 'object':
        return typeof value === 'object' ? value : {};

      default:
        return value;
    }
  }

  // Individual type checking methods
  private static isEmail(value: any): boolean {
    if (typeof value !== 'string') return false;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value);
  }

  private static isURL(value: any): boolean {
    if (typeof value !== 'string') return false;
    try {
      new URL(value);
      return true;
    } catch {
      return false;
    }
  }

  private static isUUID(value: any): boolean {
    if (typeof value !== 'string') return false;
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(value);
  }

  private static isJSON(value: any): boolean {
    if (typeof value !== 'string') return false;
    try {
      JSON.parse(value);
      return true;
    } catch {
      return false;
    }
  }

  private static isBase64(value: any): boolean {
    if (typeof value !== 'string') return false;
    const base64Regex = /^[A-Za-z0-9+/]+=*$/;
    return base64Regex.test(value) && value.length % 4 === 0;
  }

  private static isHex(value: any): boolean {
    if (typeof value !== 'string') return false;
    const hexRegex = /^[0-9a-fA-F]+$/;
    return hexRegex.test(value);
  }

  private static isAlphanumeric(value: any): boolean {
    if (typeof value !== 'string') return false;
    const alphanumericRegex = /^[a-zA-Z0-9]+$/;
    return alphanumericRegex.test(value);
  }

  private static isAlpha(value: any): boolean {
    if (typeof value !== 'string') return false;
    const alphaRegex = /^[a-zA-Z]+$/;
    return alphaRegex.test(value);
  }

  private static isNumeric(value: any): boolean {
    if (typeof value !== 'string' && typeof value !== 'number') return false;
    const numericRegex = /^[0-9]+$/;
    return numericRegex.test(String(value));
  }

  private static isInteger(value: any): boolean {
    return Number.isInteger(Number(value));
  }

  private static isFloat(value: any): boolean {
    const num = Number(value);
    return !isNaN(num) && !Number.isInteger(num);
  }

  private static isPositive(value: any): boolean {
    const num = Number(value);
    return !isNaN(num) && num > 0;
  }

  private static isNegative(value: any): boolean {
    const num = Number(value);
    return !isNaN(num) && num < 0;
  }

  private static isPercentage(value: any): boolean {
    const num = Number(value);
    return !isNaN(num) && num >= 0 && num <= 100;
  }

  private static isCreditCard(value: any): boolean {
    if (typeof value !== 'string') return false;
    const cleaned = value.replace(/\s/g, '');
    const creditCardRegex = /^[0-9]{13,19}$/;
    if (!creditCardRegex.test(cleaned)) return false;

    // Luhn algorithm
    let sum = 0;
    let isEven = false;
    for (let i = cleaned.length - 1; i >= 0; i--) {
      let digit = parseInt(cleaned[i], 10);
      if (isEven) {
        digit *= 2;
        if (digit > 9) digit -= 9;
      }
      sum += digit;
      isEven = !isEven;
    }
    return sum % 10 === 0;
  }

  private static isPhone(value: any): boolean {
    if (typeof value !== 'string') return false;
    const phoneRegex = /^[+]?[(]?[0-9]{1,4}[)]?[-\s.]?[(]?[0-9]{1,4}[)]?[-\s.]?[0-9]{1,9}$/;
    return phoneRegex.test(value);
  }

  private static isPostalCode(value: any, locale: string = 'any'): boolean {
    if (typeof value !== 'string') return false;
    const postalPatterns: Record<string, RegExp> = {
      US: /^\d{5}(-\d{4})?$/,
      CA: /^[A-Z]\d[A-Z]\s?\d[A-Z]\d$/i,
      UK: /^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$/i,
      any: /^[A-Z0-9\s-]{3,10}$/i
    };
    const pattern = postalPatterns[locale] || postalPatterns.any;
    return pattern.test(value);
  }

  private static isIPAddress(value: any): boolean {
    if (typeof value !== 'string') return false;
    const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    const ipv6Regex = /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|::|:([0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}|(([0-9a-fA-F]{1,4}:){1,7}|:):)$/;
    return ipv4Regex.test(value) || ipv6Regex.test(value);
  }

  private static isMACAddress(value: any): boolean {
    if (typeof value !== 'string') return false;
    const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
    return macRegex.test(value);
  }

  private static isDomain(value: any): boolean {
    if (typeof value !== 'string') return false;
    const domainRegex = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i;
    return domainRegex.test(value);
  }

  private static isSlug(value: any): boolean {
    if (typeof value !== 'string') return false;
    const slugRegex = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
    return slugRegex.test(value);
  }

  private static isJWT(value: any): boolean {
    if (typeof value !== 'string') return false;
    const jwtRegex = /^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$/;
    return jwtRegex.test(value);
  }

  private static isDataURI(value: any): boolean {
    if (typeof value !== 'string') return false;
    const dataUriRegex = /^data:([a-z]+\/[a-z0-9-+.]+)?(?:;([a-z-]+=[a-z0-9-]+))*;base64,([a-z0-9!$&',()*+;=\-._~:@/?%\s]*?)$/i;
    return dataUriRegex.test(value);
  }

  private static isMimeType(value: any): boolean {
    if (typeof value !== 'string') return false;
    const mimeRegex = /^[a-z]+\/[a-z0-9\-+.]+$/i;
    return mimeRegex.test(value);
  }

  private static isSemVer(value: any): boolean {
    if (typeof value !== 'string') return false;
    const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/;
    return semverRegex.test(value);
  }

  private static isLatitude(value: any): boolean {
    const num = Number(value);
    return !isNaN(num) && num >= -90 && num <= 90;
  }

  private static isLongitude(value: any): boolean {
    const num = Number(value);
    return !isNaN(num) && num >= -180 && num <= 180;
  }

  private static isPort(value: any): boolean {
    const num = Number(value);
    return Number.isInteger(num) && num >= 0 && num <= 65535;
  }

  private static isMongoId(value: any): boolean {
    if (typeof value !== 'string') return false;
    const mongoIdRegex = /^[0-9a-fA-F]{24}$/;
    return mongoIdRegex.test(value);
  }

  private static isMD5(value: any): boolean {
    if (typeof value !== 'string') return false;
    const md5Regex = /^[a-f0-9]{32}$/i;
    return md5Regex.test(value);
  }

  private static isSHA1(value: any): boolean {
    if (typeof value !== 'string') return false;
    const sha1Regex = /^[a-f0-9]{40}$/i;
    return sha1Regex.test(value);
  }

  private static isSHA256(value: any): boolean {
    if (typeof value !== 'string') return false;
    const sha256Regex = /^[a-f0-9]{64}$/i;
    return sha256Regex.test(value);
  }

  private static isSHA512(value: any): boolean {
    if (typeof value !== 'string') return false;
    const sha512Regex = /^[a-f0-9]{128}$/i;
    return sha512Regex.test(value);
  }

  private static isISBN(value: any): boolean {
    if (typeof value !== 'string') return false;
    const isbn10Regex = /^(?:\d{9}X|\d{10})$/;
    const isbn13Regex = /^(?:\d{13})$/;
    return isbn10Regex.test(value) || isbn13Regex.test(value);
  }

  private static isISSN(value: any): boolean {
    if (typeof value !== 'string') return false;
    const issnRegex = /^\d{4}-?\d{3}[\dX]$/;
    return issnRegex.test(value);
  }

  private static isISIN(value: any): boolean {
    if (typeof value !== 'string') return false;
    const isinRegex = /^[A-Z]{2}[A-Z0-9]{9}\d$/;
    return isinRegex.test(value);
  }

  private static isIBAN(value: any): boolean {
    if (typeof value !== 'string') return false;
    const ibanRegex = /^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$/;
    return ibanRegex.test(value);
  }

  private static isBIC(value: any): boolean {
    if (typeof value !== 'string') return false;
    const bicRegex = /^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$/;
    return bicRegex.test(value);
  }

  private static isLocale(value: any): boolean {
    if (typeof value !== 'string') return false;
    const localeRegex = /^[a-z]{2,3}(?:-[A-Z]{2,3}(?:-[a-zA-Z]{4})?)?$/;
    return localeRegex.test(value);
  }

  private static isCurrency(value: any): boolean {
    if (typeof value !== 'string') return false;
    const currencyRegex = /^[A-Z]{3}$/;
    return currencyRegex.test(value);
  }

  private static isFQDN(value: any): boolean {
    if (typeof value !== 'string') return false;
    const fqdnRegex = /^(?!:\/\/)(?=.{1,255}$)((.{1,63}\.){1,127}(?![0-9]*$)[a-z0-9-]+\.?)$/i;
    return fqdnRegex.test(value);
  }
}

/**
 * Type schema for complex validation
 */
export interface TypeSchema {
  type: ValidationType;
  options?: TypeValidationOptions;
  properties?: Record<string, TypeSchema>; // For objects
  items?: TypeSchema; // For arrays
  enum?: any[]; // Allowed values
  min?: number; // For numbers
  max?: number; // For numbers
  minLength?: number; // For strings
  maxLength?: number; // For strings
  pattern?: RegExp; // For strings
}

/**
 * Schema validator
 */
export class SchemaValidator {
  /**
   * Validate value against schema
   */
  static validate(value: any, schema: TypeSchema): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Validate type
    const typeResult = TypeValidator.validate(value, schema.type, schema.options);
    if (!typeResult.valid) {
      errors.push(typeResult.error || 'Type validation failed');
      return { valid: false, errors };
    }

    // Use coerced value if available
    if (typeResult.coerced !== undefined) {
      value = typeResult.coerced;
    }

    // Validate enum
    if (schema.enum && !schema.enum.includes(value)) {
      errors.push(`Value must be one of: ${schema.enum.join(', ')}`);
    }

    // String validations
    if (schema.type === 'string' && typeof value === 'string') {
      if (schema.minLength !== undefined && value.length < schema.minLength) {
        errors.push(`String must be at least ${schema.minLength} characters`);
      }
      if (schema.maxLength !== undefined && value.length > schema.maxLength) {
        errors.push(`String must not exceed ${schema.maxLength} characters`);
      }
      if (schema.pattern && !schema.pattern.test(value)) {
        errors.push(`String does not match required pattern`);
      }
    }

    // Number validations
    if ((schema.type === 'number' || schema.type === 'integer') && typeof value === 'number') {
      if (schema.min !== undefined && value < schema.min) {
        errors.push(`Number must be at least ${schema.min}`);
      }
      if (schema.max !== undefined && value > schema.max) {
        errors.push(`Number must not exceed ${schema.max}`);
      }
    }

    // Object validations
    if (schema.type === 'object' && schema.properties && typeof value === 'object') {
      for (const [key, propSchema] of Object.entries(schema.properties)) {
        const propResult = this.validate(value[key], propSchema);
        if (!propResult.valid) {
          errors.push(...propResult.errors.map(e => `${key}: ${e}`));
        }
      }
    }

    // Array validations
    if (schema.type === 'array' && schema.items && Array.isArray(value)) {
      for (let i = 0; i < value.length; i++) {
        const itemResult = this.validate(value[i], schema.items);
        if (!itemResult.valid) {
          errors.push(...itemResult.errors.map(e => `[${i}]: ${e}`));
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// Export convenience functions
export const isType = TypeValidator.isType;
export const validateType = TypeValidator.validate;
export const coerceType = TypeValidator.coerceType;
export const validateSchema = SchemaValidator.validate;
