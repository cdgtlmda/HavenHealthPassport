# Endorsement Requirements Documentation

## Overview

This document provides comprehensive guidance on implementing and using endorsement requirements in the Haven Health Passport blockchain network. Endorsement policies ensure that transactions are properly validated by the required organizations before being committed to the ledger.

## Key Concepts

### What is Endorsement?

In Hyperledger Fabric, endorsement is the process where designated peer nodes execute chaincode and sign the results. The endorsement policy specifies which organizations must endorse a transaction for it to be considered valid.

### Why Endorsement Matters for Healthcare

- **Data Integrity**: Ensures medical records are validated by authorized healthcare providers
- **Compliance**: Meets HIPAA and other regulatory requirements
- **Multi-party Trust**: Enables trust between healthcare providers, UNHCR, and refugee organizations
- **Audit Trail**: Creates verifiable record of who approved each transaction

## Endorsement Policy Structure

### Basic Components

1. **Rule**: Defines which organizations must endorse (OR, AND, OutOf)
2. **MinEndorsers**: Minimum number of endorsing peers required
3. **RequiredAttributes**: Attributes the endorser must possess
4. **AdditionalChecks**: Extra validations to perform
5. **Metadata**: Additional policy configuration

### Policy Types

#### 1. Standard Healthcare Operations
- Single healthcare provider endorsement
- Used for routine medical records
- Example: `OR('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer')`

#### 2. Sensitive Data Operations
- Multiple endorsements required
- Used for mental health, substance abuse records
- Example: `AND('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer')`

#### 3. Cross-Border Operations
- UNHCR involvement required
- Used for international data transfers
- Example: `AND('UNHCROrgMSP.peer', OR('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer'))`

#### 4. Emergency Operations
- Relaxed requirements for emergencies
- Time-limited with audit requirements
- Example: `OR('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer', 'RefugeeOrgMSP.peer')`

## Implementation Guide

### Step 1: Define Endorsement Requirements

Create your endorsement policy in the chaincode:

```go
policy := &cauthdsl.SignaturePolicyEnvelope{
    Version: 0,
    Rule: cauthdsl.Or(
        cauthdsl.SignedBy(0),
        cauthdsl.SignedBy(1),
    ),
    Identities: []*msp.MSPPrincipal{
        {
            PrincipalClassification: msp.MSPPrincipal_ROLE,
            Principal: proto.Marshal(&msp.MSPRole{
                Role:          msp.MSPRole_PEER,
                MspIdentifier: "HealthcareProvider1MSP",
            }),
        },
        {
            PrincipalClassification: msp.MSPPrincipal_ROLE,
            Principal: proto.Marshal(&msp.MSPRole{
                Role:          msp.MSPRole_PEER,
                MspIdentifier: "HealthcareProvider2MSP",
            }),
        },
    },
}
```
### Step 2: Apply Policy to Chaincode

When deploying chaincode, specify the endorsement policy:

```bash
peer lifecycle chaincode approveformyorg \
  --channelID healthcare-channel \
  --name health-records \
  --version 1.0 \
  --package-id ${PACKAGE_ID} \
  --sequence 1 \
  --signature-policy "OR('HealthcareProvider1MSP.peer','HealthcareProvider2MSP.peer')"
```

### Step 3: Function-Level Policies

Different functions can have different endorsement requirements:

```go
func (s *SmartContract) CreatePatientRecord(ctx contractapi.TransactionContextInterface, recordData string) error {
    // Standard record creation - single endorser
    if err := checkEndorsementPolicy(ctx, "StandardHealthcareOperation"); err != nil {
        return err
    }
    // Process record creation
}

func (s *SmartContract) CreateMentalHealthRecord(ctx contractapi.TransactionContextInterface, recordData string) error {
    // Sensitive data - multiple endorsers required
    if err := checkEndorsementPolicy(ctx, "SensitiveDataOperation"); err != nil {
        return err
    }
    // Process sensitive record creation
}
```

## Policy Examples by Use Case

### Patient Registration

