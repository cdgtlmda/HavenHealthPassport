#!/usr/bin/env python3
"""
Production API Configuration Script for Haven Health Passport
This script configures all required external medical API credentials.
CRITICAL: This is for real patient data - all APIs must be properly configured.
"""

import os
import sys
import json
import boto3
import argparse
from typing import Dict, Any
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MedicalAPIConfigurator:
    """Configures production medical APIs for Haven Health Passport"""

    REQUIRED_APIS = {
        "rxnorm": {
            "name": "RxNorm API",
            "endpoint": "https://rxnav.nlm.nih.gov/REST/",
            "required_keys": ["api_key"],
            "test_endpoint": "/rxcui/1723222/properties.json",
        },
        "drugbank": {
            "name": "DrugBank API",
            "endpoint": "https://api.drugbank.com/v1/",
            "required_keys": ["api_key", "license_key"],
            "test_endpoint": "drug_interactions",
        },
        "clinical_guidelines": {
            "name": "Clinical Guidelines API",
            "endpoint": "https://api.guidelines.org/v1/",
            "required_keys": ["api_key", "client_id", "client_secret"],
            "test_endpoint": "guidelines",
        },
        "google_translate": {
            "name": "Google Cloud Translation",
            "endpoint": "https://translation.googleapis.com/v3/",
            "required_keys": ["api_key", "project_id"],
            "test_endpoint": "projects/{project_id}/locations/global/supportedLanguages",
        },
        "deepl": {
            "name": "DeepL API",
            "endpoint": "https://api.deepl.com/v2/",
            "required_keys": ["auth_key"],
            "test_endpoint": "languages",
        },
        "medical_terminology": {
            "name": "UMLS Medical Terminology",
            "endpoint": "https://uts-ws.nlm.nih.gov/rest/",
            "required_keys": ["api_key", "umls_license"],
            "test_endpoint": "search/current",
        },
        "normrx": {
            "name": "NORMRX API",
            "endpoint": "https://api.normrx.com/v1/",
            "required_keys": ["api_key"],
            "test_endpoint": "health",
        },
    }

    def __init__(self, environment: str):
        self.environment = environment
        self.secrets_client = boto3.client("secretsmanager")
        self.ssm_client = boto3.client("ssm")

    def validate_api_credentials(
        self, api_name: str, credentials: Dict[str, str]
    ) -> bool:
        """Validate API credentials by making test requests"""
        api_config = self.REQUIRED_APIS[api_name]

        # Check all required keys are present
        for key in api_config["required_keys"]:
            if key not in credentials or not credentials[key]:
                logger.error(f"Missing required key '{key}' for {api_config['name']}")
                return False

        # Perform API-specific validation
        try:
            if api_name == "rxnorm":
                # RxNorm doesn't require API key for public endpoints, but validate endpoint
                import requests

                response = requests.get(
                    api_config["endpoint"] + api_config["test_endpoint"], timeout=10
                )
                return response.status_code == 200

            elif api_name == "drugbank":
                # Validate DrugBank credentials
                import requests

                headers = {
                    "Authorization": f"Bearer {credentials['api_key']}",
                    "X-License-Key": credentials["license_key"],
                }
                response = requests.get(
                    api_config["endpoint"] + api_config["test_endpoint"],
                    headers=headers,
                    timeout=10,
                )
                return response.status_code == 200

            elif api_name == "deepl":
                # Validate DeepL API key
                import requests

                response = requests.get(
                    api_config["endpoint"] + api_config["test_endpoint"],
                    headers={
                        "Authorization": f"DeepL-Auth-Key {credentials['auth_key']}"
                    },
                    timeout=10,
                )
                return response.status_code == 200

            elif api_name == "normrx":
                # Validate NORMRX API key
                import requests

                headers = {
                    "Authorization": f"Bearer {credentials['api_key']}",
                    "Content-Type": "application/json",
                }
                response = requests.get(
                    api_config["endpoint"] + api_config["test_endpoint"],
                    headers=headers,
                    timeout=10,
                )
                return response.status_code == 200

            else:
                logger.warning(f"Validation not implemented for {api_name}")
                return True

        except Exception as e:
            logger.error(f"Failed to validate {api_config['name']}: {str(e)}")
            return False

    def store_credentials(self, api_name: str, credentials: Dict[str, str]) -> bool:
        """Store validated credentials in AWS Secrets Manager"""
        try:
            secret_name = f"haven-health-passport/{self.environment}/apis/{api_name}"

            # Add metadata
            credentials["configured_at"] = datetime.utcnow().isoformat()
            credentials["configured_by"] = os.environ.get("USER", "system")

            # Store in Secrets Manager
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps(credentials),
                    Description=f"{self.REQUIRED_APIS[api_name]['name']} credentials for {self.environment}",
                    Tags=[
                        {"Key": "Environment", "Value": self.environment},
                        {"Key": "Service", "Value": "haven-health-passport"},
                        {"Key": "Type", "Value": "api-credentials"},
                    ],
                )
            except self.secrets_client.exceptions.ResourceExistsException:
                # Update existing secret
                self.secrets_client.update_secret(
                    SecretId=secret_name, SecretString=json.dumps(credentials)
                )

            logger.info(f"Successfully stored credentials for {api_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to store credentials for {api_name}: {str(e)}")
            return False

    def configure_api(self, api_name: str) -> bool:
        """Configure a single API with user input"""
        api_config = self.REQUIRED_APIS[api_name]
        print(f"\n{'='*60}")
        print(f"Configuring {api_config['name']}")
        print(f"Endpoint: {api_config['endpoint']}")
        print(f"{'='*60}")

        credentials = {}

        # Collect required credentials
        for key in api_config["required_keys"]:
            while True:
                value = input(f"Enter {key}: ").strip()
                if value:
                    credentials[key] = value
                    break
                print(f"Error: {key} cannot be empty")

        # Validate credentials
        print(f"\nValidating credentials for {api_config['name']}...")
        if self.validate_api_credentials(api_name, credentials):
            print("✅ Credentials validated successfully")

            # Store credentials
            if self.store_credentials(api_name, credentials):
                print("✅ Credentials stored securely in AWS Secrets Manager")
                return True
            else:
                print("❌ Failed to store credentials")
                return False
        else:
            print("❌ Credential validation failed")
            return False

    def configure_all_apis(self) -> None:
        """Configure all required medical APIs"""
        print("\n" + "=" * 80)
        print("Haven Health Passport - Medical API Configuration")
        print(f"Environment: {self.environment.upper()}")
        print("=" * 80)
        print("\n⚠️  CRITICAL: This system handles real patient data.")
        print("All APIs must be properly configured for patient safety.\n")

        configured = []
        failed = []

        for api_name in self.REQUIRED_APIS:
            try:
                if self.configure_api(api_name):
                    configured.append(api_name)
                else:
                    failed.append(api_name)
            except KeyboardInterrupt:
                print("\n\n⚠️  Configuration interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error configuring {api_name}: {str(e)}")
                failed.append(api_name)

        # Summary
        print("\n" + "=" * 80)
        print("Configuration Summary")
        print("=" * 80)
        print(f"✅ Successfully configured: {len(configured)}")
        for api in configured:
            print(f"   - {self.REQUIRED_APIS[api]['name']}")

        if failed:
            print(f"\n❌ Failed to configure: {len(failed)}")
            for api in failed:
                print(f"   - {self.REQUIRED_APIS[api]['name']}")
            print("\n⚠️  WARNING: System is not ready for production!")
        else:
            print("\n✅ All APIs configured successfully!")
            print("System is ready for production deployment.")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Configure medical APIs for Haven Health Passport"
    )
    parser.add_argument(
        "--environment",
        choices=["development", "staging", "production"],
        required=True,
        help="Target environment for configuration",
    )

    args = parser.parse_args()

    # Production safety check
    if args.environment == "production":
        print("\n⚠️  WARNING: Configuring PRODUCTION environment!")
        print("This will affect real patient data.")
        confirm = input("Type 'CONFIGURE PRODUCTION' to continue: ")
        if confirm != "CONFIGURE PRODUCTION":
            print("Configuration cancelled.")
            sys.exit(0)

    # Check AWS credentials
    try:
        boto3.client("sts").get_caller_identity()
    except Exception as e:
        print(f"\n❌ AWS credentials not configured: {str(e)}")
        print("Please configure AWS credentials before running this script.")
        sys.exit(1)

    # Run configuration
    configurator = MedicalAPIConfigurator(args.environment)
    configurator.configure_all_apis()


if __name__ == "__main__":
    main()
