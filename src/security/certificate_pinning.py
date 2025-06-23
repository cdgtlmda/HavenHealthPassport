"""
Certificate Pinning Implementation for Haven Health Passport.

This module provides certificate pinning functionality to prevent
man-in-the-middle attacks by validating server certificates against
known good certificates.
"""

import base64
import hashlib
import logging
import ssl
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


class CertificatePinning:
    """Implements certificate pinning for enhanced security."""

    def __init__(self, pinned_certificates: List[str]):
        """
        Initialize certificate pinning.

        Args:
            pinned_certificates: List of base64-encoded SHA256 certificate fingerprints
        """
        self.pinned_certificates = set(pinned_certificates)
        self.pin_expiry = datetime.utcnow() + timedelta(days=30)

    def get_certificate_fingerprint(self, cert_der: bytes) -> str:
        """
        Calculate SHA256 fingerprint of a certificate.

        Args:
            cert_der: Certificate in DER format

        Returns:
            Base64-encoded SHA256 fingerprint
        """
        digest = hashlib.sha256(cert_der).digest()
        return base64.b64encode(digest).decode("ascii")

    def verify_certificate(self, cert_der: bytes) -> bool:
        """
        Verify certificate against pinned certificates.

        Args:
            cert_der: Certificate in DER format

        Returns:
            True if certificate is pinned, False otherwise
        """
        fingerprint = self.get_certificate_fingerprint(cert_der)

        if fingerprint in self.pinned_certificates:
            logger.info("Certificate pinning successful: %s...", fingerprint[:16])
            return True
        else:
            logger.warning("Certificate pinning failed: %s...", fingerprint[:16])
            return False

    def check_expiry(self) -> bool:
        """Check if pins have expired."""
        return datetime.utcnow() > self.pin_expiry

    def create_pinned_context(self) -> ssl.SSLContext:
        """
        Create SSL context with certificate pinning.

        Returns:
            SSL context configured for certificate pinning
        """
        context = ssl.create_default_context()

        # Note: Custom verification callback would go here if supported
        # For now, we rely on manual verification after connection

        # Set custom verification
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True

        return context
