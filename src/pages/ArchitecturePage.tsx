import React, { useState } from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';
import { Button } from '@/components/ui/button';
import ArchitectureDiagram from '@/components/ui/architecture-diagram';
import DataFlowDiagram from '@/components/ui/data-flow-diagram';
import BlockchainDiagram from '@/components/ui/blockchain-diagram';
import {
  IconDeviceMobile,
  IconWorld,
  IconBrain,
  IconBlockquote,
  IconDatabase,
  IconShield,
} from "@tabler/icons-react";
import { Layers, GitBranch, Shield, ArrowRight } from 'lucide-react';

const ArchitecturePage: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>('high-level');

  const architectureSections = [
    {
      id: 'high-level',
      title: 'System Architecture',
      description: 'High-level system layers and components',
      icon: <Layers className="w-5 h-5" />,
      component: <ArchitectureDiagram />
    },
    {
      id: 'data-flow',
      title: 'Data Flow',
      description: 'Medical data processing sequence',
      icon: <GitBranch className="w-5 h-5" />,
      component: <DataFlowDiagram />
    },
    {
      id: 'blockchain',
      title: 'Blockchain Integration',
      description: 'Cross-border verification architecture',
      icon: <Shield className="w-5 h-5" />,
      component: <BlockchainDiagram />
    }
  ];

  const activeComponent = architectureSections.find(section => section.id === activeSection);

  const features = [
    {
      title: "Frontend Applications",
      description: "Mobile First: React Native applications optimized for low-bandwidth environments. Progressive Web Apps: Accessible from any device with offline capabilities. Healthcare Provider Portal: Streamlined interfaces for medical professionals.",
      icon: <IconDeviceMobile className="w-8 h-8" />,
      glowColor: 'blue' as const,
    },
    {
      title: "Intelligent Backend Services",
      description: "GraphQL API: Efficient data fetching optimized for mobile networks. Microservices Architecture: Scalable, maintainable service design. Event-Driven Processing: Real-time updates and synchronization.",
      icon: <IconWorld className="w-8 h-8" />,
      glowColor: 'purple' as const,
    },
    {
      title: "AI-Powered Intelligence",
      description: "Amazon Bedrock Integration: State-of-the-art language models for medical translation. LangChain Orchestration: Intelligent document processing and understanding. Amazon Comprehend Medical: Automated medical entity recognition. Custom ML Models: Specialized models for refugee healthcare patterns.",
      icon: <IconBrain className="w-8 h-8" />,
      glowColor: 'green' as const,
    },
    {
      title: "Blockchain Infrastructure",
      description: "AWS Managed Blockchain: Enterprise-grade Hyperledger Fabric deployment. Smart Contract Verification: Automated health record validation. Blockchain Trust Network: Cross-border verification without central authority.",
      icon: <IconBlockquote className="w-8 h-8" />,
      glowColor: 'orange' as const,
    },
    {
      title: "Data Layer",
      description: "Amazon HealthLake: FHIR-compliant health data storage. Encrypted Document Storage: Secure S3 repositories with patient-controlled access. OpenSearch Integration: Fast, relevant health information retrieval. DynamoDB: Low-latency metadata and session management.",
      icon: <IconDatabase className="w-8 h-8" />,
      glowColor: 'red' as const,
    },
    {
      title: "Security & Compliance",
      description: "Built from the ground up with security and privacy at its core: End-to-end encryption for all health data. HIPAA and GDPR compliance by design. Zero-trust security architecture. Biometric authentication options. Audit trails for all data access.",
      icon: <IconShield className="w-8 h-8" />,
      glowColor: 'purple' as const,
    },
  ];

  return (
    <div className="min-h-screen bg-black text-white">
      <Navigation />
      
      {/* Hero Section */}
      <motion.section 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container px-4 pt-40 pb-12"
      >
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-normal mb-4 tracking-tight text-white">
            Architecture
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto leading-relaxed">
            Building for Global Scale and Local Impact
          </p>
        </div>
      </motion.section>

      <div className="container px-4 py-8">
        {/* Introduction */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="max-w-4xl mx-auto mb-12"
        >
          <div className="prose prose-lg prose-invert max-w-none">
            <p className="text-gray-300 text-lg leading-relaxed mb-8">
              Haven Health Passport's architecture combines cutting-edge cloud technologies with practical field requirements, creating a system that works equally well in urban hospitals and remote refugee camps.
            </p>

            <h3 className="text-2xl font-semibold text-white mb-4">Technical Foundation</h3>
            <p className="text-gray-300 leading-relaxed mb-8">
              The platform leverages a modern, cloud-native architecture designed for resilience, security, and global accessibility:
            </p>
          </div>
        </motion.div>

        {/* Architecture Cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-16"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <GlowCard 
                  glowColor={feature.glowColor}
                  customSize={true}
                  className="w-full h-80 bg-white/10 backdrop-blur-sm"
                >
                  <div className="flex flex-col h-full p-2">
                    <div className="flex items-center justify-center mb-4 text-white">
                      {feature.icon}
                    </div>
                    <h3 className="text-lg font-bold mb-3 text-white text-center">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-gray-300 leading-relaxed flex-1">
                      {feature.description}
                    </p>
                  </div>
                </GlowCard>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Architecture Diagrams Navigation */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="max-w-full mx-auto mb-12"
        >
          <div className="mb-8">
            <h2 className="text-3xl lg:text-5xl lg:leading-tight font-medium text-white mb-4 text-center tracking-tight">
              Architecture Diagrams
            </h2>
            <p className="text-lg text-gray-400 text-center max-w-3xl mx-auto leading-relaxed">
              Explore Haven Health Passport's technical architecture through clear, visual diagrams. 
              Each section shows a different aspect of the system with detailed explanations.
            </p>
          </div>
          
          <div className="flex flex-wrap justify-center gap-4 mb-8">
            {architectureSections.map((section) => (
              <Button
                key={section.id}
                variant={activeSection === section.id ? "default" : "outline"}
                size="lg"
                onClick={() => setActiveSection(section.id)}
                className={`flex items-center space-x-2 ${
                  activeSection === section.id ? "button-gradient" : ""
                }`}
              >
                {section.icon}
                <span>{section.title}</span>
                {activeSection === section.id && <ArrowRight className="w-4 h-4" />}
              </Button>
            ))}
          </div>
        </motion.div>

        {/* Active Diagram */}
        <motion.div
          key={activeSection}
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          {activeComponent?.component}
        </motion.div>
      </div>

      <Footer />
    </div>
  );
};

export default ArchitecturePage;