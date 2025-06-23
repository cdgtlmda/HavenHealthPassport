"""
Contract Tests for External Service Mocks.

These tests ensure our mocks accurately simulate real API behavior
This is critical to catch integration issues before they affect refugees
"""

import time

import boto3
import pytest

from tests.mocks.external_services import (
    ExternalServiceContractTests,
    RealExternalServiceMocks,
)


@pytest.fixture
def external_mocks():
    """Provide initialized external service mocks."""
    return RealExternalServiceMocks.initialize_all_mocks()


@pytest.mark.contract
class TestTwilioContract:
    """Contract tests for Twilio SMS/Voice service mock."""

    def test_sms_valid_format(self, mocks):
        """Test SMS with valid phone numbers and content."""
        result = mocks.twilio_mock.send_sms(
            to="+12025551234",
            from_="+15555551234",
            body="Your appointment is confirmed for tomorrow at 2pm",
        )

        # Verify response format matches Twilio API
        assert result["sid"].startswith("SM")
        assert len(result["sid"]) == 34  # Twilio SID format
        assert result["to"] == "+12025551234"
        assert result["from"] == "+15555551234"
        assert result["status"] in ["queued", "sent", "delivered"]
        assert float(result["price"]) > 0
        assert result["price_unit"] == "USD"
        assert "created_at" in result

    def test_sms_invalid_phone_number(self, mocks):
        """Test SMS validation for phone numbers."""
        # Missing + prefix
        with pytest.raises(ValueError, match="Invalid.*phone number"):
            mocks.twilio_mock.send_sms(
                to="12025551234", from_="+15555551234", body="Test"
            )

        # Too short
        with pytest.raises(ValueError):
            mocks.twilio_mock.send_sms(to="+123", from_="+15555551234", body="Test")

        # Contains letters
        with pytest.raises(ValueError):
            mocks.twilio_mock.send_sms(
                to="+1202555ABCD", from_="+15555551234", body="Test"
            )

    def test_sms_body_validation(self, mocks):
        """Test SMS body length limits."""
        # Empty body
        with pytest.raises(ValueError, match="SMS body must be"):
            mocks.twilio_mock.send_sms(to="+12025551234", from_="+15555551234", body="")

        # Too long (>1600 chars)
        long_body = "A" * 1601
        with pytest.raises(ValueError, match="SMS body must be"):
            mocks.twilio_mock.send_sms(
                to="+12025551234", from_="+15555551234", body=long_body
            )

    def test_sms_rate_limiting(self, mocks):
        """Test rate limiting behavior."""
        # Send 100 messages (should work)
        for i in range(100):
            mocks.twilio_mock.send_sms(
                to=f"+1202555{i:04d}", from_="+15555551234", body=f"Message {i}"
            )

        # 101st message should fail
        with pytest.raises(Exception, match="Rate limit exceeded"):
            mocks.twilio_mock.send_sms(
                to="+12025559999", from_="+15555551234", body="Over limit"
            )

    def test_voice_call_format(self, mocks):
        """Test voice call response format."""
        result = mocks.twilio_mock.make_call(
            to="+12025551234", from_="+15555551234", url="https://example.com/twiml"
        )

        assert result["sid"].startswith("CA")
        assert len(result["sid"]) == 34
        assert result["status"] == "initiated"
        assert "created_at" in result


@pytest.mark.contract
class TestStripeContract:
    """Contract tests for Stripe payment processing mock."""

    def test_charge_creation_valid(self, mocks):
        """Test valid charge creation."""
        charge = mocks.stripe_mock.create_charge(
            amount=2500,  # $25.00
            currency="usd",
            source="tok_visa",
            description="Haven Health - Patient registration",
        )

        # Verify Stripe charge format
        assert charge["id"].startswith("ch_")
        assert len(charge["id"]) == 27  # ch_ + 24 hex chars
        assert charge["amount"] == 2500
        assert charge["currency"] == "usd"
        assert charge["status"] == "succeeded"
        assert charge["paid"] is True
        assert charge["refunded"] is False
        assert isinstance(charge["created"], int)
        assert charge["created"] > 0

    def test_charge_validation(self, mocks):
        """Test charge validation rules."""
        # Negative amount
        with pytest.raises(ValueError, match="Amount must be positive"):
            mocks.stripe_mock.create_charge(
                amount=-100, currency="usd", source="tok_visa"
            )

        # Zero amount
        with pytest.raises(ValueError, match="Amount must be positive"):
            mocks.stripe_mock.create_charge(amount=0, currency="usd", source="tok_visa")

        # Invalid currency
        with pytest.raises(ValueError, match="Unsupported currency"):
            mocks.stripe_mock.create_charge(
                amount=1000, currency="xyz", source="tok_visa"
            )

        # Invalid source
        with pytest.raises(ValueError, match="Invalid payment source"):
            mocks.stripe_mock.create_charge(
                amount=1000, currency="usd", source="invalid_token"
            )

    def test_customer_creation(self, mocks):
        """Test customer creation with payment source."""
        customer = mocks.stripe_mock.create_customer(
            email="patient@example.com", source="card_1234567890"
        )

        assert customer["id"].startswith("cus_")
        assert customer["email"] == "patient@example.com"
        assert len(customer["sources"]) == 1
        assert customer["sources"][0] == "card_1234567890"
        assert isinstance(customer["created"], int)


