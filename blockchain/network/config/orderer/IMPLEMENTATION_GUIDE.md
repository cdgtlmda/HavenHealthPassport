# Orderer Policies Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing and using the orderer policies in the Haven Health Passport blockchain network.

## Implementation Steps

### 1. Policy Integration

Run the integration script to merge orderer policies with the main configuration:

```bash
cd /blockchain/network/config/orderer
./integrate-orderer-policies.sh
```

### 2. Generate Genesis Block

After integrating policies, generate a new genesis block:

```bash
# Set environment variables
export FABRIC_CFG_PATH=$PWD
export CHANNEL_NAME=healthcare-channel

# Generate genesis block with new policies
configtxgen -profile RaftOrdererGenesis -channelID system-channel -outputBlock ./genesis.block
```

### 3. Update Orderer Configuration

Apply the new configuration to running orderers:

```bash
# For each orderer node
docker exec -it orderer1.havenhealthpassport.org sh -c 'orderer channel update -c system-channel -f genesis.block'
```

## Policy Usage Examples

### Emergency Access Request

When emergency medical access is needed:

```javascript
// Example: Emergency access request
const emergencyRequest = {
    policyName: "EmergencyOverride",
    requester: {
        org: "UNHCROrgMSP",
        role: "admin"
    },
    approver: {
        org: "HealthcareProvider1MSP",
        role: "admin"
    },
    patientId: "PATIENT-123",
    reason: "Emergency medical treatment required",
    duration: "24 hours"
};

// This triggers automatic audit and notification
await invokePolicy(emergencyRequest);
```

### Channel Creation

To create a new healthcare data channel:

```bash
# Requires either (Orderer + UNHCR) OR (All healthcare + refugee orgs)
peer channel create \
    -o orderer1.havenhealthpassport.org:7050 \
    -c refugee-health-channel \
    -f channel.tx \
    --outputBlock refugee-health-channel.block \
    --tls \
    --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/havenhealthpassport.org/orderers/orderer1.havenhealthpassport.org/msp/tlscacerts/tlsca.havenhealthpassport.org-cert.pem
```

### Consensus Node Addition

To add a new orderer node:

```yaml
# Update configtx.yaml with new consenter
Consenters:
  - Host: orderer6.havenhealthpassport.org
    Port: 12050
    ClientTLSCert: crypto-config/ordererOrganizations/havenhealthpassport.org/orderers/orderer6.havenhealthpassport.org/tls/server.crt
    ServerTLSCert: crypto-config/ordererOrganizations/havenhealthpassport.org/orderers/orderer6.havenhealthpassport.org/tls/server.crt
```

Then apply the update using the ConsensusNodeAddition policy.

## Monitoring and Compliance

### Policy Violation Alerts

Monitor policy violations through logs:

```bash
# Check orderer logs for policy violations
docker logs orderer1.havenhealthpassport.org 2>&1 | grep "Policy Violation"

# Check audit logs
tail -f /var/hyperledger/orderer/audit/policy-violations.log
```

### Compliance Reporting

Generate compliance reports:

```bash
# Monthly compliance report
./generate-compliance-report.sh --month $(date +%Y-%m)

# HIPAA compliance check
./check-hipaa-compliance.sh --policy HIPAAComplianceOperations
```

## Troubleshooting

### Common Issues

1. **Policy Not Found**
   - Verify policies are properly integrated
   - Check configtx.yaml includes policy definitions
   - Regenerate genesis block if needed

2. **Access Denied**
   - Verify MSP configuration
   - Check certificate validity
   - Review policy requirements

3. **Emergency Override Not Working**
   - Ensure both required organizations approve
   - Check time limits haven't expired
   - Verify audit system is operational

### Debug Commands

```bash
# Verify policy configuration
configtxlator proto_decode --input genesis.block --type common.Block | jq '.data.data[0].payload.data.config.channel_group.groups.Orderer.policies'

# Check current orderer configuration
peer channel fetch config config_block.pb -o orderer1.havenhealthpassport.org:7050 -c system-channel

# Decode and inspect policies
configtxlator proto_decode --input config_block.pb --type common.Block | jq '.data.data[0].payload.data.config.channel_group.groups.Orderer.policies'
```

## Best Practices

1. **Regular Policy Reviews**
   - Review policy effectiveness monthly
   - Update based on operational needs
   - Document all policy changes

2. **Emergency Preparedness**
   - Test emergency override quarterly
   - Maintain updated contact list
   - Document emergency procedures

3. **Audit Trail Maintenance**
   - Archive audit logs monthly
   - Implement log rotation
   - Ensure tamper-proof storage

4. **Performance Monitoring**
   - Monitor policy evaluation times
   - Optimize frequently used policies
   - Balance security with performance

## Next Steps

1. Run policy tests: `./test-orderer-policies.sh`
2. Deploy to test network
3. Conduct security audit
4. Train administrators on policy usage
5. Document standard operating procedures
