import React from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { motion } from 'framer-motion';
import { FeaturesSectionWithBentoGrid } from '@/components/ui/feature-section-with-bento-grid';
import { GlowCard } from '@/components/ui/spotlight-card';

const UseCasesPage: React.FC = () => {
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
            Use Cases
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto leading-relaxed">
            Real-world applications for displaced populations
          </p>
        </div>
      </motion.section>

      <div className="container px-4 py-8">
        {/* Bento Grid Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-12"
        >
          <FeaturesSectionWithBentoGrid />
        </motion.div>
        {/* Primary Use Cases Detail */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="max-w-6xl mx-auto"
        >
          <h3 className="text-3xl lg:text-5xl lg:leading-tight font-medium text-white mb-12 text-center tracking-tight">Primary Use Cases</h3>
          
          <div className="flex flex-col gap-6 mb-16">
            {/* Refugee Camp Healthcare */}
            <GlowCard glowColor="blue" customSize className="w-full h-auto aspect-auto">
              <div className="mb-4">
                <h4 className="text-xl font-semibold text-white mb-3">Refugee Camp Healthcare Management</h4>
                <p className="text-gray-300 mb-4">
                  Large refugee camps face unique challenges in managing healthcare for diverse, transient populations. Haven Health Passport enables:
                </p>
                <ul className="text-gray-300 space-y-2 text-sm">
                  <li>• Rapid patient registration using mobile devices</li>
                  <li>• Multilingual health assessments with real-time translation</li>
                  <li>• Vaccination tracking and disease outbreak prevention</li>
                  <li>• Coordination between multiple aid organizations</li>
                  <li>• Offline functionality during infrastructure failures</li>
                </ul>
              </div>
            </GlowCard>

            {/* Cross-Border Healthcare */}
            <GlowCard glowColor="purple" customSize className="w-full h-auto aspect-auto">
              <div className="mb-4">
                <h4 className="text-xl font-semibold text-white mb-3">Cross-Border Healthcare Continuity</h4>
                <p className="text-gray-300 mb-4">
                  When refugees cross borders, their health history shouldn't disappear. Haven Health Passport provides:
                </p>
                <ul className="text-gray-300 space-y-2 text-sm">
                  <li>• Portable health records that travel with individuals</li>
                  <li>• Instant verification at border checkpoints</li>
                  <li>• Selective information sharing based on context</li>
                  <li>• Translation into local healthcare provider languages</li>
                  <li>• Preservation of critical treatment continuity</li>
                </ul>
              </div>
            </GlowCard>

            {/* Emergency Medical Response */}
            <GlowCard glowColor="red" customSize className="w-full h-auto aspect-auto">
              <div className="mb-4">
                <h4 className="text-xl font-semibold text-white mb-3">Emergency Medical Response</h4>
                <p className="text-gray-300 mb-4">
                  In crisis situations, seconds matter. Haven Health Passport delivers:
                </p>
                <ul className="text-gray-300 space-y-2 text-sm">
                  <li>• QR code access to emergency medical information</li>
                  <li>• Critical allergy and medication alerts</li>
                  <li>• Blood type and emergency contact information</li>
                  <li>• Previous trauma and surgical history</li>
                  <li>• Real-time translation for first responders</li>
                </ul>
              </div>
            </GlowCard>

            {/* Healthcare Provider Coordination */}
            <GlowCard glowColor="green" customSize className="w-full h-auto aspect-auto">
              <div className="mb-4">
                <h4 className="text-xl font-semibold text-white mb-3">Healthcare Provider Coordination</h4>
                <p className="text-gray-300 mb-4">
                  Enable seamless collaboration between providers across organizations and borders:
                </p>
                <ul className="text-gray-300 space-y-2 text-sm">
                  <li>• Secure record sharing between verified providers</li>
                  <li>• Treatment history timeline visualization</li>
                  <li>• Medication reconciliation across providers</li>
                  <li>• Lab result integration and trending</li>
                  <li>• Referral management and follow-up tracking</li>
                </ul>
              </div>
            </GlowCard>
          </div>

          {/* Implementation Scenarios */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            <h3 className="text-3xl lg:text-5xl lg:leading-tight font-medium text-white mb-12 text-center tracking-tight">Implementation Scenarios</h3>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <GlowCard glowColor="blue" customSize className="w-full h-auto aspect-auto">
                <h4 className="text-lg font-semibold text-white mb-3">Urban Integration Programs</h4>
                <p className="text-gray-300 text-sm">
                  Supporting refugees integrating into urban healthcare systems with full medical history preservation and provider onboarding.
                </p>
              </GlowCard>

              <GlowCard glowColor="green" customSize className="w-full h-auto aspect-auto">
                <h4 className="text-lg font-semibold text-white mb-3">Mobile Health Clinics</h4>
                <p className="text-gray-300 text-sm">
                  Enabling traveling medical teams to access and update patient records in remote locations without reliable internet.
                </p>
              </GlowCard>

              <GlowCard glowColor="orange" customSize className="w-full h-auto aspect-auto">
                <h4 className="text-lg font-semibold text-white mb-3">International NGO Coordination</h4>
                <p className="text-gray-300 text-sm">
                  Facilitating secure health information exchange between NGOs while maintaining patient privacy and data sovereignty.
                </p>
              </GlowCard>
            </div>
          </motion.div>
        </motion.div>
      </div>

      <Footer />
    </div>
  );
};

export default UseCasesPage;