@pytest.mark.contract
class TestSendGridContract:
    """Contract tests for SendGrid email service mock."""

    def test_email_send_valid(self, mocks):
        """Test valid email sending."""
        result = mocks.sendgrid_mock.send_email(
            to="patient@example.com",
            from_="noreply@havenhealth.org",
            subject="Welcome to Haven Health",
            content="Your health passport is ready!",
        )

        # Verify SendGrid response format
        assert result["message_id"].startswith("msg_")
        assert result["to"] == "patient@example.com"
        assert result["from"] == "noreply@havenhealth.org"
        assert result["status"] == "delivered"
        assert "created_at" in result
        assert "delivered_at" in result
        assert result["delivered_at"] > result["created_at"]

    def test_email_validation(self, mocks):
        """Test email address validation."""
        # Invalid recipient
        with pytest.raises(ValueError, match="Invalid recipient email"):
            mocks.sendgrid_mock.send_email(
                to="not-an-email",
                from_="noreply@havenhealth.org",
                subject="Test",
                content="Test",
            )

        # Invalid sender
        with pytest.raises(ValueError, match="Invalid sender email"):
            mocks.sendgrid_mock.send_email(
                to="patient@example.com",
                from_="invalid@",
                subject="Test",
                content="Test",
            )

    def test_email_templates(self, mocks):
        """Test email template system."""
        # Verify templates exist
        templates = mocks.sendgrid_mock.templates
        assert "patient-welcome" in templates
        assert "appointment-reminder" in templates
        assert "emergency-alert" in templates

        # Send with template
        result = mocks.sendgrid_mock.send_email(
            to="patient@example.com",
            from_="noreply@havenhealth.org",
            subject="Welcome",
            content="",
            template_id="patient-welcome",
        )

        assert result["template_id"] == "patient-welcome"


@pytest.mark.contract
class TestExternalFHIRContract:
    """Contract tests for external FHIR server mock."""

    def test_create_patient_resource(self, mocks):
        """Test creating FHIR Patient resource."""
        patient_resource = {
            "resourceType": "Patient",
            "identifier": [{"system": "http://hospital.org/mrn", "value": "12345"}],
            "name": [{"family": "Doe", "given": ["John"]}],
            "gender": "male",
            "birthDate": "1990-01-01",
        }

        result = mocks.external_fhir_mock.create_resource("Patient", patient_resource)

        # Verify FHIR resource format
        assert result["id"].startswith("patient-")
        assert result["resourceType"] == "Patient"
        assert "meta" in result
        assert "versionId" in result["meta"]
        assert "lastUpdated" in result["meta"]

        # Original data preserved
        assert result["identifier"] == patient_resource["identifier"]
        assert result["name"] == patient_resource["name"]

    def test_resource_type_validation(self, mocks):
        """Test FHIR resource type validation."""
        # Invalid resource type
        with pytest.raises(ValueError, match="Invalid resource type"):
            mocks.external_fhir_mock.create_resource("InvalidType", {})

        # Mismatched resource type
        with pytest.raises(ValueError, match="Resource type mismatch"):
            mocks.external_fhir_mock.create_resource(
                "Patient", {"resourceType": "Observation"}
            )

    def test_search_resources(self, mocks):
        """Test FHIR search functionality."""
        # Create some resources first
        for i in range(3):
            mocks.external_fhir_mock.create_resource(
                "Patient",
                {"resourceType": "Patient", "gender": "male" if i < 2 else "female"},
            )

        # Search by gender
        results = mocks.external_fhir_mock.search_resources(
            "Patient", {"gender": "male"}
        )

        assert results["resourceType"] == "Bundle"
        assert results["type"] == "searchset"
        assert results["total"] == 2
        assert len(results["entry"]) == 2
        assert all(e["resource"]["gender"] == "male" for e in results["entry"])


