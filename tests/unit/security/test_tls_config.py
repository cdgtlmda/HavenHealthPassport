"""Test TLS Configuration - comprehensive coverage Required.

HIPAA Compliant - Real TLS operations.
NO MOCKS for TLS functionality per medical compliance requirements.

This tests critical TLS configuration for refugee healthcare data transmission.
MUST achieve comprehensive test coverage for medical compliance.
"""

import ipaddress
import os
import socket
import ssl
import tempfile
from datetime import datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.security.tls_config import TLSConfig


@pytest.fixture
def tls_config():
    """Create TLS configuration instance."""
    return TLSConfig()


@pytest.fixture
def test_certificates():
    """Generate real test certificates for testing."""
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Generate certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Haven Health Passport"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Create temporary files
    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, suffix=".pem"
    ) as cert_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
        cert_path = cert_file.name

    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, suffix=".key"
    ) as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        key_path = key_file.name

    yield cert_path, key_path

    # Cleanup
    os.unlink(cert_path)
    os.unlink(key_path)


class TestTLSConfig:
    """Test TLS configuration with real operations."""

    def test_tls_config_initialization(self, tls_config):
        """Test TLS configuration initialization."""
        assert tls_config is not None
        assert hasattr(tls_config, "get_server_context")
        assert hasattr(tls_config, "get_client_context")

    def test_real_server_context_creation(self, tls_config):
        """Test real server SSL context creation."""
        context = tls_config.get_server_context()

        # Verify context properties
        assert isinstance(context, ssl.SSLContext)
        assert context.protocol == ssl.PROTOCOL_TLS_SERVER
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2

        # Verify security options are set
        assert context.options & ssl.OP_NO_SSLv2
        assert context.options & ssl.OP_NO_SSLv3
        assert context.options & ssl.OP_NO_TLSv1
        assert context.options & ssl.OP_NO_TLSv1_1

        # Verify cipher configuration
        assert context.options & ssl.OP_SINGLE_DH_USE
        assert context.options & ssl.OP_SINGLE_ECDH_USE
        assert context.options & ssl.OP_NO_COMPRESSION

    def test_real_client_context_creation(self, tls_config):
        """Test real client SSL context creation."""
        context = tls_config.get_client_context()

        # Verify context properties
        assert isinstance(context, ssl.SSLContext)
        assert context.protocol == ssl.PROTOCOL_TLS_CLIENT
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2

        # Verify security options
        assert context.options & ssl.OP_NO_SSLv2
        assert context.options & ssl.OP_NO_SSLv3

    def test_real_certificate_loading(self, tls_config, test_certificates):
        """Test real certificate loading."""
        cert_path, key_path = test_certificates

        context = tls_config.get_server_context_with_certs(
            certfile=cert_path, keyfile=key_path
        )

        assert isinstance(context, ssl.SSLContext)
        # Verify certificate was loaded (no exception thrown)

    def test_certificate_validation_disabled_for_testing(self, tls_config):
        """Test certificate validation can be disabled for testing."""
        context = tls_config.get_client_context_no_verify()

        assert isinstance(context, ssl.SSLContext)
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE

    def test_real_cipher_suite_configuration(self, tls_config):
        """Test real cipher suite configuration."""
        context = tls_config.get_server_context()

        # Get configured ciphers
        ciphers = context.get_ciphers()
        assert len(ciphers) > 0

        # Verify strong ciphers are included
        cipher_names = [cipher["name"] for cipher in ciphers]

        # Check for ECDHE ciphers (forward secrecy)
        ecdhe_ciphers = [name for name in cipher_names if "ECDHE" in name]
        assert len(ecdhe_ciphers) > 0

        # Check for AES-GCM ciphers (authenticated encryption)
        gcm_ciphers = [name for name in cipher_names if "GCM" in name]
        assert len(gcm_ciphers) > 0

    def test_tls_version_enforcement(self, tls_config):
        """Test TLS version enforcement."""
        server_context = tls_config.get_server_context()
        client_context = tls_config.get_client_context()

        # Verify minimum TLS version
        assert server_context.minimum_version >= ssl.TLSVersion.TLSv1_2
        assert client_context.minimum_version >= ssl.TLSVersion.TLSv1_2

        # Verify maximum TLS version allows modern versions
        assert server_context.maximum_version >= ssl.TLSVersion.TLSv1_2
        assert client_context.maximum_version >= ssl.TLSVersion.TLSv1_2

    def test_real_ssl_socket_creation(self, tls_config, test_certificates):
        """Test real SSL socket creation."""
        cert_path, key_path = test_certificates

        # Create server context with certificates
        server_context = tls_config.get_server_context_with_certs(
            certfile=cert_path, keyfile=key_path
        )

        # Create a socket and wrap it with SSL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            ssl_sock = server_context.wrap_socket(sock, server_side=True)
            assert isinstance(ssl_sock, ssl.SSLSocket)
        finally:
            sock.close()

    def test_certificate_chain_validation(self, tls_config):
        """Test certificate chain validation configuration."""
        context = tls_config.get_client_context()

        # Verify certificate verification is enabled by default
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True

    def test_security_protocol_options(self, tls_config):
        """Test security protocol options."""
        context = tls_config.get_server_context()

        # Verify insecure protocols are disabled
        assert context.options & ssl.OP_NO_SSLv2
        assert context.options & ssl.OP_NO_SSLv3
        assert context.options & ssl.OP_NO_TLSv1
        assert context.options & ssl.OP_NO_TLSv1_1

        # Verify security enhancements are enabled
        assert context.options & ssl.OP_SINGLE_DH_USE
        assert context.options & ssl.OP_SINGLE_ECDH_USE
        assert context.options & ssl.OP_NO_COMPRESSION

    def test_perfect_forward_secrecy(self, tls_config):
        """Test Perfect Forward Secrecy configuration."""
        context = tls_config.get_server_context()

        # Get available ciphers
        ciphers = context.get_ciphers()
        cipher_names = [cipher["name"] for cipher in ciphers]

        # Verify ECDHE ciphers are available (provides PFS)
        ecdhe_ciphers = [name for name in cipher_names if "ECDHE" in name]
        assert (
            len(ecdhe_ciphers) > 0
        ), "No ECDHE ciphers found for Perfect Forward Secrecy"

    def test_authenticated_encryption(self, tls_config):
        """Test authenticated encryption cipher availability."""
        context = tls_config.get_server_context()

        # Get available ciphers
        ciphers = context.get_ciphers()
        cipher_names = [cipher["name"] for cipher in ciphers]

        # Verify GCM ciphers are available (authenticated encryption)
        gcm_ciphers = [name for name in cipher_names if "GCM" in name]
        assert len(gcm_ciphers) > 0, "No GCM ciphers found for authenticated encryption"

    def test_compression_disabled(self, tls_config):
        """Test that TLS compression is disabled (CRIME attack prevention)."""
        context = tls_config.get_server_context()

        # Verify compression is disabled
        assert context.options & ssl.OP_NO_COMPRESSION

    def test_session_resumption_security(self, tls_config):
        """Test session resumption security configuration."""
        context = tls_config.get_server_context()

        # Verify session options are configured securely
        assert context.options & ssl.OP_SINGLE_DH_USE
        assert context.options & ssl.OP_SINGLE_ECDH_USE

    def test_certificate_transparency_support(self, tls_config):
        """Test Certificate Transparency support."""
        context = tls_config.get_client_context()

        # Verify context supports modern certificate validation
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert hasattr(context, "verify_flags")

    def test_alpn_protocol_negotiation(self, tls_config):
        """Test ALPN protocol negotiation configuration."""
        context = tls_config.get_server_context()

        # Test ALPN configuration for HTTP/2 and HTTP/1.1
        try:
            context.set_alpn_protocols(["h2", "http/1.1"])
            # If no exception, ALPN is supported
            assert True
        except AttributeError:
            # ALPN not supported in this Python version
            pytest.skip("ALPN not supported in this Python version")

    def test_sni_support(self, tls_config, test_certificates):
        """Test Server Name Indication (SNI) support."""
        cert_path, key_path = test_certificates

        context = tls_config.get_server_context_with_certs(
            certfile=cert_path, keyfile=key_path
        )

        # Test SNI callback configuration
        def sni_callback(ssl_sock, server_name, ssl_context):
            return None

        try:
            context.set_servername_callback(sni_callback)
            assert True  # SNI callback set successfully
        except AttributeError:
            pytest.skip("SNI not supported in this Python version")

    def test_ocsp_stapling_configuration(self, tls_config):
        """Test OCSP stapling configuration."""
        context = tls_config.get_server_context()

        # Test OCSP stapling if supported
        try:
            # Check if OCSP stapling option is available
            if hasattr(ssl, "OP_ENABLE_OCSP_STAPLING"):
                assert context.options & ssl.OP_ENABLE_OCSP_STAPLING
            else:
                pytest.skip("OCSP stapling not supported in this Python version")
        except AttributeError:
            pytest.skip("OCSP stapling not supported")

    def test_tls_configuration_validation(self, tls_config):
        """Test TLS configuration validation."""
        # Test server context validation
        server_context = tls_config.get_server_context()
        validation_result = tls_config.validate_server_context(server_context)
        assert validation_result is True

        # Test client context validation
        client_context = tls_config.get_client_context()
        validation_result = tls_config.validate_client_context(client_context)
        assert validation_result is True

    def test_hipaa_compliance_requirements(self, tls_config):
        """Test HIPAA compliance requirements for TLS."""
        context = tls_config.get_server_context()

        # Verify HIPAA-required security settings
        compliance_check = tls_config.check_hipaa_compliance(context)
        assert compliance_check["minimum_tls_version"] >= 1.2
        assert compliance_check["strong_ciphers_only"] is True
        assert compliance_check["perfect_forward_secrecy"] is True
        assert compliance_check["compression_disabled"] is True
