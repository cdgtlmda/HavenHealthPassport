# Configuration Decisions Record
# Haven Health Passport - AWS Managed Blockchain

## Document Purpose
This document records all configuration decisions made during the implementation of the Haven Health Passport blockchain infrastructure, including rationale and trade-offs.

## Decision Log

### DEC-001: Blockchain Framework Selection
**Date**: 2024-01-15
**Decision**: Use Hyperledger Fabric on AWS Managed Blockchain
**Alternatives Considered**:
- Ethereum-based private network
- Hyperledger Besu
- Custom blockchain implementation

**Rationale**:
- Hyperledger Fabric is designed for enterprise use cases
- Strong privacy features with channels and private data
- AWS Managed Blockchain reduces operational overhead
- Native support for complex access control

**Trade-offs**:
- Higher complexity than public blockchain solutions
- Vendor lock-in to AWS
- Limited smart contract languages (Go, JavaScript, Java)

### DEC-002: Network Edition Selection
**Date**: 2024-01-15
**Decision**: Use STANDARD edition instead of STARTER
**Rationale**:
- Production-grade performance requirements
- Higher availability SLA (99.9%)
- Support for more peer nodes
- Better suited for healthcare compliance

**Trade-offs**:
- Higher monthly cost (~$500 vs ~$250)
- Overprovisioned for initial launch

### DEC-003: Consensus Mechanism
**Date**: 2024-01-15
**Decision**: Use RAFT ordering service with 50% approval threshold
**Rationale**:
- RAFT provides crash fault tolerance
- Simpler than Kafka-based ordering
- 50% threshold balances security and operational efficiency

**Trade-offs**:
- Not Byzantine fault tolerant
- Requires odd number of orderers
- Less throughput than Kafka

### DEC-004: Peer Node Configuration
**Date**: 2024-01-15
**Decision**: Deploy 2 peer nodes with bc.t3.small instance type
**Rationale**:
- Minimum for high availability
- bc.t3.small sufficient for initial load (100 TPS)
- Cost-effective starting point
- Can scale horizontally or vertically as needed

**Trade-offs**:
- Limited to 100 TPS initially
- May need rapid scaling for growth

### DEC-005: Logging Strategy
**Date**: 2024-01-15
**Decision**: Enable all logging types with 30-day retention
**Alternatives Considered**:
- 7-day retention for cost savings
- 90-day retention for compliance
- Selective logging by component

**Rationale**:
- 30 days balances cost and compliance needs
- Full logging required for healthcare audit trails
- CloudWatch integration simplifies log management

**Trade-offs**:
- Higher storage costs
- Potential PII in logs requires careful handling

### DEC-006: VPC Architecture
**Date**: 2024-01-15
**Decision**: Use Interface VPC Endpoint with dedicated security group
**Rationale**:
- Private connectivity without internet gateway
- Granular security control
- Reduced data transfer costs
- Better compliance posture

**Trade-offs**:
- Additional VPC endpoint hourly charges
- More complex networking setup

### DEC-007: Security Group Rules
**Date**: 2024-01-15
**Decision**: Restrictive ingress (443, 30001-30004) from VPC CIDR only
**Rationale**:
- Principle of least privilege
- Only required ports for Fabric communication
- VPC CIDR restriction prevents external access

**Trade-offs**:
- May complicate future integrations
- Requires VPN/Direct Connect for external access

### DEC-008: Multi-AZ Deployment
**Date**: 2024-01-15
**Decision**: Distribute peer nodes across 2 availability zones
**Rationale**:
- Fault tolerance for AZ failures
- Required for production SLA
- Minimal additional cost

**Trade-offs**:
- Slight increase in inter-AZ latency
- More complex deployment automation

### DEC-009: State Database
**Date**: 2024-01-15
**Decision**: Use CouchDB (default) for world state
**Alternatives Considered**:
- LevelDB for simpler setup

**Rationale**:
- Rich query support needed for healthcare records
- JSON document storage aligns with FHIR
- Better indexing capabilities

**Trade-offs**:
- Higher resource usage
- More complex backup procedures

### DEC-010: Certificate Authority
**Date**: 2024-01-15
**Decision**: Use AWS Managed CA instead of external CA
**Rationale**:
- Simplified certificate management
- Integrated with AWS services
- Automated certificate lifecycle

**Trade-offs**:
- Cannot use existing enterprise CA
- Limited customization options

## Review Schedule

Configuration decisions will be reviewed:
- **Monthly**: During operations review
- **Quarterly**: During architecture review board
- **Annually**: During compliance audit

## Change Management

All configuration changes must:
1. Be documented in this record
2. Include impact analysis
3. Have rollback procedure
4. Be approved by technical lead
5. Be tested in staging environment

## Approval

**Technical Lead**: ___________________ Date: ___________
**Security Lead**: ___________________ Date: ___________
**Operations Lead**: _________________ Date: ___________
