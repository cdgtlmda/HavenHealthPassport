import { OfflineOperation, SyncableEntity } from './types';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export class ValidationUtils {
  /**
   * Validate offline operation
   */
  static validateOperation(operation: OfflineOperation): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Required fields
    if (!operation.id) errors.push('Operation ID is required');
    if (!operation.type) errors.push('Operation type is required');
    if (!operation.entity) errors.push('Entity type is required');
    if (!operation.entityId) errors.push('Entity ID is required');
    if (typeof operation.timestamp !== 'number') errors.push('Valid timestamp is required');

    // Type validation
    if (!['create', 'update', 'delete'].includes(operation.type)) {
      errors.push('Invalid operation type');
    }

    // Data validation based on operation type
    if (operation.type === 'create' || operation.type === 'update') {
      if (!operation.data) {
        errors.push('Data is required for create/update operations');
      }
    }

    // Retry validation
    if (operation.retryCount < 0) errors.push('Retry count cannot be negative');
    if (operation.maxRetries < 0) errors.push('Max retries cannot be negative');
    if (operation.retryCount > operation.maxRetries) {
      warnings.push('Retry count exceeds max retries');
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * Validate syncable entity
   */
  static validateEntity(entity: SyncableEntity): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Required fields
    if (!entity.id) errors.push('Entity ID is required');
    if (typeof entity.version !== 'number') errors.push('Version number is required');
    if (typeof entity.lastModified !== 'number') errors.push('Last modified timestamp is required');
    // Version validation
    if (entity.version < 0) errors.push('Version cannot be negative');

    // Timestamp validation
    if (entity.lastModified > Date.now()) {
      warnings.push('Last modified timestamp is in the future');
    }

    // Deleted flag validation
    if (entity._deleted && entity._localOnly) {
      warnings.push('Entity is marked as both deleted and local-only');
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * Validate data integrity
   */
  static validateDataIntegrity(data: any, checksum?: string): boolean {
    if (!checksum) return true;
    
    const calculatedChecksum = this.calculateChecksum(data);
    return calculatedChecksum === checksum;
  }

  /**
   * Calculate checksum for data
   */
  static calculateChecksum(data: any): string {
    const str = typeof data === 'string' ? data : JSON.stringify(data);
    
    // Simple checksum implementation
    // In production, use crypto library
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    
    return Math.abs(hash).toString(16);
  }

  /**
   * Validate field types
   */
  static validateFieldTypes(
    data: any,
    schema: { [field: string]: string }
  ): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    Object.entries(schema).forEach(([field, expectedType]) => {
      const value = data[field];
      const actualType = Array.isArray(value) ? 'array' : typeof value;
      
      if (value !== undefined && actualType !== expectedType) {
        errors.push(`Field '${field}' should be ${expectedType} but is ${actualType}`);
      }
    });

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }
}

export default ValidationUtils;