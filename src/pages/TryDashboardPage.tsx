"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { 
  Shield,
  ArrowRight,
  CheckCircle,
  Globe,
  Smartphone
} from 'lucide-react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { Button } from '@/components/ui/button';
import { HavenDashboardDemo } from "../components/demos/HavenDashboardDemo";

export default function TryDashboardPage() {
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
            Try Haven Health
            <span className="block text-gradient font-medium">Passport Dashboard</span>
          </h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="text-lg md:text-xl text-gray-200 mb-8 max-w-4xl mx-auto leading-relaxed"
          >
            Experience the power of blockchain-verified health records designed for displaced populations. 
            Navigate through different views to see how AI-powered translation, offline-first mobile access, and{" "}
            <span className="text-white">tamper-proof verification</span> enable secure, portable healthcare documentation.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="flex flex-col sm:flex-row gap-4 items-center justify-center mb-8"
          >
            <Link to="/demos">
              <Button size="lg" variant="link" className="text-white hover:text-gray-200">
                View All Demos <ArrowRight className="ml-2 w-4 h-4" />
              </Button>
            </Link>
          </motion.div>
        </div>
      </motion.section>

      {/* Dashboard Demo */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="container px-4 mb-12"
      >
        <div className="max-w-7xl mx-auto">
          <h2 className="text-2xl font-bold text-white mb-6">Interactive Dashboard</h2>
          <div className="glass rounded-xl overflow-hidden">
            <HavenDashboardDemo />
          </div>
        </div>
      </motion.section>

      {/* Features Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
        className="container px-4 mb-12"
      >
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
              Dashboard Features
            </h2>
            <p className="text-lg text-gray-400 max-w-3xl mx-auto">
              Explore the comprehensive capabilities of this blockchain-verified health record management system for displaced populations.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm hover:border-white/20 transition-all duration-300"
            >
              <div className="flex items-center gap-3 mb-4">
                <Shield className="w-8 h-8 text-blue-400" />
                <h3 className="text-xl font-semibold text-white">Blockchain Verification</h3>
              </div>
              <p className="text-gray-400 leading-relaxed">
                Tamper-proof health records verified on blockchain with patient-controlled data sovereignty.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm hover:border-white/20 transition-all duration-300"
            >
              <div className="flex items-center gap-3 mb-4">
                <Globe className="w-8 h-8 text-green-400" />
                <h3 className="text-xl font-semibold text-white">Multi-Language AI</h3>
              </div>
              <p className="text-gray-400 leading-relaxed">
                AI-powered translation supporting 50+ languages with cultural adaptation for refugee populations.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm hover:border-white/20 transition-all duration-300"
            >
              <div className="flex items-center gap-3 mb-4">
                <Smartphone className="w-8 h-8 text-purple-400" />
                <h3 className="text-xl font-semibold text-white">Offline-First Mobile</h3>
              </div>
              <p className="text-gray-400 leading-relaxed">
                Works without internet connectivity, perfect for remote areas and border crossings.
              </p>
            </motion.div>
          </div>
        </div>
      </motion.section>

      {/* Call to Action Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
        className="container px-4 pb-20"
      >
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-r from-primary to-[#9fa0f7] rounded-xl p-8 md:p-12 text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
              Ready to Transform Healthcare Access?
            </h2>
            <p className="text-lg text-white/80 mb-8 max-w-2xl mx-auto">
              Supporting the mission to provide secure, portable health records for displaced populations worldwide through blockchain verification and AI-powered translation.
            </p>
            <div className="flex justify-center mb-6">
              <Link to="/demos">
                <Button size="lg" className="bg-white text-primary hover:bg-white/90">
                  View All Demos <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
            </div>
            <div className="flex items-center justify-center gap-6 text-sm text-white/60">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                <span>AWS Breaking Barriers Challenge</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                <span>UNHCR Partnership Ready</span>
              </div>
            </div>
          </div>
        </div>
      </motion.section>

      <Footer />
    </div>
  );
} 