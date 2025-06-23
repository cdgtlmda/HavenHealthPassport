import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { motion } from 'framer-motion';
import { 
  Users, 
  Activity, 
  Globe,
  MapPin,
  Heart,
  Stethoscope,
  Play,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  FileText,
  Clock,
  Shield,
  Languages,
  Building,
  Zap
} from 'lucide-react';

const DashboardDemo: React.FC = () => {
  const [activeView, setActiveView] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [selectedRegion, setSelectedRegion] = useState('all');

  // 50+ supported languages based on the project documentation
  const supportedLanguages = [
    { code: 'en', name: 'English', flag: '🇺🇸', patients: 3247 },
    { code: 'ar', name: 'Arabic', flag: '🇸🇦', patients: 8429 },
    { code: 'fr', name: 'French', flag: '🇫🇷', patients: 2156 },
    { code: 'es', name: 'Spanish', flag: '🇪🇸', patients: 1834 },
    { code: 'fa', name: 'Persian/Farsi', flag: '🇮🇷', patients: 4672 },
    { code: 'ps', name: 'Pashto', flag: '🇦🇫', patients: 3891 },
    { code: 'da', name: 'Dari', flag: '🇦🇫', patients: 2745 },
    { code: 'ku', name: 'Kurdish', flag: '🏴', patients: 1923 },
    { code: 'tr', name: 'Turkish', flag: '🇹🇷', patients: 2567 },
    { code: 'ur', name: 'Urdu', flag: '🇵🇰', patients: 1456 },
    { code: 'hi', name: 'Hindi', flag: '🇮🇳', patients: 987 },
    { code: 'bn', name: 'Bengali', flag: '🇧🇩', patients: 1234 },
    { code: 'so', name: 'Somali', flag: '🇸🇴', patients: 2891 },
    { code: 'sw', name: 'Swahili', flag: '🇰🇪', patients: 1567 },
    { code: 'am', name: 'Amharic', flag: '🇪🇹', patients: 1123 },
    { code: 'ti', name: 'Tigrinya', flag: '🇪🇷', patients: 892 },
    { code: 'my', name: 'Myanmar', flag: '🇲🇲', patients: 1345 },
    { code: 'th', name: 'Thai', flag: '🇹🇭', patients: 678 },
    { code: 'vi', name: 'Vietnamese', flag: '🇻🇳', patients: 1789 },
    { code: 'zh', name: 'Chinese', flag: '🇨🇳', patients: 2345 },
    { code: 'ru', name: 'Russian', flag: '🇷🇺', patients: 1678 },
    { code: 'uk', name: 'Ukrainian', flag: '🇺🇦', patients: 4567 },
    { code: 'pl', name: 'Polish', flag: '🇵🇱', patients: 1234 },
    { code: 'de', name: 'German', flag: '🇩🇪', patients: 987 },
    { code: 'it', name: 'Italian', flag: '🇮🇹', patients: 654 },
    { code: 'pt', name: 'Portuguese', flag: '🇵🇹', patients: 789 },
    { code: 'ro', name: 'Romanian', flag: '🇷🇴', patients: 543 },
    { code: 'hu', name: 'Hungarian', flag: '🇭🇺', patients: 432 },
    { code: 'cs', name: 'Czech', flag: '🇨🇿', patients: 321 },
    { code: 'sk', name: 'Slovak', flag: '🇸🇰', patients: 234 },
    { code: 'bg', name: 'Bulgarian', flag: '🇧🇬', patients: 345 },
    { code: 'hr', name: 'Croatian', flag: '🇭🇷', patients: 456 },
    { code: 'sr', name: 'Serbian', flag: '🇷🇸', patients: 567 },
    { code: 'bs', name: 'Bosnian', flag: '🇧🇦', patients: 678 },
    { code: 'sq', name: 'Albanian', flag: '🇦🇱', patients: 789 },
    { code: 'mk', name: 'Macedonian', flag: '🇲🇰', patients: 234 },
    { code: 'sl', name: 'Slovenian', flag: '🇸🇮', patients: 123 },
    { code: 'lv', name: 'Latvian', flag: '🇱🇻', patients: 89 },
    { code: 'lt', name: 'Lithuanian', flag: '🇱🇹', patients: 67 },
    { code: 'et', name: 'Estonian', flag: '🇪🇪', patients: 45 },
    { code: 'fi', name: 'Finnish', flag: '🇫🇮', patients: 123 },
    { code: 'sv', name: 'Swedish', flag: '🇸🇪', patients: 234 },
    { code: 'no', name: 'Norwegian', flag: '🇳🇴', patients: 345 },
    { code: 'da', name: 'Danish', flag: '🇩🇰', patients: 456 },
    { code: 'nl', name: 'Dutch', flag: '🇳🇱', patients: 567 },
    { code: 'he', name: 'Hebrew', flag: '🇮🇱', patients: 678 },
    { code: 'ja', name: 'Japanese', flag: '🇯🇵', patients: 234 },
    { code: 'ko', name: 'Korean', flag: '🇰🇷', patients: 123 },
    { code: 'id', name: 'Indonesian', flag: '🇮🇩', patients: 789 },
    { code: 'ms', name: 'Malay', flag: '🇲🇾', patients: 456 },
    { code: 'tl', name: 'Tagalog', flag: '🇵🇭', patients: 678 },
    { code: 'ta', name: 'Tamil', flag: '🇱🇰', patients: 345 },
    { code: 'si', name: 'Sinhala', flag: '🇱🇰', patients: 234 }
  ];

  const regions = [
    { code: 'all', name: 'All Regions', facilities: 127 },
    { code: 'mena', name: 'Middle East & North Africa', facilities: 34 },
    { code: 'europe', name: 'Europe', facilities: 28 },
    { code: 'africa', name: 'Sub-Saharan Africa', facilities: 31 },
    { code: 'asia', name: 'Asia Pacific', facilities: 22 },
    { code: 'americas', name: 'Americas', facilities: 12 }
  ];

  const dashboardViews = [
    {
      id: 'language-analytics',
      title: 'Multilingual Patient Analytics',
      description: 'Real-time language distribution and translation performance across all facilities',
      stats: [
        { label: 'Active Languages', value: '52', trend: '+3', icon: <Languages className="w-5 h-5" />, color: 'text-blue-400' },
        { label: 'Translation Accuracy', value: '99.2%', trend: '+0.3%', icon: <CheckCircle className="w-5 h-5" />, color: 'text-green-400' },
        { label: 'Daily Translations', value: '8,934', trend: '+12%', icon: <Globe className="w-5 h-5" />, color: 'text-purple-400' },
        { label: 'Cultural Adaptations', value: '2,847', trend: '+18%', icon: <Heart className="w-5 h-5" />, color: 'text-red-400' }
      ],
      details: supportedLanguages.slice(0, 8).map(lang => ({
        language: `${lang.flag} ${lang.name}`,
        patients: lang.patients,
        accuracy: Math.floor(Math.random() * 4) + 96,
        avg_response: `${(Math.random() * 2 + 0.5).toFixed(1)}s`
      }))
    },
    {
      id: 'provider-operations',
      title: 'Healthcare Provider Operations',
      description: 'Comprehensive view of medical operations across all partner organizations',
      stats: [
        { label: 'Active Providers', value: '847', trend: '+23', icon: <Building className="w-5 h-5" />, color: 'text-blue-400' },
        { label: 'Medical Encounters', value: '12,847', trend: '+8%', icon: <Stethoscope className="w-5 h-5" />, color: 'text-green-400' },
        { label: 'Emergency Cases', value: '234', trend: '-12%', icon: <AlertTriangle className="w-5 h-5" />, color: 'text-orange-400' },
        { label: 'Verified Records', value: '98.7%', trend: '+1.2%', icon: <Shield className="w-5 h-5" />, color: 'text-purple-400' }
      ],
      details: [
        { organization: 'UNHCR Health Units', providers: 234, encounters: 4567, specialties: 'General, Mental Health, Maternal' },
        { organization: 'MSF Field Hospitals', providers: 189, encounters: 3421, specialties: 'Emergency, Surgery, Infectious Disease' },
        { organization: 'IRC Mobile Clinics', providers: 156, encounters: 2890, specialties: 'Primary Care, Pediatrics, Nutrition' },
        { organization: 'Local Health Ministries', providers: 268, encounters: 1969, specialties: 'Integration, Chronic Care, Referrals' }
      ]
    },
    {
      id: 'real-time-monitoring',
      title: 'Real-Time System Monitoring',
      description: 'Live monitoring of system performance, blockchain operations, and AI processing',
      stats: [
        { label: 'System Uptime', value: '99.97%', trend: '+0.02%', icon: <Zap className="w-5 h-5" />, color: 'text-green-400' },
        { label: 'Blockchain TPS', value: '1,247', trend: '+5%', icon: <Shield className="w-5 h-5" />, color: 'text-blue-400' },
        { label: 'AI Processing', value: '3.2s', trend: '-0.8s', icon: <Activity className="w-5 h-5" />, color: 'text-purple-400' },
        { label: 'Active Sessions', value: '2,847', trend: '+234', icon: <Users className="w-5 h-5" />, color: 'text-orange-400' }
      ],
      details: [
        { service: 'Translation Pipeline', status: 'Healthy', latency: '1.2s', throughput: '2,847/min' },
        { service: 'Blockchain Network', status: 'Healthy', latency: '0.8s', throughput: '1,247 TPS' },
        { service: 'Medical AI Processing', status: 'Healthy', latency: '3.2s', throughput: '456/min' },
        { service: 'Document Verification', status: 'Warning', latency: '4.1s', throughput: '189/min' }
      ]
    }
  ];

  const runDemo = () => {
    setIsRunning(true);
    setActiveView(0);

    const cycleViews = () => {
      setActiveView(prev => {
        if (prev >= dashboardViews.length - 1) {
          setTimeout(() => {
            setIsRunning(false);
            setActiveView(0);
          }, 2000);
          return prev;
        }
        return prev + 1;
      });
    };

    const interval = setInterval(() => {
      cycleViews();
      if (activeView >= dashboardViews.length - 1) {
        clearInterval(interval);
      }
    }, 5000);
  };

  const currentView = dashboardViews[activeView];
  const selectedRegionData = regions.find(r => r.code === selectedRegion);
  const selectedLanguageData = supportedLanguages.find(l => l.code === selectedLanguage);

  return (
    <div className="w-full">
      {/* Demo Overview */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
        <div>
            <h3 className="text-2xl font-semibold text-white mb-2">
              Healthcare Provider Management Dashboard
            </h3>
            <p className="text-gray-300">
              Comprehensive medical operations dashboard with 52-language support for refugee healthcare
            </p>
        </div>
          <Button
            onClick={runDemo}
            disabled={isRunning}
            className="button-gradient"
          >
            <Play className="mr-2 w-4 h-4" />
            {isRunning ? 'Dashboard Active...' : 'Start Dashboard'}
          </Button>
      </div>

        {/* Language and Region Selectors */}
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex items-center space-x-2">
            <Languages className="w-4 h-4 text-gray-400" />
            <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
              <SelectTrigger className="w-48 bg-black/50 border-white/10 text-white">
              <SelectValue />
            </SelectTrigger>
              <SelectContent className="bg-black border-white/10">
                {supportedLanguages.slice(0, 15).map((lang) => (
                  <SelectItem key={lang.code} value={lang.code} className="text-white hover:bg-white/10">
                    {lang.flag} {lang.name} ({lang.patients.toLocaleString()})
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        
          <div className="flex items-center space-x-2">
            <MapPin className="w-4 h-4 text-gray-400" />
            <Select value={selectedRegion} onValueChange={setSelectedRegion}>
              <SelectTrigger className="w-48 bg-black/50 border-white/10 text-white">
              <SelectValue />
            </SelectTrigger>
              <SelectContent className="bg-black border-white/10">
                {regions.map((region) => (
                  <SelectItem key={region.code} value={region.code} className="text-white hover:bg-white/10">
                    {region.name} ({region.facilities})
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          </div>

          <div className="flex items-center space-x-4 text-sm text-gray-400">
            <span>52 Languages Active</span>
            <span>•</span>
            <span>127 Facilities</span>
            <span>•</span>
            <span>47,392 Patients</span>
          </div>
        </div>
      </div>

      {/* Current Dashboard View */}
      <div className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm">
        {/* View Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h4 className="text-xl font-semibold text-white mb-1">{currentView.title}</h4>
            <p className="text-gray-300 text-sm">{currentView.description}</p>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="border-white/20 text-gray-400">
              View {activeView + 1} of {dashboardViews.length}
            </Badge>
            {isRunning && (
              <Badge className="bg-green-600 text-white">
                <Activity className="w-3 h-3 mr-1 animate-pulse" />
                Live
              </Badge>
            )}
        </div>
          </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {currentView.stats.map((stat, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: isRunning ? 1 : 0.7, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 rounded-lg p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div className={stat.color}>
                  {stat.icon}
          </div>
                <Badge variant="outline" className={`text-xs ${
                  stat.trend.includes('+') ? 'border-green-500/30 text-green-400' : 
                  stat.trend.includes('-') ? 'border-red-500/30 text-red-400' : 'border-blue-500/30 text-blue-400'
                }`}>
                  {stat.trend}
                </Badge>
              </div>
              <div className="text-2xl font-bold text-white mb-1">{stat.value}</div>
              <div className="text-xs text-gray-400">{stat.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Detailed Data */}
        <div className="space-y-4">
          <h5 className="text-lg font-semibold text-white mb-4">
            {activeView === 0 && 'Top Languages by Patient Volume'}
            {activeView === 1 && 'Partner Organizations'}
            {activeView === 2 && 'System Services Status'}
          </h5>
          
          {currentView.details.map((detail, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: isRunning ? 1 : 0.5, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 rounded-lg p-4"
            >
              {/* Language Analytics View */}
              {activeView === 0 && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-white font-medium">{detail.language}</div>
                    <div className="text-xs text-gray-400">Language</div>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.patients.toLocaleString()}</div>
                    <div className="text-xs text-gray-400">Patients</div>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.accuracy}%</div>
                    <div className="text-xs text-gray-400">Translation Accuracy</div>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.avg_response}</div>
                    <div className="text-xs text-gray-400">Avg Response Time</div>
                  </div>
                </div>
              )}

              {/* Provider Operations View */}
              {activeView === 1 && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-white font-medium">{detail.organization}</div>
                    <div className="text-xs text-gray-400">Organization</div>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.providers}</div>
                    <div className="text-xs text-gray-400">Providers</div>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.encounters.toLocaleString()}</div>
                    <div className="text-xs text-gray-400">Encounters</div>
                  </div>
                  <div>
                    <div className="text-white font-medium text-xs">{detail.specialties}</div>
                    <div className="text-xs text-gray-400">Specialties</div>
                  </div>
                </div>
              )}

              {/* System Monitoring View */}
              {activeView === 2 && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-white font-medium">{detail.service}</div>
                    <div className="text-xs text-gray-400">Service</div>
                  </div>
                  <div>
                    <Badge className={`${
                      detail.status === 'Healthy' ? 'bg-green-600' :
                      detail.status === 'Warning' ? 'bg-orange-600' : 'bg-red-600'
                    } text-white text-xs`}>
                      {detail.status}
                    </Badge>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.latency}</div>
                    <div className="text-xs text-gray-400">Latency</div>
                  </div>
                  <div>
                    <div className="text-white font-medium">{detail.throughput}</div>
                    <div className="text-xs text-gray-400">Throughput</div>
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </div>

        {/* Language Spotlight */}
        {selectedLanguageData && (
          <div className="mt-8 bg-gradient-to-r from-blue-900/20 to-purple-900/20 border border-blue-500/30 rounded-xl p-6">
            <h5 className="text-lg font-semibold text-white mb-4 flex items-center">
              <Languages className="w-5 h-5 mr-2" />
              Language Spotlight: {selectedLanguageData.flag} {selectedLanguageData.name}
            </h5>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-2xl font-bold text-blue-400">{selectedLanguageData.patients.toLocaleString()}</div>
                <div className="text-xs text-gray-400">Active Patients</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-400">97.8%</div>
                <div className="text-xs text-gray-400">Translation Accuracy</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-400">1.4s</div>
                <div className="text-xs text-gray-400">Avg Response Time</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-orange-400">24/7</div>
                <div className="text-xs text-gray-400">Support Coverage</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Demo Complete */}
      {isRunning && activeView === dashboardViews.length - 1 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 bg-gradient-to-r from-green-900/20 to-blue-900/20 border border-green-500/30 rounded-xl p-6 text-center"
        >
          <h4 className="text-lg font-semibold text-white mb-2">
            Healthcare Provider Dashboard Complete
          </h4>
          <p className="text-gray-300 text-sm mb-4">
            Comprehensive management across 52 languages, 127 facilities, and 47,392+ patients
          </p>
          <div className="flex items-center justify-center space-x-4 text-sm text-gray-400">
            <span>🌍 52 Languages</span>
            <span>🏥 Multi-organization</span>
            <span>⚡ Real-time monitoring</span>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default DashboardDemo;