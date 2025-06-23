import React from 'react';
import { MermaidDiagram } from '@lightenna/react-mermaid-diagram';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';

const BlockchainDiagram: React.FC = () => {
  const blockchainArchitecture = `
%%{init: {
  "theme": "dark",
  "themeVariables": {
    "background": "#0f172a",
    "primaryColor": "#1e293b",
    "primaryTextColor": "#f8fafc",
    "primaryBorderColor": "#475569",
    "lineColor": "#64748b",
    "sectionBkColor": "#1e293b",
    "altSectionBkColor": "#334155",
    "gridColor": "#475569",
    "secondaryColor": "#334155",
    "tertiaryColor": "#475569",
    "cScale0": "#1e40af",
    "cScale1": "#059669",
    "cScale2": "#7c3aed",
    "cScale3": "#dc2626",
    "cScale4": "#ea580c",
    "cScale5": "#4338ca",
    "cScale6": "#374151"
  }
}}%%
graph TB
    subgraph "Patient Layer"
        P1["Patient A<br/>Syria → Lebanon"]
        P2["Patient B<br/>Afghanistan → Germany"]
        P3["Patient C<br/>Ukraine → Poland"]
    end
    
    subgraph "Healthcare Organizations"
        H1["UNHCR<br/>Registration Authority"]
        H2["MSF<br/>Field Clinic"]
        H3["German Hospital<br/>Receiving Care"]
        H4["WHO<br/>Global Coordinator"]
    end
    
    subgraph "Blockchain Network - Hyperledger Fabric"
        subgraph "Channel: HealthRecords"
            C1["Smart Contract<br/>HealthRecord"]
            C2["Smart Contract<br/>AccessControl"]
            C3["Smart Contract<br/>CrossBorder"]
        end
        
        subgraph "Peer Nodes"
            N1["UNHCR Peer<br/>Endorser"]
            N2["MSF Peer<br/>Endorser"]  
            N3["Hospital Peer<br/>Committer"]
            N4["WHO Peer<br/>Orderer"]
        end
        
        subgraph "Ledger"
            L1["Block 1<br/>Genesis"]
            L2["Block 2<br/>Patient Records"]
            L3["Block 3<br/>Access Grants"]
            L4["Block 4<br/>Cross-Border Tx"]
        end
    end
    
    subgraph "Off-Chain Storage"
        S1["IPFS<br/>Encrypted Documents"]
        S2["HealthLake<br/>FHIR Resources"]
        S3["S3<br/>Voice/Image Data"]
    end
    
    P1 --> H1
    P2 --> H2
    P3 --> H3
    
    H1 --> C1
    H2 --> C1
    H3 --> C2
    H4 --> C3
    
    C1 --> N1
    C1 --> N2
    C2 --> N3
    C3 --> N4
    
    N1 --> L2
    N2 --> L2
    N3 --> L3
    N4 --> L4
    
    L1 --> L2
    L2 --> L3
    L3 --> L4
    
    C1 -.-> S1
    C1 -.-> S2
    C2 -.-> S3
    
    classDef patient fill:#1e40af,stroke:#3b82f6,stroke-width:2px,color:#ffffff
    classDef healthcare fill:#059669,stroke:#10b981,stroke-width:2px,color:#ffffff
    classDef contract fill:#7c3aed,stroke:#a855f7,stroke-width:2px,color:#ffffff
    classDef peer fill:#dc2626,stroke:#ef4444,stroke-width:2px,color:#ffffff
    classDef ledger fill:#ea580c,stroke:#f97316,stroke-width:2px,color:#ffffff
    classDef storage fill:#4338ca,stroke:#6366f1,stroke-width:2px,color:#ffffff
    
    class P1,P2,P3 patient
    class H1,H2,H3,H4 healthcare
    class C1,C2,C3 contract
    class N1,N2,N3,N4 peer
    class L1,L2,L3,L4 ledger
    class S1,S2,S3 storage
  `;

  const blockchainComponents = [
    {
      title: "Smart Contracts",
      description: "HealthRecord contracts manage patient data verification and consent. AccessControl provides role-based permissions and emergency access. CrossBorder enables international healthcare provider verification.",
      glowColor: 'purple' as const,
    },
    {
      title: "Network Consensus",
      description: "UNHCR and MSF validate transactions through endorsement. WHO sequences blocks for global consistency. Hospitals commit verified transactions to the ledger.",
      glowColor: 'red' as const,
    },
    {
      title: "Data Privacy",
      description: "Only verification hashes and metadata stored on-chain. Encrypted medical data secured in off-chain storage. Patient-controlled encryption keys ensure data sovereignty.",
      glowColor: 'blue' as const,
    },
    {
      title: "Cross-Border Trust",
      description: "International healthcare organizations participate as network peers. Majority agreement required for record validation. Tamper-proof audit trail maintains compliance.",
      glowColor: 'green' as const,
    },
    {
      title: "Emergency Access",
      description: "Break glass emergency override with full audit logging. Time-limited access grants with automatic expiration. Multi-signature approval for sensitive access requests.",
      glowColor: 'orange' as const,
    },
    {
      title: "Scalability",
      description: "Separate channels for different use cases and regions. Regional ledgers with global synchronization capabilities. Automated archival of old transactions for performance.",
      glowColor: 'blue' as const,
    }
  ];

  return (
    <div className="w-full bg-black text-white">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="mb-8"
      >
        <h2 className="text-3xl font-bold text-white mb-4 text-center">
          Blockchain Architecture for Cross-Border Healthcare
        </h2>
        <p className="text-gray-300 text-center max-w-4xl mx-auto mb-8">
          The Hyperledger Fabric network creates an immutable, blockchain-verified system for healthcare record verification
        </p>
      </motion.div>

      {/* Mermaid Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2 }}
        className="bg-slate-900/50 rounded-xl p-8 backdrop-blur-sm border border-slate-700/50 mb-8"
      >
        <div className="mermaid-container bg-slate-900 rounded-lg p-4">
          <MermaidDiagram>{blockchainArchitecture}</MermaidDiagram>
        </div>
      </motion.div>

      {/* Key Components */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.4 }}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        {blockchainComponents.map((component, index) => (
          <motion.div
            key={component.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * index }}
          >
            <GlowCard 
              glowColor={component.glowColor}
              customSize={true}
              className="w-full h-56 bg-white/10 backdrop-blur-sm"
            >
              <div className="flex flex-col h-full p-6">
                <h3 className="text-lg font-bold mb-3 text-white text-center">
                  {component.title}
                </h3>
                <p className="text-sm text-gray-300 leading-relaxed flex-1">
                  {component.description}
                </p>
              </div>
            </GlowCard>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
};

export default BlockchainDiagram; 