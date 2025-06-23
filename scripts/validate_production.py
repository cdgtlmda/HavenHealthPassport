#!/usr/bin/env python3
"""
Production Validation Script for Haven Health Passport
Validates that all production systems are properly configured
CRITICAL: This is the final check before serving real patients
"""

import os
import sys
import json
import boto3
import requests
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionValidator:
    """Validates production readiness of Haven Health Passport"""
    
    def __init__(self, environment: str):
        if environment != 'production':
            logger.warning(f"Running production validation on {environment} environment")
        
        self.environment = environment
        self.validation_results = {}
        self.critical_issues = []
        
        # Initialize AWS clients
        self.secrets_client = boto3.client('secretsmanager')
        self.ssm_client = boto3.client('ssm')
        self.s3_client = boto3.client('s3')
        self.cloudwatch_client = boto3.client('cloudwatch')
        self.healthlake_client = boto3.client('healthlake')
        
    def validate_medical_apis(self) -> Tuple[bool, List[str]]:
        """Validate all medical APIs are properly configured"""
        print("\nValidating Medical APIs...")
        issues = []
        
        required_apis = [
            'rxnorm',
            'drugbank', 
            'clinical_guidelines',
            'medical_terminology'
        ]
        
        for api_name in required_apis:
            try:
                secret_name = f"haven-health-passport/{self.environment}/apis/{api_name}"
                secret = self.secrets_client.get_secret_value(SecretId=secret_name)
                config = json.loads(secret['SecretString'])
                
                # Check if credentials exist and are recent
                if 'configured_at' in config:
                    config_date = datetime.fromisoformat(config['configured_at'].replace('Z', '+00:00'))
                    days_old = (datetime.utcnow() - config_date.replace(tzinfo=None)).days
                    
                    if days_old > 365:
                        issues.append(f"{api_name} credentials are {days_old} days old - may need renewal")
                    else:
                        print(f"  ✅ {api_name}: Configured {days_old} days ago")
                else:
                    issues.append(f"{api_name} missing configuration timestamp")
                    
            except Exception as e:
                issues.append(f"{api_name} not configured: {str(e)}")
                self.critical_issues.append(f"Medical API {api_name} not available")
        
        return len(issues) == 0, issues
    
    def validate_security_configuration(self) -> Tuple[bool, List[str]]:
        """Validate security settings are production-ready"""
        print("\nValidating Security Configuration...")
        issues = []
        
        # Check encryption keys
        try:
            # Verify KMS keys exist
            kms_client = boto3.client('kms')
            
            # Check for patient data encryption key
            aliases = kms_client.list_aliases()
            required_aliases = [
                f'alias/haven-health-{self.environment}-patient-data',
                f'alias/haven-health-{self.environment}-backup'
            ]
            
            existing_aliases = [alias['AliasName'] for alias in aliases['Aliases']]
            
            for required_alias in required_aliases:
                if required_alias not in existing_aliases:
                    issues.append(f"KMS key missing: {required_alias}")
                else:
                    print(f"  ✅ KMS key found: {required_alias}")
                    
        except Exception as e:
            issues.append(f"Failed to check KMS keys: {str(e)}")
        
        # Check SSL certificates
        try:
            # Verify SES domain verification
            ses_client = boto3.client('ses')
            verified_domains = ses_client.list_verified_email_addresses()
            
            if len(verified_domains['VerifiedEmailAddresses']) == 0:
                issues.append("No verified email addresses for SES")
            else:
                print(f"  ✅ SES domains verified: {len(verified_domains['VerifiedEmailAddresses'])}")
                
        except Exception as e:
            issues.append(f"Failed to check SES configuration: {str(e)}")
        
        # Check CloudHSM status (if configured)
        try:
            cloudhsm_client = boto3.client('cloudhsmv2')
            clusters = cloudhsm_client.describe_clusters()
            
            active_clusters = [c for c in clusters['Clusters'] 
                             if c['State'] == 'ACTIVE' and 
                             f'haven-health-{self.environment}' in str(c.get('TagList', []))]
            
            if active_clusters:
                print(f"  ✅ CloudHSM cluster active: {active_clusters[0]['ClusterId']}")
            else:
                print("  ℹ️  No active CloudHSM cluster (optional)")
                
        except Exception as e:
            logger.debug(f"CloudHSM check failed (optional): {str(e)}")
        
        return len(issues) == 0, issues
    
    def validate_data_storage(self) -> Tuple[bool, List[str]]:
        """Validate data storage is properly configured"""
        print("\nValidating Data Storage...")
        issues = []
        
        # Check S3 buckets
        required_buckets = [
            f'haven-health-{self.environment}-medical-records',
            f'haven-health-{self.environment}-documents',
            f'haven-health-{self.environment}-backups',
            f'haven-health-{self.environment}-audit-logs'
        ]
        
        for bucket in required_buckets:
            try:
                # Check bucket exists and has proper encryption
                encryption = self.s3_client.get_bucket_encryption(Bucket=bucket)
                
                if 'Rules' in encryption['ServerSideEncryptionConfiguration']:
                    print(f"  ✅ S3 bucket {bucket}: Encrypted")
                else:
                    issues.append(f"Bucket {bucket} not encrypted")
                    
                # Check versioning
                versioning = self.s3_client.get_bucket_versioning(Bucket=bucket)
                if versioning.get('Status') != 'Enabled':
                    issues.append(f"Bucket {bucket} versioning not enabled")
                    
            except Exception as e:
                issues.append(f"Bucket {bucket} check failed: {str(e)}")
                if 'medical-records' in bucket or 'audit-logs' in bucket:
                    self.critical_issues.append(f"Critical bucket {bucket} not accessible")
        
        # Check HealthLake FHIR datastore
        try:
            param_name = f"/haven-health/{self.environment}/healthlake/datastore-id"
            response = self.ssm_client.get_parameter(Name=param_name)
            datastore_id = response['Parameter']['Value']
            
            datastore = self.healthlake_client.describe_fhir_datastore(
                DatastoreId=datastore_id
            )
            
            status = datastore['DatastoreProperties']['DatastoreStatus']
            if status == 'ACTIVE':
                print(f"  ✅ HealthLake FHIR datastore: Active")
            else:
                issues.append(f"HealthLake datastore status: {status}")
                self.critical_issues.append("FHIR datastore not active")
                
        except Exception as e:
            issues.append(f"HealthLake validation failed: {str(e)}")
            self.critical_issues.append("FHIR datastore not configured")
        
        return len(issues) == 0, issues
    
    def validate_ml_models(self) -> Tuple[bool, List[str]]:
        """Validate ML models are deployed and responding"""
        print("\nValidating ML Models...")
        issues = []
        
        required_models = [
            'risk-prediction',
            'treatment-recommendation',
            'pubmedbert',
            'bioclinicalbert'
        ]
        
        sagemaker_runtime = boto3.client('sagemaker-runtime')
        
        for model_key in required_models:
            try:
                param_name = f"/haven-health/{self.environment}/ml/endpoints/{model_key}"
                response = self.ssm_client.get_parameter(Name=param_name)
                endpoint_name = response['Parameter']['Value']
                
                # Test with minimal payload
                test_payload = {
                    'test': True,
                    'validation': 'production-check'
                }
                
                response = sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType='application/json',
                    Body=json.dumps(test_payload)
                )
                
                if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                    print(f"  ✅ ML Model {model_key}: Responding")
                else:
                    issues.append(f"Model {model_key} returned status {response['ResponseMetadata']['HTTPStatusCode']}")
                    
            except Exception as e:
                issues.append(f"Model {model_key} validation failed: {str(e)}")
                if model_key == 'risk-prediction':
                    self.critical_issues.append("Risk prediction model not available")
        
        return len(issues) == 0, issues
    
    def validate_monitoring(self) -> Tuple[bool, List[str]]:
        """Validate monitoring and alerting is configured"""
        print("\nValidating Monitoring Setup...")
        issues = []
        
        # Check CloudWatch alarms
        critical_alarms = [
            f'haven-health-{self.environment}-api-high-latency',
            f'haven-health-{self.environment}-api-errors',
            f'haven-health-{self.environment}-healthlake-errors'
        ]
        
        alarms = self.cloudwatch_client.describe_alarms(
            AlarmNamePrefix=f'haven-health-{self.environment}'
        )
        
        existing_alarms = [alarm['AlarmName'] for alarm in alarms['MetricAlarms']]
        
        for alarm_name in critical_alarms:
            if alarm_name in existing_alarms:
                alarm = next(a for a in alarms['MetricAlarms'] if a['AlarmName'] == alarm_name)
                if alarm['ActionsEnabled']:
                    print(f"  ✅ Alarm active: {alarm_name}")
                else:
                    issues.append(f"Alarm {alarm_name} actions disabled")
            else:
                issues.append(f"Critical alarm missing: {alarm_name}")
                self.critical_issues.append(f"Monitoring alarm {alarm_name} not configured")
        
        # Check log groups
        logs_client = boto3.client('logs')
        critical_log_groups = [
            f'/haven-health/{self.environment}/audit-logs',
            f'/haven-health/{self.environment}/patient-access-logs'
        ]
        
        for log_group in critical_log_groups:
            try:
                response = logs_client.describe_log_groups(
                    logGroupNamePrefix=log_group
                )
                
                if response['logGroups']:
                    retention = response['logGroups'][0].get('retentionInDays', 0)
                    if retention < 2557:  # 7 years for HIPAA
                        issues.append(f"Log group {log_group} retention too short: {retention} days")
                    else:
                        print(f"  ✅ Log group {log_group}: {retention} day retention")
                else:
                    issues.append(f"Log group {log_group} not found")
                    
            except Exception as e:
                issues.append(f"Log group {log_group} check failed: {str(e)}")
        
        return len(issues) == 0, issues
    
    def validate_compliance_requirements(self) -> Tuple[bool, List[str]]:
        """Validate HIPAA and GDPR compliance configurations"""
        print("\nValidating Compliance Requirements...")
        issues = []
        
        # Check backup configuration
        try:
            backup_client = boto3.client('backup')
            plans = backup_client.list_backup_plans()
            
            haven_plans = [p for p in plans['BackupPlansList'] 
                          if f'haven-health-{self.environment}' in p['BackupPlanName'].lower()]
            
            if haven_plans:
                print(f"  ✅ Backup plan configured: {haven_plans[0]['BackupPlanName']}")
            else:
                issues.append("No backup plan configured for disaster recovery")
                
        except Exception as e:
            logger.debug(f"Backup plan check failed: {str(e)}")
            issues.append("Backup configuration not verified")
        
        # Check audit trail configuration
        try:
            # Verify audit log bucket has proper lifecycle
            bucket_name = f'haven-health-{self.environment}-audit-logs'
            lifecycle = self.s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            
            if 'Rules' in lifecycle:
                print(f"  ✅ Audit log lifecycle configured: {len(lifecycle['Rules'])} rules")
            else:
                issues.append("Audit log bucket missing lifecycle policy")
                
        except Exception as e:
            if 'NoSuchLifecycleConfiguration' not in str(e):
                issues.append(f"Audit log lifecycle check failed: {str(e)}")
        
        return len(issues) == 0, issues
    
    def validate_all(self) -> bool:
        """Run all validation checks"""
        print("\n" + "="*80)
        print("Haven Health Passport - Production Validation")
        print(f"Environment: {self.environment.upper()}")
        print(f"Validation Time: {datetime.utcnow().isoformat()}")
        print("="*80)
        
        if self.environment != 'production':
            print(f"\n⚠️  WARNING: Running production validation on {self.environment}")
            print("Some checks may not be applicable.\n")
        
        # Run all validation checks
        validations = [
            ('Medical APIs', self.validate_medical_apis),
            ('Security Configuration', self.validate_security_configuration),
            ('Data Storage', self.validate_data_storage),
            ('ML Models', self.validate_ml_models),
            ('Monitoring', self.validate_monitoring),
            ('Compliance Requirements', self.validate_compliance_requirements)
        ]
        
        all_passed = True
        
        for name, validation_func in validations:
            try:
                passed, issues = validation_func()
                self.validation_results[name] = {
                    'passed': passed,
                    'issues': issues
                }
                
                if not passed:
                    all_passed = False
                    print(f"\n❌ {name}: FAILED")
                    for issue in issues:
                        print(f"    - {issue}")
                else:
                    print(f"\n✅ {name}: PASSED")
                    
            except Exception as e:
                logger.error(f"Validation {name} crashed: {str(e)}")
                self.validation_results[name] = {
                    'passed': False,
                    'issues': [f"Validation crashed: {str(e)}"]
                }
                all_passed = False
        
        # Generate report
        self.generate_validation_report(all_passed)
        
        return all_passed and len(self.critical_issues) == 0
    
    def generate_validation_report(self, all_passed: bool) -> None:
        """Generate detailed validation report"""
        print("\n" + "="*80)
        print("Validation Summary")
        print("="*80)
        
        # Count results
        total_checks = len(self.validation_results)
        passed_checks = sum(1 for r in self.validation_results.values() if r['passed'])
        total_issues = sum(len(r['issues']) for r in self.validation_results.values())
        
        print(f"\nValidation Checks: {passed_checks}/{total_checks} passed")
        print(f"Total Issues Found: {total_issues}")
        print(f"Critical Issues: {len(self.critical_issues)}")
        
        if self.critical_issues:
            print("\n🚨 CRITICAL ISSUES THAT BLOCK PRODUCTION:")
            for issue in self.critical_issues:
                print(f"  - {issue}")
        
        # Determine production readiness
        production_ready = all_passed and len(self.critical_issues) == 0
        
        if production_ready:
            print("\n✅ SYSTEM IS READY FOR PRODUCTION!")
            print("\nPre-launch checklist:")
            print("  □ Medical director sign-off obtained")
            print("  □ Security audit completed")
            print("  □ Disaster recovery plan tested")
            print("  □ Support team trained")
            print("  □ Patient communication prepared")
        else:
            print("\n❌ SYSTEM IS NOT READY FOR PRODUCTION!")
            print("\nAddress all issues before deploying to production.")
            print("Patient safety depends on proper system configuration.")
        
        # Save detailed report
        report = {
            'validation_id': f"validation-{self.environment}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            'environment': self.environment,
            'validation_time': datetime.utcnow().isoformat(),
            'production_ready': production_ready,
            'summary': {
                'total_checks': total_checks,
                'passed_checks': passed_checks,
                'total_issues': total_issues,
                'critical_issues': len(self.critical_issues)
            },
            'validation_results': self.validation_results,
            'critical_issues': self.critical_issues
        }
        
        report_path = f"production_validation_{self.environment}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nDetailed report saved: {report_path}")
        
        # Create human-readable summary
        summary_path = report_path.replace('.json', '_summary.txt')
        with open(summary_path, 'w') as f:
            f.write(f"Haven Health Passport - Production Validation Summary\n")
            f.write(f"{'='*60}\n")
            f.write(f"Environment: {self.environment}\n")
            f.write(f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
            f.write(f"Production Ready: {'YES' if production_ready else 'NO'}\n\n")
            
            if not production_ready:
                f.write("Issues to Address:\n")
                for category, result in self.validation_results.items():
                    if not result['passed']:
                        f.write(f"\n{category}:\n")
                        for issue in result['issues']:
                            f.write(f"  - {issue}\n")
            
            if self.critical_issues:
                f.write(f"\nCritical Issues:\n")
                for issue in self.critical_issues:
                    f.write(f"  🚨 {issue}\n")
        
        print(f"Summary report saved: {summary_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Validate Haven Health Passport production readiness'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        default='production',
        help='Environment to validate (default: production)'
    )
    
    args = parser.parse_args()
    
    # Check AWS credentials
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS Account: {identity['Account']}")
    except Exception as e:
        print(f"❌ AWS credentials not configured: {str(e)}")
        sys.exit(1)
    
    # Run validation
    validator = ProductionValidator(args.environment)
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
