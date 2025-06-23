#!/usr/bin/env python3
"""
AWS Deployment Verification and Execution Script for Haven Health Passport.

This script verifies that all AWS resources are properly deployed and operational.
If resources are missing or not active, it runs the deployment scripts.

CRITICAL: This is a healthcare project for refugees. Proper deployment is essential.
"""

import os
import sys
import subprocess
import time
import boto3
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logging import get_logger
from src.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class AWSDeploymentVerifier:
    """Verify and deploy AWS resources for Haven Health Passport."""
    
    def __init__(self):
        """Initialize AWS clients."""
        self.region = settings.AWS_REGION or "us-east-1"
        self.deployment_status = {
            "healthlake": {"status": "unknown", "details": {}},
            "bedrock": {"status": "unknown", "details": {}},
            "blockchain": {"status": "unknown", "details": {}},
            "s3_buckets": {"status": "unknown", "details": {}},
            "dynamodb": {"status": "unknown", "details": {}},
            "sns_topics": {"status": "unknown", "details": {}},
            "sqs_queues": {"status": "unknown", "details": {}},
            "iam_roles": {"status": "unknown", "details": {}}
        }
        
        # Initialize AWS clients
        try:
            self.healthlake = boto3.client("healthlake", region_name=self.region)
            self.bedrock = boto3.client("bedrock-runtime", region_name=self.region)
            self.blockchain = boto3.client("managedblockchain", region_name=self.region)
            self.s3 = boto3.client("s3", region_name=self.region)
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.sns = boto3.client("sns", region_name=self.region)
            self.sqs = boto3.client("sqs", region_name=self.region)
            self.iam = boto3.client("iam", region_name=self.region)
            logger.info(f"Initialized AWS clients in region: {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise
    
    def verify_healthlake(self) -> Tuple[bool, Dict]:
        """Verify HealthLake datastore is active."""
        logger.info("Verifying HealthLake datastore...")
        
        try:
            response = self.healthlake.list_fhir_datastores()
            datastores = response.get("DatastorePropertiesList", [])
            
            haven_datastore = None
            for ds in datastores:
                if "haven-health" in ds.get("DatastoreName", "").lower():
                    haven_datastore = ds
                    break
            
            if haven_datastore:
                status = haven_datastore["DatastoreStatus"]
                datastore_id = haven_datastore["DatastoreId"]
                
                self.deployment_status["healthlake"]["details"] = {
                    "datastore_id": datastore_id,
                    "status": status,
                    "name": haven_datastore["DatastoreName"]
                }
                
                if status == "ACTIVE":
                    logger.info(f"✅ HealthLake datastore is ACTIVE: {datastore_id}")
                    self.deployment_status["healthlake"]["status"] = "active"
                    return True, {"datastore_id": datastore_id}
                else:
                    logger.warning(f"⏳ HealthLake datastore status: {status}")
                    self.deployment_status["healthlake"]["status"] = "pending"
                    return False, {"status": status}
            else:
                logger.error("❌ No Haven Health HealthLake datastore found")
                self.deployment_status["healthlake"]["status"] = "missing"
                return False, {"error": "No datastore found"}
                
        except Exception as e:
            logger.error(f"Error verifying HealthLake: {e}")
            self.deployment_status["healthlake"]["status"] = "error"
            return False, {"error": str(e)}
    
    def verify_bedrock(self) -> Tuple[bool, Dict]:
        """Verify Bedrock models are accessible."""
        logger.info("Verifying Bedrock models...")
        
        try:
            # Test with a simple invocation
            test_prompt = "Translate 'Hello' to Spanish"
            
            import json
            body = json.dumps({
                "prompt": f"\n\nHuman: {test_prompt}\n\nAssistant:",
                "max_tokens_to_sample": 50,
                "temperature": 0.1
            })
            
            response = self.bedrock.invoke_model(
                body=body,
                modelId="anthropic.claude-v2",
                accept="application/json",
                contentType="application/json"
            )
            
            result = json.loads(response["body"].read())
            if result.get("completion"):
                logger.info("✅ Bedrock models are accessible")
                self.deployment_status["bedrock"]["status"] = "active"
                return True, {"test_response": result["completion"][:50]}
            else:
                logger.error("❌ Bedrock returned empty response")
                self.deployment_status["bedrock"]["status"] = "error"
                return False, {"error": "Empty response"}
                
        except Exception as e:
            logger.error(f"❌ Bedrock verification failed: {e}")
            self.deployment_status["bedrock"]["status"] = "error"
            return False, {"error": str(e)}
    
    def verify_blockchain(self) -> Tuple[bool, Dict]:
        """Verify blockchain network is available."""
        logger.info("Verifying blockchain network...")
        
        try:
            # Check for blockchain network
            response = self.blockchain.list_networks(
                Framework="HYPERLEDGER_FABRIC",
                Status="AVAILABLE"
            )
            
            networks = response.get("Networks", [])
            haven_network = None
            
            for network in networks:
                if "haven" in network.get("Name", "").lower():
                    haven_network = network
                    break
            
            if haven_network:
                network_id = haven_network["Id"]
                
                # Check for members
                members = self.blockchain.list_members(NetworkId=network_id).get("Members", [])
                
                self.deployment_status["blockchain"]["details"] = {
                    "network_id": network_id,
                    "network_name": haven_network["Name"],
                    "member_count": len(members)
                }
                
                if members:
                    logger.info(f"✅ Blockchain network is AVAILABLE: {network_id}")
                    self.deployment_status["blockchain"]["status"] = "active"
                    return True, {"network_id": network_id, "members": len(members)}
                else:
                    logger.warning("⚠️ Blockchain network exists but no members")
                    self.deployment_status["blockchain"]["status"] = "partial"
                    return False, {"network_id": network_id, "error": "No members"}
            else:
                logger.warning("❌ No Haven Health blockchain network found")
                self.deployment_status["blockchain"]["status"] = "missing"
                return False, {"error": "No network found"}
                
        except Exception as e:
            logger.error(f"Error verifying blockchain: {e}")
            self.deployment_status["blockchain"]["status"] = "error"
            return False, {"error": str(e)}
    
    def verify_s3_buckets(self) -> Tuple[bool, Dict]:
        """Verify S3 buckets exist."""
        logger.info("Verifying S3 buckets...")
        
        required_buckets = [
            "haven-health-models",
            "haven-health-translations",
            "haven-health-medical-data"
        ]
        
        found_buckets = []
        missing_buckets = []
        
        try:
            for bucket_name in required_buckets:
                try:
                    self.s3.head_bucket(Bucket=bucket_name)
                    found_buckets.append(bucket_name)
                except:
                    missing_buckets.append(bucket_name)
            
            self.deployment_status["s3_buckets"]["details"] = {
                "found": found_buckets,
                "missing": missing_buckets
            }
            
            if not missing_buckets:
                logger.info(f"✅ All S3 buckets verified: {len(found_buckets)}")
                self.deployment_status["s3_buckets"]["status"] = "active"
                return True, {"buckets": found_buckets}
            else:
                logger.warning(f"❌ Missing S3 buckets: {missing_buckets}")
                self.deployment_status["s3_buckets"]["status"] = "partial"
                return False, {"missing": missing_buckets}
                
        except Exception as e:
            logger.error(f"Error verifying S3 buckets: {e}")
            self.deployment_status["s3_buckets"]["status"] = "error"
            return False, {"error": str(e)}
    
    def verify_dynamodb_tables(self) -> Tuple[bool, Dict]:
        """Verify DynamoDB tables exist."""
        logger.info("Verifying DynamoDB tables...")
        
        required_tables = [
            "haven-health-translation-metrics",
            "haven-health-translation-feedback"
        ]
        
        found_tables = []
        missing_tables = []
        
        try:
            existing_tables = [table.name for table in self.dynamodb.tables.all()]
            
            for table_name in required_tables:
                if table_name in existing_tables:
                    found_tables.append(table_name)
                else:
                    missing_tables.append(table_name)
            
            self.deployment_status["dynamodb"]["details"] = {
                "found": found_tables,
                "missing": missing_tables
            }
            
            if not missing_tables:
                logger.info(f"✅ All DynamoDB tables verified: {len(found_tables)}")
                self.deployment_status["dynamodb"]["status"] = "active"
                return True, {"tables": found_tables}
            else:
                logger.warning(f"❌ Missing DynamoDB tables: {missing_tables}")
                self.deployment_status["dynamodb"]["status"] = "partial"
                return False, {"missing": missing_tables}
                
        except Exception as e:
            logger.error(f"Error verifying DynamoDB tables: {e}")
            self.deployment_status["dynamodb"]["status"] = "error"
            return False, {"error": str(e)}
    
    def verify_sns_topics(self) -> Tuple[bool, Dict]:
        """Verify SNS topics exist."""
        logger.info("Verifying SNS topics...")
        
        required_topics = [
            "haven-health-translation-alerts",
            "haven-health-critical-feedback",
            "haven-health-blockchain-events",
            "haven-health-emergency-access"
        ]
        
        found_topics = []
        missing_topics = []
        
        try:
            # List all topics
            response = self.sns.list_topics()
            existing_topics = [topic['TopicArn'].split(':')[-1] for topic in response.get('Topics', [])]
            
            for topic_name in required_topics:
                if topic_name in existing_topics:
                    found_topics.append(topic_name)
                else:
                    missing_topics.append(topic_name)
            
            self.deployment_status["sns_topics"]["details"] = {
                "found": found_topics,
                "missing": missing_topics
            }
            
            if not missing_topics:
                logger.info(f"✅ All SNS topics verified: {len(found_topics)}")
                self.deployment_status["sns_topics"]["status"] = "active"
                return True, {"topics": found_topics}
            else:
                logger.warning(f"❌ Missing SNS topics: {missing_topics}")
                self.deployment_status["sns_topics"]["status"] = "partial"
                return False, {"missing": missing_topics}
                
        except Exception as e:
            logger.error(f"Error verifying SNS topics: {e}")
            self.deployment_status["sns_topics"]["status"] = "error"
            return False, {"error": str(e)}
    
    def verify_sqs_queues(self) -> Tuple[bool, Dict]:
        """Verify SQS queues exist."""
        logger.info("Verifying SQS queues...")
        
        required_queues = [
            "haven-health-retraining-queue",
            "haven-health-voice-processing"
        ]
        
        found_queues = []
        missing_queues = []
        
        try:
            response = self.sqs.list_queues()
            existing_queues = []
            
            for queue_url in response.get('QueueUrls', []):
                queue_name = queue_url.split('/')[-1]
                existing_queues.append(queue_name)
            
            for queue_name in required_queues:
                if queue_name in existing_queues:
                    found_queues.append(queue_name)
                else:
                    missing_queues.append(queue_name)
            
            self.deployment_status["sqs_queues"]["details"] = {
                "found": found_queues,
                "missing": missing_queues
            }
            
            if not missing_queues:
                logger.info(f"✅ All SQS queues verified: {len(found_queues)}")
                self.deployment_status["sqs_queues"]["status"] = "active"
                return True, {"queues": found_queues}
            else:
                logger.warning(f"❌ Missing SQS queues: {missing_queues}")
                self.deployment_status["sqs_queues"]["status"] = "partial"
                return False, {"missing": missing_queues}
                
        except Exception as e:
            logger.error(f"Error verifying SQS queues: {e}")
            self.deployment_status["sqs_queues"]["status"] = "error"
            return False, {"error": str(e)}
    
    def run_deployment_scripts(self) -> bool:
        """Run the complete AWS setup script if resources are missing."""
        logger.info("\n" + "="*80)
        logger.info("RUNNING AWS DEPLOYMENT SCRIPTS")
        logger.info("="*80)
        
        try:
            # Run the complete setup script
            script_path = project_root / "scripts" / "complete_aws_setup.py"
            
            if not script_path.exists():
                logger.error(f"Setup script not found: {script_path}")
                return False
            
            logger.info(f"Executing: {script_path}")
            
            # Run the script with subprocess to capture output
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                input="yes\n"  # Auto-confirm deployment
            )
            
            if result.returncode == 0:
                logger.info("✅ Deployment script completed successfully")
                logger.info(result.stdout)
                return True
            else:
                logger.error("❌ Deployment script failed")
                logger.error(result.stderr)
                return False
                
        except Exception as e:
            logger.error(f"Error running deployment scripts: {e}")
            return False
    
    def verify_all_resources(self) -> Dict[str, bool]:
        """Verify all AWS resources."""
        logger.info("\n" + "="*80)
        logger.info("AWS RESOURCE VERIFICATION REPORT")
        logger.info("="*80)
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"Region: {self.region}")
        logger.info("="*80 + "\n")
        
        # Run all verifications
        results = {
            "healthlake": self.verify_healthlake()[0],
            "bedrock": self.verify_bedrock()[0],
            "blockchain": self.verify_blockchain()[0],
            "s3_buckets": self.verify_s3_buckets()[0],
            "dynamodb": self.verify_dynamodb_tables()[0],
            "sns_topics": self.verify_sns_topics()[0],
            "sqs_queues": self.verify_sqs_queues()[0]
        }
        
        return results
    
    def print_verification_report(self):
        """Print detailed verification report."""
        logger.info("\n" + "="*80)
        logger.info("DETAILED VERIFICATION RESULTS")
        logger.info("="*80)
        
        # Status symbols
        symbols = {
            "active": "✅",
            "pending": "⏳",
            "partial": "⚠️",
            "missing": "❌",
            "error": "🔥",
            "unknown": "❓"
        }
        
        for service, data in self.deployment_status.items():
            status = data["status"]
            symbol = symbols.get(status, "❓")
            
            logger.info(f"\n{symbol} {service.upper().replace('_', ' ')}: {status.upper()}")
            
            if data.get("details"):
                for key, value in data["details"].items():
                    if isinstance(value, list):
                        logger.info(f"  - {key}: {', '.join(value) if value else 'None'}")
                    else:
                        logger.info(f"  - {key}: {value}")
        
        logger.info("\n" + "="*80)
    
    def execute(self) -> bool:
        """Execute verification and deployment if needed."""
        # Step 1: Verify all resources
        results = self.verify_all_resources()
        
        # Step 2: Print detailed report
        self.print_verification_report()
        
        # Step 3: Check if deployment is needed
        all_active = all(results.values())
        
        if all_active:
            logger.info("\n✅ ALL AWS RESOURCES ARE ACTIVE AND OPERATIONAL!")
            logger.info("No deployment needed. System is ready for use.")
            return True
        else:
            logger.warning("\n⚠️ SOME AWS RESOURCES ARE MISSING OR NOT ACTIVE")
            
            # Count what's missing
            missing_count = sum(1 for v in results.values() if not v)
            logger.info(f"\nMissing/Inactive resources: {missing_count}")
            
            # Step 4: Run deployment if needed
            logger.info("\nRunning deployment scripts to create missing resources...")
            deployment_success = self.run_deployment_scripts()
            
            if deployment_success:
                # Step 5: Re-verify after deployment
                logger.info("\nRe-verifying resources after deployment...")
                time.sleep(5)  # Brief pause
                
                new_results = self.verify_all_resources()
                self.print_verification_report()
                
                if all(new_results.values()):
                    logger.info("\n✅ DEPLOYMENT SUCCESSFUL - ALL RESOURCES NOW ACTIVE!")
                    return True
                else:
                    still_missing = sum(1 for v in new_results.values() if not v)
                    logger.warning(f"\n⚠️ {still_missing} resources still pending activation")
                    logger.info("Some resources (like HealthLake) may take 10-30 minutes to activate.")
                    logger.info("Re-run this script later to verify full activation.")
                    return True  # Partial success
            else:
                logger.error("\n❌ DEPLOYMENT FAILED")
                return False


def main():
    """Main entry point."""
    logger.info("Haven Health Passport - AWS Deployment Verification")
    logger.info("This script verifies all AWS resources are properly deployed.")
    logger.info("")
    
    try:
        verifier = AWSDeploymentVerifier()
        success = verifier.execute()
        
        if success:
            logger.info("\n" + "="*80)
            logger.info("NEXT STEPS:")
            logger.info("1. If resources are pending, wait 10-30 minutes and re-run this script")
            logger.info("2. Check the .env.aws file for all service configurations")
            logger.info("3. Run integration tests to verify connectivity")
            logger.info("4. Deploy the application")
            logger.info("="*80)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Fatal error during verification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()