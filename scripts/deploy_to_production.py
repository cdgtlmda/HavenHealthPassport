#!/usr/bin/env python3
"""
Master Deployment Script for Haven Health Passport
Orchestrates the complete deployment process for production
CRITICAL: This deploys a healthcare system for real refugees
"""

import os
import sys
import subprocess
import json
import argparse
import logging
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MasterDeployer:
    """Orchestrates the complete deployment process"""
    
    def __init__(self, environment: str, skip_confirmations: bool = False):
        self.environment = environment
        self.skip_confirmations = skip_confirmations
        self.deployment_log = []
        self.critical_errors = []
        
    def run_script(self, script_name: str, args: List[str] = []) -> bool:
        """Run a deployment script and capture results"""
        print(f"\n{'='*80}")
        print(f"Running: {script_name}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        try:
            cmd = ['python3', f'scripts/{script_name}', '--environment', self.environment]
            cmd.extend(args)
            
            if self.skip_confirmations and '--skip-confirmation' not in cmd:
                # Check if script supports skip-confirmation
                if script_name in ['run_integration_tests.py']:
                    cmd.append('--skip-confirmation')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = time.time() - start_time
            
            self.deployment_log.append({
                'script': script_name,
                'status': 'SUCCESS',
                'duration': duration,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            print(f"\n✅ {script_name} completed successfully ({duration:.2f}s)")
            return True
            
        except subprocess.CalledProcessError as e:
            duration = time.time() - start_time
            
            self.deployment_log.append({
                'script': script_name,
                'status': 'FAILED',
                'duration': duration,
                'error': e.stderr,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            self.critical_errors.append(f"{script_name}: {e.stderr[:200]}")
            
            print(f"\n❌ {script_name} failed ({duration:.2f}s)")
            print(f"Error: {e.stderr[:500]}")
            return False
    
    def phase1_infrastructure(self) -> bool:
        """Phase 1: Provision AWS Infrastructure"""
        print("\n" + "="*80)
        print("PHASE 1: Infrastructure Provisioning")
        print("="*80)
        
        scripts = [
            ('provision_aws_infrastructure.py', []),
            ('setup_monitoring.py', ['--create-runbook'])
        ]
        
        for script, args in scripts:
            if not self.run_script(script, args):
                return False
        
        return True
    
    def phase2_configuration(self) -> bool:
        """Phase 2: Configure External Services"""
        print("\n" + "="*80)
        print("PHASE 2: Service Configuration")
        print("="*80)
        
        scripts = [
            ('setup_medical_apis.py', []),
            ('setup_biometric_sdks.py', []),
            ('configure_communication_services.py', [])
        ]
        
        for script, args in scripts:
            if not self.run_script(script, args):
                # Medical APIs are critical
                if script == 'setup_medical_apis.py':
                    print("\n🚨 CRITICAL: Medical APIs must be configured!")
                    return False
                # Others can be configured later
                print(f"\n⚠️  Warning: {script} failed but continuing...")
        
        return True
    
    def phase3_ml_deployment(self) -> bool:
        """Phase 3: Deploy ML Models"""
        print("\n" + "="*80)
        print("PHASE 3: ML Model Deployment")
        print("="*80)
        
        return self.run_script('deploy_ml_models.py', [])
    
    def phase4_testing(self) -> bool:
        """Phase 4: Integration Testing"""
        print("\n" + "="*80)
        print("PHASE 4: Integration Testing")
        print("="*80)
        
        if not self.run_script('run_integration_tests.py', ['--skip-confirmation']):
            print("\n🚨 CRITICAL: Integration tests failed!")
            print("System is not ready for production!")
            return False
        
        return True
    
    def phase5_validation(self) -> bool:
        """Phase 5: Final Validation"""
        print("\n" + "="*80)
        print("PHASE 5: Final Validation")
        print("="*80)
        
        # Run production validation script if it exists
        if os.path.exists('scripts/validate_production.py'):
            return self.run_script('validate_production.py', [])
        
        print("✓ Skipping validation script (not found)")
        return True
    
    def generate_deployment_report(self) -> str:
        """Generate comprehensive deployment report"""
        report = {
            'deployment_id': f"deploy-{self.environment}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            'environment': self.environment,
            'start_time': self.deployment_log[0]['timestamp'] if self.deployment_log else None,
            'end_time': datetime.utcnow().isoformat(),
            'total_duration': sum(log['duration'] for log in self.deployment_log),
            'phases_completed': [],
            'phases_failed': [],
            'critical_errors': self.critical_errors,
            'deployment_log': self.deployment_log,
            'ready_for_production': len(self.critical_errors) == 0
        }
        
        # Analyze phases
        phase_status = {
            'infrastructure': any(log['script'].startswith('provision') and log['status'] == 'SUCCESS' 
                                for log in self.deployment_log),
            'configuration': any(log['script'].startswith('setup') and log['status'] == 'SUCCESS' 
                               for log in self.deployment_log),
            'ml_models': any(log['script'] == 'deploy_ml_models.py' and log['status'] == 'SUCCESS' 
                           for log in self.deployment_log),
            'testing': any(log['script'] == 'run_integration_tests.py' and log['status'] == 'SUCCESS' 
                         for log in self.deployment_log),
            'validation': any(log['script'] == 'validate_production.py' and log['status'] == 'SUCCESS' 
                            for log in self.deployment_log)
        }
        
        report['phases_completed'] = [phase for phase, success in phase_status.items() if success]
        report['phases_failed'] = [phase for phase, success in phase_status.items() if not success]
        
        # Save report
        report_path = f"deployment_report_{self.environment}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report_path
    
    def deploy_all(self) -> bool:
        """Execute complete deployment process"""
        print("\n" + "="*80)
        print("Haven Health Passport - Master Deployment")
        print(f"Environment: {self.environment.upper()}")
        print(f"Started: {datetime.utcnow().isoformat()}")
        print("="*80)
        print("\n⚠️  CRITICAL: This deploys a healthcare system for refugees.")
        print("Any errors could impact patient care and safety.\n")
        
        # Confirm deployment
        if not self.skip_confirmations and self.environment == 'production':
            print("You are about to deploy to PRODUCTION!")
            print("This will:")
            print("- Provision AWS infrastructure (costs will be incurred)")
            print("- Deploy ML models for medical predictions")
            print("- Configure biometric authentication")
            print("- Enable real patient data processing")
            print("\nThis process will take approximately 30-45 minutes.")
            
            confirm = input("\nType 'DEPLOY TO PRODUCTION' to continue: ")
            if confirm != 'DEPLOY TO PRODUCTION':
                print("Deployment cancelled.")
                return False
        
        # Execute deployment phases
        phases = [
            (self.phase1_infrastructure, "Infrastructure Provisioning"),
            (self.phase2_configuration, "Service Configuration"),
            (self.phase3_ml_deployment, "ML Model Deployment"),
            (self.phase4_testing, "Integration Testing"),
            (self.phase5_validation, "Final Validation")
        ]
        
        for phase_func, phase_name in phases:
            print(f"\n{'*'*80}")
            print(f"Starting: {phase_name}")
            print(f"{'*'*80}")
            
            if not phase_func():
                print(f"\n🚨 Deployment failed during: {phase_name}")
                break
        
        # Generate report
        report_path = self.generate_deployment_report()
        
        # Final summary
        print("\n" + "="*80)
        print("Deployment Summary")
        print("="*80)
        
        if len(self.critical_errors) == 0:
            print("\n✅ DEPLOYMENT SUCCESSFUL!")
            print(f"\nEnvironment {self.environment} is ready for use.")
            print("\nIMPORTANT NEXT STEPS:")
            print("1. Review deployment report:", report_path)
            print("2. Perform smoke tests with test patient data")
            print("3. Brief medical staff on system usage")
            print("4. Monitor system closely for first 48 hours")
            print("5. Have incident response team on standby")
            
            if self.environment == 'production':
                print("\n🏥 PRODUCTION CHECKLIST:")
                print("[ ] Medical director approval obtained")
                print("[ ] Data privacy officer signed off")
                print("[ ] Emergency rollback plan ready")
                print("[ ] Support team briefed")
                print("[ ] Patient notification sent (if applicable)")
        else:
            print("\n❌ DEPLOYMENT FAILED!")
            print(f"\n{len(self.critical_errors)} critical errors occurred:")
            for error in self.critical_errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            
            print(f"\nFull details in report: {report_path}")
            print("\n⚠️  DO NOT USE THIS ENVIRONMENT FOR PATIENT DATA!")
            
        return len(self.critical_errors) == 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Master deployment script for Haven Health Passport'
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        required=True,
        help='Target environment for deployment'
    )
    parser.add_argument(
        '--skip-confirmations',
        action='store_true',
        help='Skip all confirmation prompts (dangerous!)'
    )
    parser.add_argument(
        '--phases',
        nargs='+',
        choices=['infrastructure', 'configuration', 'ml', 'testing', 'validation'],
        help='Run only specific phases'
    )
    
    args = parser.parse_args()
    
    # Safety check
    if args.environment == 'production' and args.skip_confirmations:
        print("\n⚠️  WARNING: Skipping confirmations for PRODUCTION deployment!")
        print("This is extremely dangerous!")
        time.sleep(3)  # Give time to cancel
    
    # Check prerequisites
    print("Checking prerequisites...")
    
    # Check AWS credentials
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ AWS Account: {identity['Account']}")
        print(f"✅ AWS User: {identity['Arn']}")
    except Exception as e:
        print(f"❌ AWS credentials not configured: {str(e)}")
        print("\nPlease run: aws configure")
        sys.exit(1)
    
    # Check required scripts exist
    required_scripts = [
        'provision_aws_infrastructure.py',
        'setup_medical_apis.py',
        'setup_biometric_sdks.py',
        'deploy_ml_models.py',
        'configure_communication_services.py',
        'run_integration_tests.py',
        'setup_monitoring.py'
    ]
    
    missing_scripts = []
    for script in required_scripts:
        if not os.path.exists(f'scripts/{script}'):
            missing_scripts.append(script)
    
    if missing_scripts:
        print("\n❌ Missing required scripts:")
        for script in missing_scripts:
            print(f"  - scripts/{script}")
        print("\nPlease ensure all deployment scripts are present.")
        sys.exit(1)
    
    print("✅ All required scripts found")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python {sys.version_info.major}.{sys.version_info.minor} detected")
        print("Python 3.8+ is required")
        sys.exit(1)
    
    print("✅ Python version compatible")
    
    # Run deployment
    deployer = MasterDeployer(
        environment=args.environment,
        skip_confirmations=args.skip_confirmations
    )
    
    success = deployer.deploy_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
