#!/usr/bin/env python3

"""
Haven Health Passport - Network Diagram Generator
This script generates a visual network diagram for the blockchain architecture
"""

import json
import os
from pathlib import Path


def generate_mermaid_diagram():
    """Generate a Mermaid diagram of the network architecture"""

    # Get script directory
    script_dir = Path(__file__).parent
    config_dir = script_dir.parent / "config"
    docs_dir = script_dir.parent / "docs"

    # Create docs directory if needed
    docs_dir.mkdir(exist_ok=True)

    # Load configuration data
    try:
        with open(config_dir / "network-info.json", "r") as f:
            network_info = json.load(f)
    except:
        network_info = {}

    try:
        with open(config_dir / "vpc-info.json", "r") as f:
            vpc_info = json.load(f)
    except:
        vpc_info = {}

    # Generate Mermaid diagram
    diagram = """# Haven Health Passport - Blockchain Network Architecture

```mermaid
graph TB
    subgraph "AWS Cloud"
        subgraph "VPC"
            subgraph "AWS Managed Blockchain"
                MBN[Managed Blockchain Network<br/>Hyperledger Fabric v2.2]

                subgraph "Network Members"
                    M1[HavenHealthFoundation<br/>Primary Member]
                end

                subgraph "Peer Nodes"
                    P1[Peer Node 1<br/>bc.m5.large]
                end

                subgraph "Certificate Authority"
                    CA[Managed CA<br/>AWS HSM Protected]
                end

                subgraph "Ordering Service"
                    OS[Ordering Service<br/>Raft Consensus]
                end
            end

            subgraph "Network Security"
                VPE[VPC Endpoint]
                SG[Security Group<br/>Restrictive Rules]
                NACL[Network ACL<br/>Additional Security]
            end

            subgraph "Monitoring"
                CW[CloudWatch Logs]
                VFL[VPC Flow Logs]
            end
        end

        subgraph "Application Layer"
            API[API Gateway]
            APP[Haven Health App]
        end
    end

    subgraph "External Systems"
        HC[Healthcare Providers]
        NGO[NGO Partners]
        GOV[Government Agencies]
    end

    %% Connections
    APP --> API
    API --> VPE
    VPE --> MBN
    MBN --> M1
    M1 --> P1
    P1 --> CA
    P1 --> OS

    %% Security connections
    VPE -.->|Protected by| SG
    VPE -.->|Protected by| NACL

    %% Monitoring connections
    P1 -.->|Logs to| CW
    CA -.->|Logs to| CW
    OS -.->|Logs to| CW
    VPE -.->|Flow logs to| VFL

    %% External connections
    HC -->|Verify Records| API
    NGO -->|Access Records| API
    GOV -->|Audit Trail| API

    %% Styling
    classDef blockchain fill:#4B8BBE,stroke:#646464,stroke-width:2px,color:#fff
    classDef security fill:#FF6B6B,stroke:#C92A2A,stroke-width:2px,color:#fff
    classDef monitoring fill:#51CF66,stroke:#2F9E44,stroke-width:2px,color:#fff
    classDef external fill:#FFD93D,stroke:#FCC419,stroke-width:2px,color:#000

    class MBN,M1,P1,CA,OS blockchain
    class VPE,SG,NACL security
    class CW,VFL monitoring
    class HC,NGO,GOV external
```

## Network Components

### Core Blockchain Infrastructure
- **Managed Blockchain Network**: Enterprise-grade Hyperledger Fabric network
- **Member Organization**: HavenHealthFoundation as primary governing member
- **Peer Nodes**: High-performance nodes for transaction processing
- **Certificate Authority**: AWS HSM-protected certificate management
- **Ordering Service**: Raft consensus for transaction ordering

### Security Layer
- **VPC Endpoint**: Private connectivity to blockchain network
- **Security Groups**: Application-level firewall rules
- **Network ACLs**: Subnet-level access control
- **TLS Encryption**: All communications encrypted

### Monitoring & Compliance
- **CloudWatch Logs**: Comprehensive logging for audit trails
- **VPC Flow Logs**: Network traffic monitoring
- **Performance Metrics**: Real-time performance monitoring
- **Compliance Reporting**: HIPAA-compliant audit logs

### Integration Points
- **Healthcare Providers**: Verify patient records and credentials
- **NGO Partners**: Access refugee health records with consent
- **Government Agencies**: Audit trail for compliance verification
"""

    # Write diagram to file
    diagram_file = docs_dir / "network-architecture-diagram.md"
    with open(diagram_file, "w") as f:
        f.write(diagram)

    print(f"✅ Network diagram generated: {diagram_file}")

    # Also generate a simplified text diagram
    text_diagram = """
# Haven Health Passport - Network Architecture (Text)

┌─────────────────────────────────────────────────────────────────┐
│                           AWS Cloud                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                          VPC                             │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │         AWS Managed Blockchain Network            │  │   │
│  │  │                                                   │  │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │  │   │
│  │  │  │   Member    │  │  Peer Node  │  │    CA    │ │  │   │
│  │  │  │   Haven     │──│  bc.m5.lg   │──│  (HSM)   │ │  │   │
│  │  │  │ Foundation  │  │             │  │          │ │  │   │
│  │  │  └─────────────┘  └─────────────┘  └──────────┘ │  │   │
│  │  │                                                   │  │   │
│  │  │            ┌─────────────────────┐               │  │   │
│  │  │            │  Ordering Service   │               │  │   │
│  │  │            │  (Raft Consensus)   │               │  │   │
│  │  │            └─────────────────────┘               │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │   │
│  │  │ VPC Endpoint │  │Security Group│  │ Network ACL  │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────────────────────┐   │
│  │ CloudWatch Logs  │  │        Application Layer         │   │
│  └──────────────────┘  └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
"""

    # Write text diagram
    text_file = docs_dir / "network-architecture-text.txt"
    with open(text_file, "w") as f:
        f.write(text_diagram)

    print(f"✅ Text diagram generated: {text_file}")


if __name__ == "__main__":
    generate_mermaid_diagram()
