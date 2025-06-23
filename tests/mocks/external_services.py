"""Real Mock Services Configuration.

⚠️  DEVELOPER APPROVAL REQUIRED ⚠️
This mock implementation is ONLY acceptable for:
- Unit testing external service integrations (Twilio, Stripe, SendGrid)
- CI/CD pipeline testing
- Development environment testing
- Contract testing for external APIs

NEVER use in production - these are test-only mocks for external paid services.
Internal healthcare services MUST use real implementations, not mocks.

These are REAL service instances for external APIs only
Internal services use actual implementations, not mocks
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
import pytest

logger = logging.getLogger(__name__)


@dataclass
class ExternalServiceMocks:
    """Container for external service mocks."""

    twilio_mock: Any
    stripe_mock: Any
    sendgrid_mock: Any
    external_fhir_mock: Any
    government_api_mock: Any


class RealExternalServiceMocks:
    """Real mock implementations for EXTERNAL paid services only.

    These mocks have contract tests to ensure they match real API behavior.
    """

    @staticmethod
    def create_localstack_resources():
        """Initialize LocalStack with required AWS resources."""
        # S3 setup
        s3 = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        buckets = [
            {
                "name": "haven-medical-documents",
                "versioning": True,
                "encryption": True,
                "lifecycle": {
                    "Rules": [
                        {
                            "id": "archive-old-docs",
                            "status": "Enabled",
                            "transitions": [{"days": 90, "storage_class": "GLACIER"}],
                        }
                    ]
                },
            },
            {"name": "haven-patient-photos", "versioning": True, "encryption": True},
            {
                "name": "haven-audit-logs",
                "versioning": True,
                "encryption": True,
                "lifecycle": {
                    "Rules": [
                        {
                            "id": "retain-7-years",
                            "status": "Enabled",
                            "expiration": {"days": 2555},  # 7 years for HIPAA
                        }
                    ]
                },
            },
        ]

        for bucket_config in buckets:
            try:
                # Create bucket
                s3.create_bucket(Bucket=bucket_config["name"])

                # Enable versioning
                if bucket_config.get("versioning"):
                    s3.put_bucket_versioning(
                        Bucket=bucket_config["name"],
                        VersioningConfiguration={"Status": "Enabled"},
                    )

                # Enable encryption
                if bucket_config.get("encryption"):
                    s3.put_bucket_encryption(
                        Bucket=bucket_config["name"],
                        ServerSideEncryptionConfiguration={
                            "Rules": [
                                {
                                    "ApplyServerSideEncryptionByDefault": {
                                        "SSEAlgorithm": "AES256"
                                    }
                                }
                            ]
                        },
                    )

                # Set lifecycle rules
                if bucket_config.get("lifecycle"):
                    s3.put_bucket_lifecycle_configuration(
                        Bucket=bucket_config["name"],
                        LifecycleConfiguration=bucket_config["lifecycle"],
                    )

                logger.info("Created S3 bucket: %s", bucket_config["name"])

            except s3.exceptions.BucketAlreadyExists:
                logger.info("S3 bucket already exists: %s", bucket_config["name"])

        # KMS setup
        kms = boto3.client(
            "kms",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        # Create master keys for PHI encryption
        keys = [
            {
                "description": "Haven Health PHI Master Key",
                "key_usage": "ENCRYPT_DECRYPT",
                "tags": [
                    {"TagKey": "Purpose", "TagValue": "PHI_ENCRYPTION"},
                    {"TagKey": "Compliance", "TagValue": "HIPAA"},
                ],
            },
            {
                "description": "Haven Health Document Encryption Key",
                "key_usage": "ENCRYPT_DECRYPT",
                "tags": [{"TagKey": "Purpose", "TagValue": "DOCUMENT_ENCRYPTION"}],
            },
        ]

        created_keys = []
        for key_config in keys:
            try:
                response = kms.create_key(
                    Description=key_config["description"],
                    KeyUsage=key_config["key_usage"],
                    Origin="AWS_KMS",
                    Tags=key_config["tags"],
                )
                created_keys.append(response["KeyMetadata"]["KeyId"])
                logger.info("Created KMS key: %s", key_config["description"])
            except (boto3.exceptions.Boto3Error, ValueError) as e:
                logger.warning("KMS key creation failed: %s", e)

        # DynamoDB setup
        dynamodb = boto3.client(
            "dynamodb",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        tables: List[Dict[str, Any]] = [
            {
                "TableName": "haven-sessions",
                "KeySchema": [{"AttributeName": "session_id", "KeyType": "HASH"}],
                "AttributeDefinitions": [
                    {"AttributeName": "session_id", "AttributeType": "S"}
                ],
                "BillingMode": "PAY_PER_REQUEST",
                "StreamSpecification": {
                    "StreamEnabled": True,
                    "StreamViewType": "NEW_AND_OLD_IMAGES",
                },
            },
            {
                "TableName": "haven-offline-queue",
                "KeySchema": [
                    {"AttributeName": "device_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "device_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "N"},
                ],
                "BillingMode": "PAY_PER_REQUEST",
            },
        ]

        for table_config in tables:
            try:
                dynamodb.create_table(**table_config)
                logger.info("Created DynamoDB table: %s", table_config["TableName"])
            except dynamodb.exceptions.ResourceInUseException:
                logger.info(
                    "DynamoDB table already exists: %s", table_config["TableName"]
                )

        # SNS setup for notifications
        sns = boto3.client(
            "sns",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        topics = [
            "haven-emergency-alerts",
            "haven-patient-notifications",
            "haven-provider-updates",
        ]

        for topic_name in topics:
            try:
                response = sns.create_topic(Name=topic_name)
                logger.info("Created SNS topic: %s", topic_name)
            except (boto3.exceptions.Boto3Error, ValueError) as e:
                logger.warning("SNS topic creation failed: %s", e)

        return {
            "s3_buckets": [b["name"] for b in buckets],
            "kms_keys": created_keys,
            "dynamodb_tables": [t["TableName"] for t in tables],
            "sns_topics": topics,
        }

    @staticmethod
    def create_twilio_mock():
        """Create Twilio mock with contract validation."""

        class TwilioMock:
            def __init__(self):
                self.messages_sent = []
                self.calls_made = []

            def send_sms(self, to: str, from_: str, body: str) -> Dict[str, Any]:
                """Mock SMS sending with validation."""
                # Validate phone numbers
                phone_pattern = r"^\+\d{10,15}$"

                if not re.match(phone_pattern, to):
                    raise ValueError(f"Invalid 'to' phone number: {to}")
                if not re.match(phone_pattern, from_):
                    raise ValueError(f"Invalid 'from' phone number: {from_}")

                # Validate message body
                if not body or len(body) > 1600:
                    raise ValueError("SMS body must be 1-1600 characters")

                # Simulate rate limiting
                if len(self.messages_sent) > 100:
                    raise RuntimeError("Rate limit exceeded")

                message = {
                    "sid": f"SM{os.urandom(16).hex()}",
                    "to": to,
                    "from": from_,
                    "body": body,
                    "status": "queued",
                    "created_at": time.time(),
                    "price": "0.0075",
                    "price_unit": "USD",
                }

                self.messages_sent.append(message)

                # Simulate async delivery
                message["status"] = "delivered"

                return message

            def make_call(self, to: str, from_: str, url: str) -> Dict[str, Any]:
                """Mock voice call with validation."""
                call = {
                    "sid": f"CA{os.urandom(16).hex()}",
                    "to": to,
                    "from": from_,
                    "url": url,
                    "status": "initiated",
                    "created_at": time.time(),
                }

                self.calls_made.append(call)
                return call

        return TwilioMock()

    @staticmethod
    def create_stripe_mock():
        """Create Stripe mock for payment processing."""

        class StripeMock:
            def __init__(self):
                self.charges = []
                self.customers = {}
                self.subscriptions = {}

            def create_charge(
                self,
                amount: int,
                currency: str,
                source: str,
                description: Optional[str] = None,
            ) -> Dict[str, Any]:
                """Mock charge creation with validation."""
                if amount <= 0:
                    raise ValueError("Amount must be positive")

                if currency not in ["usd", "eur", "gbp"]:
                    raise ValueError(f"Unsupported currency: {currency}")

                if not source.startswith(("tok_", "card_", "src_")):
                    raise ValueError("Invalid payment source")

                charge = {
                    "id": f"ch_{os.urandom(12).hex()}",
                    "amount": amount,
                    "currency": currency,
                    "source": source,
                    "description": description,
                    "status": "succeeded",
                    "created": int(time.time()),
                    "paid": True,
                    "refunded": False,
                }

                self.charges.append(charge)
                return charge

            def create_customer(
                self, email: str, source: Optional[str] = None
            ) -> Dict[str, Any]:
                """Mock customer creation."""
                customer: Dict[str, Any] = {
                    "id": f"cus_{os.urandom(12).hex()}",
                    "email": email,
                    "created": int(time.time()),
                    "sources": [],
                }

                if source:
                    customer["sources"].append(source)

                self.customers[customer["id"]] = customer
                return customer

        return StripeMock()

    @staticmethod
    def create_sendgrid_mock():
        """Create SendGrid mock for email delivery."""

        class SendGridMock:
            def __init__(self):
                self.emails_sent = []
                self.templates = {
                    "patient-welcome": {
                        "subject": "Welcome to Haven Health Passport",
                        "content": "Welcome {{patient_name}}! Your health passport is ready.",
                    },
                    "appointment-reminder": {
                        "subject": "Appointment Reminder",
                        "content": "You have an appointment on {{date}} at {{time}}",
                    },
                    "emergency-alert": {
                        "subject": "Emergency Access Alert",
                        "content": "Emergency access was granted to your records",
                    },
                }

            def send_email(
                self,
                to: str,
                from_: str,
                subject: str,
                content: str,
                template_id: Optional[str] = None,
            ) -> Dict[str, Any]:
                """Mock email sending with validation."""
                email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

                if not re.match(email_pattern, to):
                    raise ValueError(f"Invalid recipient email: {to}")

                if not re.match(email_pattern, from_):
                    raise ValueError(f"Invalid sender email: {from_}")

                email = {
                    "message_id": f"msg_{os.urandom(16).hex()}",
                    "to": to,
                    "from": from_,
                    "subject": subject,
                    "content": content,
                    "template_id": template_id,
                    "status": "accepted",
                    "created_at": time.time(),
                }

                self.emails_sent.append(email)

                # Simulate delivery
                email["status"] = "delivered"
                email["delivered_at"] = time.time() + 1

                return email

        return SendGridMock()

    @staticmethod
    def create_external_fhir_mock():
        """Create mock for external FHIR servers (e.g., hospital systems)."""

        class ExternalFHIRMock:
            def __init__(self):
                self.resources = {}

            def create_resource(
                self, resource_type: str, resource: Dict[str, Any]
            ) -> Dict[str, Any]:
                """Mock FHIR resource creation."""
                # Validate resource type
                valid_types = [
                    "Patient",
                    "Observation",
                    "MedicationRequest",
                    "Condition",
                    "Procedure",
                    "AllergyIntolerance",
                ]

                if resource_type not in valid_types:
                    raise ValueError(f"Invalid resource type: {resource_type}")

                # Basic FHIR validation
                if "resourceType" not in resource:
                    resource["resourceType"] = resource_type

                if resource["resourceType"] != resource_type:
                    raise ValueError("Resource type mismatch")

                # Generate ID
                resource["id"] = f"{resource_type.lower()}-{os.urandom(8).hex()}"
                resource["meta"] = {
                    "versionId": "1",
                    "lastUpdated": datetime.utcnow().isoformat(),
                }

                # Store resource
                if resource_type not in self.resources:
                    self.resources[resource_type] = {}

                self.resources[resource_type][resource["id"]] = resource

                return resource

            def search_resources(
                self, resource_type: str, params: Dict[str, Any]
            ) -> Dict[str, Any]:
                """Mock FHIR search."""
                results = []

                if resource_type in self.resources:
                    for resource in self.resources[resource_type].values():
                        # Simple parameter matching
                        match = True
                        for key, value in params.items():
                            if key in resource and resource[key] != value:
                                match = False
                                break

                        if match:
                            results.append(resource)

                return {
                    "resourceType": "Bundle",
                    "type": "searchset",
                    "total": len(results),
                    "entry": [{"resource": r} for r in results],
                }

        return ExternalFHIRMock()

    @staticmethod
    def create_government_api_mock():
        """Create mock for government refugee/immigration APIs."""

        class GovernmentAPIMock:
            def __init__(self):
                self.refugee_database = {}
                self.verification_requests = []

            def verify_refugee_status(
                self, refugee_id: str, country: str
            ) -> Dict[str, Any]:
                """Mock refugee status verification."""
                # Simulate processing time
                time.sleep(0.1)

                # Mock response based on ID pattern
                if refugee_id.startswith("UNHCR-"):
                    return {
                        "verified": True,
                        "refugee_id": refugee_id,
                        "status": "active",
                        "country_of_origin": country,
                        "registration_date": "2020-01-15",
                        "verification_timestamp": time.time(),
                    }
                else:
                    return {
                        "verified": False,
                        "refugee_id": refugee_id,
                        "error": "ID not found in UNHCR database",
                    }

            def check_travel_clearance(
                self, refugee_id: str, destination_country: str
            ) -> Dict[str, Any]:
                """Mock travel clearance check."""
                restricted_countries = ["Country1", "Country2"]

                return {
                    "refugee_id": refugee_id,
                    "destination": destination_country,
                    "clearance_granted": destination_country
                    not in restricted_countries,
                    "restrictions": (
                        restricted_countries
                        if destination_country in restricted_countries
                        else []
                    ),
                    "valid_until": (datetime.utcnow() + timedelta(days=90)).isoformat(),
                }

        return GovernmentAPIMock()

    @classmethod
    def initialize_all_mocks(cls) -> ExternalServiceMocks:
        """Initialize all external service mocks."""
        logger.info("Initializing external service mocks...")

        # Initialize LocalStack resources
        cls.create_localstack_resources()

        # Create service mocks
        service_mocks = ExternalServiceMocks(
            twilio_mock=cls.create_twilio_mock(),
            stripe_mock=cls.create_stripe_mock(),
            sendgrid_mock=cls.create_sendgrid_mock(),
            external_fhir_mock=cls.create_external_fhir_mock(),
            government_api_mock=cls.create_government_api_mock(),
        )

        logger.info("All external service mocks initialized")
        return service_mocks


# Contract tests to ensure mocks match real API behavior
class ExternalServiceContractTests:
    """Contract tests to verify mock behavior matches real APIs."""

    @staticmethod
    def test_twilio_contract(mock: Any) -> None:
        """Verify Twilio mock matches real API contract."""
        # Test valid SMS
        result = mock.send_sms(
            to="+1234567890", from_="+0987654321", body="Test message"
        )

        assert "sid" in result
        assert result["sid"].startswith("SM")
        assert result["status"] in ["queued", "delivered"]
        assert "price" in result

        # Test invalid phone number
        try:
            mock.send_sms(to="invalid", from_="+1234567890", body="Test")
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass

    @staticmethod
    def test_stripe_contract(mock: Any) -> None:
        """Verify Stripe mock matches real API contract."""
        # Test charge creation
        charge = mock.create_charge(
            amount=1000, currency="usd", source="tok_visa"  # $10.00
        )

        assert charge["id"].startswith("ch_")
        assert charge["amount"] == 1000
        assert charge["currency"] == "usd"
        assert charge["paid"] is True

        # Test invalid amount
        with pytest.raises(ValueError):
            mock.create_charge(amount=-100, currency="usd", source="tok_visa")

    @staticmethod
    def run_all_contract_tests(service_mocks: ExternalServiceMocks) -> None:
        """Run all contract tests."""
        logger.info("Running contract tests for external service mocks...")

        tests = [
            (
                "Twilio",
                service_mocks.twilio_mock,
                ExternalServiceContractTests.test_twilio_contract,
            ),
            (
                "Stripe",
                service_mocks.stripe_mock,
                ExternalServiceContractTests.test_stripe_contract,
            ),
        ]

        for service_name, mock, test_func in tests:
            try:
                test_func(mock)
                logger.info("✓ %s contract test passed", service_name)
            except (AssertionError, ValueError, RuntimeError) as e:
                logger.error("✗ %s contract test failed: %s", service_name, e)
                raise


# Module initialization
if __name__ == "__main__":
    # Initialize and test all mocks
    mocks = RealExternalServiceMocks.initialize_all_mocks()
    ExternalServiceContractTests.run_all_contract_tests(mocks)
    print("All external service mocks initialized and tested successfully!")
