import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { motion } from 'framer-motion';
import { 
  Users, 
  Globe,
  TrendingUp,
  Heart,
  MapPin,
  Play,
  BarChart3,
  Activity,
  FileText,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

const EnhancedAutomatedReportingDemo: React.FC = () => {
  const [activeReport, setActiveReport] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);

  const reportTypes = [
    {
      id: 'population-health',
      title: 'Population Health Analytics',
      description: 'Comprehensive health metrics across refugee populations',
      icon: <Heart className="w-5 h-5" />,
      color: 'text-red-400',
      data: {
        overview: {
          total_beneficiaries: '47,392',
          active_cases: '12,847',
          health_score: '87.3%',
          intervention_rate: '94.2%'
        },
        key_insights: [
          'Diabetes management improved by 23% across Syrian refugee population',
          'Mental health support needs increased 18% in winter months',
          'Vaccination coverage reached 96.7% in all operational areas',
          'Maternal health outcomes show 91% positive birth outcomes'
        ],
        locations: [
          { name: 'Lebanon - Bekaa Valley', population: 15240, health_score: 89.2 },
          { name: 'Jordan - Zaatari Camp', population: 18650, health_score: 84.7 },
          { name: 'Turkey - Istanbul Hub', population: 8920, health_score: 91.4 },
          { name: 'Germany - Integration Centers', population: 4582, health_score: 93.1 }
        ]
      }
    },
    {
      id: 'cross-border-continuity',
      title: 'Cross-Border Care Continuity',
      description: 'Medical record transfer and care continuity tracking',
      icon: <Globe className="w-5 h-5" />,
      color: 'text-blue-400',
      data: {
        overview: {
          border_crossings: '3,247',
          successful_transfers: '98.7%',
          avg_verification_time: '4.2 minutes',
          care_continuity_rate: '91.8%'
        },
        key_insights: [
          'Record verification time improved by 67% with blockchain integration',
          'Care continuity maintained for 91.8% of cross-border patients',
          'Emergency medical access reduced from 4.2 hours to 12 minutes',
          'Multi-language support covers 14 languages with 96% accuracy'
        ],
        routes: [
          { route: 'Syria → Lebanon → Germany', patients: 847, success_rate: 96.2 },
          { route: 'Afghanistan → Turkey → Sweden', patients: 623, success_rate: 89.4 },
          { route: 'Somalia → Kenya → Canada', patients: 412, success_rate: 91.7 },
          { route: 'Ukraine → Poland → Multiple EU', patients: 1365, success_rate: 98.9 }
        ]
      }
    },
    {
      id: 'organizational-impact',
      title: 'Multi-Organization Impact',
      description: 'Collaboration effectiveness and resource optimization',
      icon: <Users className="w-5 h-5" />,
      color: 'text-purple-400',
      data: {
        overview: {
          partner_organizations: '127',
          coordinated_interventions: '2,847',
          resource_efficiency: '89.4%',
          data_sharing_compliance: '99.2%'
        },
        key_insights: [
          'Inter-agency coordination reduced duplicate services by 34%',
          'Resource sharing improved emergency response time by 58%',
          'Data standardization enabled seamless patient handoffs',
          'Joint programs served 23% more beneficiaries with same resources'
        ],
        organizations: [
          { name: 'UNHCR', collaboration_score: 97.3, shared_cases: 8420 },
          { name: 'MSF', collaboration_score: 94.7, shared_cases: 6250 },
          { name: 'IRC', collaboration_score: 91.2, shared_cases: 4180 },
          { name: 'Local Health Ministries', collaboration_score: 88.9, shared_cases: 12750 }
        ]
      }
    }
  ];

  const generateReport = () => {
    setIsGenerating(true);
    
    const cycleReports = () => {
      setActiveReport(prev => {
        if (prev >= reportTypes.length - 1) {
          setTimeout(() => {
            setIsGenerating(false);
            setActiveReport(0);
          }, 2000);
          return prev;
        }
        return prev + 1;
      });
    };

    const interval = setInterval(() => {
      cycleReports();
      if (activeReport >= reportTypes.length - 1) {
        clearInterval(interval);
      }
    }, 4000);
  };

  const currentReport = reportTypes[activeReport];

  return (
    <div className="w-full">
      {/* Demo Overview */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-2xl font-semibold text-white mb-2">
              Multi-Organization Analytics Dashboard
            </h3>
            <p className="text-gray-300">
              Real-time reporting and analytics across refugee healthcare organizations
            </p>
          </div>
          <Button 
            onClick={generateReport}
            disabled={isGenerating}
            className="button-gradient"
          >
            <Play className="mr-2 w-4 h-4" />
            {isGenerating ? 'Generating Reports...' : 'Generate Reports'}
          </Button>
        </div>
      </div>

      {/* Current Report */}
      <div className="bg-black/50 border border-white/10 rounded-xl p-6 backdrop-blur-sm">
        {/* Report Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className={`${currentReport.color} p-2 bg-white/10 rounded-lg`}>
              {currentReport.icon}
            </div>
            <div>
              <h4 className="text-xl font-semibold text-white">{currentReport.title}</h4>
              <p className="text-gray-300 text-sm">{currentReport.description}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="border-white/20 text-gray-400">
              Report {activeReport + 1} of {reportTypes.length}
            </Badge>
            {isGenerating && (
              <Badge className="bg-green-600 text-white">
                <Activity className="w-3 h-3 mr-1 animate-pulse" />
                Live
              </Badge>
            )}
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {Object.entries(currentReport.data.overview).map(([key, value], index) => (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: isGenerating ? 1 : 0.7, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 rounded-lg p-4"
            >
              <div className="text-2xl font-bold text-white mb-1">{value}</div>
              <div className="text-xs text-gray-400 capitalize">
                {key.replace(/_/g, ' ')}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Key Insights */}
        <div className="mb-8">
          <h5 className="text-lg font-semibold text-white mb-4">Key Insights</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {currentReport.data.key_insights.map((insight, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: isGenerating ? 1 : 0.5, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="bg-white/5 rounded-lg p-4 flex items-start space-x-3"
              >
                <CheckCircle className="w-5 h-5 text-green-400 mt-0.5 flex-shrink-0" />
                <p className="text-gray-300 text-sm">{insight}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Detailed Data */}
        <div className="space-y-4">
          <h5 className="text-lg font-semibold text-white mb-4">
            {activeReport === 0 && 'Location Breakdown'}
            {activeReport === 1 && 'Migration Routes'}
            {activeReport === 2 && 'Organization Collaboration'}
          </h5>
          
          {/* Location data for Population Health */}
          {activeReport === 0 && currentReport.data.locations.map((location, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: isGenerating ? 1 : 0.5, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 rounded-lg p-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-white font-medium">{location.name}</div>
                  <div className="text-xs text-gray-400">Location</div>
                </div>
                <div>
                  <div className="text-white font-medium">{location.population.toLocaleString()}</div>
                  <div className="text-xs text-gray-400">Population</div>
                </div>
                <div>
                  <div className="text-white font-medium">{location.health_score}%</div>
                  <div className="text-xs text-gray-400">Health Score</div>
                </div>
              </div>
            </motion.div>
          ))}

          {/* Route data for Cross-Border */}
          {activeReport === 1 && currentReport.data.routes.map((route, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: isGenerating ? 1 : 0.5, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 rounded-lg p-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-white font-medium">{route.route}</div>
                  <div className="text-xs text-gray-400">Migration Route</div>
                </div>
                <div>
                  <div className="text-white font-medium">{route.patients}</div>
                  <div className="text-xs text-gray-400">Patients</div>
                </div>
                <div>
                  <div className="text-white font-medium">{route.success_rate}%</div>
                  <div className="text-xs text-gray-400">Success Rate</div>
                </div>
              </div>
            </motion.div>
          ))}

          {/* Organization data for Multi-Org */}
          {activeReport === 2 && currentReport.data.organizations.map((org, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: isGenerating ? 1 : 0.5, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 rounded-lg p-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-white font-medium">{org.name}</div>
                  <div className="text-xs text-gray-400">Organization</div>
                </div>
                <div>
                  <div className="text-white font-medium">{org.collaboration_score}%</div>
                  <div className="text-xs text-gray-400">Collaboration Score</div>
                </div>
                <div>
                  <div className="text-white font-medium">{org.shared_cases.toLocaleString()}</div>
                  <div className="text-xs text-gray-400">Shared Cases</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Demo Complete */}
      {isGenerating && activeReport === reportTypes.length - 1 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 bg-gradient-to-r from-green-900/20 to-blue-900/20 border border-green-500/30 rounded-xl p-6 text-center"
        >
          <h4 className="text-lg font-semibold text-white mb-2">
            Multi-Organization Analytics Complete
          </h4>
          <p className="text-gray-300 text-sm mb-4">
            Comprehensive analytics across population health, cross-border care, and organizational impact
          </p>
          <div className="flex items-center justify-center space-x-4 text-sm text-gray-400">
            <span>📊 Population health</span>
            <span>🌍 Cross-border care</span>
            <span>🤝 Organization impact</span>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default EnhancedAutomatedReportingDemo; 