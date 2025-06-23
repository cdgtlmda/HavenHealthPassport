import { ReactNativeMigrationTool } from './ReactNativeMigrationTool';
import { WebMigrationTool } from './WebMigrationTool';
import { PlatformMigrationTool } from './types';
import { getStorageAdapter, getSecurityAdapter } from '../adapters';

/**
 * Factory function to get the appropriate migration tool for the current platform
 */
export function getMigrationTool(): PlatformMigrationTool {
  const storageAdapter = getStorageAdapter();
  const securityAdapter = getSecurityAdapter();

  if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    // Web environment
    return new WebMigrationTool(storageAdapter, securityAdapter);
  } else {
    // React Native environment
    return new ReactNativeMigrationTool(storageAdapter, securityAdapter);
  }
}

/**
 * Helper to create a cross-platform migration package
 */
export async function createCrossPlatformPackage(
  data: Record<string, any>,
  sourcePlatform: 'react-native' | 'web'
): Promise<string> {
  const migrationTool = getMigrationTool();
  const cryptoAdapter = getSecurityAdapter();
  
  const packageData = {
    version: '1.0.0',
    sourcePlatform,
    timestamp: Date.now(),
    data,
    checksum: await cryptoAdapter.hash(JSON.stringify(data))
  };
  
  return JSON.stringify(packageData);
}

/**
 * Helper to validate a migration package
 */
export async function validateMigrationPackage(packageString: string): Promise<boolean> {
  try {
    const packageData = JSON.parse(packageString);
    const cryptoAdapter = getSecurityAdapter();
    
    const calculatedChecksum = await cryptoAdapter.hash(JSON.stringify(packageData.data));
    return calculatedChecksum === packageData.checksum;
  } catch (error) {
    console.error('Package validation failed:', error);
    return false;
  }
}

export { ReactNativeMigrationTool, WebMigrationTool };
export * from './types';