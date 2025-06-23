import React, { useState } from 'react';
import Navigation from '@/components/Navigation';
import Footer from '@/components/Footer';
import { motion } from 'framer-motion';
import { GlowCard } from '@/components/ui/spotlight-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  UserCheck,
  Stethoscope, 
  FileText, 
  Globe, 
  ShieldCheck,
  ArrowRight,
  Play,
  Users,
  Heart,
  Building,
  Brain,
  Cpu,
  Bot,
  Cloud,
  Mic,
  Languages,
  Info,
  Zap,
  Database
} from 'lucide-react';
import { Link } from 'react-router-dom';

// Import demo components
import AwsBreakingBarriersDemo from '@/components/demos/AwsBreakingBarriersDemo';
import MedicalTranscriptionDemo from '@/components/demos/MedicalTranscriptionDemo';
import EnhancedICD10MapperDemo from '@/components/demos/EnhancedICD10MapperDemo';
import EnhancedAutomatedReportingDemo from '@/components/demos/EnhancedAutomatedReportingDemo';
import DashboardDemo from '@/components/demos/DashboardDemo';

interface Demo {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  glowColor: 'blue' | 'green' | 'purple' | 'orange' | 'red';
  audience: string;
  awsServices?: string[];
  component: React.ReactElement;
}

