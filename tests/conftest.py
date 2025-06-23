"""Test configuration for the Haven Health Passport project.

This module configures the test environment, including database setup
and medical compliance enforcement.
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
import requests
import stripe
from cryptography.fernet import Fernet
from fhirclient import client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from twilio.rest import Client

from src.core.database import Base
from tests.config.localstack_aws_setup import LocalStackAWSServices
from tests.config.real_test_config import RealTestConfig
from tests.config.test_database_schema import (
    EmergencyAccess,
    Patient,
    create_test_schema,
)

# Set testing environment BEFORE any other imports
os.environ["TESTING"] = "true"

# Configure strict medical compliance logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [MEDICAL_COMPLIANCE] %(message)s",
)


# Medical compliance markers - register custom markers
def pytest_configure(config):
    """Register custom markers for medical compliance."""
    config.addinivalue_line(
        "markers", "fhir_compliance: mark test as requiring FHIR compliance"
    )
    config.addinivalue_line(
        "markers", "hipaa_required: mark test as requiring HIPAA compliance"
    )
    config.addinivalue_line(
        "markers", "emergency_access: mark test as handling emergency access"
    )
    config.addinivalue_line(
        "markers", "phi_encryption: mark test as requiring PHI encryption"
    )
    config.addinivalue_line(
        "markers", "audit_required: mark test as requiring audit logging"
    )
    config.addinivalue_line("markers", "blockchain_safe: mark test as blockchain safe")


# Global test encryption key (for test data only)
TEST_ENCRYPTION_KEY = Fernet.generate_key()
FERNET = Fernet(TEST_ENCRYPTION_KEY)

# Medical compliance flags
ENFORCE_HIPAA = True
ENFORCE_FHIR = True
ENFORCE_AUDIT = True
ENFORCE_ENCRYPTION = True

# Override database URL for testing - Use PostgreSQL for production code coverage
TEST_DATABASE_URL = (
    "postgresql://test_user:test_password@localhost:5432/haven_health_test"
)


class MedicalComplianceError(Exception):
    """Raised when tests violate medical compliance standards."""


class PHILeakageError(Exception):
    """CRITICAL: Raised when unencrypted PHI is detected."""


@pytest.fixture(scope="session")
def medical_compliance_config() -> Dict[str, Any]:
    """Global medical compliance configuration for all tests."""
    return {
        "fhir_version": "R4",
        "hipaa_compliance": True,
        "encryption_algorithm": "AES-256-GCM",
        "audit_retention_days": 2555,  # 7 years for HIPAA
        "min_password_length": 12,
        "session_timeout_minutes": 15,
        "max_login_attempts": 3,
        "phi_fields": [
            "patient_id",
            "name",
            "date_of_birth",
            "ssn",
            "medical_record_number",
            "diagnosis",
            "medication",
            "procedure",
            "lab_result",
            "address",
            "phone",
        ],
        "required_audit_fields": [
            "user_id",
            "timestamp",
            "action",
            "resource_type",
            "resource_id",
            "ip_address",
            "success",
            "reason",
        ],
    }


@pytest.fixture
def encrypt_phi():
    """Fixture to encrypt PHI data for testing."""

    def _encrypt(data: str) -> bytes:
        if not data:
            raise ValueError("Cannot encrypt empty PHI data")
        return FERNET.encrypt(data.encode())

    return _encrypt


@pytest.fixture
def decrypt_phi():
    """Fixture to decrypt PHI data for testing."""

    def _decrypt(encrypted_data: bytes) -> str:
        return FERNET.decrypt(encrypted_data).decode()

    return _decrypt


@pytest.fixture
def hipaa_audit_logger():
    """HIPAA-compliant audit logger for all PHI access in tests."""
    audit_logs = []

    def log_access(
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        success: bool = True,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        audit_entry = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,  # READ, WRITE, DELETE, UPDATE
            "resource_type": resource_type,
            "resource_id": resource_id,
            "success": success,
            "reason": reason,
            "test_context": True,
        }
        audit_logs.append(audit_entry)
        logging.info("HIPAA_AUDIT: %s", audit_entry)
        return audit_entry

    # Return logger function and logs for verification
    def get_logs() -> List[Dict[str, Any]]:
        return audit_logs

    # Create a namespace object to hold the function and its utilities
    class AuditLogger:
        def __call__(
            self,
            user_id: str,
            action: str,
            resource_type: str,
            resource_id: str,
            success: bool = True,
            reason: Optional[str] = None,
        ) -> Dict[str, Any]:
            return log_access(
                user_id, action, resource_type, resource_id, success, reason
            )

        def get_logs(self) -> List[Dict[str, Any]]:
            return get_logs()

        def clear(self) -> None:
            audit_logs.clear()

    return AuditLogger()


@pytest.fixture
def fhir_validator():
    """FHIR resource validator for medical data compliance."""

    def validate_resource(resource: Dict[str, Any]) -> bool:
        """Validate FHIR resource structure and required fields."""
        # Check resourceType
        if "resourceType" not in resource:
            raise MedicalComplianceError("Missing resourceType in FHIR resource")

        # Check for id
        if "id" not in resource:
            raise MedicalComplianceError("Missing id in FHIR resource")

        # Resource-specific validation
        resource_type = resource["resourceType"]

        if resource_type == "Patient":
            required = ["identifier", "name", "gender", "birthDate"]
            for field in required:
                if field not in resource:
                    raise MedicalComplianceError(
                        f"Missing required field '{field}' in Patient resource"
                    )

        elif resource_type == "Observation":
            required = ["status", "code", "subject"]
            for field in required:
                if field not in resource:
                    raise MedicalComplianceError(
                        f"Missing required field '{field}' in Observation resource"
                    )

        elif resource_type == "MedicationRequest":
            required = ["status", "intent", "medication", "subject"]
            for field in required:
                if field not in resource:
                    raise MedicalComplianceError(
                        f"Missing required field '{field}' in MedicationRequest"
                    )

        return True

    return validate_resource


@pytest.fixture
def blockchain_phi_validator():
    """Validate that NO unencrypted PHI is ever stored on blockchain."""
    phi_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
        r"\b\d{4}-\d{2}-\d{2}\b",  # Dates (potential DOB)
        r"(?i)(patient|name|diagnosis|medication|procedure)",
        r"(?i)(ssn|social.?security|date.?of.?birth|dob)",
        r"(?i)(medical.?record|mrn|health|treatment)",
    ]

    def validate_no_phi(data: Any) -> bool:
        """Ensure data contains no unencrypted PHI before blockchain storage."""
        # Convert to string for pattern matching
        if isinstance(data, dict):
            data_str = json.dumps(data)
        else:
            data_str = str(data)

        # Check for PHI patterns
        for pattern in phi_patterns:
            if re.search(pattern, data_str):
                raise PHILeakageError(
                    f"CRITICAL: Unencrypted PHI detected! Pattern '{pattern}' found. "
                    "This would violate HIPAA if stored on blockchain."
                )

        # Ensure only hashes or encrypted data
        if len(data_str) > 64 and not data_str.startswith(
            ("0x", "hash:", "encrypted:")
        ):
            logging.warning(
                "Suspicious data length (%d) for blockchain storage", len(data_str)
            )

        return True

    return validate_no_phi


@pytest.fixture
def emergency_access_context():
    """Context manager for emergency access scenarios with full audit trail."""

    class EmergencyAccess:
        def __init__(self):
            self.active = False
            self.reason = None
            self.authorized_by = None
            self.patient_id = None
            self.start_time = None
            self.audit_entries = []

        def activate(self, patient_id: str, reason: str, authorized_by: str) -> None:
            self.active = True
            self.patient_id = patient_id
            self.reason = reason
            self.authorized_by = authorized_by
            self.start_time = datetime.utcnow()

            audit_entry = {
                "event": "EMERGENCY_ACCESS_ACTIVATED",
                "patient_id": patient_id,
                "reason": reason,
                "authorized_by": authorized_by,
                "timestamp": self.start_time.isoformat(),
            }
            self.audit_entries.append(audit_entry)
            logging.critical("EMERGENCY ACCESS: %s", audit_entry)

        def deactivate(self):
            if self.active:
                end_time = datetime.utcnow()
                duration = (
                    (end_time - self.start_time).total_seconds()
                    if self.start_time
                    else 0
                )

                audit_entry = {
                    "event": "EMERGENCY_ACCESS_DEACTIVATED",
                    "patient_id": self.patient_id,
                    "duration_seconds": duration,
                    "timestamp": end_time.isoformat(),
                }
                self.audit_entries.append(audit_entry)
                logging.critical("EMERGENCY ACCESS ENDED: %s", audit_entry)

            self.active = False
            self.reason = None
            self.authorized_by = None
            self.patient_id = None

    return EmergencyAccess()


@pytest.fixture
def create_test_patient(phi_encryptor, validator):
    """Create a FHIR-compliant test patient with encrypted PHI."""

    def _create(
        patient_id: str = "test-patient-001",
        name: str = "Test Patient",
        gender: str = "unknown",
        birth_date: str = "1990-01-01",
    ) -> Dict[str, Any]:
        # Encrypt sensitive fields
        encrypted_name = phi_encryptor(name).decode("utf-8")

        patient = {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [
                {"system": "http://haven-health.org/refugee-id", "value": patient_id}
            ],
            "name": [{"_encrypted": True, "encryptedData": encrypted_name}],
            "gender": gender,
            "birthDate": birth_date,
            "_security": {"encryption": "AES-256-GCM", "encryptedFields": ["name"]},
        }

        # Validate FHIR compliance
        validator(patient)
        return patient

    return _create


@pytest.fixture(autouse=True)
def enforce_medical_compliance(request):
    """Automatically enforce medical compliance for all tests."""
    # Log test execution for audit
    test_name = request.node.name
    logging.info("Starting medical compliance test: %s", test_name)

    # Pre-test compliance checks
    if "blockchain" in test_name.lower() and "phi" in test_name.lower():
        logging.warning("Testing blockchain with PHI - ensuring encryption")

    yield  # Run the test

    # Post-test compliance verification
    if hasattr(request.node, "compliance_violations"):
        violations = request.node.compliance_violations
        if violations:
            raise MedicalComplianceError(
                f"Test '{test_name}' had {len(violations)} compliance violations: {violations}"
            )


# Test environment configuration
@pytest.fixture(scope="session")
def test_environment():
    """Configure test environment with medical compliance settings."""
    os.environ["HIPAA_COMPLIANCE_MODE"] = "STRICT"
    os.environ["FHIR_VALIDATION"] = "ENABLED"
    os.environ["PHI_ENCRYPTION_REQUIRED"] = "TRUE"
    os.environ["AUDIT_ALL_ACCESS"] = "TRUE"
    os.environ["BLOCKCHAIN_PHI_CHECK"] = "ENABLED"

    yield

    # Cleanup is handled by pytest


# Compliance violation tracking handled by the first pytest_configure above


# Hook to check compliance after each test
def pytest_runtest_makereport(item, call):
    """Check for compliance violations after each test."""
    if call.when == "call":
        # Check for any PHI leakage or compliance issues
        if hasattr(item, "compliance_report"):
            report = item.compliance_report
            if report.get("phi_leaked", False):
                item.compliance_violations = ["PHI leakage detected"]
            if report.get("audit_missing", False):
                item.compliance_violations = ["Audit logging missing"]


# ==================== REAL SERVICE FIXTURES ====================
# These fixtures provide REAL service connections for testing
# NO MOCKS - Lives depend on accurate testing


@pytest.fixture(scope="session")
def real_test_services():
    """Provide all REAL test services for the entire test session.

    This includes real database, Redis, Elasticsearch, AWS services, etc.
    """
    # Initialize all real services
    services = RealTestConfig.get_real_test_services()

    # Create database schema
    create_test_schema(services.database.bind)

    yield services

    # Cleanup after all tests
    RealTestConfig.cleanup_test_data(services)
    services.database.close()


@pytest.fixture
def real_db_session(real_test_services):
    """Provide a real database session with transaction rollback."""
    session = real_test_services.database

    # Begin a transaction
    session.begin_nested()

    yield session

    # Rollback to keep test data isolated
    session.rollback()


@pytest.fixture
def real_patient_repository(db_session, test_services):
    """Provide real patient repository with actual database operations."""

    class RealPatientRepository:
        def __init__(self, session, encryption_service, audit_service):
            self.session = session
            self.encryption = encryption_service
            self.audit_service = audit_service

        def create(self, patient_data):
            """Create patient with real encryption and database storage."""
            # Encrypt PHI fields
            patient = Patient(
                id=uuid.uuid4(),
                first_name_encrypted=self.encryption.encrypt_phi(
                    patient_data["firstName"],
                    {"field": "first_name", "patient_id": str(uuid.uuid4())},
                ),
                last_name_encrypted=self.encryption.encrypt_phi(
                    patient_data["lastName"], {"field": "last_name"}
                ),
                date_of_birth_encrypted=self.encryption.encrypt_phi(
                    patient_data["dateOfBirth"], {"field": "date_of_birth"}
                ),
                medical_record_number=patient_data.get(
                    "mrn", f"MRN{uuid.uuid4().hex[:8]}"
                ),
                refugee_id=patient_data.get("refugeeId", f"REF{uuid.uuid4().hex[:8]}"),
                gender=patient_data.get("gender", "unknown"),
                nationality=patient_data.get("nationality", "unknown"),
                preferred_language=patient_data.get("language", "en"),
            )

            # Add to real database
            self.session.add(patient)
            self.session.commit()

            # Create audit log entry
            self.audit_service.log_access(
                user_id="test-user",
                action="CREATE",
                resource_type="Patient",
                resource_id=str(patient.id),
                details={"test_context": True},
            )

            return patient

        def find_by_id(self, patient_id):
            """Find patient with real database query."""
            patient = self.session.query(Patient).filter_by(id=patient_id).first()

            if patient:
                # Log access
                self.audit_service.log_access(
                    user_id="test-user",
                    action="READ",
                    resource_type="Patient",
                    resource_id=str(patient.id),
                )

            return patient

    return RealPatientRepository(
        db_session, test_services.encryption_service, test_services.audit_service
    )


@pytest.fixture
def real_fhir_client(test_services):
    """Provide real FHIR client for medical data validation."""
    return test_services.fhir_client


@pytest.fixture
def real_blockchain_service(test_services):
    """Provide real blockchain service for verification testing."""

    class RealBlockchainService:
        def __init__(self, web3):
            self.web3 = web3
            self.contract_address = None
            self.contract_abi = self._get_verification_contract_abi()

        def _get_verification_contract_abi(self):
            """Get the ABI for the verification smart contract."""
            return [
                {
                    "inputs": [
                        {"name": "patientId", "type": "string"},
                        {"name": "recordHash", "type": "bytes32"},
                        {"name": "providerId", "type": "address"},
                    ],
                    "name": "createVerification",
                    "outputs": [{"name": "", "type": "bytes32"}],
                    "type": "function",
                },
                {
                    "inputs": [{"name": "verificationId", "type": "bytes32"}],
                    "name": "getVerification",
                    "outputs": [
                        {"name": "patientId", "type": "string"},
                        {"name": "recordHash", "type": "bytes32"},
                        {"name": "providerId", "type": "address"},
                        {"name": "timestamp", "type": "uint256"},
                        {"name": "isValid", "type": "bool"},
                    ],
                    "type": "function",
                },
            ]

        def deploy_contract(self):
            """Deploy real smart contract to test blockchain."""
            # In real implementation, this would compile and deploy the contract
            # For testing, we'll use a pre-deployed address
            self.contract_address = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
            return self.web3.eth.contract(
                address=self.contract_address, abi=self.contract_abi
            )

        def create_verification(self, patient_id, record_hash):
            """Create real blockchain verification."""
            contract = self.deploy_contract()

            # Ensure no PHI in the data
            if len(patient_id) > 32 or any(c.isalpha() for c in patient_id[8:]):
                raise ValueError("Patient ID appears to contain PHI")

            # Create transaction
            tx_hash = contract.functions.createVerification(
                patient_id,
                self.web3.keccak(text=record_hash),
                self.web3.eth.default_account,
            ).transact()

            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            return {
                "tx_hash": receipt.transactionHash.hex(),
                "block_number": receipt.blockNumber,
                "gas_used": receipt.gasUsed,
            }

    return RealBlockchainService(test_services.blockchain_web3)


@pytest.fixture
def real_emergency_access_service(real_db_session, real_test_services):
    """Provide real emergency access service with full audit trail."""

    class RealEmergencyAccessService:
        def __init__(self, session, audit_service):
            self.session = session
            self.audit = audit_service

        def grant_emergency_access(self, patient_id, provider_id, reason):
            """Grant real emergency access with database record."""
            # Create emergency access record
            emergency_access = EmergencyAccess(
                patient_id=patient_id,
                provider_id=provider_id,
                reason=reason,
                severity="critical",
                access_expires_at=datetime.utcnow() + timedelta(hours=1),
            )

            self.session.add(emergency_access)
            self.session.commit()

            # Create audit log
            self.audit.log_access(
                user_id=str(provider_id),
                action="EMERGENCY_ACCESS",
                resource_type="Patient",
                resource_id=str(patient_id),
                details={
                    "reason": reason,
                    "emergency_access_id": str(emergency_access.id),
                },
            )

            return emergency_access

    return RealEmergencyAccessService(real_db_session, real_test_services.audit_service)


# Update the test environment fixture to use real services
@pytest.fixture(scope="session", autouse=True)
def setup_real_test_environment():
    """Set up real test environment with actual service connections."""
    # Ensure we're in test mode but with REAL services
    os.environ["TESTING"] = "true"
    os.environ["USE_REAL_SERVICES"] = "true"
    os.environ["DATABASE_TRANSACTIONS"] = "true"  # For rollback support

    # Medical compliance settings remain strict
    os.environ["HIPAA_COMPLIANCE_MODE"] = "STRICT"
    os.environ["FHIR_VALIDATION"] = "ENABLED"
    os.environ["PHI_ENCRYPTION_REQUIRED"] = "TRUE"
    os.environ["AUDIT_ALL_ACCESS"] = "TRUE"
    os.environ["BLOCKCHAIN_PHI_CHECK"] = "ENABLED"

    # Create test database engine
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    yield

    # Cleanup
    engine.dispose()
    # PostgreSQL cleanup happens via transaction rollback, no file to remove


@pytest.fixture
def real_twilio_service():
    """Provide real Twilio service for SMS/Voice testing."""
    # Use test credentials if available
    account_sid = os.environ.get("TEST_TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TEST_TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        pytest.skip("Twilio test credentials not available")

    return Client(account_sid, auth_token)


@pytest.fixture
def real_stripe_service():
    """Provide real Stripe service for payment testing."""
    # Use test API key if available
    api_key = os.environ.get("TEST_STRIPE_API_KEY")

    if not api_key:
        pytest.skip("Stripe test API key not available")

    stripe.api_key = api_key
    return stripe


@pytest.fixture
def real_sendgrid_service():
    """Provide real SendGrid service for email testing."""
    # Use test API key if available
    api_key = os.environ.get("TEST_SENDGRID_API_KEY")

    if not api_key:
        pytest.skip("SendGrid test API key not available")

    return SendGridAPIClient(api_key)


@pytest.fixture
def real_fhir_service():
    """Provide real FHIR server connection."""
    # Use test FHIR server if available
    fhir_base_url = os.environ.get("TEST_FHIR_SERVER_URL", "http://localhost:8080/fhir")

    fhir_client_settings = {"app_id": "haven_health_test", "api_base": fhir_base_url}
    return client.FHIRClient(settings=fhir_client_settings)


@pytest.fixture
def real_government_api_service():
    """Provide real government API connection for refugee verification."""
    # Use test API endpoint if available
    api_base_url = os.environ.get("TEST_GOV_API_URL")
    api_key = os.environ.get("TEST_GOV_API_KEY")

    if not api_base_url or not api_key:
        pytest.skip("Government API test credentials not available")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_key}"})
    return session


# Update the real patient repository to include notification capability
@pytest.fixture
def real_patient_service(
    real_patient_repository, real_twilio_service, real_sendgrid_service
):
    """Provide real patient service with notification capabilities."""

    class RealPatientService:
        def __init__(self, repository, sms_service, email_service):
            self.repository = repository
            self.sms = sms_service
            self.email = email_service

        async def create_patient_with_notifications(self, patient_data):
            """Create patient and send welcome notifications."""
            # Create patient in real database
            patient = self.repository.create(patient_data)

            # Send welcome SMS with real Twilio (if phone provided)
            if patient_data.get("phone") and self.sms:
                try:
                    self.sms.messages.create(
                        to=patient_data["phone"],
                        from_=os.environ.get("TEST_TWILIO_FROM_NUMBER", "+15005550006"),
                        body=f"Welcome to Haven Health, {patient_data['firstName']}! Your health passport is ready.",
                    )
                except (ValueError, AttributeError, RuntimeError) as e:
                    logging.warning("SMS notification failed: %s", e)

            # Send welcome email with real SendGrid (if email provided)
            if patient_data.get("email") and self.email:
                try:
                    message = Mail(
                        from_email="welcome@havenhealth.org",
                        to_emails=patient_data["email"],
                        subject="Welcome to Haven Health Passport",
                        html_content=f"<p>Dear {patient_data['firstName']}, your health passport has been created.</p>",
                    )
                    self.email.send(message)
                except (ValueError, AttributeError, RuntimeError) as e:
                    logging.warning("Email notification failed: %s", e)

            return patient

    return RealPatientService(
        real_patient_repository, real_twilio_service, real_sendgrid_service
    )


# ==================== AWS SERVICES FIXTURES ====================
# Real AWS service fixtures using LocalStack


@pytest.fixture(scope="session")
def aws_services(real_test_services):
    """Provide initialized LocalStack AWS services for testing."""
    # Initialize AWS services
    aws = LocalStackAWSServices()
    aws.initialize_all_services()

    # Store AWS clients in real_test_services for easy access
    real_test_services.s3_client = aws._get_client("s3")
    real_test_services.kms_client = aws._get_client("kms")
    real_test_services.dynamodb_client = aws._get_client("dynamodb")
    real_test_services.sqs_client = aws._get_client("sqs")
    real_test_services.sns_client = aws._get_client("sns")
    real_test_services.lambda_client = aws._get_client("lambda")
    real_test_services.secretsmanager_client = aws._get_client("secretsmanager")

    return aws


@pytest.fixture
def s3_bucket(aws_services):
    """Provide S3 bucket for medical document storage."""
    return "haven-health-medical-documents"


@pytest.fixture
def kms_key_id(aws_services):
    """Provide KMS key ID for PHI encryption."""
    return "alias/haven-health-master-key"


@pytest.fixture
def document_queue_url(aws_services):
    """Provide SQS queue URL for document processing."""
    sqs = aws_services._get_client("sqs")
    response = sqs.get_queue_url(QueueName="haven-health-document-processing")
    return response["QueueUrl"]


@pytest.fixture
def session_table(aws_services):
    """Provide DynamoDB table name for session management."""
    return "haven-health-sessions"


@pytest.fixture
def emergency_topic_arn(aws_services):
    """Provide SNS topic ARN for emergency alerts."""
    sns = aws_services._get_client("sns")
    topics = sns.list_topics()

    for topic in topics["Topics"]:
        if "emergency-alerts" in topic["TopicArn"]:
            return topic["TopicArn"]

    raise ValueError("Emergency alerts topic not found")


# Update the real test services fixture to include AWS
@pytest.fixture(scope="session")
def real_test_services_with_aws(real_test_services, aws_services):
    """Provide all real test services including AWS."""
    # AWS services are already attached in aws_services fixture
    return real_test_services


# Helper fixture for S3 document uploads
@pytest.fixture
def s3_document_uploader(real_test_services_with_aws, s3_bucket, kms_key_id):
    """Provide helper for uploading encrypted documents to S3."""

    class S3DocumentUploader:
        def __init__(self, s3_client, kms_client, bucket, key_id):
            self.s3 = s3_client
            self.kms = kms_client
            self.bucket = bucket
            self.key_id = key_id

        def upload_medical_document(self, patient_id, document_type, content, filename):
            """Upload encrypted medical document with metadata."""
            key = f"patients/{patient_id}/{document_type}/{filename}"

            # Encrypt content if not already encrypted
            if isinstance(content, str):
                content = content.encode()

            # Upload with encryption and metadata
            response = self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self.key_id,
                Metadata={
                    "patient-id": patient_id,
                    "document-type": document_type,
                    "upload-timestamp": str(int(time.time())),
                    "hipaa-compliant": "true",
                },
                ContentType=self._get_content_type(filename),
            )

            return {
                "bucket": self.bucket,
                "key": key,
                "etag": response["ETag"],
                "version_id": response.get("VersionId"),
            }

        def _get_content_type(self, filename):
            """Determine content type from filename."""
            ext = filename.lower().split(".")[-1]
            content_types = {
                "pdf": "application/pdf",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "json": "application/json",
                "xml": "application/xml",
            }
            return content_types.get(ext, "application/octet-stream")

    return S3DocumentUploader(
        real_test_services_with_aws.s3_client,
        real_test_services_with_aws.kms_client,
        s3_bucket,
        kms_key_id,
    )


# Helper fixture for DynamoDB operations
@pytest.fixture
def dynamodb_helper(real_test_services_with_aws):
    """Provide helper for DynamoDB operations."""

    class DynamoDBHelper:
        def __init__(self, dynamodb_client):
            self.dynamodb = dynamodb_client

        def create_session(self, session_id, user_id, ttl_seconds=3600):
            """Create user session with TTL."""
            item = {
                "session_id": {"S": session_id},
                "user_id": {"S": user_id},
                "created_at": {"N": str(int(time.time()))},
                "expires_at": {"N": str(int(time.time() + ttl_seconds))},
                "last_activity": {"N": str(int(time.time()))},
                "ip_address": {"S": "127.0.0.1"},
                "user_agent": {"S": "TestRunner/1.0"},
            }

            self.dynamodb.put_item(TableName="haven-health-sessions", Item=item)

            return item

        def add_offline_sync_record(self, device_id, patient_id, data):
            """Add offline sync record."""
            item = {
                "device_id": {"S": device_id},
                "sync_timestamp": {"N": str(int(time.time() * 1000))},
                "patient_id": {"S": patient_id},
                "sync_status": {"S": "pending"},
                "data": {"S": json.dumps(data)},
                "retry_count": {"N": "0"},
            }

            self.dynamodb.put_item(TableName="haven-health-offline-sync", Item=item)

            return item

    return DynamoDBHelper(real_test_services_with_aws.dynamodb_client)


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def override_get_db(db_session):
    """Override the get_db dependency for testing."""

    def _get_test_db():
        try:
            yield db_session
        finally:
            pass

    return _get_test_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables and database."""
    # Set test environment variables
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["TESTING"] = "true"

    # Create test database engine
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    yield

    # Cleanup test database
    if os.path.exists("test.db"):
        os.remove("test.db")
