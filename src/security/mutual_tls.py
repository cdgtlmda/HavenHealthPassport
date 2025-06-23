"""
Mutual TLS (mTLS) Implementation for Haven Health Passport.

This module provides mutual TLS authentication for secure
client-server communication with certificate-based authentication.
"""

import logging
import ssl
from datetime import datetime
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class MutualTLS:
    """Implements mutual TLS authentication."""

    def __init__(
        self,
        ca_cert_path: str,
        server_cert_path: Optional[str] = None,
        server_key_path: Optional[str] = None,
    ):
        """
        Initialize mutual TLS configuration.

        Args:
            ca_cert_path: Path to CA certificate for client verification
            server_cert_path: Path to server certificate
            server_key_path: Path to server private key
        """
        self.ca_cert_path = ca_cert_path
        self.server_cert_path = server_cert_path
        self.server_key_path = server_key_path
        self.allowed_clients: set[str] = set()

    def create_server_context(self) -> ssl.SSLContext:
        """
        Create SSL context for mTLS server.

        Returns:
            Configured SSL context for server
        """
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

        # Load server certificate and key
        if self.server_cert_path and self.server_key_path:
            context.load_cert_chain(self.server_cert_path, self.server_key_path)
        # Configure client certificate verification
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(self.ca_cert_path)

        # Set secure options
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

        return context

    def create_client_context(
        self, client_cert_path: str, client_key_path: str
    ) -> ssl.SSLContext:
        """
        Create SSL context for mTLS client.

        Args:
            client_cert_path: Path to client certificate
            client_key_path: Path to client private key

        Returns:
            Configured SSL context for client
        """
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        # Load client certificate and key
        context.load_cert_chain(client_cert_path, client_key_path)

        # Load CA certificate for server verification
        context.load_verify_locations(self.ca_cert_path)

        # Set secure options
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        return context

    def validate_client_certificate(self, cert_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a client certificate.

        Args:
            cert_path: Path to client certificate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Load certificate
            with open(cert_path, "rb") as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            # Check certificate validity period
            now = datetime.utcnow()
            if now < cert.not_valid_before:
                return False, "Certificate not yet valid"
            if now > cert.not_valid_after:
                return False, "Certificate has expired"

            # Check certificate purpose
            try:
                key_usage = cert.extensions.get_extension_for_oid(
                    x509.ExtensionOID.KEY_USAGE
                ).value
                if not getattr(key_usage, "digital_signature", False):
                    return False, "Certificate not valid for digital signature"
            except x509.ExtensionNotFound:
                pass

            # Additional checks can be added here

            return True, None

        except (ValueError, AttributeError) as e:
            return False, str(e)

    def add_allowed_client(self, client_cn: str) -> None:
        """Add a client common name to allowed list."""
        self.allowed_clients.add(client_cn)

    def remove_allowed_client(self, client_cn: str) -> None:
        """Remove a client common name from allowed list."""
        self.allowed_clients.discard(client_cn)

    def is_client_allowed(self, client_cn: str) -> bool:
        """Check if client is in allowed list."""
        return client_cn in self.allowed_clients
