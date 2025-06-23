#!/usr/bin/env python3
"""
AWS Deployment Status Checker for Haven Health Passport.

This script checks the status of all required AWS services without
making any changes. It's designed for CI/CD and automated monitoring.

CRITICAL: This healthcare project requires all services to be properly configured.
"""

import os
import sys
import json
import boto3
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logging import get_logger
from src.core.config import AWSConfig

logger = get_logger(__name__)


class AWSDeploymentChecker:
    """Check deployment status of AWS services."""
    
    def __init__(self):
        """Initialize the deployment checker."""
        self.aws_config = AWSConfig()
        self.status = {}
        self.issues = []
    
    def check_all_services(self) -> Tuple[bool, Dict[str, bool], List[str]]:
        """
        Check all required AWS services.
        
        Returns:
            Tuple of (all_healthy, service_status, issues)
        """
        logger.info("=" * 80)
        logger.info("HAVEN HEALTH PASSPORT - AWS DEPLOYMENT STATUS CHECK")
        logger.info("=" * 80)
        
        # Check each service group
        self.status['s3'] = self._check_s3()
        self.status['dynamodb'] = self._check_dynamodb()
        self.status['sns'] = self._check_sns()
        self.status['bedrock'] = self._check_bedrock()
        self.status['healthlake'] = self._check_healthlake()
        self.status['sagemaker'] = self._check_sagemaker()
        self.status['blockchain'] = self._check_blockchain()
        
        # Overall health
        all_healthy = all(self.status.values())
        
        return all_healthy, self.status, self.issues
    
    def _check_s3(self) -> bool:
        """Check S3 bucket configuration."""
        try:
            s3 = boto3.client('s3', **self.aws_config.get_boto3_kwargs('s3'))
            
            # Check main bucket
            bucket_name = self.aws_config.s3_bucket_name
            
            # Check if bucket exists
            s3.head_bucket(Bucket=bucket_name)
            
            # Check encryption
            encryption = s3.get_bucket_encryption(Bucket=bucket_name)
            if not encryption.get('ServerSideEncryptionConfiguration'):
                self.issues.append(f"S3 bucket {bucket_name} is not encrypted")
                return False
            
            # Check versioning
            versioning = s3.get_bucket_versioning(Bucket=bucket_name)
            if versioning.get('Status') != 'Enabled':
                self.issues.append(f"S3 bucket {bucket_name} versioning is not enabled")
                # This is a warning, not a failure
            
            logger.info("✓ S3 bucket configured correctly")
            return True
            
        except Exception as e:
            self.issues.append(f"S3 check failed: {str(e)}")
            logger.error(f"✗ S3 check failed: {e}")
            return False
    
    def _check_dynamodb(self) -> bool:
        """Check DynamoDB tables."""
        try:
            dynamodb = boto3.client('dynamodb', **self.aws_config.get_boto3_kwargs('dynamodb'))
            
            required_tables = [
                'model_configs',
                'translation_corrections',
                'translation_metrics',
                'translation_feedback'
            ]
            
            # List existing tables
            response = dynamodb.list_tables()
            existing_tables = response.get('TableNames', [])
            
            missing_tables = []
            for table in required_tables:
                full_name = f"{self.aws_config.dynamodb_table_prefix}{table}"
                if full_name not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                self.issues.append(f"Missing DynamoDB tables: {', '.join(missing_tables)}")
                logger.error(f"✗ Missing DynamoDB tables: {missing_tables}")
                return False
            
            logger.info("✓ All DynamoDB tables exist")
            return True
            
        except Exception as e:
            self.issues.append(f"DynamoDB check failed: {str(e)}")
            logger.error(f"✗ DynamoDB check failed: {e}")
            return False
    
    def _check_sns(self) -> bool:
        """Check SNS topics."""
        try:
            sns = boto3.client('sns', **self.aws_config.get_boto3_kwargs('sns'))
            
            required_topics = [
                'translation-alerts',
                'quality-notifications',
                'system-alerts'
            ]
            
            # List topics
            response = sns.list_topics()
            existing_topics = [t['TopicArn'].split(':')[-1] for t in response.get('Topics', [])]
            
            missing_topics = []
            for topic in required_topics:
                full_name = f"haven-health-{topic}"
                if not any(full_name in t for t in existing_topics):
                    missing_topics.append(topic)
            
            if missing_topics:
                self.issues.append(f"Missing SNS topics: {', '.join(missing_topics)}")
                logger.error(f"✗ Missing SNS topics: {missing_topics}")
                return False
            
            logger.info("✓ All SNS topics configured")
            return True
            
        except Exception as e:
            self.issues.append(f"SNS check failed: {str(e)}")
            logger.error(f"✗ SNS check failed: {e}")
            return False
    
    def _check_bedrock(self) -> bool:
        """Check Bedrock configuration."""
        try:
            bedrock = boto3.client(
                'bedrock',
                region_name=self.aws_config.bedrock_region,
                **self.aws_config.get_boto3_kwargs('bedrock')
            )
            
            # List foundation models
            response = bedrock.list_foundation_models()
            models = response.get('modelSummaries', [])
            
            # Check for required models
            required_models = [
                'anthropic.claude',
                'amazon.titan'
            ]
            
            available_models = [m['modelId'] for m in models]
            
            for required in required_models:
                if not any(required in model for model in available_models):
                    self.issues.append(f"Bedrock model {required} not available")
                    logger.warning(f"⚠ Bedrock model {required} not available in region")
            
            logger.info("✓ Bedrock service accessible")
            return True
            
        except Exception as e:
            self.issues.append(f"Bedrock check failed: {str(e)}")
            logger.error(f"✗ Bedrock check failed: {e}")
            return False
    
    def _check_healthlake(self) -> bool:
        """Check HealthLake datastore."""
        try:
            healthlake = boto3.client(
                'healthlake',
                **self.aws_config.get_boto3_kwargs('healthlake')
            )
            
            # List datastores
            response = healthlake.list_fhir_datastores()
            datastores = response.get('DatastorePropertiesList', [])
            
            if not datastores:
                self.issues.append("No HealthLake datastores found")
                logger.error("✗ No HealthLake datastores found")
                return False
            
            # Check for active datastore
            active_stores = [d for d in datastores if d['DatastoreStatus'] == 'ACTIVE']
            if not active_stores:
                self.issues.append("No active HealthLake datastores")
                logger.error("✗ No active HealthLake datastores")
                return False
            
            logger.info(f"✓ HealthLake datastore active: {active_stores[0]['DatastoreName']}")
            return True
            
        except Exception as e:
            self.issues.append(f"HealthLake check failed: {str(e)}")
            logger.error(f"✗ HealthLake check failed: {e}")
            return False
    
    def _check_sagemaker(self) -> bool:
        """Check SageMaker endpoints."""
        try:
            sagemaker = boto3.client(
                'sagemaker',
                **self.aws_config.get_boto3_kwargs('sagemaker')
            )
            
            # List endpoints
            response = sagemaker.list_endpoints()
            endpoints = response.get('Endpoints', [])
            
            # Check for haven-specific endpoints
            haven_endpoints = [e for e in endpoints if 'haven' in e['EndpointName'].lower()]
            
            if not haven_endpoints:
                logger.warning("⚠ No Haven-specific SageMaker endpoints found")
                # This is not a critical failure
            else:
                logger.info(f"✓ Found {len(haven_endpoints)} SageMaker endpoints")
            
            return True
            
        except Exception as e:
            self.issues.append(f"SageMaker check failed: {str(e)}")
            logger.error(f"✗ SageMaker check failed: {e}")
            return False
    
    def _check_blockchain(self) -> bool:
        """Check Managed Blockchain network."""
        try:
            blockchain = boto3.client(
                'managedblockchain',
                **self.aws_config.get_boto3_kwargs('managedblockchain')
            )
            
            # List networks
            response = blockchain.list_networks()
            networks = response.get('Networks', [])
            
            # Check for haven network
            haven_networks = [n for n in networks if 'haven' in n.get('Name', '').lower()]
            
            if not haven_networks:
                logger.warning("⚠ No Haven blockchain networks found")
                # Blockchain is optional for initial deployment
                return True
            
            # Check network status
            for network in haven_networks:
                if network['Status'] != 'AVAILABLE':
                    self.issues.append(f"Blockchain network {network['Name']} is {network['Status']}")
                    return False
            
            logger.info(f"✓ Blockchain network available")
            return True
            
        except Exception as e:
            # Blockchain is optional
            logger.warning(f"⚠ Blockchain check skipped: {e}")
            return True
    
    def generate_report(self) -> str:
        """Generate a deployment status report."""
        report = []
        report.append("=" * 80)
        report.append("HAVEN HEALTH PASSPORT - DEPLOYMENT STATUS REPORT")
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("=" * 80)
        report.append("")
        
        # Service status
        report.append("SERVICE STATUS:")
        for service, healthy in self.status.items():
            status_icon = "✓" if healthy else "✗"
            report.append(f"  {status_icon} {service.upper()}: {'Healthy' if healthy else 'Issues Found'}")
        
        # Issues
        if self.issues:
            report.append("")
            report.append("ISSUES FOUND:")
            for issue in self.issues:
                report.append(f"  - {issue}")
        
        # Recommendations
        report.append("")
        report.append("RECOMMENDATIONS:")
        if all(self.status.values()):
            report.append("  ✅ All services are healthy. Ready for deployment.")
        else:
            report.append("  ❌ Some services have issues. Run the setup script to fix:")
            report.append("     python scripts/complete_aws_setup.py")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check AWS deployment status for Haven Health Passport"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress detailed output'
    )
    
    args = parser.parse_args()
    
    if not args.quiet:
        logger.info("Checking AWS deployment status...")
    
    checker = AWSDeploymentChecker()
    all_healthy, status, issues = checker.check_all_services()
    
    if args.json:
        # JSON output
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "all_healthy": all_healthy,
            "status": status,
            "issues": issues
        }
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        report = checker.generate_report()
        print(report)
    
    # Exit code based on health
    sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
