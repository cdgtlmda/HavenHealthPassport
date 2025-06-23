import React from 'react';
import { MermaidDiagram } from '@lightenna/react-mermaid-diagram';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';

const TimelineDiagram: React.FC = () => {
  const timelineDiagram = `
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
    "cScale0": "#059669",
    "cScale1": "#eab308", 
    "cScale2": "#3b82f6",
    "cScale3": "#7c3aed",
    "cScale4": "#dc2626"
  }
}}%%
graph LR
    subgraph "Foundation (Complete)"
        A[Core Architecture]
        B[Blockchain Integration]
        C[AI/ML Services]
        D[API Development]
    end
    
    subgraph "Testing Phase (Critical Gap)"
        E[Unit Testing<br/>1-3% → 90%]
        F[Integration Testing]
        G[Security Testing]
        H[Performance Testing]
    end
    
    subgraph "Infrastructure (Not Started)"
        I[AWS Deployment]
        J[CI/CD Pipeline]
        K[Container Orchestration]
    end
    
    subgraph "Certification (Final Phase)"
        L[Healthcare Compliance]
        M[Security Audit]
        N[Production Review]
    end
    
    A --> E
    B --> F
    C --> G
    D --> H
    E --> I
    F --> J
    G --> K
    H --> K
    I --> L
    J --> M
    K --> N
    
    classDef complete fill:#059669,stroke:#10b981,stroke-width:2px,color:#ffffff
    classDef critical fill:#eab308,stroke:#f59e0b,stroke-width:2px,color:#000000
    classDef infrastructure fill:#3b82f6,stroke:#60a5fa,stroke-width:2px,color:#ffffff
    classDef certification fill:#7c3aed,stroke:#a855f7,stroke-width:2px,color:#ffffff
    
    class A,B,C,D complete
    class E,F,G,H critical
    class I,J,K infrastructure
    class L,M,N certification
  `;

  const phases = [
    {
      title: "Foundation Complete",
      description: "Core architecture, blockchain integration, AI/ML services, and API development are fully implemented and functional.",
      status: "100% Complete",
      statusColor: "text-green-400",
      glowColor: 'green' as const,
    },
    {
      title: "Testing Phase (Critical Gap)",
      description: "Current test coverage is only 1-3%. Need to achieve 90%+ coverage across unit, integration, security, and performance testing.",
      status: "Weeks 1-6",
      statusColor: "text-yellow-400",
      glowColor: 'yellow' as const,
    },
    {
      title: "Infrastructure Deployment",
      description: "AWS production environment setup, CI/CD pipeline implementation, and container orchestration deployment.",
      status: "Weeks 7-9",
      statusColor: "text-blue-400",
      glowColor: 'blue' as const,
    },
    {
      title: "Certification & Compliance",
      description: "Healthcare compliance certification, comprehensive security audit, and final production readiness review.",
      status: "Weeks 13-14",
      statusColor: "text-purple-400",
      glowColor: 'purple' as const,
    }
  ];

  const criticalGaps = [
    {
      gap: "Testing Coverage",
      current: "1-3%",
      required: "90%+",
      impact: "Production Blocker"
    },
    {
      gap: "Deployment Infrastructure", 
      current: "Not Started",
      required: "Full AWS Setup",
      impact: "Deployment Blocker"
    },
    {
      gap: "QA Processes",
      current: "0% Complete",
      required: "Full QA Framework",
      impact: "Quality Assurance"
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
          Development Implementation Timeline
        </h2>
        <p className="text-gray-300 text-center max-w-4xl mx-auto mb-8">
          Haven Health Passport is 75% demo-ready but only 25% production-ready. 
          The timeline below shows the 14-week path to production deployment with critical development gaps highlighted.
        </p>
      </motion.div>

      {/* Mermaid Timeline Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2 }}
        className="bg-slate-900/50 rounded-xl p-8 backdrop-blur-sm border border-slate-700/50 mb-8"
      >
        <div className="mermaid-container bg-slate-900 rounded-lg p-4 overflow-x-auto">
          <MermaidDiagram>{timelineDiagram}</MermaidDiagram>
        </div>
      </motion.div>

      {/* Phase Explanations */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.4 }}
        className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12"
      >
        {phases.map((phase, index) => (
          <motion.div
            key={phase.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * index }}
          >
            <GlowCard 
              glowColor={phase.glowColor}
              customSize={true}
              className="w-full h-56 bg-white/10 backdrop-blur-sm"
            >
              <div className="flex flex-col h-full p-6">
                <h3 className="text-lg font-bold mb-3 text-white">
                  {phase.title}
                </h3>
                <p className="text-sm text-gray-300 leading-relaxed flex-1 mb-3">
                  {phase.description}
                </p>
                <div className={`text-sm font-medium ${phase.statusColor}`}>
                  {phase.status}
                </div>
              </div>
            </GlowCard>
          </motion.div>
        ))}
      </motion.div>

      {/* Critical Gaps */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.6 }}
        className="bg-red-500/10 border border-red-500/20 rounded-xl p-8 backdrop-blur-sm"
      >
        <h3 className="text-2xl font-bold text-red-400 mb-6 text-center">
          Critical Development Gaps
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {criticalGaps.map((gap, index) => (
            <motion.div
              key={gap.gap}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * index }}
              className="bg-red-900/20 rounded-lg p-6 border border-red-500/30"
            >
              <h4 className="text-lg font-semibold text-white mb-3">{gap.gap}</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Current:</span>
                  <span className="text-red-300">{gap.current}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Required:</span>
                  <span className="text-green-300">{gap.required}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Impact:</span>
                  <span className="text-yellow-300">{gap.impact}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
};

export default TimelineDiagram; 