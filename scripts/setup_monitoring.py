#!/usr/bin/env python3
"""
Monitoring and Alerting Setup for Haven Health Passport
Configures CloudWatch dashboards, alarms, and alerting for patient safety
CRITICAL: Ensures system issues are detected before they impact patient care
"""

import os
import sys
import json
import boto3
import argparse
import logging
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MonitoringSetup:
    """Sets up comprehensive monitoring for Haven Health Passport"""
    
    def __init__(self, environment: str, region: str = 'us-east-1'):
        self.environment = environment
        self.region = region
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.sns = boto3.client('sns', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        self.ssm = boto3.client('ssm', region_name=region)
        
        # Critical metrics thresholds
        self.thresholds = {
            'api_response_time_ms': 500,  # API response time
            'api_error_rate_percent': 1,   # API error rate
            'ml_model_latency_ms': 2000,  # ML model inference time
            'sync_queue_size': 1000,       # Offline sync queue
            'biometric_match_failure_rate': 5,  # Biometric failures
            'healthlake_error_rate': 0.5,  # FHIR datastore errors
        }
    
    def create_cloudwatch_dashboard(self) -> bool:
        """Create comprehensive CloudWatch dashboard"""
        print("\n" + "="*60)
        print("Creating CloudWatch Dashboard")
        print("="*60)
        
        dashboard_name = f"HavenHealth-{self.environment}"
        
        dashboard_body = {
            "widgets": [
                # API Performance Widget
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            ["AWS/ApiGateway", "Count", {"stat": "Sum"}],
                            [".", "4XXError", {"stat": "Sum"}],
                            [".", "5XXError", {"stat": "Sum"}],
                            [".", "Latency", {"stat": "Average"}]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": self.region,
                        "title": "API Performance",
                        "yAxis": {"left": {"min": 0}}
                    }
                },
                # Patient Registration Rate
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            ["HavenHealth", "PatientRegistrations", 
                             {"stat": "Sum", "label": "New Registrations"}],
                            [".", "BiometricEnrollments", 
                             {"stat": "Sum", "label": "Biometric Enrollments"}]
                        ],
                        "period": 3600,
                        "stat": "Sum",
                        "region": self.region,
                        "title": "Patient Registration Activity"
                    }
                },
                # ML Model Performance
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            ["AWS/SageMaker", "ModelLatency", 
                             {"stat": "Average", "label": "Inference Latency"}],
                            [".", "Invocations", 
                             {"stat": "Sum", "label": "Total Invocations"}]
                        ],
                        "period": 300,
                        "region": self.region,
                        "title": "ML Model Performance"
                    }
                },
                # Critical Errors Log
                {
                    "type": "log",
                    "properties": {
                        "query": '''fields @timestamp, @message
                            | filter @message like /ERROR/
                            | filter @message like /patient|medical|health/
                            | sort @timestamp desc
                            | limit 20''',
                        "region": self.region,
                        "title": "Critical Patient Safety Errors"
                    }
                }
            ]
        }
        
        try:
            self.cloudwatch.put_dashboard(
                DashboardName=dashboard_name,
                DashboardBody=json.dumps(dashboard_body)
            )
            
            print(f"✅ Created dashboard: {dashboard_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create dashboard: {str(e)}")
            print("❌ Failed to create dashboard")
            return False
    
    def create_critical_alarms(self) -> bool:
        """Create critical alarms for patient safety"""
        print("\n" + "="*60)
        print("Creating Critical Alarms")
        print("="*60)
        
        # Get SNS topic ARN for critical alerts
        try:
            param_name = f"/haven-health/{self.environment}/sns/critical-alerts"
            response = self.ssm.get_parameter(Name=param_name)
            alert_topic_arn = response['Parameter']['Value']
        except:
            print("❌ Critical alerts SNS topic not found")
            return False
        
        alarms = [
            {
                'name': f'haven-health-{self.environment}-api-high-latency',
                'description': 'API response time exceeds safe threshold',
                'metric_name': 'Latency',
                'namespace': 'AWS/ApiGateway',
                'statistic': 'Average',
                'period': 300,
                'evaluation_periods': 2,
                'threshold': self.thresholds['api_response_time_ms'],
                'comparison': 'GreaterThanThreshold',
                'severity': 'CRITICAL'
            },
            {
                'name': f'haven-health-{self.environment}-api-errors',
                'description': 'High API error rate detected',
                'metric_name': '5XXError',
                'namespace': 'AWS/ApiGateway',
                'statistic': 'Sum',
                'period': 300,
                'evaluation_periods': 1,
                'threshold': 10,
                'comparison': 'GreaterThanThreshold',
                'severity': 'CRITICAL'
            },
            {
                'name': f'haven-health-{self.environment}-biometric-failures',
                'description': 'High biometric authentication failure rate',
                'metric_name': 'BiometricAuthFailures',
                'namespace': 'HavenHealth',
                'statistic': 'Average',
                'period': 300,
                'evaluation_periods': 2,
                'threshold': self.thresholds['biometric_match_failure_rate'],
                'comparison': 'GreaterThanThreshold',
                'severity': 'HIGH'
            },
            {
                'name': f'haven-health-{self.environment}-sync-queue-backlog',
                'description': 'Offline sync queue growing too large',
                'metric_name': 'SyncQueueSize',
                'namespace': 'HavenHealth',
                'statistic': 'Maximum',
                'period': 600,
                'evaluation_periods': 2,
                'threshold': self.thresholds['sync_queue_size'],
                'comparison': 'GreaterThanThreshold',
                'severity': 'HIGH'
            },
            {
                'name': f'haven-health-{self.environment}-healthlake-errors',
                'description': 'FHIR datastore experiencing errors',
                'metric_name': 'UserErrors',
                'namespace': 'AWS/HealthLake',
                'statistic': 'Sum',
                'period': 300,
                'evaluation_periods': 1,
                'threshold': 5,
                'comparison': 'GreaterThanThreshold',
                'severity': 'CRITICAL'
            }
        ]
        
        created = 0
        for alarm in alarms:
            try:
                self.cloudwatch.put_metric_alarm(
                    AlarmName=alarm['name'],
                    AlarmDescription=alarm['description'],
                    ActionsEnabled=True,
                    AlarmActions=[alert_topic_arn],
                    MetricName=alarm['metric_name'],
                    Namespace=alarm['namespace'],
                    Statistic=alarm['statistic'],
                    Period=alarm['period'],
                    EvaluationPeriods=alarm['evaluation_periods'],
                    Threshold=alarm['threshold'],
                    ComparisonOperator=alarm['comparison'],
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Severity', 'Value': alarm['severity']},
                        {'Key': 'Service', 'Value': 'haven-health-passport'}
                    ]
                )
                
                print(f"✅ Created alarm: {alarm['name']}")
                created += 1
                
            except Exception as e:
                logger.error(f"Failed to create alarm {alarm['name']}: {str(e)}")
                print(f"❌ Failed to create alarm: {alarm['name']}")
        
        print(f"\nCreated {created}/{len(alarms)} alarms")
        return created == len(alarms)
    
    def setup_log_groups(self) -> bool:
        """Setup CloudWatch log groups with retention policies"""
        print("\n" + "="*60)
        print("Setting up Log Groups")
        print("="*60)
        
        log_groups = [
            {
                'name': f'/aws/lambda/haven-health-{self.environment}-api',
                'retention_days': 30
            },
            {
                'name': f'/aws/lambda/haven-health-{self.environment}-patient-sync',
                'retention_days': 30
            },
            {
                'name': f'/aws/ecs/haven-health-{self.environment}',
                'retention_days': 30
            },
            {
                'name': f'/haven-health/{self.environment}/audit-logs',
                'retention_days': 2557  # 7 years for compliance
            },
            {
                'name': f'/haven-health/{self.environment}/patient-access-logs',
                'retention_days': 2557  # 7 years for HIPAA
            }
        ]
        
        created = 0
        for log_group in log_groups:
            try:
                # Create log group
                try:
                    self.logs.create_log_group(
                        logGroupName=log_group['name'],
                        tags={
                            'Environment': self.environment,
                            'Service': 'haven-health-passport'
                        }
                    )
                    print(f"✅ Created log group: {log_group['name']}")
                except self.logs.exceptions.ResourceAlreadyExistsException:
                    print(f"✓ Log group exists: {log_group['name']}")
                
                # Set retention policy
                self.logs.put_retention_policy(
                    logGroupName=log_group['name'],
                    retentionInDays=log_group['retention_days']
                )
                
                created += 1
                
            except Exception as e:
                logger.error(f"Failed to setup log group {log_group['name']}: {str(e)}")
                print(f"❌ Failed to setup: {log_group['name']}")
        
        return created == len(log_groups)
    
    def setup_custom_metrics(self) -> bool:
        """Setup custom application metrics"""
        print("\n" + "="*60)
        print("Setting up Custom Metrics")
        print("="*60)
        
        # Create metric filters for critical events
        metric_filters = [
            {
                'log_group': f'/haven-health/{self.environment}/audit-logs',
                'filter_name': 'PatientDataAccessDenied',
                'filter_pattern': '[timestamp, request_id, event_type=ACCESS_DENIED, ...]',
                'metric_name': 'PatientDataAccessDenied',
                'metric_namespace': 'HavenHealth',
                'metric_value': '1'
            },
            {
                'log_group': f'/haven-health/{self.environment}/audit-logs',
                'filter_name': 'BiometricEnrollmentFailure',
                'filter_pattern': '[timestamp, request_id, event_type=BIOMETRIC_ENROLLMENT_FAILED, ...]',
                'metric_name': 'BiometricEnrollmentFailures',
                'metric_namespace': 'HavenHealth',
                'metric_value': '1'
            },
            {
                'log_group': f'/aws/lambda/haven-health-{self.environment}-api',
                'filter_name': 'MedicalDataError',
                'filter_pattern': '[timestamp, request_id, level=ERROR, message="*medical*" || message="*patient*"]',
                'metric_name': 'MedicalDataErrors',
                'metric_namespace': 'HavenHealth',
                'metric_value': '1'
            }
        ]
        
        created = 0
        for mf in metric_filters:
            try:
                self.logs.put_metric_filter(
                    logGroupName=mf['log_group'],
                    filterName=mf['filter_name'],
                    filterPattern=mf['filter_pattern'],
                    metricTransformations=[{
                        'metricName': mf['metric_name'],
                        'metricNamespace': mf['metric_namespace'],
                        'metricValue': mf['metric_value'],
                        'defaultValue': 0.0
                    }]
                )
                
                print(f"✅ Created metric filter: {mf['filter_name']}")
                created += 1
                
            except Exception as e:
                logger.error(f"Failed to create metric filter {mf['filter_name']}: {str(e)}")
                print(f"❌ Failed to create: {mf['filter_name']}")
        
        return created == len(metric_filters)
    
    def setup_all_monitoring(self) -> None:
        """Setup all monitoring components"""
        print("\n" + "="*80)
        print("Haven Health Passport - Monitoring Setup")
        print(f"Environment: {self.environment.upper()}")
        print(f"Region: {self.region}")
        print("="*80)
        print("\n⚠️  CRITICAL: Proper monitoring ensures patient safety.")
        print("All critical events must be tracked and alerted.\n")
        
        results = {
            'CloudWatch Dashboard': self.create_cloudwatch_dashboard(),
            'Critical Alarms': self.create_critical_alarms(),
            'Log Groups': self.setup_log_groups(),
            'Custom Metrics': self.setup_custom_metrics()
        }
        
        # Summary
        print("\n" + "="*80)
        print("Monitoring Setup Summary")
        print("="*80)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        for component, success in results.items():
            status = "✅ Configured" if success else "❌ Failed"
            print(f"{component}: {status}")
        
        print(f"\nTotal: {success_count}/{total_count} components configured")
        
        if success_count == total_count:
            print("\n✅ All monitoring components configured successfully!")
            print("\nNext steps:")
            print("1. Verify alarms are triggering correctly")
            print("2. Set up PagerDuty or other incident management")
            print("3. Configure log analysis and anomaly detection")
            print("4. Create runbooks for each alarm type")
            print("\nDashboard URL:")
            print(f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={f'HavenHealth-{self.environment}'}")
        else:
            print("\n⚠️  WARNING: Some monitoring components failed!")
            print("System issues may go undetected without proper monitoring.")
    
    def create_ops_runbook(self) -> None:
        """Create operational runbook for common issues"""
        runbook = f"""
# Haven Health Passport - Operational Runbook
Environment: {self.environment}
Generated: {datetime.utcnow().isoformat()}

## Critical Alarms Response Procedures

### 1. API High Latency Alert
**Severity**: CRITICAL
**Impact**: Refugees may experience delays accessing health records
**Response**:
1. Check API Gateway metrics for error spikes
2. Verify backend services are healthy
3. Check database connection pool
4. Scale up if needed
5. Notify on-call physician if delays exceed 5 minutes

### 2. Biometric Authentication Failures
**Severity**: HIGH
**Impact**: Patients unable to access their records
**Response**:
1. Check Rekognition service status
2. Verify biometric SDK configuration
3. Enable fallback authentication
4. Monitor for potential security issues

### 3. Sync Queue Backlog
**Severity**: HIGH
**Impact**: Offline data not syncing, potential data loss
**Response**:
1. Check network connectivity in affected regions
2. Verify API throttling limits
3. Increase sync worker capacity
4. Prioritize critical medical data

### 4. HealthLake FHIR Errors
**Severity**: CRITICAL
**Impact**: Medical records unavailable
**Response**:
1. Check HealthLake service status
2. Verify FHIR resource formatting
3. Enable read replica if available
4. Activate contingency data access

## Contact Information
- On-call Engineer: Check PagerDuty
- Medical Director: Via secure channel
- AWS Support: Premium support ticket

## Compliance Note
All incidents must be logged for HIPAA compliance.
Patient data access during incidents must be audited.
"""
        
        with open(f'haven-health-runbook-{self.environment}.md', 'w') as f:
            f.write(runbook)
        
        print(f"\n📚 Operational runbook created: haven-health-runbook-{self.environment}.md")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Setup monitoring for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Target environment'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--create-runbook',
        action='store_true',
        help='Create operational runbook'
    )
    
    args = parser.parse_args()
    
    # Production safety check
    if args.environment == 'production':
        print("\n⚠️  WARNING: Setting up PRODUCTION monitoring!")
        print("This will create alarms that may trigger pages.")
        confirm = input("Type 'SETUP PRODUCTION' to continue: ")
        if confirm != 'SETUP PRODUCTION':
            print("Setup cancelled.")
            sys.exit(0)
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"\n❌ AWS credentials not configured: {str(e)}")
        sys.exit(1)
    
    # Run setup
    setup = MonitoringSetup(args.environment, args.region)
    setup.setup_all_monitoring()
    
    if args.create_runbook:
        setup.create_ops_runbook()


if __name__ == '__main__':
    main()
