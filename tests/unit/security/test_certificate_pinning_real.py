"""
Comprehensive test suite for Certificate Pinning module.

MEDICAL COMPLIANCE: This module requires 100% statement coverage as it handles
security-critical certificate validation to prevent MITM attacks on PHI data.

Uses REAL production code - NO MOCKS for core functionality.
"""

import base64
import hashlib
import ssl
from datetime import datetime, timedelta

import pytest

from src.security.certificate_pinning import CertificatePinning


class TestCertificatePinningReal:
    """Test suite for CertificatePinning using REAL production code."""

    @pytest.fixture
    def sample_cert_der(self):
        """Create sample certificate in DER format for testing."""
        # Real certificate data (simplified for testing)
        return b"FAKE_CERT_DER_DATA_FOR_TESTING_PURPOSES_ONLY"

    @pytest.fixture
    def sample_fingerprint(self, sample_cert_der):
        """Calculate real fingerprint for sample certificate."""
        digest = hashlib.sha256(sample_cert_der).digest()
        return base64.b64encode(digest).decode("ascii")

    @pytest.fixture
    def pinned_certs(self, sample_fingerprint):
        """List of pinned certificate fingerprints."""
        return [
            sample_fingerprint,
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",
        ]

    @pytest.fixture
    def cert_pinning(self, pinned_certs):
        """Create CertificatePinning instance with real pinned certificates."""
        return CertificatePinning(pinned_certs)

    def test_certificate_pinning_initialization(self, cert_pinning, pinned_certs):
        """Test CertificatePinning initialization - covers lines 26-29."""
        # Verify initialization
        assert cert_pinning.pinned_certificates == set(pinned_certs)
        assert isinstance(cert_pinning.pin_expiry, datetime)

        # Verify expiry is set to 30 days from now
        expected_expiry = datetime.utcnow() + timedelta(days=30)
        time_diff = abs((cert_pinning.pin_expiry - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance

        print("✅ CERTIFICATE PINNING INITIALIZATION TESTED")

    def test_get_certificate_fingerprint_real_calculation(
        self, cert_pinning, sample_cert_der
    ):
        """Test real certificate fingerprint calculation - covers lines 31-40."""
        # Calculate fingerprint using REAL production code
        fingerprint = cert_pinning.get_certificate_fingerprint(sample_cert_der)

        # Verify it's a valid base64-encoded SHA256 hash
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 44  # Base64 encoded SHA256 is 44 chars
        assert fingerprint.endswith("=")  # Base64 padding

        # Verify it matches manual calculation
        expected_digest = hashlib.sha256(sample_cert_der).digest()
        expected_fingerprint = base64.b64encode(expected_digest).decode("ascii")
        assert fingerprint == expected_fingerprint

        print("✅ REAL CERTIFICATE FINGERPRINT CALCULATION TESTED")

    def test_get_certificate_fingerprint_different_certs(self, cert_pinning):
        """Test fingerprint calculation with different certificates."""
        cert1 = b"CERTIFICATE_DATA_1"
        cert2 = b"CERTIFICATE_DATA_2"

        fingerprint1 = cert_pinning.get_certificate_fingerprint(cert1)
        fingerprint2 = cert_pinning.get_certificate_fingerprint(cert2)

        # Different certificates should produce different fingerprints
        assert fingerprint1 != fingerprint2
        assert len(fingerprint1) == 44
        assert len(fingerprint2) == 44

        print("✅ DIFFERENT CERTIFICATE FINGERPRINTS TESTED")

    def test_verify_certificate_success(self, cert_pinning, sample_cert_der):
        """Test successful certificate verification - covers lines 42-54."""
        # Verify certificate that is in pinned list
        result = cert_pinning.verify_certificate(sample_cert_der)

        # Should return True for pinned certificate
        assert result is True

        print("✅ SUCCESSFUL CERTIFICATE VERIFICATION TESTED")

    def test_verify_certificate_failure(self, cert_pinning):
        """Test failed certificate verification - covers lines 42-54."""
        # Create certificate that's NOT in pinned list
        unpinned_cert = b"UNPINNED_CERTIFICATE_DATA"

        result = cert_pinning.verify_certificate(unpinned_cert)

        # Should return False for unpinned certificate
        assert result is False

        print("✅ FAILED CERTIFICATE VERIFICATION TESTED")

    def test_verify_certificate_logging_success(
        self, cert_pinning, sample_cert_der, caplog
    ):
        """Test logging for successful verification - covers line 51."""
        # Verify certificate and check logging
        result = cert_pinning.verify_certificate(sample_cert_der)

        assert result is True
        # Verify info log was generated for successful pinning
        assert "Certificate pinning successful" in caplog.text

        print("✅ SUCCESS LOGGING TESTED")

    def test_verify_certificate_logging_failure(self, cert_pinning, caplog):
        """Test logging for failed verification - covers line 54."""
        unpinned_cert = b"UNPINNED_CERTIFICATE_DATA"

        result = cert_pinning.verify_certificate(unpinned_cert)

        assert result is False
        # Verify warning log was generated for failed pinning
        assert "Certificate pinning failed" in caplog.text

        print("✅ FAILURE LOGGING TESTED")

    def test_check_expiry_not_expired(self, cert_pinning):
        """Test expiry check when pins are not expired - covers line 57."""
        # Pins should not be expired (set to 30 days from now)
        result = cert_pinning.check_expiry()

        assert result is False  # Not expired

        print("✅ NON-EXPIRED PINS TESTED")

    def test_check_expiry_expired(self, pinned_certs):
        """Test expiry check when pins are expired - covers line 57."""
        # Create pinning with expired pins
        cert_pinning = CertificatePinning(pinned_certs)

        # Manually set expiry to past date
        cert_pinning.pin_expiry = datetime.utcnow() - timedelta(days=1)

        result = cert_pinning.check_expiry()

        assert result is True  # Expired

        print("✅ EXPIRED PINS TESTED")

    def test_create_pinned_context_real_ssl(self, cert_pinning):
        """Test SSL context creation - covers lines 59-76."""
        # Create SSL context using REAL production code
        context = cert_pinning.create_pinned_context()

        # Verify it's a real SSL context
        assert isinstance(context, ssl.SSLContext)

        # Verify security settings
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

        print("✅ REAL SSL CONTEXT CREATION TESTED")

    def test_create_pinned_context_security_settings(self, cert_pinning):
        """Test SSL context security configuration - covers lines 71-73."""
        context = cert_pinning.create_pinned_context()

        # Verify all security settings are properly configured
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

        # Verify it's using default context as base
        default_context = ssl.create_default_context()
        assert context.protocol == default_context.protocol

        print("✅ SSL SECURITY SETTINGS TESTED")

    def test_pinned_certificates_set_conversion(self, pinned_certs):
        """Test that pinned certificates are converted to set - covers line 28."""
        cert_pinning = CertificatePinning(pinned_certs)

        # Verify pinned_certificates is a set (not list)
        assert isinstance(cert_pinning.pinned_certificates, set)
        assert len(cert_pinning.pinned_certificates) == len(pinned_certs)

        # Verify all certificates are in the set
        for cert in pinned_certs:
            assert cert in cert_pinning.pinned_certificates

        print("✅ SET CONVERSION TESTED")

    def test_empty_pinned_certificates(self):
        """Test initialization with empty pinned certificates list."""
        cert_pinning = CertificatePinning([])

        assert cert_pinning.pinned_certificates == set()
        assert isinstance(cert_pinning.pin_expiry, datetime)

        # Any certificate should fail verification
        test_cert = b"ANY_CERTIFICATE_DATA"
        result = cert_pinning.verify_certificate(test_cert)
        assert result is False

        print("✅ EMPTY PINNED CERTIFICATES TESTED")

    def test_duplicate_pinned_certificates(self):
        """Test initialization with duplicate certificates in list."""
        duplicate_certs = ["CERT1", "CERT2", "CERT1", "CERT3", "CERT2"]
        cert_pinning = CertificatePinning(duplicate_certs)

        # Set should remove duplicates
        assert len(cert_pinning.pinned_certificates) == 3
        assert cert_pinning.pinned_certificates == {"CERT1", "CERT2", "CERT3"}

        print("✅ DUPLICATE CERTIFICATES HANDLING TESTED")

    def test_fingerprint_truncation_in_logs(
        self, cert_pinning, sample_cert_der, caplog
    ):
        """Test fingerprint truncation in log messages - covers fingerprint[:16]."""
        # Test successful verification
        cert_pinning.verify_certificate(sample_cert_der)

        # Get the logged fingerprint
        fingerprint = cert_pinning.get_certificate_fingerprint(sample_cert_der)

        # Verify truncation to 16 characters appears in logs
        assert fingerprint[:16] in caplog.text

        print("✅ FINGERPRINT TRUNCATION IN LOGS TESTED")
