import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  FileText, 
  Download, 
  Calendar, 
  Mail, 
  Settings,
  BarChart3,
  TrendingUp,
  Clock,
  Users
} from 'lucide-react';

interface ReportConfig {
  id: string;
  name: string;
  type: 'DAILY_SUMMARY' | 'WEEKLY_ANALYSIS' | 'MONTHLY_OVERVIEW' | 'CUSTOM';
  schedule: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
  format: 'HTML' | 'PDF' | 'EXCEL' | 'MARKDOWN' | 'JSON';
  recipients: string[];
  lastGenerated: string;
  nextScheduled: string;
  status: 'active' | 'paused' | 'error';
}

interface ReportData {
  id: string;
  title: string;
  generatedAt: string;
  period: string;
  sections: {
    executive_summary: {
      total_translations: number;
      quality_score: number;
      pass_rate: number;
      critical_issues: number;
    };
    performance_metrics: {
      avg_response_time: number;
      uptime: number;
      throughput: number;
    };
    quality_trends: {
      trend: 'improving' | 'stable' | 'declining';
      change_percentage: number;
    };
    recommendations: string[];
  };
}

const AutomatedReportingDemo: React.FC = () => {
  const [reportConfigs] = useState<ReportConfig[]>([
    {
      id: 'daily_summary',
      name: 'Daily Quality Summary',
      type: 'DAILY_SUMMARY',
      schedule: 'DAILY',
      format: 'HTML',
      recipients: ['quality-team@havenhealth.org'],
      lastGenerated: '2024-01-15 08:00:00',
      nextScheduled: '2024-01-16 08:00:00',
      status: 'active'
    },
    {
      id: 'weekly_analysis',
      name: 'Weekly Performance Analysis',
      type: 'WEEKLY_ANALYSIS',
      schedule: 'WEEKLY',
      format: 'PDF',
      recipients: ['management@havenhealth.org', 'quality-team@havenhealth.org'],
      lastGenerated: '2024-01-14 09:00:00',
      nextScheduled: '2024-01-21 09:00:00',
      status: 'active'
    },
    {
      id: 'language_pair_analysis',
      name: 'Language Pair Analysis',
      type: 'CUSTOM',
      schedule: 'WEEKLY',
      format: 'MARKDOWN',
      recipients: ['translation-team@havenhealth.org'],
      lastGenerated: '2024-01-14 10:00:00',
      nextScheduled: '2024-01-21 10:00:00',
      status: 'active'
    }
  ]);

  const [selectedReport, setSelectedReport] = useState<string>('daily_summary');
  const [generatedReport, setGeneratedReport] = useState<ReportData | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const generateReport = async (reportId: string) => {
    setIsGenerating(true);
    
    // Simulate report generation
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    const mockReport: ReportData = {
      id: reportId,
      title: reportConfigs.find(r => r.id === reportId)?.name || 'Report',
      generatedAt: new Date().toISOString(),
      period: 'Last 24 Hours',
      sections: {
        executive_summary: {
          total_translations: 15420,
          quality_score: 0.94,
          pass_rate: 0.96,
          critical_issues: 3
        },
        performance_metrics: {
          avg_response_time: 1.2,
          uptime: 0.999,
          throughput: 642
        },
        quality_trends: {
          trend: 'improving',
          change_percentage: 2.3
        },
        recommendations: [
          'Monitor Spanish-English translations for terminology consistency',
          'Review medical terminology validation rules',
          'Consider increasing cache size for better performance'
        ]
      }
    };
    
    setGeneratedReport(mockReport);
    setIsGenerating(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'paused': return 'bg-yellow-100 text-yellow-800';
      case 'error': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Automated Reporting Demo</h2>
          <p className="text-gray-600">Translation quality monitoring and automated report generation</p>
        </div>
        <Button onClick={() => generateReport(selectedReport)} disabled={isGenerating}>
          {isGenerating ? (
            <>
              <Clock className="w-4 h-4 mr-2 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <FileText className="w-4 h-4 mr-2" />
              Generate Report
            </>
          )}
        </Button>
      </div>

      <Tabs defaultValue="configurations" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="configurations">Report Configurations</TabsTrigger>
          <TabsTrigger value="generator">Report Generator</TabsTrigger>
          <TabsTrigger value="preview">Report Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="configurations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Settings className="w-5 h-5 mr-2" />
                Configured Reports
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {reportConfigs.map(config => (
                  <div key={config.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <h3 className="font-medium">{config.name}</h3>
                        <Badge className={getStatusColor(config.status)}>
                          {config.status}
                        </Badge>
                        <Badge variant="outline">{config.schedule}</Badge>
                        <Badge variant="outline">{config.format}</Badge>
                      </div>
                      <div className="text-sm text-gray-600 mt-1">
                        <div>Last: {formatDateTime(config.lastGenerated)}</div>
                        <div>Next: {formatDateTime(config.nextScheduled)}</div>
                        <div>Recipients: {config.recipients.join(', ')}</div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button variant="outline" size="sm">
                        <Settings className="w-4 h-4" />
                      </Button>
                      <Button variant="outline" size="sm">
                        <Download className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="generator" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Generate Custom Report</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Report Type</label>
                  <Select value={selectedReport} onValueChange={setSelectedReport}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {reportConfigs.map(config => (
                        <SelectItem key={config.id} value={config.id}>
                          {config.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium mb-2">Output Format</label>
                  <Select defaultValue="HTML">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="HTML">HTML</SelectItem>
                      <SelectItem value="PDF">PDF</SelectItem>
                      <SelectItem value="EXCEL">Excel</SelectItem>
                      <SelectItem value="MARKDOWN">Markdown</SelectItem>
                      <SelectItem value="JSON">JSON</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Time Period</label>
                <Select defaultValue="24h">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1h">Last Hour</SelectItem>
                    <SelectItem value="24h">Last 24 Hours</SelectItem>
                    <SelectItem value="7d">Last 7 Days</SelectItem>
                    <SelectItem value="30d">Last 30 Days</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button 
                onClick={() => generateReport(selectedReport)} 
                disabled={isGenerating}
                className="w-full"
              >
                {isGenerating ? 'Generating Report...' : 'Generate Report'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="preview" className="space-y-4">
          {generatedReport ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{generatedReport.title}</span>
                  <div className="flex space-x-2">
                    <Button variant="outline" size="sm">
                      <Download className="w-4 h-4 mr-2" />
                      Download
                    </Button>
                    <Button variant="outline" size="sm">
                      <Mail className="w-4 h-4 mr-2" />
                      Email
                    </Button>
                  </div>
                </CardTitle>
                <p className="text-sm text-gray-600">
                  Generated: {formatDateTime(generatedReport.generatedAt)} | Period: {generatedReport.period}
                </p>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Executive Summary */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Executive Summary</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-3 bg-blue-50 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {generatedReport.sections.executive_summary.total_translations.toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-600">Total Translations</div>
                    </div>
                    <div className="text-center p-3 bg-green-50 rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {(generatedReport.sections.executive_summary.quality_score * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-gray-600">Quality Score</div>
                    </div>
                    <div className="text-center p-3 bg-purple-50 rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {(generatedReport.sections.executive_summary.pass_rate * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-gray-600">Pass Rate</div>
                    </div>
                    <div className="text-center p-3 bg-red-50 rounded-lg">
                      <div className="text-2xl font-bold text-red-600">
                        {generatedReport.sections.executive_summary.critical_issues}
                      </div>
                      <div className="text-sm text-gray-600">Critical Issues</div>
                    </div>
                  </div>
                </div>

                {/* Performance Metrics */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Performance Metrics</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Avg Response Time</span>
                        <Clock className="w-4 h-4 text-gray-400" />
                      </div>
                      <div className="text-xl font-bold">
                        {generatedReport.sections.performance_metrics.avg_response_time}s
                      </div>
                    </div>
                    <div className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Uptime</span>
                        <TrendingUp className="w-4 h-4 text-gray-400" />
                      </div>
                      <div className="text-xl font-bold">
                        {(generatedReport.sections.performance_metrics.uptime * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Throughput</span>
                        <BarChart3 className="w-4 h-4 text-gray-400" />
                      </div>
                      <div className="text-xl font-bold">
                        {generatedReport.sections.performance_metrics.throughput}/min
                      </div>
                    </div>
                  </div>
                </div>

                {/* Quality Trends */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Quality Trends</h3>
                  <div className="p-4 border rounded-lg">
                    <div className="flex items-center space-x-2">
                      <TrendingUp className={`w-5 h-5 ${
                        generatedReport.sections.quality_trends.trend === 'improving' ? 'text-green-500' :
                        generatedReport.sections.quality_trends.trend === 'stable' ? 'text-blue-500' :
                        'text-red-500'
                      }`} />
                      <span className="font-medium capitalize">
                        {generatedReport.sections.quality_trends.trend}
                      </span>
                      <Badge variant="outline">
                        {generatedReport.sections.quality_trends.change_percentage > 0 ? '+' : ''}
                        {generatedReport.sections.quality_trends.change_percentage}%
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Recommendations */}
                <div>
                  <h3 className="text-lg font-semibold mb-3">Recommendations</h3>
                  <div className="space-y-2">
                    {generatedReport.sections.recommendations.map((rec, index) => (
                      <div key={index} className="flex items-start space-x-2 p-3 bg-yellow-50 rounded-lg">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full mt-2 flex-shrink-0" />
                        <span className="text-sm">{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="text-center py-12">
                <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No report generated yet. Use the Report Generator tab to create a report.</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AutomatedReportingDemo;