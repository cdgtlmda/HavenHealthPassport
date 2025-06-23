import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  AlertTriangle, 
  Bell, 
  CheckCircle, 
  Clock, 
  Mail, 
  MessageSquare,
  TrendingDown,
  Settings
} from 'lucide-react';

interface AlertRule {
  id: string;
  name: string;
  priority: 'P1_CRITICAL' | 'P2_HIGH' | 'P3_MEDIUM' | 'P4_LOW' | 'P5_INFO';
  metric: string;
  threshold: number;
  operator: string;
  channels: string[];
  status: 'active' | 'triggered' | 'resolved';
}

interface AlertMetrics {
  quality_score: number;
  pass_rate: number;
  validation_time: number;
  terminology_accuracy: number;
}

const AlertMechanismsDemo: React.FC = () => {
  const [metrics, setMetrics] = useState<AlertMetrics>({
    quality_score: 0.85,
    pass_rate: 0.92,
    validation_time: 2.1,
    terminology_accuracy: 0.96
  });

  const [alertRules] = useState<AlertRule[]>([
    {
      id: 'critical_quality',
      name: 'Critical Quality Drop',
      priority: 'P1_CRITICAL',
      metric: 'quality_score',
      threshold: 0.70,
      operator: '<',
      channels: ['email', 'slack', 'sms'],
      status: 'active'
    },
    {
      id: 'high_pass_rate',
      name: 'Low Pass Rate Alert',
      priority: 'P2_HIGH',
      metric: 'pass_rate',
      threshold: 0.80,
      operator: '<',
      channels: ['email', 'slack'],
      status: 'active'
    },
    {
      id: 'performance_alert',
      name: 'Performance Degradation',
      priority: 'P3_MEDIUM',
      metric: 'validation_time',
      threshold: 5.0,
      operator: '>',
      channels: ['slack'],
      status: 'active'
    },
    {
      id: 'terminology_accuracy',
      name: 'Terminology Accuracy Drop',
      priority: 'P2_HIGH',
      metric: 'terminology_accuracy',
      threshold: 0.95,
      operator: '<',
      channels: ['email', 'slack'],
      status: 'active'
    }
  ]);

  const [triggeredAlerts, setTriggeredAlerts] = useState<AlertRule[]>([]);

  const simulateQualityDrop = () => {
    setMetrics({
      quality_score: 0.65,
      pass_rate: 0.75,
      validation_time: 6.0,
      terminology_accuracy: 0.92
    });
  };

  const resetMetrics = () => {
    setMetrics({
      quality_score: 0.85,
      pass_rate: 0.92,
      validation_time: 2.1,
      terminology_accuracy: 0.96
    });
  };

  useEffect(() => {
    const triggered = alertRules.filter(rule => {
      const metricValue = metrics[rule.metric as keyof AlertMetrics];
      if (rule.operator === '<') {
        return metricValue < rule.threshold;
      } else if (rule.operator === '>') {
        return metricValue > rule.threshold;
      }
      return false;
    });
    setTriggeredAlerts(triggered);
  }, [metrics, alertRules]);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'P1_CRITICAL': return 'bg-red-100 text-red-800 border-red-200';
      case 'P2_HIGH': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'P3_MEDIUM': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'P4_LOW': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'P5_INFO': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getMetricStatus = (metric: keyof AlertMetrics, value: number) => {
    const rule = alertRules.find(r => r.metric === metric);
    if (!rule) return 'normal';
    
    if (rule.operator === '<' && value < rule.threshold) return 'critical';
    if (rule.operator === '>' && value > rule.threshold) return 'critical';
    return 'normal';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Alert Mechanisms Demo</h2>
          <p className="text-gray-600">Translation quality monitoring and alerting system</p>
        </div>
        <div className="flex space-x-2">
          <Button onClick={simulateQualityDrop} variant="destructive">
            <TrendingDown className="w-4 h-4 mr-2" />
            Simulate Quality Drop
          </Button>
          <Button onClick={resetMetrics} variant="outline">
            Reset Metrics
          </Button>
        </div>
      </div>

      {/* Current Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(metrics).map(([key, value]) => {
          const status = getMetricStatus(key as keyof AlertMetrics, value);
          const isPercentage = key !== 'validation_time';
          const displayValue = isPercentage ? `${(value * 100).toFixed(1)}%` : `${value.toFixed(1)}s`;
          
          return (
            <Card key={key} className={status === 'critical' ? 'border-red-200 bg-red-50' : ''}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 capitalize">
                  {key.replace('_', ' ')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {displayValue}
                </div>
                {isPercentage && (
                  <Progress 
                    value={value * 100} 
                    className="mt-2"
                    // @ts-ignore
                    indicatorClassName={status === 'critical' ? 'bg-red-500' : 'bg-green-500'}
                  />
                )}
                {status === 'critical' && (
                  <div className="flex items-center mt-2 text-red-600">
                    <AlertTriangle className="w-4 h-4 mr-1" />
                    <span className="text-xs">Below threshold</span>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Active Alerts */}
      {triggeredAlerts.length > 0 && (
        <Card className="border-red-200">
          <CardHeader>
            <CardTitle className="flex items-center text-red-700">
              <Bell className="w-5 h-5 mr-2" />
              Active Alerts ({triggeredAlerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {triggeredAlerts.map(alert => (
              <Alert key={alert.id} className="border-red-200">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{alert.name}</div>
                      <div className="text-sm text-gray-600">
                        {alert.metric} {alert.operator} {alert.threshold}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge className={getPriorityColor(alert.priority)}>
                        {alert.priority}
                      </Badge>
                      <div className="flex space-x-1">
                        {alert.channels.includes('email') && <Mail className="w-4 h-4 text-gray-400" />}
                        {alert.channels.includes('slack') && <MessageSquare className="w-4 h-4 text-gray-400" />}
                      </div>
                    </div>
                  </div>
                </AlertDescription>
              </Alert>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Alert Rules Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Settings className="w-5 h-5 mr-2" />
            Alert Rules Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {alertRules.map(rule => (
              <div key={rule.id} className="flex items-center justify-between p-3 border rounded-lg">
                <div>
                  <div className="font-medium">{rule.name}</div>
                  <div className="text-sm text-gray-600">
                    {rule.metric} {rule.operator} {rule.threshold}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge className={getPriorityColor(rule.priority)}>
                    {rule.priority}
                  </Badge>
                  <div className="flex space-x-1">
                    {rule.channels.map(channel => (
                      <Badge key={channel} variant="outline" className="text-xs">
                        {channel}
                      </Badge>
                    ))}
                  </div>
                  {triggeredAlerts.some(a => a.id === rule.id) ? (
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                  ) : (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Alert Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Total Alerts (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{triggeredAlerts.length}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Critical Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {triggeredAlerts.filter(a => a.priority === 'P1_CRITICAL').length}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Response Time</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">2.3s</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AlertMechanismsDemo;