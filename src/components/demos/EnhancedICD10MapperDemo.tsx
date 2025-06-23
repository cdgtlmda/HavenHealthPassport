import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { motion } from 'framer-motion';
import { 
  Search, 
  FileText, 
  Clock,
  CheckCircle,
  AlertCircle,
  Play,
  ArrowRight
} from 'lucide-react';

const EnhancedICD10MapperDemo: React.FC = () => {
  const [activeScenario, setActiveScenario] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  const codingScenarios = [
    {
      id: 'refugee-diabetes',
      title: 'Refugee Diabetes Management',
      context: 'Syrian refugee with poorly controlled diabetes',
      symptoms: 'Patient reports frequent urination, excessive thirst, fatigue, and weight loss',
      aiSuggestions: [
        { code: 'E11.9', description: 'Type 2 diabetes mellitus without complications', confidence: '94%', selected: true },
        { code: 'R35.0', description: 'Frequency of micturition', confidence: '91%', selected: true },
        { code: 'R63.1', description: 'Polydipsia', confidence: '89%', selected: true },
        { code: 'R53.83', description: 'Fatigue', confidence: '85%', selected: false }
      ],
      culturalNotes: 'Consider Ramadan fasting impact on medication timing and blood sugar control',
      finalCoding: 'Primary: E11.9 (Type 2 DM), Secondary: R35.0, R63.1'
    },
    {
      id: 'chest-pain-emergency',
      title: 'Emergency Chest Pain',
      context: 'African refugee presenting to ER with chest pain',
      symptoms: 'Chest pain radiating to left arm, diaphoresis, shortness of breath, nausea',
      aiSuggestions: [
        { code: 'I20.9', description: 'Angina pectoris, unspecified', confidence: '96%', selected: true },
        { code: 'R06.00', description: 'Dyspnea, unspecified', confidence: '93%', selected: true },
        { code: 'R50.9', description: 'Hyperhidrosis, unspecified', confidence: '88%', selected: false },
        { code: 'R11.10', description: 'Vomiting, unspecified', confidence: '82%', selected: false }
      ],
      culturalNotes: 'Patient may minimize symptoms due to fear of medical costs or deportation',
      finalCoding: 'Primary: I20.9 (Angina), Secondary: R06.00'
    },
    {
      id: 'prenatal-care',
      title: 'Prenatal Care Visit',
      context: 'Pregnant refugee woman, first prenatal visit',
      symptoms: 'Amenorrhea 12 weeks, nausea, breast tenderness, positive pregnancy test',
      aiSuggestions: [
        { code: 'Z34.00', description: 'Encounter for supervision of normal first pregnancy, unspecified trimester', confidence: '98%', selected: true },
        { code: 'O21.9', description: 'Vomiting of pregnancy, unspecified', confidence: '94%', selected: true },
        { code: 'N64.4', description: 'Mastodynia', confidence: '87%', selected: false },
        { code: 'Z87.59', description: 'Personal history of other complications of pregnancy, childbirth and the puerperium', confidence: '45%', selected: false }
      ],
      culturalNotes: 'May need additional screening for nutritional deficiencies common in refugee populations',
      finalCoding: 'Primary: Z34.00 (Normal pregnancy supervision), Secondary: O21.9'
    }
  ];

  const runDemo = () => {
    setIsProcessing(true);
    setActiveScenario(0);

    const processScenarios = () => {
      setActiveScenario(prev => {
        if (prev >= codingScenarios.length - 1) {
          setTimeout(() => {
            setIsProcessing(false);
            setActiveScenario(0);
          }, 2000);
          return prev;
        }
        return prev + 1;
      });
    };

    const interval = setInterval(() => {
      processScenarios();
      if (activeScenario >= codingScenarios.length - 1) {
        clearInterval(interval);
      }
    }, 4000);
  };

  const currentScenario = codingScenarios[activeScenario];

  return (
    <div className="w-full">
      {/* Demo Overview */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-2xl font-semibold text-white mb-2">
              AI Medical Coding Assistant
            </h3>
            <p className="text-gray-300">
              Automated ICD-10 code suggestions for refugee healthcare scenarios
            </p>
          </div>
          <Button 
            onClick={runDemo}
            disabled={isProcessing}
            className="button-gradient"
          >
            <Play className="mr-2 w-4 h-4" />
            {isProcessing ? 'Processing Cases...' : 'Start Coding'}
          </Button>
        </div>
      </div>

      {/* Current Scenario Display */}
      <div className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Patient Case */}
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-semibold text-white flex items-center">
                <FileText className="w-6 h-6 mr-3" />
                {currentScenario.title}
              </h4>
              <Badge variant="outline" className="border-white/20 text-gray-400">
                Case {activeScenario + 1} of {codingScenarios.length}
              </Badge>
            </div>

            <div className="bg-white/5 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-2">Clinical Context</h5>
              <p className="text-sm text-gray-300">{currentScenario.context}</p>
            </div>

            <div className="bg-white/5 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-2">Presenting Symptoms</h5>
              <p className="text-sm text-gray-300 leading-relaxed">
                {currentScenario.symptoms}
              </p>
            </div>

            {/* AI Processing Indicator */}
            {isProcessing && (
              <div className="bg-white/5 rounded-lg p-4">
                <div className="flex items-center justify-center space-x-3">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                  <span className="text-sm text-gray-300">AI analyzing symptoms...</span>
                </div>
              </div>
            )}
          </div>

          {/* AI Coding Suggestions */}
          <div className="space-y-6">
            <h4 className="text-lg font-semibold text-white flex items-center">
              <Search className="w-6 h-6 mr-3" />
              AI Code Suggestions
            </h4>

            <div className="space-y-3">
              {currentScenario.aiSuggestions.map((suggestion, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: isProcessing ? 0.3 : 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                  className={`bg-white/5 rounded-lg p-4 border ${
                    suggestion.selected 
                      ? 'border-green-500/50 bg-green-900/20' 
                      : 'border-white/10'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <Badge variant="outline" className="text-xs font-mono border-blue-500/30 text-blue-400">
                          {suggestion.code}
                        </Badge>
                        <Badge variant="outline" className={`text-xs ${
                          parseFloat(suggestion.confidence) > 90 
                            ? 'border-green-500/30 text-green-400' 
                            : 'border-yellow-500/30 text-yellow-400'
                        }`}>
                          {suggestion.confidence}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-300 leading-relaxed">
                        {suggestion.description}
                      </p>
                    </div>
                    <div className="ml-3">
                      {suggestion.selected ? (
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      ) : (
                        <div className="w-5 h-5 rounded-full border-2 border-gray-600"></div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Cultural Considerations */}
            <div className="bg-orange-900/20 border border-orange-500/30 rounded-lg p-4">
              <div className="flex items-start space-x-2">
                <AlertCircle className="w-5 h-5 text-orange-400 mt-0.5" />
                <div>
                  <h5 className="text-sm font-medium text-white mb-1">Cultural Considerations</h5>
                  <p className="text-sm text-orange-200">
                    {currentScenario.culturalNotes}
                  </p>
                </div>
              </div>
            </div>

            {/* Final Coding */}
            <div className="bg-green-900/20 border border-green-500/30 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-2 flex items-center">
                <ArrowRight className="w-4 h-4 mr-2" />
                Final Coding Decision
              </h5>
              <p className="text-sm text-green-200 font-mono">
                {isProcessing ? 'Generating final codes...' : currentScenario.finalCoding}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Completion Summary */}
      {isProcessing && activeScenario === codingScenarios.length - 1 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 bg-gradient-to-r from-green-900/20 to-blue-900/20 border border-green-500/30 rounded-xl p-6 text-center"
        >
          <h4 className="text-lg font-semibold text-white mb-2">
            Medical Coding Complete
          </h4>
          <p className="text-gray-300 text-sm mb-4">
            3 refugee healthcare cases successfully coded with cultural considerations
          </p>
          <div className="flex items-center justify-center space-x-4 text-sm text-gray-400">
            <span>📋 95% accuracy</span>
            <span>⚡ 3x faster coding</span>
            <span>🌍 Cultural awareness</span>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default EnhancedICD10MapperDemo; 