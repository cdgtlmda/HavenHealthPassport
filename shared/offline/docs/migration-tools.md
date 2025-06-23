# Platform Migration Tools

## Overview

The platform migration tools enable secure and reliable data transfer between React Native and Web platforms in the Haven Health Passport system. These tools ensure data integrity, handle platform-specific data formats, and provide progress tracking during migration.

## Architecture

### Core Components

1. **BaseMigrationTool**: Abstract base class providing common migration functionality
2. **ReactNativeMigrationTool**: React Native specific implementation
3. **WebMigrationTool**: Web browser specific implementation
4. **MigrationFactory**: Automatic platform detection and tool selection

### Data Flow

```
Source Platform → Export Data → Migration Package → Validate → Import → Target Platform
```

## Usage

### Automatic Platform Detection

```typescript
import { getMigrationTool } from '@haven/offline/migration';

const migrationTool = getMigrationTool(); // Automatically selects the right tool
```

### React Native Migration

#### Export Data

```typescript
import { ReactNativeMigrationTool } from '@haven/offline/migration';

const tool = new ReactNativeMigrationTool(storageAdapter, cryptoAdapter);

// Export to shareable file
const filePath = await tool.exportToFile({
  includeSecureData: true,
  progressCallback: (progress) => {
    console.log(`${progress.stage}: ${progress.percentage}%`);
  }
});

// Export specific data for QR code
const qrData = await tool.exportToQRCode((key) => key.startsWith('critical_'));
```

#### Import Data

```typescript
// Import from file picker
const result = await tool.importFromFile({
  validateData: true,
  progressCallback: (progress) => {
    updateUI(progress);
  }
});

console.log(`Imported ${result.itemsImported} items`);
```

### Web Migration

#### Export Data

```typescript
import { WebMigrationTool } from '@haven/offline/migration';

const tool = new WebMigrationTool(storageAdapter, cryptoAdapter);

// Export with download dialog
await tool.exportToFile({
  includeMetadata: true
});

// Export with File System Access API (Chrome 86+)
await tool.exportWithFileSystemAccess();

// Export small data to clipboard
await tool.exportToClipboard((key) => key.includes('settings'));
```

#### Import Data

```typescript
// Import from file input
const result = await tool.importFromFile(); // Shows file picker

// Import from specific file
const file = fileInput.files[0];
const result = await tool.importFromFile(file);
```

## Migration Data Format

### Structure

```typescript
interface MigrationData {
  version: string;           // Migration format version
  platform: 'react-native' | 'web';  // Source platform
  timestamp: number;         // Export timestamp
  data: Record<string, any>; // Actual data
  metadata?: {               // Optional metadata
    deviceInfo?: any;
    appVersion: string;
    offlineDataVersion: string;
    encryptionMethod?: string;
    compressionMethod?: string;
  };
  checksum: string;          // Data integrity hash
}
```

### Data Transformations

The migration tools automatically handle platform-specific data transformations:

- **WatermelonDB records** → Plain objects (React Native → Web)
- **IndexedDB objects** → AsyncStorage format (Web → React Native)
- **File/Blob objects** → Base64 encoded data
- **Date objects** → ISO strings

## Progress Tracking

Migration operations provide detailed progress updates:

```typescript
interface MigrationProgress {
  stage: 'preparing' | 'exporting' | 'importing' | 'validating' | 'complete' | 'error';
  current: number;
  total: number;
  percentage: number;
  message?: string;
  error?: string;
}
```

## Security Considerations

1. **Encryption**: Sensitive data is encrypted using the platform's security adapter
2. **Checksum Validation**: All migration packages include SHA-256 checksums
3. **Platform Verification**: Source platform is verified during import
4. **Secure Storage**: Migration files should be deleted after successful import

## Error Handling

```typescript
try {
  const result = await migrationTool.importData(migrationData);
  
  if (!result.success) {
    // Handle errors
    result.errors?.forEach(error => {
      console.error(`Failed to import ${error.key}: ${error.error}`);
      if (error.recoverable) {
        // Attempt recovery
      }
    });
  }
  
  // Check warnings
  result.warnings?.forEach(warning => {
    console.warn(warning);
  });
} catch (error) {
  // Critical failure
  console.error('Migration failed:', error);
}
```

## Best Practices

1. **Always validate data** before import using `validateMigrationData()`
2. **Use progress callbacks** for better user experience
3. **Handle platform-specific features** gracefully
4. **Test migrations** in development before production use
5. **Keep migration packages small** - filter unnecessary data
6. **Delete migration files** after successful import

## Advanced Usage

### Custom Data Filtering

```typescript
const migrationData = await tool.exportData({
  progressCallback: updateProgress,
  // Custom filter function
  filter: (key) => !key.includes('cache') && !key.includes('temp')
});
```

### Cross-Platform Helpers

```typescript
import { createCrossPlatformPackage, validateMigrationPackage } from '@haven/offline/migration';

// Create a migration package
const packageString = await createCrossPlatformPackage(data, 'react-native');

// Validate before import
const isValid = await validateMigrationPackage(packageString);
```

## Troubleshooting

### Common Issues

1. **Checksum Mismatch**
   - Cause: Data corruption during transfer
   - Solution: Re-export and transfer again

2. **Platform Mismatch Warning**
   - Cause: Importing data from same platform type
   - Solution: This is usually safe, just a warning

3. **Large File Export Timeout**
   - Cause: Too much data for single export
   - Solution: Use filtering to export in chunks

4. **Import Failures**
   - Cause: Storage quota exceeded or permissions
   - Solution: Clear unnecessary data or request more storage

## Performance Tips

- Export only necessary data using filters
- Use compression for large datasets (automatic for data > 1KB)
- Process imports in batches for better progress tracking
- Consider using QR codes for small, critical data sets

## Future Enhancements

- Peer-to-peer transfer using WebRTC
- Incremental/differential exports
- Automatic conflict resolution strategies
- Cloud backup integration