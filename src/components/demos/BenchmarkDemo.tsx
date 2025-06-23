import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Target, 
  TrendingUp, 
  Award, 
  CheckCircle, 
  AlertTriangle,
  Star,
  BarChart3,
  Clock
} from 'lucide-react';

interface BenchmarkResult {
  id: string;
  name: string;
  category: 'quality' | 'performance' | 'reliability' | 'accuracy';
  level: 'WORLD_CLASS' | 'EXCELLENT' | 'TARGET' | 'MINIMUM';
  actualValue: number;
  targetValue: number;
  unit: string;
  isPassing: boolean;
  exceedsTarget: boolean;
  targetPercentage: number;
  description: string;
}

interface TranslationMetrics {
  totalValidations: number;
  passedValidations: number;
  failedValidations: number;
  warnings: number;
  confidenceScore: number;
  validationTime: number;
  semanticSimilarity: number;
  terminologyAccuracy: number;
  formatPreservation: number;
  fluencyScore: number;
  passRate: number;
  qualityScore: number;
}

const BenchmarkDemo: React.FC = () => {
  const [metrics, setMetrics] = useState<TranslationMetrics>({
    totalValidations: 100,
    passedValidations: 99,
    failedValidations: 1,
    warnings: 2,
    confidenceScore: 0.94,
    validationTime: 1.2,
    semanticSimilarity: 0.93,
    terminologyAccuracy: 0.99,
    formatPreservation: 0.98,
    fluencyScore: 0.92,
    passRate: 0.99,
    qualityScore: 0.94
  });

  const [benchmarkResults, setBenchmarkResults] = useState<BenchmarkResult[]>([]);
  const [isEvaluating, setIsEvaluating] = useState(false);

  const benchmarkDefinitions: BenchmarkResult[] = [
    {
      id: 'pass_rate',
      name: 'Translation Pass Rate',
      category: 'quality',
      level: 'TARGET',
      actualValue: 0,
      targetValue: 0.95,
      unit: '%',
      isPassing: false,
      exceedsTarget: false,
      targetPercentage: 0,
      description: 'Percentage of translations that pass validation'
    },
    {
      id: 'quality_score',
      name: 'Overall Quality Score',
      category: 'quality',
      level: 'TARGET',
      actualValue: 0,
      targetValue: 0.90,
      unit: '%',
      isPassing: false,
      exceedsTarget: false,
      targetPercentage: 0,
      description: 'Composite quality score across all metrics'
    },
    {
      id: 'terminology_accuracy',
      name: 'Medical Terminology Accuracy',
      category: 'accuracy',
      level: 'TARGET',
      actualValue: 0,
      targetValue: 0.99,
      unit: '%',
      isPassing: false,
      exceedsTarget: false,
      targetPercentage: 0,
      description: 'Accuracy of medical terminology translation'
    },
    {
      id: 'validation_time',
      name: 'Validation Response Time',
      category: 'performance',
      level: 'TARGET',
      actualValue: 0,
      targetValue: 2.0,
      unit: 's',
      isPassing: false,
      exceedsTarget: false,
      targetPercentage: 0,
      description: 'Time taken to validate translations'
    },
    {
      id: 'semantic_similarity',
      name: 'Semantic Similarity',
      category: 'quality',
      level: 'TARGET',
      actualValue: 0,
      targetValue: 0.85,
      unit: '%',
      isPassing: false,
      exceedsTarget: false,
      targetPercentage: 0,
      description: 'Semantic similarity between source and target'
    },
    {
      id: 'fluency_score',
      name: 'Translation Fluency',
      category: 'quality',
      level: 'TARGET',
      actualValue: 0,
      targetValue: 0.90,
      unit: '%',
      isPassing: false,
      exceedsTarget: false,
      targetPercentage: 0,
      description: 'Fluency and naturalness of translations'
    }
  ];

  const evaluateBenchmarks = () => {
    setIsEvaluating(true);
    
    setTimeout(() => {
      const results = benchmarkDefinitions.map(benchmark => {
        let actualValue: number;
        
        switch (benchmark.id) {
          case 'pass_rate':
            actualValue = metrics.passRate;
            break;
          case 'quality_score':
            actualValue = metrics.qualityScore;
            break;
          case 'terminology_accuracy':
            actualValue = metrics.terminologyAccuracy;
            break;
          case 'validation_time':
            actualValue = metrics.validationTime;
            break;
          case 'semantic_similarity':
            actualValue = metrics.semanticSimilarity;
            break;
          case 'fluency_score':
            actualValue = metrics.fluencyScore;
            break;
          default:
            actualValue = 0;
        }

        const isPassing = benchmark.id === 'validation_time' 
          ? actualValue <= benchmark.targetValue 
          : actualValue >= benchmark.targetValue;
        
        const exceedsTarget = benchmark.id === 'validation_time'
          ? actualValue < benchmark.targetValue * 0.8
          : actualValue > benchmark.targetValue * 1.1;

        const targetPercentage = benchmark.id === 'validation_time'
          ? Math.min(100, (benchmark.targetValue / actualValue) * 100)
          : (actualValue / benchmark.targetValue) * 100;

        // Determine achievement level
        let level: 'WORLD_CLASS' | 'EXCELLENT' | 'TARGET' | 'MINIMUM';
        if (benchmark.id === 'validation_time') {
          if (actualValue <= benchmark.targetValue * 0.5) level = 'WORLD_CLASS';
          else if (actualValue <= benchmark.targetValue * 0.7) level = 'EXCELLENT';
          else if (actualValue <= benchmark.targetValue) level = 'TARGET';
          else level = 'MINIMUM';
        } else {
          if (actualValue >= benchmark.targetValue * 1.2) level = 'WORLD_CLASS';
          else if (actualValue >= benchmark.targetValue * 1.1) level = 'EXCELLENT';
          else if (actualValue >= benchmark.targetValue) level = 'TARGET';
          else level = 'MINIMUM';
        }

        return {
          ...benchmark,
          actualValue,
          isPassing,
          exceedsTarget,
          targetPercentage: Math.min(100, targetPercentage),
          level
        };
      });

      setBenchmarkResults(results);
      setIsEvaluating(false);
    }, 1500);
  };

  useEffect(() => {
    evaluateBenchmarks();
  }, [metrics]);

  const simulatePerformanceChange = (type: 'improve' | 'degrade') => {
    if (type === 'improve') {
      setMetrics({
        ...metrics,
        passRate: 0.98,
        qualityScore: 0.96,
        terminologyAccuracy: 0.995,
        validationTime: 0.8,
        semanticSimilarity: 0.95,
        fluencyScore: 0.94
      });
    } else {
      setMetrics({
        ...metrics,
        passRate: 0.85,
        qualityScore: 0.82,
        terminologyAccuracy: 0.92,
        validationTime: 3.5,
        semanticSimilarity: 0.78,
        fluencyScore: 0.85
      });
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'WORLD_CLASS': return <Star className="w-4 h-4 text-yellow-500" />;
      case 'EXCELLENT': return <Award className="w-4 h-4 text-purple-500" />;
      case 'TARGET': return <Target className="w-4 h-4 text-blue-500" />;
      case 'MINIMUM': return <AlertTriangle className="w-4 h-4 text-orange-500" />;
      default: return <Target className="w-4 h-4 text-gray-500" />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'WORLD_CLASS': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'EXCELLENT': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'TARGET': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'MINIMUM': return 'bg-orange-100 text-orange-800 border-orange-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'quality': return <CheckCircle className="w-4 h-4" />;
      case 'performance': return <Clock className="w-4 h-4" />;
      case 'reliability': return <Target className="w-4 h-4" />;
      case 'accuracy': return <Award className="w-4 h-4" />;
      default: return <BarChart3 className="w-4 h-4" />;
    }
  };

  const passingCount = benchmarkResults.filter(r => r.isPassing).length;
  const exceedingCount = benchmarkResults.filter(r => r.exceedsTarget).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Performance Benchmarks Demo</h2>
          <p className="text-gray-600">Translation quality benchmarks and performance evaluation</p>
        </div>
        <div className="flex space-x-2">
          <Button onClick={() => simulatePerformanceChange('improve')} variant="outline">
            <TrendingUp className="w-4 h-4 mr-2" />
            Simulate Improvement
          </Button>
          <Button onClick={() => simulatePerformanceChange('degrade')} variant="outline">
            <AlertTriangle className="w-4 h-4 mr-2" />
            Simulate Degradation
          </Button>
          <Button onClick={evaluateBenchmarks} disabled={isEvaluating}>
            {isEvaluating ? 'Evaluating...' : 'Re-evaluate'}
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Total Benchmarks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{benchmarkResults.length}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Passing</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{passingCount}</div>
            <div className="text-xs text-gray-500">
              {benchmarkResults.length > 0 ? ((passingCount / benchmarkResults.length) * 100).toFixed(1) : 0}%
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Exceeding Target</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{exceedingCount}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-600">Overall Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {benchmarkResults.length > 0 ? 
                (benchmarkResults.reduce((sum, r) => sum + r.targetPercentage, 0) / benchmarkResults.length).toFixed(1) : 0}%
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="results" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="results">Benchmark Results</TabsTrigger>
          <TabsTrigger value="metrics">Current Metrics</TabsTrigger>
          <TabsTrigger value="trends">Performance Trends</TabsTrigger>
        </TabsList>

        <TabsContent value="results" className="space-y-4">
          <div className="grid gap-4">
            {benchmarkResults.map(result => (
              <Card key={result.id} className={result.isPassing ? 'border-green-200' : 'border-red-200'}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      {getCategoryIcon(result.category)}
                      <CardTitle className="text-lg">{result.name}</CardTitle>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge className={getLevelColor(result.level)}>
                        {getLevelIcon(result.level)}
                        <span className="ml-1">{result.level.replace('_', ' ')}</span>
                      </Badge>
                      {result.isPassing ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-600">{result.description}</p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span>Current: <strong>
                        {result.unit === '%' ? (result.actualValue * 100).toFixed(1) : result.actualValue.toFixed(2)}{result.unit}
                      </strong></span>
                      <span>Target: <strong>
                        {result.unit === '%' ? (result.targetValue * 100).toFixed(1) : result.targetValue.toFixed(2)}{result.unit}
                      </strong></span>
                    </div>
                    <Progress 
                      value={result.targetPercentage} 
                      className="h-2"
                    />
                    <div className="text-xs text-gray-500">
                      Achievement: {result.targetPercentage.toFixed(1)}% of target
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="metrics" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(metrics).map(([key, value]) => (
              <Card key={key}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-xl font-bold">
                    {key.includes('Rate') || key.includes('Score') || key.includes('Accuracy') || key.includes('Similarity') || key.includes('Preservation') ? 
                      `${(value * 100).toFixed(1)}%` : 
                      key === 'validationTime' ? `${value.toFixed(2)}s` :
                      value.toLocaleString()
                    }
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Trends</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="text-center py-8 text-gray-500">
                  <BarChart3 className="w-12 h-12 mx-auto mb-4" />
                  <p>Performance trend charts would be displayed here</p>
                  <p className="text-sm">Showing historical benchmark performance over time</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default BenchmarkDemo;