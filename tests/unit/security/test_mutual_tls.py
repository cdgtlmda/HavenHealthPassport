"""Tests for Mutual TLS Security Module.

This module tests the mutual TLS authentication with real SSL/TLS functionality.
NO MOCKS for production code - Uses real SSL contexts and certificate operations.
Target: 100% statement coverage for security compliance.
"""

import os
import ssl
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.mutual_tls import MutualTLS


class TestCertificateGeneration:
    """Helper class to generate test certificates."""

    @staticmethod
    def generate_private_key():
        """Generate a private key for testing."""
        return rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

    @staticmethod
    def create_test_certificate(
        subject_name: str,
        issuer_key: Any = None,
        issuer_cert: Any = None,
        is_ca: bool = False,
        valid_days: int = 365,
        expired: bool = False,
    ) -> tuple:
        """Create a test certificate for mTLS testing."""
        # Generate private key
        private_key = TestCertificateGeneration.generate_private_key()

        # Create certificate subject
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, subject_name),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Haven Health Test"),
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            ]
        )

        # Set issuer (self-signed if no issuer provided)
        if issuer_cert:
            issuer = issuer_cert.subject
            signing_key = issuer_key
        else:
            issuer = subject
            signing_key = private_key

        # Set validity period
        if expired:
            not_valid_before = datetime.utcnow() - timedelta(days=30)
            not_valid_after = datetime.utcnow() - timedelta(days=1)
        else:
            not_valid_before = datetime.utcnow() - timedelta(days=1)
            not_valid_after = datetime.utcnow() + timedelta(days=valid_days)

        # Create certificate
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(issuer)
        builder = builder.public_key(private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(not_valid_before)
        builder = builder.not_valid_after(not_valid_after)

        # Add extensions
        if is_ca:
            builder = builder.add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )

        # Add key usage
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=is_ca,
                crl_sign=is_ca,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )

        # Sign certificate
        certificate = builder.sign(signing_key, hashes.SHA256(), default_backend())

        return certificate, private_key


