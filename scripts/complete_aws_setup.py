#!/usr/bin/env python3
"""
Comprehensive AWS Configuration Script for Haven Health Passport.

This script sets up all required AWS services for the refugee healthcare project:
- AWS Bedrock for AI/ML
- HealthLake for FHIR data
- Comprehend Medical for entity extraction
- SageMaker for custom models
- S3 for storage
- SNS for notifications
- DynamoDB for metrics
- Managed Blockchain for verification

CRITICAL: This is a healthcare project where lives depend on proper configuration.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.aws_genai_setup import AWSGenAIConfigurator
from scripts.aws_blockchain_setup import AWSBlockchainConfigurator
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HavenHealthAWSSetup:
    """Complete AWS setup for Haven Health Passport."""
    
    def __init__(self):
        """Initialize setup coordinator."""
        self.genai_configurator = AWSGenAIConfigurator()
        self.blockchain_configurator = AWSBlockchainConfigurator()
        self.results = {}
    
    def run_complete_setup(self):
        """Run complete AWS setup for the healthcare project."""
        logger.info("=" * 80)
        logger.info("HAVEN HEALTH PASSPORT - AWS INFRASTRUCTURE SETUP")
        logger.info("=" * 80)
        logger.info("Setting up critical infrastructure for refugee healthcare...")
        logger.info("")
        
        # Phase 1: GenAI Services
        logger.info("PHASE 1: Setting up AI/ML Services")
        logger.info("-" * 40)
        genai_success = self.genai_configurator.run_full_setup()
        self.results["genai"] = genai_success
        
        # Phase 2: Blockchain Services
        logger.info("\nPHASE 2: Setting up Blockchain Services")
        logger.info("-" * 40)
        blockchain_success = self.blockchain_configurator.run_full_setup()
        self.results["blockchain"] = blockchain_success
        
        # Phase 3: Additional Services
        logger.info("\nPHASE 3: Setting up Additional Services")
        logger.info("-" * 40)
        additional_success = self._setup_additional_services()
        self.results["additional"] = additional_success
        
        # Phase 4: Integration Testing
        logger.info("\nPHASE 4: Integration Testing")
        logger.info("-" * 40)
        test_success = self._run_integration_tests()
        self.results["tests"] = test_success
        
        # Final Summary
        self._print_final_summary()
        
        return all(self.results.values())
    
    def _setup_additional_services(self) -> bool:
        """Set up additional AWS services."""
        import boto3
        
        success = True
        
        try:
            # 1. Set up SNS topics for notifications
            logger.info("1. Setting up SNS topics...")
            sns = boto3.client('sns')
            
            topics = {
                "translation-alerts": "Haven Health Translation Service Alerts",
                "critical-feedback": "Haven Health Critical Feedback",
                "blockchain-events": "Haven Health Blockchain Events",
                "emergency-access": "Haven Health Emergency Access Alerts"
            }
            
            topic_arns = {}
            for topic_key, topic_name in topics.items():
                try:
                    response = sns.create_topic(
                        Name=f"haven-health-{topic_key}",
                        Attributes={
                            'DisplayName': topic_name
                        }
                    )
                    topic_arns[topic_key] = response['TopicArn']
                    logger.info(f"  ✓ Created SNS topic: {topic_key}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to create SNS topic {topic_key}: {e}")
                    success = False
            
            # 2. Set up DynamoDB tables
            logger.info("\n2. Setting up DynamoDB tables...")
            dynamodb = boto3.resource('dynamodb')
            
            tables = {
                "translation-metrics": {
                    "KeySchema": [
                        {"AttributeName": "pk", "KeyType": "HASH"},
                        {"AttributeName": "sk", "KeyType": "RANGE"}
                    ],
                    "AttributeDefinitions": [
                        {"AttributeName": "pk", "AttributeType": "S"},
                        {"AttributeName": "sk", "AttributeType": "S"}
                    ],
                    "BillingMode": "PAY_PER_REQUEST"
                },
                "translation-feedback": {
                    "KeySchema": [
                        {"AttributeName": "pk", "KeyType": "HASH"},
                        {"AttributeName": "sk", "KeyType": "RANGE"}
                    ],
                    "AttributeDefinitions": [
                        {"AttributeName": "pk", "AttributeType": "S"},
                        {"AttributeName": "sk", "AttributeType": "S"}
                    ],
                    "BillingMode": "PAY_PER_REQUEST"
                }
            }
            
            for table_name, config in tables.items():
                try:
                    full_name = f"haven-health-{table_name}"
                    
                    # Check if table exists
                    existing_tables = [t.name for t in dynamodb.tables.all()]
                    if full_name in existing_tables:
                        logger.info(f"  ✓ Table already exists: {table_name}")
                    else:
                        table = dynamodb.create_table(
                            TableName=full_name,
                            **config
                        )
                        table.wait_until_exists()
                        logger.info(f"  ✓ Created DynamoDB table: {table_name}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to create table {table_name}: {e}")
                    success = False
            
            # 3. Set up SQS queues
            logger.info("\n3. Setting up SQS queues...")
            sqs = boto3.client('sqs')
            
            queues = {
                "retraining-queue": {
                    "MessageRetentionPeriod": "1209600",  # 14 days
                    "VisibilityTimeout": "3600"  # 1 hour for processing
                },
                "voice-processing": {
                    "MessageRetentionPeriod": "345600",  # 4 days
                    "VisibilityTimeout": "300"  # 5 minutes
                }
            }
            
            queue_urls = {}
            for queue_name, attributes in queues.items():
                try:
                    response = sqs.create_queue(
                        QueueName=f"haven-health-{queue_name}",
                        Attributes=attributes
                    )
                    queue_urls[queue_name] = response['QueueUrl']
                    logger.info(f"  ✓ Created SQS queue: {queue_name}")
                except Exception as e:
                    if "QueueAlreadyExists" in str(e):
                        logger.info(f"  ✓ Queue already exists: {queue_name}")
                    else:
                        logger.error(f"  ✗ Failed to create queue {queue_name}: {e}")
                        success = False
            
            # 4. Update .env.aws with additional services
            if topic_arns or queue_urls:
                self._update_env_file(topic_arns, queue_urls)
            
        except Exception as e:
            logger.error(f"Error setting up additional services: {e}")
            success = False
        
        return success
    
    def _update_env_file(self, topic_arns: Dict, queue_urls: Dict):
        """Update .env.aws file with service endpoints."""
        env_file = project_root / ".env.aws"
        
        lines = []
        lines.append("\n# Additional Services Configuration")
        lines.append("# Generated by complete_aws_setup.py")
        lines.append("")
        
        # SNS Topics
        if topic_arns:
            lines.append("# SNS Topics")
            for key, arn in topic_arns.items():
                env_key = f"SNS_TOPIC_ARN_{key.upper().replace('-', '_')}"
                lines.append(f"{env_key}={arn}")
            lines.append("")
        
        # SQS Queues
        if queue_urls:
            lines.append("# SQS Queues")
            for key, url in queue_urls.items():
                env_key = f"SQS_QUEUE_URL_{key.upper().replace('-', '_')}"
                lines.append(f"{env_key}={url}")
            lines.append("")
        
        # Append to file
        with open(env_file, "a") as f:
            f.write("\n".join(lines))
        
        logger.info("Updated .env.aws with additional service endpoints")
    
    def _run_integration_tests(self) -> bool:
        """Run basic integration tests."""
        success = True
        
        try:
            # Test 1: Bedrock connectivity
            logger.info("1. Testing Bedrock connectivity...")
            from src.services.bedrock_service import BedrockService
            bedrock = BedrockService()
            
            try:
                response = bedrock.generate_text(
                    prompt="Translate 'Hello' to Spanish",
                    max_tokens=10
                )
                if response:
                    logger.info("  ✓ Bedrock is responding correctly")
                else:
                    logger.error("  ✗ Bedrock returned empty response")
                    success = False
            except Exception as e:
                logger.error(f"  ✗ Bedrock test failed: {e}")
                success = False
            
            # Test 2: HealthLake connectivity
            logger.info("\n2. Testing HealthLake connectivity...")
            import boto3
            healthlake = boto3.client('healthlake')
            
            try:
                # Just check if we can list datastores
                response = healthlake.list_fhir_datastores()
                logger.info(f"  ✓ HealthLake accessible, found {len(response.get('DatastorePropertiesList', []))} datastores")
            except Exception as e:
                logger.error(f"  ✗ HealthLake test failed: {e}")
                success = False
            
            # Test 3: Comprehend Medical
            logger.info("\n3. Testing Comprehend Medical...")
            comprehend_medical = boto3.client('comprehendmedical')
            
            try:
                response = comprehend_medical.detect_entities_v2(
                    Text="Patient has diabetes and hypertension"
                )
                entities = response.get('Entities', [])
                logger.info(f"  ✓ Comprehend Medical detected {len(entities)} medical entities")
            except Exception as e:
                logger.error(f"  ✗ Comprehend Medical test failed: {e}")
                success = False
            
        except Exception as e:
            logger.error(f"Integration tests failed: {e}")
            success = False
        
        return success
    
    def _print_final_summary(self):
        """Print final setup summary."""
        logger.info("\n" + "=" * 80)
        logger.info("SETUP COMPLETE - FINAL SUMMARY")
        logger.info("=" * 80)
        
        # Status of each phase
        status_symbols = {True: "✅", False: "❌"}
        
        logger.info("\nPhase Results:")
        logger.info(f"  {status_symbols[self.results.get('genai', False)]} GenAI Services (Bedrock, HealthLake, SageMaker)")
        logger.info(f"  {status_symbols[self.results.get('blockchain', False)]} Blockchain Services (Managed Blockchain)")
        logger.info(f"  {status_symbols[self.results.get('additional', False)]} Additional Services (SNS, DynamoDB, SQS)")
        logger.info(f"  {status_symbols[self.results.get('tests', False)]} Integration Tests")
        
        # Overall status
        all_success = all(self.results.values())
        
        if all_success:
            logger.info("\n✅ ALL SERVICES CONFIGURED SUCCESSFULLY!")
            logger.info("\nNext Steps:")
            logger.info("1. Review the .env.aws file for all service configurations")
            logger.info("2. Wait for async resources to fully activate (HealthLake, Blockchain)")
            logger.info("3. Deploy the application using the deployment scripts")
            logger.info("4. Run the full test suite to verify everything is working")
        else:
            logger.error("\n❌ SOME SERVICES FAILED TO CONFIGURE")
            logger.error("\nRequired Actions:")
            logger.error("1. Review the error messages above")
            logger.error("2. Fix any permission or configuration issues")
            logger.error("3. Re-run this script to complete setup")
            logger.error("4. DO NOT deploy until all services are configured")
        
        logger.info("\n" + "=" * 80)


def main():
    """Main entry point."""
    logger.info("Starting Haven Health Passport AWS setup...")
    logger.info("This will configure all required AWS services for the healthcare platform.")
    logger.info("")
    
    # Confirm with user
    response = input("Do you want to proceed with the complete AWS setup? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Setup cancelled.")
        return
    
    setup = HavenHealthAWSSetup()
    success = setup.run_complete_setup()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
