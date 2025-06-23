import React from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { CompetitiveAnalysis } from "@/components/ui/competitive-analysis";
import { motion } from 'framer-motion';

const PricingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-black text-white">
      <Navigation />
      
      {/* Hero Section */}
      <motion.section 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="container px-4 pt-40 pb-8"
      >
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-normal mb-4 tracking-tight text-white">
            Competitive Analysis
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-4xl mx-auto leading-relaxed">
            <span className="text-primary">Haven Health Passport</span> compared to existing digital health solutions. 
            How blockchain-verified health records specifically designed for displaced populations 
            deliver <span className="text-green-400">unprecedented value</span> to the 
            <span className="text-blue-400">100+ million displaced people worldwide</span>.
          </p>
        </div>
      </motion.section>

      {/* Competitive Analysis Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <CompetitiveAnalysis />
      </motion.div>

      <Footer />
    </div>
  );
};

export default PricingPage; 