```yaml
Requirements:
  Rule: "OR('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer', 'RefugeeOrgMSP.peer')"
  MinEndorsers: 1
  RequiredAttributes:
    - "registration_authority"
```

### Prescription Management

```yaml
StandardPrescription:
  Rule: "OR('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer')"
  MinEndorsers: 1
  RequiredAttributes:
    - "prescribing_authority"

ControlledSubstance:
  Rule: "AND('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer')"
  MinEndorsers: 2
  RequiredAttributes:
    - "dea_number"
    - "controlled_substance_authority"
```

### Emergency Access

```yaml
EmergencyOverride:
  Rule: "OR('HealthcareProvider1MSP.peer', 'HealthcareProvider2MSP.peer')"
  MinEndorsers: 1
  TimeLimit: "24 hours"
  AutomaticAudit: true
  NotificationRequired: "ALL organizations"
```

## Validation and Testing

### Unit Testing Endorsement Policies

```go
func TestEndorsementPolicy(t *testing.T) {
    // Create mock context with endorser information
    ctx := createMockContext("HealthcareProvider1MSP", "peer")

    // Test standard operation
    err := validateEndorsement(ctx, "StandardHealthcareOperation")
    assert.NoError(t, err)

    // Test operation requiring multiple endorsers
    err = validateEndorsement(ctx, "SensitiveDataOperation")
    assert.Error(t, err) // Should fail with single endorser
}
```

### Integration Testing

```bash
# Test endorsement with different organizations
docker exec peer0.healthcare1.havenhealthpassport.org peer chaincode invoke \
  -o orderer.havenhealthpassport.org:7050 \
  -C healthcare-channel \
  -n health-records \
  -c '{"function":"CreatePatientRecord","Args":["patient123", "{...}"]}'
```

## Monitoring and Compliance

### Endorsement Metrics

Monitor these key metrics:
- Endorsement success rate
- Average endorsement time
- Failed endorsement reasons
- Policy violation attempts

### Audit Queries

```javascript
// Query endorsement history
const endorsementHistory = await contract.evaluateTransaction(
    'GetEndorsementHistory',
    'policyName',
    'startDate',
    'endDate'
);
```

## Troubleshooting

### Common Issues

1. **"Endorsement policy failure"**
   - Check if required organizations are online
   - Verify MSP configuration
   - Ensure peers have correct certificates

2. **"Missing required attributes"**
   - Verify user certificates contain required attributes
   - Check attribute names match exactly
   - Ensure CA is configured to issue attributes

3. **"Timeout waiting for endorsements"**
   - Check network connectivity
   - Verify peer availability
   - Review endorsement timeout settings

### Debug Commands

```bash
# Check peer endorsement capabilities
peer channel getinfo -c healthcare-channel

# Verify policy configuration
peer lifecycle chaincode querycommitted -C healthcare-channel -n health-records

# View endorsement policy details
discover --configFile discovery-config.yaml \
  endorsers --channel healthcare-channel \
  --chaincode health-records
```

## Best Practices

1. **Principle of Least Privilege**
   - Only require endorsements necessary for operation
   - Use OR policies for routine operations
   - Reserve AND policies for sensitive data

2. **Performance Optimization**
   - Cache endorsement validations where appropriate
   - Use efficient endorsement policies
   - Monitor endorsement latency

3. **Disaster Recovery**
   - Define emergency override policies
   - Maintain backup endorsers
   - Document failover procedures

4. **Compliance**
   - Regular policy audits
   - Document policy changes
   - Maintain endorsement logs

## Migration and Updates

### Updating Endorsement Policies

```bash
# Update chaincode with new endorsement policy
peer lifecycle chaincode approveformyorg \
  --channelID healthcare-channel \
  --name health-records \
  --version 2.0 \
  --sequence 2 \
  --signature-policy "OutOf(2, 'Org1MSP.peer', 'Org2MSP.peer', 'Org3MSP.peer')"
```

### Backward Compatibility

- Maintain old policy support during transition
- Gradually migrate to new policies
- Test thoroughly before production deployment
