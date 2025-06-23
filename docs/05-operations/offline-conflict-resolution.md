# Offline Conflict Resolution

## Overview

The conflict resolution UI provides a user-friendly interface for resolving data conflicts that occur when syncing offline changes with the server. This is a critical component of the offline-first architecture.

## Components

### ConflictResolutionUI

The main dialog component that presents conflicts to users and allows them to choose how to resolve each one.

**Features:**
- Visual comparison of local vs remote values
- Timestamp and device information
- User attribution for changes
- Multiple resolution strategies
- Bulk resolution options

### OfflineSyncManager

A persistent UI component that monitors sync status and provides quick access to conflict resolution.

**Features:**
- Real-time sync status
- Pending changes counter
- Last sync timestamp
- Manual sync trigger
- Conflict notification

## Usage

### Basic Integration

```tsx
import { OfflineSyncManager } from '@components/offline';

// Add to your main layout
function AppLayout() {
  return (
    <div>
      {/* Your app content */}
      <OfflineSyncManager />
    </div>
  );
}
```

### Custom Conflict Handling

```tsx
import { useConflictResolution } from '@components/offline';

function MyComponent() {
  const { conflicts, showConflictUI, resolveConflicts } = useConflictResolution();

  // Custom conflict handling logic
  const handleCustomResolution = async () => {
    // Apply custom resolution strategy
    const resolutions = {};
    conflicts.forEach(conflict => {
      resolutions[conflict.id] = 'local'; // or 'remote' or 'merge'
    });
    
    await resolveConflicts(resolutions);
  };

  return (
    // Your component UI
  );
}
```

## Conflict Resolution Strategies

### 1. Manual Resolution
Users review each conflict individually and choose which version to keep.

### 2. Bulk Resolution Options
- **Use All Local**: Keep all local changes
- **Use All Remote**: Accept all server changes  
- **Use All Newest**: Automatically choose the most recent version

### 3. Merge Strategy (Future Enhancement)
For certain field types, allow merging of changes rather than choosing one version.

## Data Structure

Conflicts are represented with the following structure:

```typescript
interface ConflictData {
  id: string;
  type: 'patient' | 'health_record' | 'document';
  field: string;
  localValue: any;
  remoteValue: any;
  localTimestamp: Date;
  remoteTimestamp: Date;
  localDevice?: string;
  remoteDevice?: string;
  localUser?: string;
  remoteUser?: string;
}
```

## Accessibility

The conflict resolution UI is fully accessible:
- ARIA labels for all interactive elements
- Keyboard navigation support
- Screen reader announcements for status changes
- Focus management during dialog interactions

## Best Practices

1. **Minimize Conflicts**: Design your data model to reduce conflict likelihood
2. **Clear Communication**: Always show users what data is being synced
3. **Preserve Data**: Never lose user data - always provide rollback options
4. **Audit Trail**: Log all conflict resolutions for compliance
5. **User Education**: Provide tooltips and help text explaining conflicts

## Testing

Test conflict resolution by:
1. Making changes offline on multiple devices
2. Modifying the same records
3. Going online to trigger sync
4. Verifying conflict detection and resolution

## Future Enhancements

1. **Smart Conflict Detection**: AI-powered conflict resolution suggestions
2. **Field-Level Merging**: Automatic merging for compatible changes
3. **Conflict Prevention**: Real-time collaboration features
4. **Historical View**: Show full history of conflicted fields
5. **Team Resolution**: Allow team members to collaboratively resolve conflicts
