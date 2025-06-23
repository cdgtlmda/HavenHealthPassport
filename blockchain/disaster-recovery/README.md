# Blockchain Disaster Recovery Testing Framework

## Overview

This directory contains the comprehensive disaster recovery testing framework for the Haven Health Passport blockchain infrastructure. The tests validate that the blockchain network can recover from various failure scenarios while maintaining data integrity and meeting compliance requirements.

## Directory Structure

```
disaster-recovery/
├── docs/
│   └── disaster-recovery-test-plan.md    # Comprehensive test plan
├── scripts/
│   ├── run-dr-node-001.sh               # Execute single peer failure test
│   └── run-all-tests.sh                  # Execute all DR tests (TBD)
├── tests/
│   ├── test_dr_node_001_single_peer_failure.py
│   └── [additional test implementations]
└── results/
    └── [test execution results organized by timestamp]
```

## Test Categories

1. **Node Failure Recovery (DR-NODE-XXX)**
   - Single peer node failure
   - Multiple peer node failure
   - Orderer node failure
   - Certificate Authority failure

2. **Data Recovery (DR-DATA-XXX)**
   - Ledger corruption recovery
   - State database recovery
   - Private data collection recovery
   - Smart contract state recovery

3. **Network Failure Recovery (DR-NET-XXX)**
   - Network partition recovery
   - AWS region failure
   - VPC connectivity loss
   - Load balancer failure

4. **Security Recovery (DR-SEC-XXX)**
   - Compromised certificate recovery
   - HSM failure recovery
   - Access control corruption
   - Encryption key recovery
5. **Application Integration Recovery (DR-APP-XXX)**
   - SDK connection recovery
   - Event hub recovery
   - Transaction queue recovery
   - API gateway recovery

6. **Compliance Recovery (DR-COMP-XXX)**
   - Audit trail recovery
   - HIPAA compliance validation
   - GDPR data portability
   - Cross-border data sovereignty

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Python 3.8+ with required dependencies
3. Access to AWS Managed Blockchain network
4. Environment variables set:
   - `AMB_NETWORK_ID`: Your AWS Managed Blockchain network ID
   - `AMB_MEMBER_ID`: Your member ID in the network

## Running Tests

### Individual Test Execution

To run a specific disaster recovery test:

```bash
cd blockchain/disaster-recovery/scripts
export AMB_NETWORK_ID="your-network-id"
export AMB_MEMBER_ID="your-member-id"
./run-dr-node-001.sh
```

### Test Results

Test results are saved in the `results/` directory with timestamps:
- JSON reports with detailed metrics
- Log files with execution details
- RTO/RPO achievement metrics

## Success Criteria

Each test must meet:
1. Recovery Time Objective (RTO) targets
2. Recovery Point Objective (RPO) targets
3. Data integrity validation
4. Compliance requirements maintenance

## Important Notes

- Always execute tests in a dedicated test environment first
- Ensure rollback procedures are in place
- Monitor production systems during any production testing
- Document all deviations from expected behavior
