import React from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { BentoCard, BentoGrid } from '@/components/ui/bento-grid';
import { motion } from 'framer-motion';
import {
  Shield,
  Globe,
  Smartphone,
  Building,
  AlertTriangle,
  Lock,
} from 'lucide-react';

const OverviewPage: React.FC = () => {
  const features = [
    {
      Icon: Shield,
      name: "Blockchain-Verified Security",
      description: "Leveraging AWS Managed Blockchain and Hyperledger Fabric to create tamper-proof health records that maintain integrity across borders and systems.",
      href: "/architecture",
      cta: "Learn more",
      background: <div className="absolute -right-20 -top-20 opacity-60" />,
      className: "lg:row-start-1 lg:row-end-4 lg:col-start-2 lg:col-end-3",
    },
    {
      Icon: Globe,
      name: "Universal Language Access",
      description: "Supporting 50+ languages with culturally-aware medical translation powered by Amazon Bedrock and LangChain.",
      href: "/use-cases",
      cta: "Learn more",
      background: <div className="absolute -right-20 -top-20 opacity-60" />,
      className: "lg:col-start-1 lg:col-end-2 lg:row-start-1 lg:row-end-3",
    },
    {
      Icon: Smartphone,
      name: "Offline-First Design",
      description: "Built for the realities of displacement - full functionality without internet connectivity, with intelligent synchronization.",
      href: "/demos",
      cta: "Learn more",
      background: <div className="absolute -right-20 -top-20 opacity-60" />,
      className: "lg:col-start-1 lg:col-end-2 lg:row-start-3 lg:row-end-4",
    },
    {
      Icon: Building,
      name: "Healthcare Provider Integration",
      description: "FHIR-compliant records that integrate seamlessly with existing healthcare systems while maintaining patient data sovereignty.",
      href: "/architecture",
      cta: "Learn more",
      background: <div className="absolute -right-20 -top-20 opacity-60" />,
      className: "lg:col-start-3 lg:col-end-3 lg:row-start-1 lg:row-end-2",
    },
    {
      Icon: AlertTriangle,
      name: "Emergency Response Ready",
      description: "Instant access to critical medical information, allergies, and medications during emergencies, potentially saving lives when seconds count.",
      href: "/use-cases",
      cta: "Learn more",
      background: <div className="absolute -right-20 -top-20 opacity-60" />,
      className: "lg:col-start-3 lg:col-end-3 lg:row-start-2 lg:row-end-4",
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
            Overview
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto leading-relaxed">
            Blockchain-verified health records system for displaced populations worldwide
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
              Haven Health Passport addresses critical healthcare challenges for displaced populations through blockchain-verified, AI-powered health records. The system enables the 100+ million displaced people worldwide to securely access their medical history anywhere, anytime.
            </p>

            <h3 className="text-2xl font-semibold text-white mb-4">The Vision</h3>
            <p className="text-gray-300 leading-relaxed mb-8">
              Haven Health Passport envisions a future where crossing borders doesn't mean losing access to critical health information. The system creates portable, secure, and verifiable health records that travel with refugees and displaced populations throughout their journey.
            </p>

            <h3 className="text-2xl font-semibold text-white mb-6">Key Features</h3>
          </div>
        </motion.div>

        {/* Bento Grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-16"
        >
          <BentoGrid className="lg:grid-rows-3 max-w-6xl mx-auto">
            {features.map((feature) => (
              <BentoCard key={feature.name} {...feature} />
            ))}
          </BentoGrid>
        </motion.div>

        {/* Additional Features */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="max-w-4xl mx-auto"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm">
              <div className="flex items-center mb-4">
                <Lock className="w-8 h-8 text-blue-400 mr-3" />
                <h4 className="text-xl font-semibold text-white">Privacy by Design</h4>
              </div>
              <p className="text-gray-300">
                Zero-knowledge proof architecture ensures verification without exposing sensitive medical details, giving patients complete control over their data.
              </p>
            </div>

            <div className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm">
              <div className="flex items-center mb-4">
                <Shield className="w-8 h-8 text-green-400 mr-3" />
                <h4 className="text-xl font-semibold text-white">Tamper-Proof Records</h4>
              </div>
              <p className="text-gray-300">
                Blockchain technology ensures that once health records are created, they cannot be altered or falsified, maintaining trust across all healthcare providers.
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      <Footer />
    </div>
  );
};

export default OverviewPage;