@pytest.fixture
def temp_certs():
    """Create temporary certificates for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Generate CA certificate (self-signed)
        ca_cert, ca_key = TestCertificateGeneration.create_test_certificate(
            "Test CA", is_ca=True
        )

        # Generate server certificate (signed by CA)
        server_cert, server_key = TestCertificateGeneration.create_test_certificate(
            "test-server.example.com", issuer_key=ca_key, issuer_cert=ca_cert
        )

        # Generate client certificate (signed by CA)
        client_cert, client_key = TestCertificateGeneration.create_test_certificate(
            "test-client", issuer_key=ca_key, issuer_cert=ca_cert
        )

        # Generate expired certificate
        expired_cert, expired_key = TestCertificateGeneration.create_test_certificate(
            "expired-client", issuer_key=ca_key, issuer_cert=ca_cert, expired=True
        )

        # Generate certificate without digital signature
        no_sig_cert, no_sig_key = TestCertificateGeneration.create_test_certificate(
            "no-sig-client", issuer_key=ca_key, issuer_cert=ca_cert
        )
        # Modify the certificate to remove digital signature usage
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(no_sig_cert.subject)
        builder = builder.issuer_name(no_sig_cert.issuer)
        builder = builder.public_key(no_sig_cert.public_key())
        builder = builder.serial_number(no_sig_cert.serial_number)
        builder = builder.not_valid_before(no_sig_cert.not_valid_before)
        builder = builder.not_valid_after(no_sig_cert.not_valid_after)

        # Add key usage WITHOUT digital signature
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=False,  # This is the key difference
                key_cert_sign=False,
                crl_sign=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )

        no_sig_cert = builder.sign(ca_key, hashes.SHA256(), default_backend())

        # Write certificates to files
        ca_cert_path = temp_path / "ca.crt"
        server_cert_path = temp_path / "server.crt"
        server_key_path = temp_path / "server.key"
        client_cert_path = temp_path / "client.crt"
        client_key_path = temp_path / "client.key"
        expired_cert_path = temp_path / "expired.crt"
        no_sig_cert_path = temp_path / "no_sig.crt"

        # Write CA certificate
        with open(ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

        # Write server certificate and key
        with open(server_cert_path, "wb") as f:
            f.write(server_cert.public_bytes(serialization.Encoding.PEM))
        with open(server_key_path, "wb") as f:
            f.write(
                server_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write client certificate and key
        with open(client_cert_path, "wb") as f:
            f.write(client_cert.public_bytes(serialization.Encoding.PEM))
        with open(client_key_path, "wb") as f:
            f.write(
                client_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write expired certificate
        with open(expired_cert_path, "wb") as f:
            f.write(expired_cert.public_bytes(serialization.Encoding.PEM))

        # Write no-signature certificate
        with open(no_sig_cert_path, "wb") as f:
            f.write(no_sig_cert.public_bytes(serialization.Encoding.PEM))

        yield {
            "ca_cert": str(ca_cert_path),
            "server_cert": str(server_cert_path),
            "server_key": str(server_key_path),
            "client_cert": str(client_cert_path),
            "client_key": str(client_key_path),
            "expired_cert": str(expired_cert_path),
            "no_sig_cert": str(no_sig_cert_path),
        }


class TestMutualTLS:
    """Test mutual TLS functionality with real certificates."""

    def test_initialization_basic(self, temp_certs):
        """Test basic initialization of MutualTLS."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        assert mtls.ca_cert_path == temp_certs["ca_cert"]
        assert mtls.server_cert_path is None
        assert mtls.server_key_path is None
        assert len(mtls.allowed_clients) == 0

    def test_initialization_with_server_certs(self, temp_certs):
        """Test initialization with server certificates."""
        mtls = MutualTLS(
            ca_cert_path=temp_certs["ca_cert"],
            server_cert_path=temp_certs["server_cert"],
            server_key_path=temp_certs["server_key"],
        )

        assert mtls.ca_cert_path == temp_certs["ca_cert"]
        assert mtls.server_cert_path == temp_certs["server_cert"]
        assert mtls.server_key_path == temp_certs["server_key"]
        assert len(mtls.allowed_clients) == 0

    def test_create_server_context_without_server_certs(self, temp_certs):
        """Test server context creation without server certificates."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        context = mtls.create_server_context()

        # Verify SSL context properties
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2

        # Verify security options
        assert context.options & ssl.OP_NO_TLSv1
        assert context.options & ssl.OP_NO_TLSv1_1

    def test_create_server_context_with_server_certs(self, temp_certs):
        """Test server context creation with server certificates."""
        mtls = MutualTLS(
            ca_cert_path=temp_certs["ca_cert"],
            server_cert_path=temp_certs["server_cert"],
            server_key_path=temp_certs["server_key"],
        )

        context = mtls.create_server_context()

        # Verify SSL context properties
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2

        # Verify security options
        assert context.options & ssl.OP_NO_TLSv1
        assert context.options & ssl.OP_NO_TLSv1_1

    def test_create_client_context(self, temp_certs):
        """Test client context creation."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        context = mtls.create_client_context(
            temp_certs["client_cert"], temp_certs["client_key"]
        )

        # Verify SSL context properties
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2
        assert context.check_hostname is True

    def test_validate_client_certificate_valid(self, temp_certs):
        """Test validation of valid client certificate."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        is_valid, error_msg = mtls.validate_client_certificate(
            temp_certs["client_cert"]
        )

        assert is_valid is True
        assert error_msg is None

    def test_validate_client_certificate_expired(self, temp_certs):
        """Test validation of expired certificate."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        is_valid, error_msg = mtls.validate_client_certificate(
            temp_certs["expired_cert"]
        )

        assert is_valid is False
        assert error_msg is not None
        assert "expired" in error_msg.lower()

    def test_validate_client_certificate_no_digital_signature(self, temp_certs):
        """Test validation of certificate without digital signature capability."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        is_valid, error_msg = mtls.validate_client_certificate(
            temp_certs["no_sig_cert"]
        )

        assert is_valid is False
        assert error_msg is not None
        assert "digital signature" in error_msg.lower()

    def test_validate_client_certificate_invalid_file(self, temp_certs):
        """Test validation with invalid certificate file."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        # Create a file with invalid certificate data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as f:
            f.write("INVALID CERTIFICATE DATA")
            invalid_cert_path = f.name

        try:
            is_valid, error_msg = mtls.validate_client_certificate(invalid_cert_path)

            assert is_valid is False
            assert error_msg is not None
            assert len(error_msg) > 0
        finally:
            os.unlink(invalid_cert_path)

    def test_validate_client_certificate_nonexistent_file(self, temp_certs):
        """Test validation with nonexistent certificate file."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        # Production code raises FileNotFoundError for nonexistent files
        with pytest.raises(FileNotFoundError):
            mtls.validate_client_certificate("/nonexistent/path/cert.crt")

    def test_add_allowed_client(self, temp_certs):
        """Test adding allowed client."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        assert len(mtls.allowed_clients) == 0

        mtls.add_allowed_client("test-client")

        assert len(mtls.allowed_clients) == 1
        assert "test-client" in mtls.allowed_clients

    def test_remove_allowed_client(self, temp_certs):
        """Test removing allowed client."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        # Add client first
        mtls.add_allowed_client("test-client")
        mtls.add_allowed_client("another-client")
        assert len(mtls.allowed_clients) == 2

        # Remove one client
        mtls.remove_allowed_client("test-client")

        assert len(mtls.allowed_clients) == 1
        assert "test-client" not in mtls.allowed_clients
        assert "another-client" in mtls.allowed_clients

    def test_remove_nonexistent_client(self, temp_certs):
        """Test removing nonexistent client (should not error)."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        # Try to remove client that doesn't exist
        mtls.remove_allowed_client("nonexistent-client")

        # Should not raise error and set should remain empty
        assert len(mtls.allowed_clients) == 0

    def test_is_client_allowed(self, temp_certs):
        """Test checking if client is allowed."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        # Initially no clients allowed
        assert mtls.is_client_allowed("test-client") is False

        # Add client
        mtls.add_allowed_client("test-client")

        # Now should be allowed
        assert mtls.is_client_allowed("test-client") is True
        assert mtls.is_client_allowed("other-client") is False

    def test_client_allowlist_management_comprehensive(self, temp_certs):
        """Test comprehensive client allowlist management."""
        mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])

        clients = ["client1", "client2", "client3"]

        # Add multiple clients
        for client in clients:
            mtls.add_allowed_client(client)

        # Verify all are allowed
        assert len(mtls.allowed_clients) == 3
        for client in clients:
            assert mtls.is_client_allowed(client) is True

        # Remove middle client
        mtls.remove_allowed_client("client2")

        # Verify remaining clients
        assert len(mtls.allowed_clients) == 2
        assert mtls.is_client_allowed("client1") is True
        assert mtls.is_client_allowed("client2") is False
        assert mtls.is_client_allowed("client3") is True

        # Add duplicate (should not increase count)
        mtls.add_allowed_client("client1")
        assert len(mtls.allowed_clients) == 2


class TestMutualTLSEdgeCases:
    """Test edge cases and error conditions."""

    def test_certificate_validation_future_validity(self, temp_certs):
        """Test certificate that's not yet valid."""
        # Generate certificate valid in the future
        future_cert, _ = TestCertificateGeneration.create_test_certificate(
            "future-client"
        )

        # Modify to be valid in the future
        builder = x509.CertificateBuilder()
        builder = builder.subject_name(future_cert.subject)
        builder = builder.issuer_name(future_cert.issuer)
        builder = builder.public_key(future_cert.public_key())
        builder = builder.serial_number(future_cert.serial_number)
        builder = builder.not_valid_before(
            datetime.utcnow() + timedelta(days=1)
        )  # Future
        builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))

        # Add key usage
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=False,
                crl_sign=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )

        # Re-sign with proper dates
        ca_cert, ca_key = TestCertificateGeneration.create_test_certificate(
            "Test CA", is_ca=True
        )
        future_cert = builder.sign(ca_key, hashes.SHA256(), default_backend())

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".crt", delete=False) as f:
            f.write(future_cert.public_bytes(serialization.Encoding.PEM))
            future_cert_path = f.name

        try:
            # Write CA cert too
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".crt", delete=False
            ) as f:
                f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
                ca_cert_path = f.name

            try:
                mtls = MutualTLS(ca_cert_path=ca_cert_path)
                is_valid, error_msg = mtls.validate_client_certificate(future_cert_path)

                assert is_valid is False
                assert error_msg is not None
                assert "not yet valid" in error_msg.lower()
            finally:
                os.unlink(ca_cert_path)
        finally:
            os.unlink(future_cert_path)

    def test_certificate_without_key_usage_extension(self, temp_certs):
        """Test certificate without key usage extension."""
        # Generate certificate without key usage extension
        private_key = TestCertificateGeneration.generate_private_key()

        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "no-key-usage"),
            ]
        )

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(subject)
        builder = builder.issuer_name(subject)
        builder = builder.public_key(private_key.public_key())
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.not_valid_before(datetime.utcnow() - timedelta(days=1))
        builder = builder.not_valid_after(datetime.utcnow() + timedelta(days=365))

        # Don't add key usage extension
        cert = builder.sign(private_key, hashes.SHA256(), default_backend())

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".crt", delete=False) as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            cert_path = f.name

        try:
            mtls = MutualTLS(ca_cert_path=temp_certs["ca_cert"])
            is_valid, error_msg = mtls.validate_client_certificate(cert_path)

            # Should be valid since key usage extension is optional in validation
            assert is_valid is True
            assert error_msg is None
        finally:
            os.unlink(cert_path)
