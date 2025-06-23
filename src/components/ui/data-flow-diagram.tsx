import React from 'react';
import { MermaidDiagram } from '@lightenna/react-mermaid-diagram';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';

const DataFlowDiagram: React.FC = () => {
  const dataFlowSequence = `
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
    "mainBkg": "#1e293b",
    "secondBkg": "#334155",
    "tertiaryBkg": "#475569",
    "actorBkg": "#1e293b",
    "actorBorder": "#475569",
    "actorTextColor": "#f8fafc",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b",
    "signalTextColor": "#f8fafc",
    "c0": "#1e40af",
    "c1": "#059669",
    "c2": "#7c3aed",
    "c3": "#dc2626"
  }
}}%%
sequenceDiagram
    participant P as Patient/Refugee
    participant M as Mobile App
    participant E as SageMaker Edge
    participant A as API Gateway
    participant C as Comprehend
    participant CM as Comprehend Medical
    participant L as LangChain
    participant B as Bedrock Claude 3
    participant H as HealthLake
    participant BC as Blockchain
    participant D as Data Layer
    participant HP as Healthcare Provider

    P->>M: Upload documents + voice
    Note over M: Offline AI preprocessing
    M->>E: Local AI processing
    E-->>M: Processed data
    M->>A: Encrypted sync
    Note over A: When connectivity available
    A->>C: Language detection
    C->>CM: Medical entity extraction
    Note over CM: ICD-10/RxNorm coding
    CM->>L: Extracted entities
    L->>B: Translation request + RAG
    Note over B: Cultural adaptation
    B-->>L: Culturally-aware translation
    L->>H: FHIR resource creation
    Note over H: FHIR R4 compliance
    H->>BC: Blockchain verification
    Note over BC: Immutable hash creation
    BC->>D: Secure storage
    Note over D: Patient-controlled access
    HP->>A: Access request
    Note over A: AI-powered verification
    A->>HP: Verified access + translated records
  `;

  const processingSteps = [
    {
      title: "Offline-First Processing",
      description: "SageMaker Edge runs quantized models on-device for privacy and offline capability. AppSync GraphQL provides automatic retry and conflict resolution when connected.",
      glowColor: 'blue' as const,
    },
    {
      title: "AI-Powered Translation",
      description: "Comprehend Medical identifies conditions, medications, and procedures. Bedrock Claude 3 with RAG provides culturally-aware medical translations.",
      glowColor: 'purple' as const,
    },
    {
      title: "FHIR Compliance",
      description: "Convert processed data to FHIR R4 Patient, Observation, and Condition resources. HealthLake provides built-in NLP processing and population health analytics.",
      glowColor: 'green' as const,
    },
    {
      title: "Blockchain Verification",
      description: "Hyperledger Fabric smart contracts create tamper-proof verification hashes. Multi-organization consensus enables international healthcare access.",
      glowColor: 'orange' as const,
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
          Medical Data Processing Flow
        </h2>
        <p className="text-gray-300 text-center max-w-4xl mx-auto mb-8">
          This sequence diagram shows how medical data flows through the system from initial patient input 
          to final healthcare provider access, highlighting the AI processing and security measures at each step.
        </p>
      </motion.div>

      {/* Mermaid Sequence Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2 }}
        className="bg-slate-900/50 rounded-xl p-8 backdrop-blur-sm border border-slate-700/50 mb-8"
      >
        <div className="mermaid-container bg-slate-900 rounded-lg p-4">
          <MermaidDiagram>{dataFlowSequence}</MermaidDiagram>
        </div>
      </motion.div>

      {/* Key Processing Steps */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.4 }}
        className="grid grid-cols-1 md:grid-cols-2 gap-6"
      >
        {processingSteps.map((step, index) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * index }}
          >
            <GlowCard 
              glowColor={step.glowColor}
              customSize={true}
              className="w-full h-56 bg-white/10 backdrop-blur-sm"
            >
              <div className="flex flex-col h-full p-6">
                <h3 className="text-xl font-bold mb-4 text-white text-center">
                  {step.title}
                </h3>
                <p className="text-sm text-gray-300 leading-relaxed flex-1">
                  {step.description}
                </p>
              </div>
            </GlowCard>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
};

export default DataFlowDiagram; 