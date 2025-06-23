import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { motion } from 'framer-motion';
import { 
  Mic, 
  MicOff, 
  Play, 
  FileAudio,
  Volume2,
  Stethoscope,
  Globe,
  ArrowRight
} from 'lucide-react';

const MedicalTranscriptionDemo: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  const transcriptionScenarios = [
    {
      id: 'refugee-intake',
      title: 'Refugee Medical Intake',
      language: 'Arabic',
      flag: '🇸🇦',
      context: 'New refugee patient with no documentation',
      audio: '"اسمي أحمد، عمري 35 سنة، أعاني من السكري منذ 5 سنوات"',
      transcription: 'My name is Ahmed, I am 35 years old, I have been suffering from diabetes for 5 years',
      medicalEntities: [
        { type: 'Patient Name', value: 'Ahmed', confidence: '98%' },
        { type: 'Age', value: '35 years', confidence: '99%' },
        { type: 'Medical Condition', value: 'Diabetes Mellitus', confidence: '96%' },
        { type: 'Duration', value: '5 years', confidence: '94%' }
      ],
      clinicalNote: 'CHIEF COMPLAINT: Diabetes management\nHISTORY: 35-year-old male with 5-year history of diabetes mellitus seeking continuity of care.',
      icon: <Globe className="w-6 h-6" />
    },
    {
      id: 'emergency-consult',
      title: 'Emergency Consultation',
      language: 'French',
      flag: '🇫🇷',
      context: 'Urgent care consultation for chest pain',
      audio: '"Douleur thoracique depuis 2 heures, irradiant vers le bras gauche"',
      transcription: 'Chest pain for 2 hours, radiating to the left arm',
      medicalEntities: [
        { type: 'Symptom', value: 'Chest pain', confidence: '97%' },
        { type: 'Duration', value: '2 hours', confidence: '95%' },
        { type: 'Location', value: 'Left arm radiation', confidence: '93%' }
      ],
      clinicalNote: 'CHIEF COMPLAINT: Chest pain\nHPI: Patient reports chest pain x 2 hours with radiation to left arm. Possible cardiac etiology.',
      icon: <Stethoscope className="w-6 h-6" />
    },
    {
      id: 'follow-up',
      title: 'Follow-up Care',
      language: 'Spanish',
      flag: '🇪🇸',
      context: 'Medication review and adjustment',
      audio: '"Tomo metformina 500mg dos veces al día, pero mi azúcar sigue alta"',
      transcription: 'I take metformin 500mg twice daily, but my blood sugar remains high',
      medicalEntities: [
        { type: 'Medication', value: 'Metformin 500mg', confidence: '99%' },
        { type: 'Dosage', value: 'Twice daily', confidence: '97%' },
        { type: 'Symptom', value: 'Hyperglycemia', confidence: '94%' }
      ],
      clinicalNote: 'MEDICATIONS: Metformin 500mg BID\nASSESSMENT: Suboptimal glycemic control despite current therapy.',
      icon: <FileAudio className="w-6 h-6" />
    }
  ];

  const runDemo = () => {
    setIsProcessing(true);
    setActiveStep(0);

    const processSteps = () => {
      setActiveStep(prev => {
        if (prev >= transcriptionScenarios.length - 1) {
          setTimeout(() => {
            setIsProcessing(false);
            setActiveStep(0);
          }, 2000);
          return prev;
        }
        return prev + 1;
      });
    };

    // Step through scenarios
    const interval = setInterval(() => {
      processSteps();
      if (activeStep >= transcriptionScenarios.length - 1) {
        clearInterval(interval);
      }
    }, 4000);
  };

  const currentScenario = transcriptionScenarios[activeStep];

  return (
    <div className="w-full">
      {/* Demo Overview */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-2xl font-semibold text-white mb-2">
              Voice-to-Medical Records Processing
            </h3>
            <p className="text-gray-300">
              Transform multilingual voice recordings into structured clinical documentation
            </p>
          </div>
          <Button 
            onClick={runDemo}
            disabled={isProcessing}
            className="button-gradient"
          >
            <Play className="mr-2 w-4 h-4" />
            {isProcessing ? 'Processing Audio...' : 'Start Demo'}
          </Button>
        </div>

        {/* Progress */}
        {isProcessing && (
          <div className="mb-6">
            <div className="flex justify-between text-sm text-gray-400 mb-2">
              <span>Processing Progress</span>
              <span>{Math.round(((activeStep + 1) / transcriptionScenarios.length) * 100)}%</span>
            </div>
            <Progress 
              value={((activeStep + 1) / transcriptionScenarios.length) * 100} 
              className="h-2 bg-white/10"
            />
          </div>
        )}
      </div>

      {/* Current Scenario Display */}
      <div className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Audio Input Section */}
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-semibold text-white flex items-center">
                {currentScenario.icon}
                <span className="ml-3">{currentScenario.title}</span>
              </h4>
              <div className="flex items-center space-x-2">
                <Badge variant="outline" className="border-white/20 text-gray-400">
                  {currentScenario.language}
                </Badge>
                <span className="text-2xl">{currentScenario.flag}</span>
              </div>
            </div>

            <div className="bg-white/5 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-2">Clinical Context</h5>
              <p className="text-sm text-gray-300">{currentScenario.context}</p>
            </div>

            {/* Audio Visualization */}
            <div className="bg-white/5 rounded-lg p-6">
              <div className="flex items-center justify-center mb-4">
                <div className={`p-4 rounded-full ${isProcessing ? 'bg-primary/20 animate-pulse' : 'bg-white/10'}`}>
                  {isProcessing ? (
                    <Volume2 className="w-8 h-8 text-primary" />
                  ) : (
                    <Mic className="w-8 h-8 text-gray-400" />
                  )}
                </div>
              </div>
              
              <div className="text-center">
                <h5 className="text-sm font-medium text-white mb-2">Original Audio ({currentScenario.language})</h5>
                <div className="bg-black/30 rounded p-3 font-mono text-sm text-gray-300 text-right">
                  {currentScenario.audio}
                </div>
              </div>
            </div>
          </div>

          {/* Processing Results */}
          <div className="space-y-6">
            {/* Transcription */}
            <div className="bg-white/5 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-3 flex items-center">
                <ArrowRight className="w-4 h-4 mr-2" />
                English Transcription
              </h5>
              <div className="bg-black/30 rounded p-3 text-sm text-gray-300">
                {isProcessing ? (
                  <motion.div
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                  >
                    Transcribing audio...
                  </motion.div>
                ) : (
                  currentScenario.transcription
                )}
              </div>
            </div>

            {/* Medical Entities */}
            <div className="bg-white/5 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-3">Medical Entity Extraction</h5>
              <div className="space-y-2">
                {currentScenario.medicalEntities.map((entity, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: isProcessing ? 0.3 : 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-center justify-between bg-black/30 rounded p-2"
                  >
                    <div>
                      <span className="text-xs text-gray-400">{entity.type}</span>
                      <div className="text-sm text-white font-medium">{entity.value}</div>
                    </div>
                    <Badge variant="outline" className="text-xs border-green-500/30 text-green-400">
                      {entity.confidence}
                    </Badge>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Clinical Note */}
            <div className="bg-white/5 rounded-lg p-4">
              <h5 className="text-sm font-medium text-white mb-3">Generated Clinical Note</h5>
              <div className="bg-black/30 rounded p-3 text-sm text-gray-300 font-mono whitespace-pre-line">
                {isProcessing ? 'Generating structured note...' : currentScenario.clinicalNote}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Processing Complete */}
      {isProcessing && activeStep === transcriptionScenarios.length - 1 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 bg-gradient-to-r from-green-900/20 to-blue-900/20 border border-green-500/30 rounded-xl p-6 text-center"
        >
          <h4 className="text-lg font-semibold text-white mb-2">
            Medical Records Successfully Generated
          </h4>
          <p className="text-gray-300 text-sm">
            Voice recordings from 3 languages processed into structured clinical documentation
          </p>
        </motion.div>
      )}
    </div>
  );
};

export default MedicalTranscriptionDemo; 