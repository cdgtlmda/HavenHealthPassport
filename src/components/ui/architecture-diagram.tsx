import React from 'react';
import { MermaidDiagram } from '@lightenna/react-mermaid-diagram';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';

const ArchitectureDiagram: React.FC = () => {
  const architectureDiagram = `
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
    subgraph "Frontend Layer"
        A["Mobile App<br/>React Native + AI"]
        B["Web Portal<br/>QuickSight ML"]
        C["Provider Portal<br/>Clinical AI"]
    end
    
    subgraph "API Layer"
        D["GraphQL Gateway<br/>AppSync + Bedrock"]
        E["REST Endpoints<br/>Lambda + AI"]
    end
    
    subgraph "Application Services"
        F["Auth Service<br/>Cognito + Fraud AI"]
        G["Health Records<br/>HealthLake + Comprehend"]
        H["Translation<br/>LangChain + Bedrock"]
        I["Voice Processing<br/>Transcribe + Polly"]
    end
    
    subgraph "AI/ML Services"
        J["Bedrock Claude 3<br/>Medical Translation"]
        K["SageMaker<br/>Custom Models"]
        L["Comprehend Medical<br/>Entity Extraction"]
        M["Fraud Detector<br/>Risk Assessment"]
    end
    
    subgraph "Blockchain Layer"
        N["Managed Blockchain<br/>Hyperledger Fabric"]
        O["Smart Contracts<br/>AI-Triggered"]
    end
    
    subgraph "Data Layer"
        P["HealthLake<br/>FHIR R4 + NLP"]
        Q["OpenSearch<br/>Vector RAG"]
        R["DynamoDB<br/>Sessions"]
        S["S3<br/>Documents"]
    end
    
    subgraph "Infrastructure"
        T["Multi-Region<br/>Auto-Failover"]
        U["Edge Computing<br/>Offline AI"]
    end
    
    A --> D
    B --> D
    C --> E
    D --> F
    D --> G
    E --> H
    E --> I
    F --> M
    G --> L
    H --> J
    I --> J
    G --> P
    H --> Q
    F --> R
    G --> S
    N --> O
    P --> N
    
    classDef frontend fill:#1e40af,stroke:#3b82f6,stroke-width:2px,color:#ffffff
    classDef api fill:#059669,stroke:#10b981,stroke-width:2px,color:#ffffff
    classDef services fill:#7c3aed,stroke:#a855f7,stroke-width:2px,color:#ffffff
    classDef ai fill:#dc2626,stroke:#ef4444,stroke-width:2px,color:#ffffff
    classDef blockchain fill:#ea580c,stroke:#f97316,stroke-width:2px,color:#ffffff
    classDef data fill:#4338ca,stroke:#6366f1,stroke-width:2px,color:#ffffff
    classDef infra fill:#374151,stroke:#6b7280,stroke-width:2px,color:#ffffff
    
    class A,B,C frontend
    class D,E api
    class F,G,H,I services
    class J,K,L,M ai
    class N,O blockchain
    class P,Q,R,S data
    class T,U infra
  `;

  const layers = [
    {
      title: "Frontend Layer",
      description: "User-facing applications optimized for low-bandwidth environments with offline AI capabilities.",
      glowColor: 'blue' as const,
    },
    {
      title: "API Layer", 
      description: "Intelligent API gateway with GraphQL and REST endpoints, enhanced by AI for optimal routing.",
      glowColor: 'green' as const,
    },
    {
      title: "Application Services",
      description: "Core business logic including authentication, health records, translation, and voice processing.",
      glowColor: 'purple' as const,
    },
    {
      title: "AI/ML Services",
      description: "Advanced AI pipeline using Amazon Bedrock, SageMaker, and Comprehend Medical for intelligent processing.",
      glowColor: 'red' as const,
    },
    {
      title: "Blockchain Layer",
      description: "Hyperledger Fabric network for immutable health record verification and cross-border trust.",
      glowColor: 'orange' as const,
    },
    {
      title: "Data Layer",
      description: "FHIR-compliant storage with HealthLake, vector search, and encrypted document repositories.",
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
          High-Level System Architecture
        </h2>
        <p className="text-gray-300 text-center max-w-4xl mx-auto mb-8">
          Haven Health Passport follows a layered architecture designed for scalability, security, and offline-first operation. 
          Each layer serves a specific purpose in delivering healthcare services to displaced populations.
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
          <MermaidDiagram>{architectureDiagram}</MermaidDiagram>
        </div>
      </motion.div>

      {/* Layer Explanations */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.4 }}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        {layers.map((layer, index) => (
          <motion.div
            key={layer.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * index }}
          >
            <GlowCard 
              glowColor={layer.glowColor}
              customSize={true}
              className="w-full h-48 bg-white/10 backdrop-blur-sm"
            >
              <div className="flex flex-col h-full p-6">
                <h3 className="text-lg font-bold mb-3 text-white text-center">
                  {layer.title}
                </h3>
                <p className="text-sm text-gray-300 leading-relaxed flex-1">
                  {layer.description}
                </p>
              </div>
            </GlowCard>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
};

export default ArchitectureDiagram; 