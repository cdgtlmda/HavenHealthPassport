import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { motion } from 'framer-motion';
import { 
  Mic, 
  FileText, 
  Globe, 
  Shield, 
  Activity,
  Play,
  ArrowRight,
  MapPin,
  User,
  Heart
} from 'lucide-react';

const AwsBreakingBarriersDemo: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [isRunning, setIsRunning] = useState(false);

  const journeySteps = [
    {
      id: 'crisis-registration',
      title: 'Crisis Registration',
      location: 'Refugee Camp, Lebanon',
      description: 'Syrian family arrives with no documentation',
      icon: <User className="w-6 h-6" />,
      content: {
        scenario: 'Ahmed and his family arrive at a refugee camp in Lebanon after fleeing conflict in Syria. They have no medical documentation.',
        action: 'Voice registration in Arabic captures basic medical history and current health concerns.',
        outcome: 'Secure digital health identity created with patient consent and privacy controls.'
      }
    },
    {
      id: 'voice-capture',
      title: 'Voice Medical History',
      location: 'Medical Tent, Lebanon',
      description: 'Medical history captured through voice in Arabic',
      icon: <Mic className="w-6 h-6" />,
      content: {
        scenario: 'Ahmed speaks to a healthcare worker about his diabetes and his wife\'s pregnancy.',
        action: 'Amazon Transcribe Medical processes Arabic speech into structured medical data.',
        outcome: 'Medical conditions, medications, and allergies properly documented and coded.'
      }
    },
    {
      id: 'document-processing',
      title: 'Document Recovery',
      location: 'Medical Tent, Lebanon',
      description: 'Fragmentary medical documents digitized',
      icon: <FileText className="w-6 h-6" />,
      content: {
        scenario: 'Family provides damaged prescription papers and vaccination cards from Syria.',
        action: 'AI extracts medical information from damaged documents and handwritten notes.',
        outcome: 'Complete medical timeline reconstructed from fragmentary evidence.'
      }
    },
    {
      id: 'cultural-translation',
      title: 'Cultural Medical Care',
      location: 'Medical Tent, Lebanon',
      description: 'Care instructions adapted for cultural context',
      icon: <Globe className="w-6 h-6" />,
      content: {
        scenario: 'Diabetes management instructions need to account for Ramadan fasting practices.',
        action: 'AI provides culturally-aware medical recommendations respecting religious observances.',
        outcome: 'Personalized care plan that respects cultural and religious practices.'
      }
    },
    {
      id: 'border-verification',
      title: 'Border Crossing',
      location: 'German Border',
      description: 'Health records verified at border crossing',
      icon: <Shield className="w-6 h-6" />,
      content: {
        scenario: 'Family reaches German border. Officials need to verify health status and vaccination records.',
        action: 'Blockchain verification provides instant, tamper-proof confirmation of health records.',
        outcome: 'Border processing completed in minutes instead of days, with full medical continuity.'
      }
    },
    {
      id: 'healthcare-integration',
      title: 'Healthcare Integration',
      location: 'Berlin Hospital',
      description: 'Seamless integration with German healthcare',
      icon: <Activity className="w-6 h-6" />,
      content: {
        scenario: 'Ahmed needs insulin adjustment and his wife requires prenatal care in Berlin.',
        action: 'FHIR-compliant records integrate seamlessly with German healthcare systems.',
        outcome: 'Continuous care with complete medical history, no gaps in treatment.'
      }
    }
  ];

  const runJourney = () => {
    setIsRunning(true);
    setActiveStep(0);
    
    const interval = setInterval(() => {
      setActiveStep(prev => {
        if (prev >= journeySteps.length - 1) {
          clearInterval(interval);
          setTimeout(() => {
            setIsRunning(false);
            setActiveStep(0);
          }, 2000);
          return prev;
        }
        return prev + 1;
      });
    }, 3000);
  };

  return (
    <div className="w-full">
      {/* Journey Overview */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-2xl font-semibold text-white mb-2">
              Syrian Family Healthcare Journey
            </h3>
            <p className="text-gray-300">
              Follow Ahmed's family from crisis to care across two countries
            </p>
          </div>
          <Button 
            onClick={runJourney}
            disabled={isRunning}
            className="button-gradient"
          >
            <Play className="mr-2 w-4 h-4" />
            {isRunning ? 'Journey in Progress...' : 'Start Journey'}
          </Button>
        </div>

        {/* Progress Bar */}
        {isRunning && (
          <div className="mb-6">
            <div className="flex justify-between text-sm text-gray-400 mb-2">
              <span>Journey Progress</span>
              <span>{Math.round(((activeStep + 1) / journeySteps.length) * 100)}%</span>
            </div>
            <Progress 
              value={((activeStep + 1) / journeySteps.length) * 100} 
              className="h-2 bg-white/10"
            />
          </div>
        )}
      </div>

      {/* Journey Steps */}
      <div className="space-y-4">
        {journeySteps.map((step, index) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0.3, scale: 0.95 }}
            animate={{ 
              opacity: isRunning && index === activeStep ? 1 : 0.3,
              scale: isRunning && index === activeStep ? 1 : 0.95
            }}
            transition={{ duration: 0.5 }}
            className={`bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm ${
              isRunning && index === activeStep ? 'ring-2 ring-primary' : ''
            }`}
          >
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Step Header */}
              <div className="flex items-start space-x-4">
                <div className={`p-3 rounded-lg ${
                  isRunning && index === activeStep 
                    ? 'bg-primary/20 text-primary' 
                    : 'bg-white/10 text-gray-400'
                }`}>
                  {step.icon}
                </div>
                <div>
                  <div className="flex items-center space-x-2 mb-1">
                    <Badge variant="outline" className="text-xs border-white/20 text-gray-400">
                      Step {index + 1}
                    </Badge>
                    {isRunning && index === activeStep && (
                      <Badge className="bg-green-600 text-white text-xs">
                        <Play className="w-3 h-3 mr-1" />
                        Active
                      </Badge>
                    )}
                  </div>
                  <h4 className="text-lg font-semibold text-white mb-1">
                    {step.title}
                  </h4>
                  <div className="flex items-center text-sm text-gray-400 mb-2">
                    <MapPin className="w-4 h-4 mr-1" />
                    {step.location}
                  </div>
                  <p className="text-sm text-gray-300">
                    {step.description}
                  </p>
                </div>
              </div>

              {/* Step Content */}
              <div className="lg:col-span-2 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-white/5 rounded-lg p-4">
                    <h5 className="text-sm font-medium text-white mb-2">Scenario</h5>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {step.content.scenario}
                    </p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <h5 className="text-sm font-medium text-white mb-2">Technology</h5>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {step.content.action}
                    </p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4">
                    <h5 className="text-sm font-medium text-white mb-2">Impact</h5>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      {step.content.outcome}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Journey Completion */}
      {isRunning && activeStep === journeySteps.length - 1 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 bg-gradient-to-r from-green-900/20 to-blue-900/20 border border-green-500/30 rounded-xl p-6 text-center"
        >
          <div className="flex items-center justify-center mb-4">
            <div className="bg-green-600 p-3 rounded-full">
              <Heart className="w-6 h-6 text-white" />
            </div>
          </div>
          <h4 className="text-xl font-semibold text-white mb-2">
            Healthcare Continuity Achieved
          </h4>
          <p className="text-gray-300 mb-4">
            Ahmed's family now has seamless healthcare access across borders, 
            with complete medical history and cultural considerations preserved.
          </p>
          <div className="flex items-center justify-center space-x-4 text-sm text-gray-400">
            <span>🏥 Medical records: Secure</span>
            <span>🌐 Translation: Complete</span>
            <span>🔒 Privacy: Protected</span>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default AwsBreakingBarriersDemo; 