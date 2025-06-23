# Haven Health Passport - Role-Based Access Control (RBAC)

## Overview

The Haven Health Passport RBAC system provides comprehensive access control for healthcare data, ensuring HIPAA compliance, data sovereignty, and proper authorization across all system components.

## Features

### Core RBAC Features
- **Role Hierarchy**: Inherited permissions through role relationships
- **Permission Matrix**: Granular resource-action mappings
- **Attribute-Based Control (ABAC)**: Dynamic permissions based on attributes
- **Dynamic Permissions**: Context-aware access decisions
- **Least Privilege**: Minimal necessary access granted
- **Segregation of Duties**: Conflicting role prevention
- **Approval Workflows**: Multi-step approval processes
- **Role Delegation**: Temporary role assignment capabilities
- **Emergency Access**: Break-glass procedures for critical situations
- **Audit Trail**: Comprehensive logging of all access decisions
- **Access Reviews**: Periodic certification of user access
- **Automated Remediation**: Automatic cleanup of expired/unused access

## System Roles

### Administrative Roles
- **Super Admin**: Full system access with no restrictions
- **System Admin**: System administration and configuration
- **Healthcare Admin**: Healthcare organization administration

### Healthcare Roles
- **Physician**: Licensed physician with full patient care access
- **Nurse**: Registered nurse with patient care access
- **Pharmacist**: Licensed pharmacist with prescription access
- **Lab Technician**: Laboratory technician with lab result access
- **Billing Specialist**: Billing and insurance specialist

### Special Roles
- **Emergency Responder**: Emergency access with override capabilities
- **Auditor**: Compliance auditor with read-only access
- **Patient**: Patient with access to own health records
- **Guest**: Guest with minimal access to shared records

## Quick Start

### Basic Usage

```typescript
import {
  checkAccess,
  assignRole,
  SYSTEM_ROLES,
  PermissionType
} from './security/access-control';

// Check access
const decision = await checkAccess({
  user: {
    id: 'user123',
    roles: [],
    attributes: { department: 'cardiology' }
  },
  resource: {
    type: 'patient_record',
    id: 'record456',
    attributes: { department: 'cardiology' }
  },
  action: PermissionType.RECORD_VIEW,
  environment: {
    time: new Date(),
    ipAddress: '192.168.1.1',
    sessionId: 'session123'
  }
});

if (decision.allowed) {
  // Access granted
} else {
  // Access denied
  console.log('Missing permissions:', decision.missingPermissions);
}
```

### Role Assignment

```typescript
// Assign a role
const assignment = await assignRole(
  'user123',                    // User ID
  SYSTEM_ROLES.PHYSICIAN,       // Role ID
  'admin123',                   // Assigned by
  {
    expiresAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000), // 1 year
    scope: {
      type: 'department',
      id: 'cardiology',
      children: true
    }
  }
);

// Delegate a role
const delegation = await delegateRole(
  'user123',                    // From user
  'user456',                    // To user
  SYSTEM_ROLES.PHYSICIAN,       // Role to delegate
  new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // 7 days
);
```

### Emergency Access

```typescript
// Emergency access (break-glass)
const emergencyDecision = await checkAccess({
  user: {
    id: 'emergency-responder',
    roles: [],
    attributes: {
      emergencyOverride: true,
      emergencyJustification: 'Patient in critical condition, regular physician unavailable'
    }
  },
  resource: {
    type: 'patient_record',
    id: 'critical-patient-123',
    attributes: {}
  },
  action: PermissionType.RECORD_VIEW,
  environment: {
    time: new Date(),
    ipAddress: '192.168.1.1',
    sessionId: 'emergency-session'
  }
});
```

### Access Reviews

```typescript
// Perform access review
const review = await performAccessReview('user123');

console.log('Effective roles:', review.effectiveRoles);
console.log('Unused roles:', review.unusedRoles);
console.log('Recommendations:', review.recommendations);

// Create certification campaign
const campaign = await certificationManager.createCampaign(
  'high_privilege_quarterly',
  'admin123'
);
```

## Advanced Features

### Attribute-Based Access Control (ABAC)

The system supports dynamic access control based on attributes:

