# Patient Query API Examples

## Basic Patient Lookup

### Get Patient by ID
```graphql
query GetPatient {
  patient(id: "123e4567-e89b-12d3-a456-426614174000") {
    id
    name {
      family
      given
      text
    }
    gender
    birthDate
    preferredLanguage
    refugeeStatus {
      status
      registrationNumber
      countryOfOrigin
    }
    # Audit fields
    createdAt
    updatedAt
    version
  }
}
```

### Include Archived Patients
```graphql
query GetArchivedPatient {
  patient(
    id: "123e4567-e89b-12d3-a456-426614174000"
    includeArchived: true
  ) {
    id
    name {
      text
    }
    deletedAt
  }
}
```

## Advanced Patient Search

### Search with Filters
```graphql
query SearchPatients {
  patients(
    filter: {
      gender: FEMALE
      refugeeStatus: "registered"
      campLocation: "Kakuma"
      birthDateFrom: "1990-01-01"
      birthDateTo: "2000-12-31"
      preferredLanguage: "sw"
    }
    sort: {
      field: "birthDate"
      direction: "asc"
    }
    page: 1
    pageSize: 20
  ) {
    patients {
      id
      name {
        family
        given
      }
      birthDate
      refugeeStatus {
        status
        campLocation
      }
    }
    totalCount
    page
    pageSize
    totalPages
    hasNextPage
    hasPreviousPage
  }
}
```

### Search by Identifier
```graphql
query SearchByIdentifier {
  patients(
    filter: {
      identifier: "UNHCR123456"
      identifierSystem: "UNHCR"
    }
  ) {
    patients {
      id
      identifiers {
        system
        value
      }
      name {
        text
      }
    }
    totalCount
  }
}
```

### Family Group Search
```graphql
query SearchFamilyMembers {
  patients(
    filter: {
      familyGroupId: "456e7890-e89b-12d3-a456-426614174000"
    }
    sort: {
      field: "birthDate"
      direction: "desc"
    }
  ) {
    patients {
      id
      name {
        text
      }
      familyGroup {
        headOfHousehold
        relationshipToHead
      }
    }
    totalCount
  }
}
```

### Date Range Search
```graphql
query RecentRegistrations {
  patients(
    filter: {
      createdFrom: "2024-01-01T00:00:00Z"
      createdTo: "2024-12-31T23:59:59Z"
    }
    sort: {
      field: "createdAt"
      direction: "desc"
    }
  ) {
    patients {
      id
      name {
        text
      }
      createdAt
      refugeeStatus {
        dateOfRegistration
      }
    }
    totalCount
  }
}
```

## Access Control

The patient queries automatically apply access control based on user roles:

- **Admin/Healthcare Provider**: Can access all patients
- **Staff**: Can access patients in their assigned organization/camp
- **Patient**: Can only access their own record and family members

## Sorting Options

Available sort fields:
- `name`: Sort by patient name
- `birthDate`: Sort by date of birth
- `createdAt`: Sort by registration date (default)
- `updatedAt`: Sort by last update date

## Performance Tips

1. Use specific filters to reduce result sets
2. Request only needed fields to reduce payload size
3. Use pagination for large result sets
4. Consider caching frequently accessed patient data