const DemoShowcase: React.FC = () => {
  const [selectedPerspective, setSelectedPerspective] = useState('displaced');
  const [selectedDemo, setSelectedDemo] = useState('');

  const audienceTypes = [
    {
      id: 'displaced',
      title: 'Displaced Individuals',
      description: 'See how you can securely manage your health records across borders',
      icon: <UserCheck className="w-6 h-6" />,
      color: 'text-blue-400'
    },
    {
      id: 'providers',
      title: 'Healthcare Providers',
      description: 'Understand how to serve patients with incomplete medical histories',
      icon: <Stethoscope className="w-6 h-6" />,
      color: 'text-green-400'
    },
    {
      id: 'organizations',
      title: 'Aid Organizations',
      description: 'Learn how to coordinate care across multiple displaced populations',
      icon: <Building className="w-6 h-6" />,
      color: 'text-red-400'
    }
  ];

  const allDemos = {
    displaced: [
      {
        id: 'refugee-journey',
        title: 'Complete Healthcare Journey',
        description: 'Follow a Syrian family\'s journey from Lebanon to Germany with full medical continuity',
        icon: <UserCheck className="w-8 h-8" />,
        glowColor: 'blue' as const,
        audience: 'Experience how health records travel with you across borders',
        awsServices: ['Amazon Translate', 'Amazon Comprehend Medical', 'Amazon Managed Blockchain'],
        component: <AwsBreakingBarriersDemo />
      },
      {
        id: 'voice-records',
        title: 'Voice Medical History',
        description: 'See how speaking in your native language creates structured medical records',
        icon: <Mic className="w-8 h-8" />,
        glowColor: 'green' as const,
        audience: 'Speak in Arabic, get English medical records instantly',
        awsServices: ['Amazon Transcribe Medical', 'Amazon Bedrock', 'Amazon Polly'],
        component: <MedicalTranscriptionDemo />
      }
    ],
    providers: [
      {
        id: 'voice-transcription',
        title: 'Multilingual Patient Intake',
        description: 'Process patient histories in 52 languages with medical accuracy',
        icon: <Languages className="w-8 h-8" />,
        glowColor: 'green' as const,
        audience: 'Serve patients regardless of language barriers',
        awsServices: ['Amazon Transcribe Medical', 'Amazon Translate', 'Amazon Comprehend Medical'],
        component: <MedicalTranscriptionDemo />
      },
      {
        id: 'medical-coding',
        title: 'AI Medical Coding Assistant',
        description: 'Automatically code symptoms and treatments for insurance and records',
        icon: <Bot className="w-8 h-8" />,
        glowColor: 'purple' as const,
        audience: 'Reduce coding time and improve accuracy',
        awsServices: ['Amazon Bedrock', 'Amazon Comprehend Medical', 'Amazon Textract'],
        component: <EnhancedICD10MapperDemo />
      },
      {
        id: 'patient-dashboard',
        title: 'Integrated Patient Dashboard',
        description: 'Manage displaced patient populations with complete medical visibility',
        icon: <Database className="w-8 h-8" />,
        glowColor: 'blue' as const,
        audience: 'See complete patient timelines across countries',
        awsServices: ['Amazon DynamoDB', 'Amazon S3', 'Amazon CloudFront'],
        component: <DashboardDemo />
      }
    ],
    organizations: [
      {
        id: 'population-reporting',
        title: 'Population Health Analytics',
        description: 'Monitor health outcomes across refugee populations and camps',
        icon: <Brain className="w-8 h-8" />,
        glowColor: 'orange' as const,
        audience: 'Track health trends and resource needs',
        awsServices: ['Amazon QuickSight', 'Amazon Comprehend Medical', 'Amazon SageMaker'],
        component: <EnhancedAutomatedReportingDemo />
      },
      {
        id: 'coordination-dashboard',
        title: 'Multi-Organization Dashboard',
        description: 'Coordinate care delivery across multiple NGOs and healthcare providers',
        icon: <Cloud className="w-8 h-8" />,
        glowColor: 'red' as const,
        audience: 'Unified view across all partner organizations',
        awsServices: ['Amazon API Gateway', 'AWS Lambda', 'Amazon EventBridge'],
        component: <DashboardDemo />
      },
      {
        id: 'refugee-journey-org',
        title: 'End-to-End Journey Tracking',
        description: 'Monitor complete refugee healthcare journeys from crisis to resettlement',
        icon: <Zap className="w-8 h-8" />,
        glowColor: 'purple' as const,
        audience: 'See how your programs impact refugee health outcomes',
        awsServices: ['Amazon Kinesis', 'Amazon OpenSearch', 'Amazon Managed Blockchain'],
        component: <AwsBreakingBarriersDemo />
      }
    ]
  };

  const currentDemos = allDemos[selectedPerspective] || [];
  
  // Auto-select first demo when perspective changes
  React.useEffect(() => {
    if (currentDemos.length > 0) {
      setSelectedDemo(currentDemos[0].id);
    }
  }, [selectedPerspective]);

  const currentDemo = React.useMemo(() => {
    return currentDemos.find(demo => demo.id === selectedDemo) || currentDemos[0];
  }, [currentDemos, selectedDemo]);

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
            Experience the
            <span className="text-gradient font-medium"> Journey</span>
          </h1>
          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto leading-relaxed">
            Walk through real healthcare scenarios and see how Haven Health Passport addresses challenges faced by displaced populations, healthcare providers, and humanitarian organizations
          </p>

        </div>
      </motion.section>

      {/* AWS GenAI Services Showcase */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="container px-4 py-16"
      >
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
              Built with <span className="bg-clip-text text-transparent bg-gradient-to-r from-orange-500 to-red-500">AWS GenAI Services</span>
            </h2>
            <p className="text-lg text-gray-400 max-w-3xl mx-auto">
              Haven Health Passport leverages cutting-edge AWS AI and machine learning services to provide 
              intelligent, scalable healthcare solutions for displaced populations worldwide.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                service: 'Amazon Bedrock',
                description: 'Advanced language models for medical context understanding',
                icon: <Brain className="w-6 h-6" />,
                color: 'from-purple-500 to-pink-500'
              },
              {
                service: 'Amazon Transcribe Medical',
                description: 'Accurate medical speech-to-text in multiple languages',
                icon: <Mic className="w-6 h-6" />,
                color: 'from-green-500 to-teal-500'
              },
              {
                service: 'Amazon Comprehend Medical',
                description: 'Extract medical entities and relationships from text',
                icon: <FileText className="w-6 h-6" />,
                color: 'from-blue-500 to-cyan-500'
              },
              {
                service: 'Amazon Translate',
                description: 'Real-time translation for 75+ languages',
                icon: <Languages className="w-6 h-6" />,
                color: 'from-orange-500 to-red-500'
              }
            ].map((service, index) => (
              <motion.div
                key={service.service}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
                className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm hover:border-white/20 transition-all duration-300"
              >
                <div className={`bg-gradient-to-r ${service.color} p-3 rounded-lg w-fit mb-4`}>
                  <div className="text-white">
                    {service.icon}
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {service.service}
                </h3>
                <p className="text-sm text-gray-300 leading-relaxed">
                  {service.description}
                </p>
              </motion.div>
            ))}
          </div>
          
          <div className="text-center mt-12">
            <Badge className="bg-white/10 text-white border border-white/20 px-4 py-2">
              <Info className="w-4 h-4 mr-2" />
              Each demo below showcases specific AWS GenAI services in action
            </Badge>
          </div>
        </div>
      </motion.section>

      <div className="container px-4 py-8">
        {/* Audience Selection */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="max-w-6xl mx-auto mb-16"
        >
          <h2 className="text-3xl font-semibold text-white mb-8 text-center">
            Choose Your Perspective
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {audienceTypes.map((audience, index) => (
              <motion.div
                key={audience.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
                className={`cursor-pointer transition-all duration-300 ${
                  selectedPerspective === audience.id 
                    ? 'ring-2 ring-primary' 
                    : ''
                }`}
                onClick={() => setSelectedPerspective(audience.id)}
              >
                <div className={`bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm hover:border-white/20 transition-all duration-300 h-full ${
                  selectedPerspective === audience.id ? 'bg-white/10' : ''
                }`}>
                  <div className={`${audience.color} mb-4`}>
                    {audience.icon}
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {audience.title}
                  </h3>
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {audience.description}
                  </p>
                  {selectedPerspective === audience.id && (
                    <div className="mt-3">
                      <Badge className="bg-primary text-white text-xs">
                        <Play className="w-3 h-3 mr-1" />
                        Selected
                      </Badge>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Demo Selection for Current Perspective */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="mb-16"
        >
          <h2 className="text-3xl font-semibold text-white mb-8 text-center">
            Interactive Healthcare Scenarios
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto mb-12">
            {currentDemos.map((demo, index) => (
              <motion.div
                key={demo.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index }}
                className="cursor-pointer"
                onClick={() => setSelectedDemo(demo.id)}
              >
                <GlowCard 
                  glowColor={demo.glowColor}
                  customSize={true}
                  className={`w-full h-auto bg-white/10 backdrop-blur-sm transition-all duration-300 ${
                    selectedDemo === demo.id ? 'ring-2 ring-primary' : ''
                  }`}
                >
                  <div className="flex flex-col p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="text-white">
                        {demo.icon}
                      </div>
                      {selectedDemo === demo.id && (
                        <Badge className="bg-primary text-white text-xs">
                          <Play className="w-3 h-3 mr-1" />
                          Active
                        </Badge>
                      )}
                    </div>
                    <h3 className="text-lg font-bold mb-3 text-white">
                      {demo.title}
                    </h3>
                    <p className="text-sm text-gray-300 leading-relaxed mb-4">
                      {demo.description}
                    </p>
                    <div className="mt-auto space-y-3">
                      <Badge variant="outline" className="text-xs text-gray-400 border-white/20">
                        {demo.audience}
                      </Badge>
                      {demo.awsServices && (
                        <div className="space-y-1">
                          <p className="text-xs text-gray-500 font-medium">AWS Services:</p>
                          <div className="flex flex-wrap gap-1">
                            {demo.awsServices.map((service, idx) => (
                              <Badge 
                                key={idx}
                                className="bg-primary/10 text-primary text-xs px-2 py-1 border border-primary/20"
                              >
                                {service}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </GlowCard>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Active Demo Display */}
        {currentDemo && (
          <motion.div
            key={`${selectedPerspective}-${selectedDemo}`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="max-w-7xl mx-auto"
          >
            <div className="bg-black/50 border border-white/10 rounded-xl p-8 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center">
                  <div className="text-white mr-4">
                    {currentDemo.icon}
                  </div>
                  <div>
                    <h3 className="text-2xl font-semibold text-white">{currentDemo.title}</h3>
                    <p className="text-gray-300">{currentDemo.description}</p>
                  </div>
                </div>
                <Badge className="bg-green-600 text-white">
                  <Play className="w-4 h-4 mr-2" />
                  Interactive Demo
                </Badge>
              </div>
              
              <div className="border-t border-white/10 pt-6" key={`demo-${selectedDemo}`}>
                {React.cloneElement(currentDemo.component, { key: selectedDemo })}
              </div>
            </div>
          </motion.div>
        )}

        {/* AWS GenAI Impact Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="max-w-6xl mx-auto mt-16"
        >
          <div className="bg-gradient-to-r from-gray-900 to-black rounded-xl p-8 md:p-12 border border-white/10">
            <div className="text-center mb-8">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
                AWS GenAI: Powering Healthcare Innovation
              </h2>
              <p className="text-lg text-gray-300 max-w-3xl mx-auto">
                Every feature you see in these demos is powered by AWS's cutting-edge GenAI services, 
                enabling real-time translation, medical understanding, and intelligent document processing 
                for the world's most vulnerable populations.
              </p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <GlowCard 
                  glowColor="blue"
                  customSize={true}
                  className="w-full h-64 bg-white/10 backdrop-blur-sm"
                >
                  <div className="flex flex-col items-center text-center h-full p-6">
                    <div className="bg-gradient-to-r from-blue-500 to-purple-500 p-4 rounded-full w-16 h-16 mb-4 flex items-center justify-center">
                      <Brain className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">Intelligent Processing</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">Amazon Bedrock and Comprehend Medical understand medical context across languages</p>
                  </div>
                </GlowCard>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <GlowCard 
                  glowColor="green"
                  customSize={true}
                  className="w-full h-64 bg-white/10 backdrop-blur-sm"
                >
                  <div className="flex flex-col items-center text-center h-full p-6">
                    <div className="bg-gradient-to-r from-green-500 to-teal-500 p-4 rounded-full w-16 h-16 mb-4 flex items-center justify-center">
                      <Mic className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">Voice-First Interface</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">Amazon Transcribe Medical captures medical histories in native languages</p>
                  </div>
                </GlowCard>
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <GlowCard 
                  glowColor="orange"
                  customSize={true}
                  className="w-full h-64 bg-white/10 backdrop-blur-sm"
                >
                  <div className="flex flex-col items-center text-center h-full p-6">
                    <div className="bg-gradient-to-r from-orange-500 to-red-500 p-4 rounded-full w-16 h-16 mb-4 flex items-center justify-center">
                      <Languages className="w-8 h-8 text-white" />
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">Global Accessibility</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">Amazon Translate breaks down language barriers for displaced populations</p>
                  </div>
                </GlowCard>
              </motion.div>
            </div>
            
            <div className="text-center">
              <Badge className="bg-primary/10 text-primary px-4 py-2 mb-6 border border-primary/20">
                <Cpu className="w-4 h-4 mr-2" />
                Built for AWS Breaking Barriers Challenge
              </Badge>
            </div>
          </div>
        </motion.div>

        {/* Call to Action */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0 }}
          className="max-w-4xl mx-auto mt-16 text-center"
        >
          <div className="bg-gradient-to-r from-primary to-[#9fa0f7] rounded-xl p-8 md:p-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
              Ready to Transform Healthcare Access?
            </h2>
            <p className="text-lg text-white/80 mb-8 max-w-2xl mx-auto">
              See how Haven Health Passport can serve your community or organization
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/try-dashboard">
                <Button size="lg" className="bg-white text-primary hover:bg-white/90">
                  Try the Interactive Dashboard
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
            </div>
          </div>
        </motion.div>
      </div>

      <Footer />
    </div>
  );
};

export default DemoShowcase;