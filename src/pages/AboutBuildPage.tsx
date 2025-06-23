import React from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import ZoomableImage from '@/components/ui/ZoomableImage';
import { GlowCard } from '@/components/ui/spotlight-card';
import { motion } from 'framer-motion';
import {
  IconUsers,
  IconShield,
  IconDeviceMobile,
  IconGauge,
  IconCloud,
  IconBrain,
  IconShieldLock,
  IconServer,
} from "@tabler/icons-react";

const AboutBuildPage: React.FC = () => {
  const philosophyFeatures = [
    {
      title: "User-Centered Design",
      description: "Every feature is designed with input from refugees, healthcare workers, and aid organizations. The platform prioritizes usability in challenging environments over technical complexity.",
      icon: <IconUsers className="w-8 h-8" />,
      glowColor: 'blue' as const,
    },
    {
      title: "Security Without Compromise",
      description: "Healthcare data demands the highest security standards. The implementation includes defense-in-depth strategies, end-to-end encryption, and regular security audits.",
      icon: <IconShield className="w-8 h-8" />,
      glowColor: 'purple' as const,
    },
    {
      title: "Built for Reality",
      description: "Technology choices reflect field realities: intermittent connectivity, device constraints, language diversity, and the need for immediate usability under stress.",
      icon: <IconDeviceMobile className="w-8 h-8" />,
      glowColor: 'green' as const,
    },
    {
      title: "Performance at Scale",
      description: "Optimized for everything from low-end smartphones to high-volume border checkpoints, ensuring consistent performance across all deployment scenarios.",
      icon: <IconGauge className="w-8 h-8" />,
      glowColor: 'orange' as const,
    },
  ];

  const innovationFeatures = [
    {
      title: "Offline-First Architecture",
      description: "The custom synchronization engine handles complex medical data updates across intermittently connected devices, ensuring healthcare continuity regardless of infrastructure.",
      icon: <IconCloud className="w-8 h-8" />,
      glowColor: 'blue' as const,
    },
    {
      title: "Medical Language AI",
      description: "Specialized models for medical translation have been developed that understand context, maintain clinical accuracy, and respect cultural sensitivities across 50+ languages.",
      icon: <IconBrain className="w-8 h-8" />,
      glowColor: 'green' as const,
    },
    {
      title: "Privacy-Preserving Verification",
      description: "The zero-knowledge proof implementation allows instant verification of health credentials without exposing underlying medical data, balancing security with privacy.",
      icon: <IconShieldLock className="w-8 h-8" />,
      glowColor: 'purple' as const,
    },
    {
      title: "Resilient Infrastructure",
      description: "Multi-region deployment with automatic failover ensures system availability during regional conflicts or natural disasters that often affect refugee populations.",
      icon: <IconServer className="w-8 h-8" />,
      glowColor: 'red' as const,
    },
  ];

  return (
    <div className="min-h-screen bg-black text-white">
      <Navigation />
      
      {/* Hero Section */}
      <section className="container px-4 pt-40 pb-12">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-normal mb-4 tracking-tight text-white">
            About the Build
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto leading-relaxed">
            Building blockchain-verified health records for displaced populations
          </p>
        </div>
      </section>

      <div className="container px-4 py-8">
        {/* Implementation Timeline */}
        <div className="max-w-6xl mx-auto mb-16">
          <h2 className="text-3xl lg:text-5xl lg:leading-tight font-medium text-white mb-12 text-center tracking-tight">
            Implementation Timeline
          </h2>
          
          <ZoomableImage
            src="/Haven-Development-Timeline.png"
            alt="Haven Health Passport Development Timeline"
            className="w-full"
          />
        </div>

        {/* Development Philosophy */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="max-w-6xl mx-auto mb-16"
        >
          <h2 className="text-3xl lg:text-5xl lg:leading-tight font-medium text-white mb-12 text-center tracking-tight">
            Development Philosophy
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-7xl mx-auto">
            {philosophyFeatures.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <GlowCard 
                  glowColor={feature.glowColor}
                  customSize={true}
                  className="w-full h-auto bg-white/10 backdrop-blur-sm"
                >
                  <div className="flex flex-col p-6">
                    <div className="flex items-center justify-center mb-4 text-white">
                      {feature.icon}
                    </div>
                    <h3 className="text-lg font-bold mb-3 text-white text-center">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </GlowCard>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Technical Innovation */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="max-w-6xl mx-auto"
        >
          <h2 className="text-3xl lg:text-5xl lg:leading-tight font-medium text-white mb-12 text-center tracking-tight">
            Technical Innovation
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-7xl mx-auto">
            {innovationFeatures.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
              >
                <GlowCard 
                  glowColor={feature.glowColor}
                  customSize={true}
                  className="w-full h-auto bg-white/10 backdrop-blur-sm"
                >
                  <div className="flex flex-col p-6">
                    <div className="flex items-center justify-center mb-4 text-white">
                      {feature.icon}
                    </div>
                    <h3 className="text-lg font-bold mb-3 text-white text-center">
                      {feature.title}
                    </h3>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </GlowCard>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      <Footer />
    </div>
  );
};

export default AboutBuildPage;