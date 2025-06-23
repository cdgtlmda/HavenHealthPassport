# GraphQL API Versioning Guide

## Overview

Haven Health Passport uses a comprehensive versioning system for its GraphQL API to ensure backward compatibility while allowing for schema evolution. This guide explains how to use and maintain API versions.

## Current Version

- **Current Version**: 2.0
- **Supported Versions**: 1.0, 1.1, 2.0
- **Deprecated Versions**: 0.9

## Requesting a Specific Version

Clients can request a specific API version using:

### HTTP Header (Recommended)
```
X-API-Version: 1.1
```

### Query Parameter
```
/graphql?version=1.1
```

If no version is specified, the current version (2.0) is used.

## Version Features

### Version 1.0 (Initial Release)
- Basic patient demographics
- Health record management
- Authentication and authorization

### Version 1.1 (June 2024)
- Added refugee-specific fields to Patient type
- Family linking support
- Protection concerns tracking
- Emergency contacts

### Version 2.0 (December 2024) - Breaking Changes
- Full FHIR compliance for health records
- Restructured Patient type with versioning
- Enhanced verification workflows
- Audit trail support


## Using Versioned Fields

### For GraphQL Type Developers

```python
from src.api.graphql_versioning import VersionedField, VersionedType

@strawberry.type
@VersionedType(added_in="1.0")
class Patient:
    # Field available in all versions
    id: UUID
    name: str
    
    # Field added in v1.1
    @strawberry.field
    @VersionedField(added_in="1.1")
    async def refugee_status(self, info) -> Optional[RefugeeStatus]:
        return self.refugeeStatus
    
    # Field deprecated in v2.0
    @strawberry.field
    @VersionedField(
        added_in="1.0",
        deprecated_in="2.0",
        replacement="healthRecords"
    )
    async def medical_records(self, info) -> List[MedicalRecord]:
        return self.records
```

## Querying Version Information

```graphql
query {
  version {
    versionInfo {
      current
      supported
      deprecated
      changes {
        version
        date
        breaking
        description
        affectedTypes
      }
    }
    checkCompatibility(version: "1.1")
  }
}
```

## Handling Deprecations

When fields or types are deprecated, the API will include deprecation warnings in the response headers:

```
X-API-Deprecation: Field deprecated in 2.0. Use healthRecords instead.
```


## Best Practices

### For API Consumers

1. **Always specify a version** in production to avoid breaking changes
2. **Monitor deprecation warnings** and plan migrations
3. **Test against new versions** before upgrading
4. **Use introspection** to discover available fields for your version

### For API Developers

1. **Use semantic versioning** for API versions
2. **Deprecate before removing** - give clients time to migrate
3. **Document all changes** in version history
4. **Provide migration guides** for breaking changes
5. **Test compatibility** across supported versions

## Migration Example

Migrating from v1.1 to v2.0:

```python
# v1.1 query
query {
  patient(id: "123") {
    medicalRecords {  # Deprecated
      id
      type
    }
  }
}

# v2.0 query
query {
  patient(id: "123") {
    healthRecords {  # New field
      id
      resourceType
      content
    }
  }
}
```

## Version History Tracking

All version changes are tracked and can be queried through the API. This includes:
- Version number and release date
- Breaking vs non-breaking changes
- Affected types and fields
- Migration guides when applicable
