# Conflict Resolution Guide

## Introduction

This guide provides comprehensive documentation on handling data conflicts in Haven Health Passport's offline-first architecture. Healthcare data requires special attention to conflict resolution to ensure patient safety and data integrity.

## Table of Contents

1. [Understanding Conflicts](#understanding-conflicts)
2. [Conflict Types](#conflict-types)
3. [Resolution Strategies](#resolution-strategies)
4. [CRDT Implementation](#crdt-implementation)
5. [Healthcare-Specific Rules](#healthcare-specific-rules)
6. [Implementation Guide](#implementation-guide)
7. [Testing Conflicts](#testing-conflicts)
8. [Best Practices](#best-practices)

## Understanding Conflicts

### What Causes Conflicts?

Conflicts occur when:
- Multiple devices modify the same data while offline
- Network partitions cause temporary inconsistencies
- Clock skew leads to ordering ambiguities
- Schema changes happen during offline periods

### Conflict Detection

```typescript
interface ConflictDetection {
  // Version-based detection
  hasVersionConflict(local: Document, remote: Document): boolean;
  
  // Content-based detection
  hasContentConflict(local: Document, remote: Document): boolean;
  
  // Schema-based detection
  hasSchemaConflict(local: Document, remote: Document): boolean;
}
```

## Conflict Types

### 1. Update-Update Conflicts

**Scenario**: Same field modified on different devices

```typescript
// Device A
patient.bloodType = "A+";
patient.updatedAt = "2024-01-01T10:00:00Z";

// Device B (same time)
patient.bloodType = "B+";
patient.updatedAt = "2024-01-01T10:00:00Z";
```

**Detection**:
```typescript
function detectUpdateConflict(local: any, remote: any): boolean {
  return local.id === remote.id && 
         local.version === remote.version &&
         local.updatedAt !== remote.updatedAt;
}
```

### 2. Delete-Update Conflicts

**Scenario**: Record deleted on one device, updated on another

```typescript
// Device A
deleteRecord(recordId);

// Device B
updateRecord(recordId, { status: "active" });
```

**Detection**:
```typescript
function detectDeleteConflict(local: any, remote: any): boolean {
  return (local.deleted && !remote.deleted) ||
         (!local.deleted && remote.deleted);
}
```

### 3. Create-Create Conflicts

**Scenario**: Same logical entity created on multiple devices

```typescript
// Device A
createPatient({ 
  nationalId: "123456", 
  name: "John Doe",
  id: "uuid-1"
});

// Device B
createPatient({ 
  nationalId: "123456", 
  name: "John M. Doe",
  id: "uuid-2"
});
```

### 4. Schema Conflicts

**Scenario**: Data structure changes between versions

```typescript
// Version 1
{ 
  name: "John Doe",
  phone: "+1234567890"
}

// Version 2
{ 
  name: { first: "John", last: "Doe" },
  phones: [{ type: "mobile", number: "+1234567890" }]
}
```

## Resolution Strategies

### 1. Last-Write-Wins (LWW)

**Use Case**: Non-critical fields, user preferences

```typescript
class LWWResolver implements ConflictResolver {
  resolve(local: Document, remote: Document): Document {
    return local.updatedAt > remote.updatedAt ? local : remote;
  }
}
```

**Pros**: Simple, deterministic
**Cons**: May lose data

### 2. Multi-Value Register (MVR)

**Use Case**: When all versions should be preserved

```typescript
class MVRResolver implements ConflictResolver {
  resolve(local: Document, remote: Document): Document {
    return {
      ...local,
      _conflicts: [local, remote],
      _requiresResolution: true
    };
  }
}
```

### 3. Semantic Merging

**Use Case**: Structured data that can be intelligently merged

```typescript
class SemanticResolver implements ConflictResolver {
  resolve(local: Document, remote: Document): Document {
    // Merge non-conflicting fields
    const merged = { ...local };
    
    for (const field in remote) {
      if (local[field] === undefined) {
        merged[field] = remote[field];
      } else if (local[field] !== remote[field]) {
        merged[field] = this.mergeField(field, local[field], remote[field]);
      }
    }
    
    return merged;
  }
  
  private mergeField(field: string, localValue: any, remoteValue: any): any {
    // Field-specific merge logic
    switch (field) {
      case 'medications':
        return this.mergeMedications(localValue, remoteValue);
      case 'allergies':
        return [...new Set([...localValue, ...remoteValue])];
      default:
        return localValue; // Default to local
    }
  }
}
```

### 4. Three-Way Merge

**Use Case**: When common ancestor is available

```typescript
class ThreeWayMergeResolver implements ConflictResolver {
  async resolve(
    base: Document,
    local: Document,
    remote: Document
  ): Promise<Document> {
    const localChanges = this.diff(base, local);
    const remoteChanges = this.diff(base, remote);
    
    // Apply non-conflicting changes
    let merged = { ...base };
    
    for (const change of [...localChanges, ...remoteChanges]) {
      if (!this.hasConflict(change, localChanges, remoteChanges)) {
        merged = this.applyChange(merged, change);
      }
    }
    
    return merged;
  }
}
```

## CRDT Implementation

### Overview

CRDTs (Conflict-free Replicated Data Types) provide automatic conflict resolution through mathematical properties.

### State-based CRDTs

```typescript
// G-Counter (Grow-only Counter)
class GCounter {
  private counts: Map<string, number> = new Map();
  
  increment(replicaId: string): void {
    const current = this.counts.get(replicaId) || 0;
    this.counts.set(replicaId, current + 1);
  }
  
  merge(other: GCounter): void {
    for (const [replica, count] of other.counts) {
      const localCount = this.counts.get(replica) || 0;
      this.counts.set(replica, Math.max(localCount, count));
    }
  }
  
  value(): number {
    return Array.from(this.counts.values()).reduce((a, b) => a + b, 0);
  }
}
```

### Operation-based CRDTs

```typescript
// LWW-Element-Set
class LWWElementSet<T> {
  private addSet: Map<T, Timestamp> = new Map();
  private removeSet: Map<T, Timestamp> = new Map();
  
  add(element: T, timestamp: Timestamp): void {
    this.addSet.set(element, timestamp);
  }
  
  remove(element: T, timestamp: Timestamp): void {
    this.removeSet.set(element, timestamp);
  }
  
  contains(element: T): boolean {
    const addTime = this.addSet.get(element);
    const removeTime = this.removeSet.get(element);
    
    if (!addTime) return false;
    if (!removeTime) return true;
    
    return addTime > removeTime;
  }
  
  merge(other: LWWElementSet<T>): void {
    // Merge add sets
    for (const [element, timestamp] of other.addSet) {
      const localTime = this.addSet.get(element);
      if (!localTime || timestamp > localTime) {
        this.addSet.set(element, timestamp);
      }
    }
    
    // Merge remove sets
    for (const [element, timestamp] of other.removeSet) {
      const localTime = this.removeSet.get(element);
      if (!localTime || timestamp > localTime) {
        this.removeSet.set(element, timestamp);
      }
    }
  }
}
```

### Healthcare-Specific CRDTs

```typescript
// Medical Record CRDT
class MedicalRecordCRDT {
  private fields: Map<string, LWWRegister> = new Map();
  private medications: LWWElementSet<Medication> = new LWWElementSet();
  private allergies: GSet<string> = new GSet(); // Grow-only set
  
  updateField(field: string, value: any, timestamp: Timestamp): void {
    if (!this.fields.has(field)) {
      this.fields.set(field, new LWWRegister());
    }
    this.fields.get(field)!.set(value, timestamp);
  }
  
  addMedication(medication: Medication, timestamp: Timestamp): void {
    this.medications.add(medication, timestamp);
  }
  
  addAllergy(allergy: string): void {
    // Allergies are never removed, only added
    this.allergies.add(allergy);
  }
  
  merge(other: MedicalRecordCRDT): void {
    // Merge fields
    for (const [field, register] of other.fields) {
      if (!this.fields.has(field)) {
        this.fields.set(field, new LWWRegister());
      }
      this.fields.get(field)!.merge(register);
    }
    
    // Merge medications
    this.medications.merge(other.medications);
    
    // Merge allergies
    this.allergies.merge(other.allergies);
  }
}
```

## Healthcare-Specific Rules

### Critical Data Rules

```typescript
const CRITICAL_FIELDS = [
  'bloodType',
  'allergies',
  'medications',
  'emergencyContacts',
  'chronicConditions'
];

class HealthcareConflictResolver {
  resolve(local: any, remote: any, field: string): any {
    if (CRITICAL_FIELDS.includes(field)) {
      return this.resolveCriticalField(local, remote, field);
    }
    
    return this.resolveNonCriticalField(local, remote, field);
  }
  
  private resolveCriticalField(local: any, remote: any, field: string): any {
    switch (field) {
      case 'bloodType':
        // Never auto-resolve blood type conflicts
        throw new CriticalConflictError('Blood type conflict requires manual resolution');
        
      case 'allergies':
        // Union of all allergies (never remove)
        return [...new Set([...local, ...remote])];
        
      case 'medications':
        // Require review for medication conflicts
        return {
          active: this.mergeMedications(local, remote),
          requiresReview: true,
          conflicts: this.findMedicationConflicts(local, remote)
        };
        
      default:
        return local; // Default to local for critical fields
    }
  }
}
```

### Prescription Conflict Resolution

```typescript
class PrescriptionResolver {
  resolve(
    localPrescription: Prescription,
    remotePrescription: Prescription
  ): Resolution {
    // Check if same medication
    if (localPrescription.medicationId !== remotePrescription.medicationId) {
      return { action: 'MANUAL_REVIEW', reason: 'Different medications' };
    }
    
    // Check prescriber authority
    const localAuth = this.getPrescriberAuthority(localPrescription.prescriberId);
    const remoteAuth = this.getPrescriberAuthority(remotePrescription.prescriberId);
    
    if (localAuth.level > remoteAuth.level) {
      return { action: 'USE_LOCAL', reason: 'Higher authority prescriber' };
    }
    
    // Check timestamps
    if (localPrescription.prescribedAt > remotePrescription.prescribedAt) {
      return { action: 'USE_LOCAL', reason: 'More recent prescription' };
    }
    
    // Require manual review for equal authority and time
    return { action: 'MANUAL_REVIEW', reason: 'Equal authority conflict' };
  }
}
```

### Lab Result Conflicts

```typescript
class LabResultResolver {
  resolve(local: LabResult, remote: LabResult): LabResult {
    // Lab results are immutable - keep both
    return {
      id: local.id,
      results: [
        { ...local, source: 'local' },
        { ...remote, source: 'remote' }
      ],
      latestResult: local.collectedAt > remote.collectedAt ? local : remote,
      requiresVerification: true
    };
  }
}
```

## Implementation Guide

### 1. Conflict Resolver Factory

```typescript
class ConflictResolverFactory {
  private resolvers: Map<string, ConflictResolver> = new Map();
  
  constructor() {
    this.registerDefaultResolvers();
  }
  
  private registerDefaultResolvers(): void {
    this.register('patient', new PatientConflictResolver());
    this.register('prescription', new PrescriptionResolver());
    this.register('labResult', new LabResultResolver());
    this.register('appointment', new LWWResolver());
    this.register('note', new SemanticResolver());
  }
  
  register(type: string, resolver: ConflictResolver): void {
    this.resolvers.set(type, resolver);
  }
  
  getResolver(type: string): ConflictResolver {
    return this.resolvers.get(type) || new LWWResolver();
  }
}
```

### 2. Conflict Resolution Pipeline

```typescript
class ConflictResolutionPipeline {
  private factory: ConflictResolverFactory;
  private auditLogger: AuditLogger;
  
  async resolve(conflict: Conflict): Promise<Resolution> {
    try {
      // 1. Pre-resolution validation
      this.validateConflict(conflict);
      
      // 2. Get appropriate resolver
      const resolver = this.factory.getResolver(conflict.type);
      
      // 3. Attempt automatic resolution
      const resolution = await resolver.resolve(
        conflict.local,
        conflict.remote,
        conflict.ancestor
      );
      
      // 4. Post-resolution validation
      await this.validateResolution(resolution);
      
      // 5. Audit log
      await this.auditLogger.logResolution(conflict, resolution);
      
      return resolution;
      
    } catch (error) {
      if (error instanceof CriticalConflictError) {
        return this.handleCriticalConflict(conflict, error);
      }
      throw error;
    }
  }
  
  private async handleCriticalConflict(
    conflict: Conflict,
    error: CriticalConflictError
  ): Promise<Resolution> {
    // Queue for manual review
    await this.queueForManualReview(conflict, error.message);
    
    // Return safe default
    return {
      resolved: conflict.local, // Keep local version
      requiresManualReview: true,
      reason: error.message
    };
  }
}
```

### 3. Manual Conflict Resolution UI

```typescript
interface ManualResolutionUI {
  // Show conflict to user
  displayConflict(conflict: Conflict): Promise<void>;
  
  // Get user's resolution choice
  getUserResolution(): Promise<ResolutionChoice>;
  
  // Apply user's choice
  applyResolution(choice: ResolutionChoice): Promise<void>;
}

class ConflictResolutionModal implements ManualResolutionUI {
  async displayConflict(conflict: Conflict): Promise<void> {
    // Show side-by-side comparison
    this.showLocalVersion(conflict.local);
    this.showRemoteVersion(conflict.remote);
    
    // Highlight differences
    this.highlightDifferences(conflict);
    
    // Show resolution options
    this.showResolutionOptions(conflict.type);
  }
  
  private showResolutionOptions(type: string): void {
    const options = this.getResolutionOptions(type);
    
    // Display options based on conflict type
    options.forEach(option => {
      this.addResolutionButton(option);
    });
  }
}
```

## Testing Conflicts

### Conflict Simulation

```typescript
class ConflictSimulator {
  // Create update-update conflict
  createUpdateConflict(): Conflict {
    const base = { id: '1', name: 'John', version: 1 };
    const local = { ...base, name: 'John Doe', version: 2 };
    const remote = { ...base, name: 'J. Doe', version: 2 };
    
    return { type: 'update-update', base, local, remote };
  }
  
  // Create delete-update conflict
  createDeleteConflict(): Conflict {
    const base = { id: '1', name: 'John', version: 1 };
    const local = { ...base, deleted: true, version: 2 };
    const remote = { ...base, name: 'John Doe', version: 2 };
    
    return { type: 'delete-update', base, local, remote };
  }
  
  // Test resolution
  async testResolution(conflict: Conflict): Promise<void> {
    const resolver = new ConflictResolver();
    const result = await resolver.resolve(conflict);
    
    // Verify resolution properties
    expect(result).toHaveProperty('resolved');
    expect(result.resolved).toHaveValidStructure();
  }
}
```

### Integration Tests

```typescript
describe('Conflict Resolution', () => {
  let resolver: ConflictResolver;
  let simulator: ConflictSimulator;
  
  beforeEach(() => {
    resolver = new ConflictResolver();
    simulator = new ConflictSimulator();
  });
  
  it('should resolve simple update conflicts', async () => {
    const conflict = simulator.createUpdateConflict();
    const result = await resolver.resolve(conflict);
    
    expect(result.resolved).toBeDefined();
    expect(result.requiresManualReview).toBe(false);
  });
  
  it('should flag critical conflicts for review', async () => {
    const conflict = simulator.createCriticalConflict('bloodType');
    const result = await resolver.resolve(conflict);
    
    expect(result.requiresManualReview).toBe(true);
    expect(result.reason).toContain('manual resolution');
  });
});
```

## Best Practices

### 1. Design for Conflicts
- Use unique IDs (UUIDs) for all entities
- Include version numbers or timestamps
- Keep operations idempotent
- Design data structures that merge well

### 2. Healthcare Safety
- Never auto-resolve critical medical data
- Maintain audit trails for all resolutions
- Require medical professional review when needed
- Preserve all versions of critical data

### 3. User Experience
- Make conflicts visible but not alarming
- Provide clear resolution options
- Show impact of each choice
- Allow undo for resolutions

### 4. Performance
- Resolve conflicts asynchronously when possible
- Batch conflict resolution
- Cache resolution strategies
- Monitor resolution performance

### 5. Testing
- Test all conflict scenarios
- Include edge cases
- Test with real medical data structures
- Verify audit trails

## Common Pitfalls

### 1. Timestamp Reliability
```typescript
// Bad: Relying solely on device time
const timestamp = new Date().toISOString();

// Good: Use hybrid logical clocks
const timestamp = HybridLogicalClock.now();
```

### 2. Silent Data Loss
```typescript
// Bad: Silently choosing one version
return local.updatedAt > remote.updatedAt ? local : remote;

// Good: Preserve both versions when uncertain
return {
  current: local,
  alternatives: [remote],
  conflicted: true
};
```

### 3. Over-Merging
```typescript
// Bad: Merging incompatible data
const merged = { ...local, ...remote };

// Good: Validate compatibility before merging
if (this.areCompatible(local, remote)) {
  return this.merge(local, remote);
} else {
  return this.flagForReview(local, remote);
}
```

## Advanced Topics

### Causal Consistency

```typescript
class CausalConsistencyTracker {
  private dependencies: Map<string, Set<string>> = new Map();
  
  recordDependency(operation: string, dependsOn: string[]): void {
    this.dependencies.set(operation, new Set(dependsOn));
  }
  
  canApply(operation: string, applied: Set<string>): boolean {
    const deps = this.dependencies.get(operation) || new Set();
    return Array.from(deps).every(dep => applied.has(dep));
  }
}
```

### Convergent Conflict Resolution

```typescript
class ConvergentResolver {
  // Ensures all replicas converge to same state
  resolve(conflicts: Conflict[]): any {
    // Sort conflicts deterministically
    const sorted = conflicts.sort((a, b) => 
      a.id.localeCompare(b.id)
    );
    
    // Apply in order
    return sorted.reduce((state, conflict) => 
      this.applyConflict(state, conflict), 
      {}
    );
  }
}
```

## Conclusion

Effective conflict resolution is critical for offline-first healthcare applications. By combining automatic resolution strategies with healthcare-specific rules and manual review processes, Haven Health Passport ensures data integrity while maintaining usability. Always prioritize patient safety and data accuracy over automation convenience.