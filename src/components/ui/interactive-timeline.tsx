import React from 'react';
import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { 
  Calendar,
  CheckCircle,
  Clock,
  Code,
  Database,
  Shield,
  Brain,
  Globe,
  Settings,
  Rocket,
  GitBranch
} from 'lucide-react';

interface ChangelogEntry {
  version: string;
  date: string;
  status: 'released' | 'in-progress' | 'planned';
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  changes: {
    type: 'added' | 'changed' | 'security' | 'infrastructure' | 'healthcare';
    items: string[];
  }[];
}

const ScrollChangelog: React.FC = () => {
  const changelogEntries: ChangelogEntry[] = [
    {
      version: "Unreleased",
      date: "In Progress",
      status: 'in-progress',
      title: "Production Preparation",
      description: "Final testing and deployment infrastructure for production readiness",
      icon: <Rocket className="w-5 h-5" />,
      color: "from-yellow-500 to-orange-500",
      changes: [
        {
          type: 'added',
          items: [
            'Comprehensive documentation structure',
            'Contributing guidelines',
            'SDK documentation'
          ]
        },
        {
          type: 'infrastructure',
          items: [
            'Unit testing implementation (targeting 90% coverage)',
            'Integration testing framework',
            'Performance testing suite',
            'AWS Organizations setup for production deployment'
          ]
        }
      ]
    },
    {
      version: "0.9.0",
      date: "2025-06-20",
      status: 'released',
      title: "Multi-Language & Security Enhancement",
      description: "Comprehensive language support and advanced security implementation",
      icon: <Globe className="w-5 h-5" />,
      color: "from-green-500 to-emerald-500",
      changes: [
        {
          type: 'added',
          items: [
            'Multi-language support for 50+ languages',
            'Offline functionality for mobile applications',
            'Web portal development completed',
            'Mobile app development completed',
            'Security implementation with MFA & authentication',
            'Encryption systems deployment'
          ]
        },
        {
          type: 'changed',
          items: [
            'Enhanced translation accuracy for medical terminology',
            'Improved offline sync algorithms',
            'Optimized mobile app performance'
          ]
        },
        {
          type: 'security',
          items: [
            'End-to-end encryption for all health data',
            'HIPAA-compliant infrastructure implementation',
            'Zero-trust security architecture',
            'Penetration testing initiated'
          ]
        }
      ]
    },
    {
      version: "0.8.0",
      date: "2025-06-11",
      status: 'released',
      title: "Encryption & API Development",
      description: "Core API completion and advanced encryption systems",
      icon: <Shield className="w-5 h-5" />,
      color: "from-blue-500 to-cyan-500",
      changes: [
        {
          type: 'added',
          items: [
            'Encryption systems implementation',
            'Core API development completed',
            'Healthcare provider web portal',
            'Biometric authentication systems'
          ]
        },
        {
          type: 'changed',
          items: [
            'Enhanced blockchain integration stability',
            'Improved FHIR R4 compliance implementation'
          ]
        }
      ]
    },
    {
      version: "0.7.0",
      date: "2025-06-09",
      status: 'released',
      title: "Security Framework Implementation",
      description: "Advanced security and authentication systems deployment",
      icon: <Settings className="w-5 h-5" />,
      color: "from-purple-500 to-pink-500",
      changes: [
        {
          type: 'added',
          items: [
            'Security implementation framework',
            'Multi-factor authentication (MFA)',
            'Advanced authentication systems',
            'Security audit framework'
          ]
        },
        {
          type: 'security',
          items: [
            'Blockchain-based audit trails',
            'Enhanced access control mechanisms'
          ]
        }
      ]
    },
    {
      version: "0.6.0",
      date: "2025-06-06",
      status: 'released',
      title: "AI/ML Integration & Medical Standards",
      description: "Advanced AI capabilities and healthcare standards implementation",
      icon: <Brain className="w-5 h-5" />,
      color: "from-indigo-500 to-purple-500",
      changes: [
        {
          type: 'added',
          items: [
            'AI/ML setup and integration',
            'API development framework',
            'Enhanced medical translation capabilities',
            'Amazon Bedrock integration'
          ]
        },
        {
          type: 'healthcare',
          items: [
            'ICD-10, SNOMED CT, RxNorm, LOINC integration',
            'Medical document OCR capabilities',
            'Enhanced FHIR R4 resource support'
          ]
        }
      ]
    },
    {
      version: "0.5.0",
      date: "2025-06-02",
      status: 'released',
      title: "Blockchain & Healthcare Standards",
      description: "Core blockchain implementation and FHIR compliance",
      icon: <GitBranch className="w-5 h-5" />,
      color: "from-orange-500 to-red-500",
      changes: [
        {
          type: 'added',
          items: [
            'Blockchain implementation using Hyperledger Fabric',
            'Healthcare standards framework',
            'FHIR R4 compliance with Amazon HealthLake',
            'Cross-border verification protocols'
          ]
        },
        {
          type: 'changed',
          items: [
            'Core architecture improvements',
            'Database optimization'
          ]
        }
      ]
    },
    {
      version: "0.2.0",
      date: "2025-05-31",
      status: 'released',
      title: "Core Architecture & Database",
      description: "Foundation architecture and database systems implementation",
      icon: <Database className="w-5 h-5" />,
      color: "from-teal-500 to-green-500",
      changes: [
        {
          type: 'added',
          items: [
            'Core architecture implementation',
            'Database and services setup',
            'Initial health record management system'
          ]
        },
        {
          type: 'changed',
          items: [
            'Project structure optimization'
          ]
        }
      ]
    },
    {
      version: "0.1.0",
      date: "2025-05-28",
      status: 'released',
      title: "Project Foundation",
      description: "Initial project setup and development environment",
      icon: <Code className="w-5 h-5" />,
      color: "from-gray-500 to-slate-500",
      changes: [
        {
          type: 'added',
          items: [
            'Initial project setup and configuration',
            'Basic documentation structure',
            'Development environment setup',
            'Core foundation architecture'
          ]
        },
        {
          type: 'infrastructure',
          items: [
            'AWS infrastructure planning',
            'Development toolchain setup'
          ]
        }
      ]
    }
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'released':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'in-progress':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      default:
        return <Calendar className="w-4 h-4 text-gray-500" />;
    }
  };

  const getChangeTypeColor = (type: string) => {
    switch (type) {
      case 'added':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'changed':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'security':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'infrastructure':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'healthcare':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-500 via-purple-500 to-orange-500"></div>
        
        <div className="space-y-8">
          {changelogEntries.map((entry, index) => (
            <motion.div
              key={entry.version}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1, duration: 0.5 }}
              className="relative flex items-start"
            >
              {/* Timeline node */}
              <div className={`relative z-10 flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-r ${entry.color} shadow-lg`}>
                <div className="text-white">
                  {entry.icon}
                </div>
              </div>
              
              {/* Content */}
              <div className="ml-6 flex-1">
                <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <h3 className="text-xl font-bold text-gray-900">
                        {entry.version}
                      </h3>
                      {getStatusIcon(entry.status)}
                    </div>
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      <Calendar className="w-4 h-4" />
                      <span>{entry.date}</span>
                    </div>
                  </div>
                  
                  <h4 className="text-lg font-semibold text-gray-800 mb-2">
                    {entry.title}
                  </h4>
                  <p className="text-gray-600 mb-4">
                    {entry.description}
                  </p>
                  
                  <div className="space-y-4">
                    {entry.changes.map((changeGroup, groupIndex) => (
                      <div key={groupIndex}>
                        <Badge 
                          variant="outline" 
                          className={`mb-2 ${getChangeTypeColor(changeGroup.type)}`}
                        >
                          {changeGroup.type.charAt(0).toUpperCase() + changeGroup.type.slice(1)}
                        </Badge>
                        <ul className="space-y-1 ml-4">
                          {changeGroup.items.map((item, itemIndex) => (
                            <li key={itemIndex} className="text-sm text-gray-700 flex items-start">
                              <span className="text-gray-400 mr-2">•</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ScrollChangelog; 