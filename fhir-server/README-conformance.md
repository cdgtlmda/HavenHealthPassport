# FHIR Conformance Resources Setup

## Overview

The Haven Health Passport FHIR server now includes comprehensive conformance resources that define:
- Custom patient profiles for refugees
- Custom search parameters for refugee-specific data
- Value sets and code systems for refugee status and camp locations
- Extension definitions for additional patient data

## Components Implemented

### 1. CapabilityStatement Configuration
- Location: `HavenCapabilityStatementConfig.java`
- Defines server capabilities, supported resources, and operations
- Includes custom search parameters and security requirements

### 2. Conformance Resource Providers
- Location: `ConformanceResourceProvider.java`
- Implements providers for:
  - StructureDefinitions (custom profiles)
  - SearchParameters (custom search capabilities)
  - ValueSets (terminology bindings)
  - CodeSystems (custom codes)

### 3. Extension Definitions
- Location: `ExtensionDefinitionProvider.java`
- Defines extensions for:
  - Refugee status
  - Camp location

### 4. Server Configuration
- Updated `HavenFhirServerConfig.java` to register all conformance resource providers
- Created `HavenFhirServerApplication.java` as the main Spring Boot application

## Custom Resources

### Refugee Patient Profile
- URL: `https://havenhealthpassport.org/fhir/StructureDefinition/refugee-patient`
- Extends the base Patient resource with refugee-specific extensions

### Custom Search Parameters
1. **refugee-status**: Search patients by refugee status
2. **camp-location**: Search patients by refugee camp location

### Value Sets
1. **Refugee Status**: Classifications for refugee/displaced person status
2. **Camp Location**: Known refugee camp locations

### Code Systems
1. **Refugee Status Codes**: refugee, asylum-seeker, internally-displaced, stateless, returnee
2. **Camp Location Codes**: kakuma, dadaab, zaatari, cox-bazar

## Testing

A test class `ConformanceResourcesTest.java` has been created to verify:
- CapabilityStatement is properly exposed
- Custom search parameters are included
- Server metadata is correctly configured

## Next Steps

The conformance resources are now properly set up. The next items in the healthcare standards checklist are:
- Configure capability statement ✓ (COMPLETED)
- Define supported resources
- Set interaction capabilities
- Configure search parameters
