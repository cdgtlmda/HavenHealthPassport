import React from 'react';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';

const DevelopmentTimelineDiagram: React.FC = () => {

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

      {/* Timeline Visualization */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2 }}
        className="bg-slate-900/50 rounded-xl p-8 backdrop-blur-sm border border-slate-700/50 mb-8"
      >
        <div className="text-center py-12">
          <h3 className="text-2xl font-bold text-white mb-4">Development Timeline</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            <div className="bg-green-500/20 rounded-lg p-4 border border-green-500/30">
              <h4 className="text-green-400 font-semibold mb-2">Foundation</h4>
              <p className="text-sm text-gray-300">Complete</p>
            </div>
            <div className="bg-yellow-500/20 rounded-lg p-4 border border-yellow-500/30">
              <h4 className="text-yellow-400 font-semibold mb-2">Testing</h4>
              <p className="text-sm text-gray-300">Weeks 1-6</p>
            </div>
            <div className="bg-blue-500/20 rounded-lg p-4 border border-blue-500/30">
              <h4 className="text-blue-400 font-semibold mb-2">Infrastructure</h4>
              <p className="text-sm text-gray-300">Weeks 7-9</p>
            </div>
            <div className="bg-purple-500/20 rounded-lg p-4 border border-purple-500/30">
              <h4 className="text-purple-400 font-semibold mb-2">Certification</h4>
              <p className="text-sm text-gray-300">Weeks 13-14</p>
            </div>
          </div>
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

export default DevelopmentTimelineDiagram; 