```typescript
// Access granted if user and resource departments match
const context = {
  user: {
    id: 'user123',
    roles: [],
    attributes: {
      department: 'oncology',
      clearanceLevel: 3
    }
  },
  resource: {
    type: 'patient_record',
    id: 'record789',
    attributes: {
      department: 'oncology',
      classificationLevel: 2
    }
  },
  action: PermissionType.RECORD_VIEW,
  environment: { /* ... */ }
};
```

### Segregation of Duties

Conflicting roles are automatically prevented:

```typescript
// This will throw an error
await assignRole('user123', SYSTEM_ROLES.AUDITOR, 'admin');
await assignRole('user123', SYSTEM_ROLES.SYSTEM_ADMIN, 'admin'); // Error!
```

### Approval Workflows

Sensitive operations require approval:

```typescript
const request = await rbacManager.createApprovalRequest(
  'data_export',
  'user123',
  {
    recordIds: ['record1', 'record2'],
    purpose: 'Research study',
    destination: 'external-system'
  }
);

// Process approval
await rbacManager.processApproval(
  request.id,
  'approver123',
  'approve',
  'Approved for research purposes'
);
```

## Security Considerations

1. **Zero Trust**: Every access request is evaluated independently
2. **Least Privilege**: Users only get minimum necessary permissions
3. **Time-Based Access**: Roles can have expiration dates
4. **Audit Trail**: All access decisions are logged
5. **Emergency Override**: Break-glass procedures are logged and monitored

## Integration

### With Express/FastAPI Middleware

```typescript
// Express middleware
app.use(async (req, res, next) => {
  const decision = await checkAccess({
    user: {
      id: req.user.id,
      roles: [],
      attributes: req.user.attributes
    },
    resource: {
      type: req.params.resourceType,
      id: req.params.resourceId,
      attributes: {}
    },
    action: mapHttpMethodToPermission(req.method),
    environment: {
      time: new Date(),
      ipAddress: req.ip,
      sessionId: req.sessionID
    }
  });

  if (!decision.allowed) {
    return res.status(403).json({
      error: 'Access denied',
      missingPermissions: decision.missingPermissions
    });
  }

  next();
});
```

### With GraphQL

```typescript
// GraphQL resolver
const resolvers = {
  Query: {
    patientRecord: async (parent, args, context) => {
      const decision = await checkAccess({
        user: context.user,
        resource: {
          type: 'patient_record',
          id: args.id,
          attributes: {}
        },
        action: PermissionType.RECORD_VIEW,
        environment: context.environment
      });

      if (!decision.allowed) {
        throw new ForbiddenError('Access denied');
      }

      return getPatientRecord(args.id);
    }
  }
};
```

## Monitoring and Compliance

### Access Analytics

```typescript
// Export audit logs
const logs = rbacManager.exportAuditLog(
  new Date('2024-01-01'),
  new Date('2024-12-31')
);

// Analyze access patterns
const analysis = analyzeAccessPatterns(logs);
```

### Compliance Reports

```typescript
// Generate compliance report
const report = await generateComplianceReport({
  period: 'quarterly',
  includeEmergencyAccess: true,
  includeRoleChanges: true,
  includeFailedAttempts: true
});
```

## Best Practices

1. **Regular Reviews**: Schedule periodic access reviews
2. **Role Hygiene**: Remove unused roles promptly
3. **Minimal Permissions**: Start with least privilege, add as needed
4. **Audit Everything**: Enable comprehensive logging
5. **Emergency Procedures**: Document and test break-glass procedures
6. **Training**: Ensure staff understand the access control system

## Troubleshooting

### Common Issues

1. **Access Denied**: Check effective roles and permissions
2. **Role Conflicts**: Review segregation of duties rules
3. **Expired Access**: Check role assignment expiration dates
4. **Missing Attributes**: Ensure user/resource attributes are populated

### Debug Mode

```typescript
// Enable debug logging
process.env.RBAC_DEBUG = 'true';

// Check effective permissions
const permissions = await rbacManager.getUserEffectivePermissions('user123');
console.log('Effective permissions:', permissions);
```

## Performance

- Access decisions are cached for performance
- Role hierarchy is pre-computed
- Audit logs are written asynchronously
- Bulk operations are optimized

## Contributing

When adding new features:
1. Update role definitions if needed
2. Add to permission matrix
3. Update access certification schedule
4. Add tests for new functionality
5. Update documentation

## License

This RBAC implementation is part of the Haven Health Passport system and follows the same licensing terms.
