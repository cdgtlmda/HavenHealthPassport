# Haven Health Passport Blockchain Network Diagram

```mermaid
graph TB
    subgraph "AWS Cloud"
        subgraph "VPC"
            subgraph "Availability Zone 1"
                P1[Peer Node 1<br/>bc.t3.small]
                CL1[CloudWatch Logs<br/>Peer 1]
            end

            subgraph "Availability Zone 2"
                P2[Peer Node 2<br/>bc.t3.small]
                CL2[CloudWatch Logs<br/>Peer 2]
            end

            VPE[VPC Endpoint<br/>Interface Type]
            SG[Security Group<br/>Port 443, 30001-30004]
            NACL[Network ACL<br/>Additional Security Layer]
        end

        subgraph "AWS Managed Blockchain"
            NET[Blockchain Network<br/>Hyperledger Fabric 2.2]
            MEM[Primary Member<br/>haven-health-primary]
            CA[Certificate Authority<br/>Member CA]
            ORD[Ordering Service<br/>RAFT Consensus]
        end

        subgraph "Storage & Monitoring"
            CW[CloudWatch<br/>Logs & Metrics]
            S3[S3 Bucket<br/>Backup Storage]
            SSM[SSM Parameter Store<br/>Configuration]
            KMS[AWS KMS<br/>Key Management]
        end

        subgraph "Access Layer"
            IAM[IAM Roles<br/>& Policies]
            API[API Gateway<br/>Future]
        end
    end

    subgraph "External Systems"
        WEB[Web Portal]
        MOB[Mobile App]
        HL7[Healthcare Systems<br/>HL7 FHIR]
    end

    %% Connections
    P1 -.-> CL1
    P2 -.-> CL2
    P1 <--> NET
    P2 <--> NET
    NET --> MEM
    MEM --> CA
    NET --> ORD
    VPE --> NET
    SG --> VPE
    NACL --> VPE
    CL1 --> CW
    CL2 --> CW
    NET --> SSM
    NET --> KMS
    NET -.-> S3
    IAM --> NET
    API -.-> VPE
    WEB -.-> API
    MOB -.-> API
    HL7 -.-> API

    %% Styling
    classDef aws fill:#FF9900,stroke:#333,stroke-width:2px,color:#fff
    classDef blockchain fill:#4B6EAF,stroke:#333,stroke-width:2px,color:#fff
    classDef storage fill:#569A31,stroke:#333,stroke-width:2px,color:#fff
    classDef external fill:#232F3E,stroke:#333,stroke-width:2px,color:#fff

    class NET,MEM,CA,ORD blockchain
    class CW,S3,SSM,KMS storage
    class P1,P2,VPE,SG,NACL,IAM,API aws
    class WEB,MOB,HL7 external
```

## Network Flow Description

### 1. Client Connection Flow
1. External clients (Web Portal, Mobile App, Healthcare Systems) connect via API Gateway
2. API Gateway routes requests through VPC Endpoint
3. VPC Endpoint provides secure, private connectivity to Managed Blockchain
4. Security Group and Network ACL enforce access policies

### 2. Transaction Flow
1. Client submits transaction to peer node
2. Peer node validates transaction against chaincode
3. Endorsing peers sign the transaction
4. Transaction sent to ordering service
5. Orderer creates block and distributes to all peers
6. Peers validate and commit block to ledger

### 3. Certificate Management Flow
1. New members/users request certificates from CA
2. CA validates identity and issues certificates
3. Certificates stored in user wallet (application-side)
4. All blockchain operations require valid certificates

### 4. Monitoring Flow
1. All components emit logs to CloudWatch
2. Metrics collected for performance monitoring
3. Alerts configured for critical events
4. Regular backups to S3 for disaster recovery

## Security Zones

### Public Zone
- API Gateway (future implementation)
- Public-facing endpoints with WAF protection

### Private Zone
- VPC with private subnets
- Peer nodes and blockchain network
- No direct internet access

### Data Zone
- Encrypted storage in S3
- Configuration in SSM Parameter Store
- Keys managed by AWS KMS

## High Availability Design

1. **Multi-AZ Deployment**: Peer nodes in separate availability zones
2. **Redundant Peers**: Minimum 2 peers for fault tolerance
3. **Automatic Failover**: Managed by AWS Managed Blockchain
4. **Data Replication**: Blockchain ledger replicated across all peers