@pytest.mark.contract
class TestGovernmentAPIContract:
    """Contract tests for government refugee API mock."""

    def test_verify_refugee_status_valid(self, mocks):
        """Test valid refugee status verification."""
        result = mocks.government_api_mock.verify_refugee_status(
            refugee_id="UNHCR-2024-12345", country="Syria"
        )

        assert result["verified"] is True
        assert result["refugee_id"] == "UNHCR-2024-12345"
        assert result["status"] == "active"
        assert result["country_of_origin"] == "Syria"
        assert "registration_date" in result
        assert "verification_timestamp" in result

    def test_verify_refugee_status_invalid(self, mocks):
        """Test invalid refugee ID verification."""
        result = mocks.government_api_mock.verify_refugee_status(
            refugee_id="INVALID-ID", country="Syria"
        )

        assert result["verified"] is False
        assert result["refugee_id"] == "INVALID-ID"
        assert "error" in result
        assert "not found" in result["error"]

    def test_travel_clearance_check(self, mocks):
        """Test travel clearance validation."""
        # Allowed country
        result = mocks.government_api_mock.check_travel_clearance(
            refugee_id="UNHCR-2024-12345", destination_country="Germany"
        )

        assert result["clearance_granted"] is True
        assert result["destination"] == "Germany"
        assert "valid_until" in result
        assert len(result["restrictions"]) == 0

        # Restricted country
        result = mocks.government_api_mock.check_travel_clearance(
            refugee_id="UNHCR-2024-12345", destination_country="Country1"
        )

        assert result["clearance_granted"] is False
        assert "Country1" in result["restrictions"]

    def test_api_response_timing(self, mocks):
        """Test API simulates realistic response times."""
        start_time = time.time()

        mocks.government_api_mock.verify_refugee_status(
            refugee_id="UNHCR-2024-12345", country="Syria"
        )

        elapsed = time.time() - start_time

        # Should have some delay to simulate network/processing
        assert elapsed >= 0.1


@pytest.mark.contract
class TestLocalStackResources:
    """Test LocalStack AWS resource initialization."""

    def test_s3_buckets_created(self):
        """Verify S3 buckets are properly configured."""
        s3 = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        # List buckets
        response = s3.list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]

        expected_buckets = [
            "haven-medical-documents",
            "haven-patient-photos",
            "haven-audit-logs",
        ]

        for bucket in expected_buckets:
            assert bucket in bucket_names

            # Check versioning
            versioning = s3.get_bucket_versioning(Bucket=bucket)
            assert versioning.get("Status") == "Enabled"

            # Check encryption
            try:
                encryption = s3.get_bucket_encryption(Bucket=bucket)
                assert "ServerSideEncryptionConfiguration" in encryption
            except s3.exceptions.ServerSideEncryptionConfigurationNotFoundError:
                pytest.fail(f"Bucket {bucket} missing encryption")

    def test_kms_keys_created(self):
        """Verify KMS keys are properly configured."""
        kms = boto3.client(
            "kms",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        # List keys
        response = kms.list_keys()
        assert len(response["Keys"]) >= 2

        # Verify key tags
        for key in response["Keys"]:
            tags = kms.list_resource_tags(KeyId=key["KeyId"])
            tag_dict = {t["TagKey"]: t["TagValue"] for t in tags.get("Tags", [])}

            if tag_dict.get("Purpose") == "PHI_ENCRYPTION":
                assert tag_dict.get("Compliance") == "HIPAA"

    def test_dynamodb_tables_created(self):
        """Verify DynamoDB tables are properly configured."""
        dynamodb = boto3.client(
            "dynamodb",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        # List tables
        response = dynamodb.list_tables()
        table_names = response["TableNames"]

        expected_tables = ["haven-sessions", "haven-offline-queue"]

        for table in expected_tables:
            assert table in table_names

            # Check table configuration
            desc = dynamodb.describe_table(TableName=table)
            assert (
                desc["Table"]["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST"
            )

            if table == "haven-sessions":
                # Check stream is enabled
                assert "StreamSpecification" in desc["Table"]
                assert desc["Table"]["StreamSpecification"]["StreamEnabled"] is True


@pytest.mark.contract
def test_all_contracts_pass(mocks):
    """Run all contract tests to ensure mocks are properly configured."""
    ExternalServiceContractTests.run_all_contract_tests(mocks)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
