"""
Certificate Validation and Revocation Checking for Haven Health Passport.

This module provides comprehensive certificate validation including
OCSP checking and CRL verification.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.ocsp import OCSPRequestBuilder, OCSPResponseStatus
from cryptography.x509.oid import ExtensionOID, ObjectIdentifier

logger = logging.getLogger(__name__)


class CertificateValidator:
    """Validates certificates and checks revocation status."""

    def __init__(self, ca_bundle_path: Optional[str] = None):
        """
        Initialize certificate validator.

        Args:
            ca_bundle_path: Path to CA bundle for validation
        """
        self.ca_bundle_path = ca_bundle_path
        self.ocsp_cache: Dict[str, Dict[str, Any]] = {}
        self.crl_cache: Dict[str, Dict[str, Any]] = {}

    def validate_certificate_chain(self, cert_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate entire certificate chain.

        Args:
            cert_path: Path to certificate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Load certificate
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            # Basic validation
            basic_valid, error = self._validate_basic(cert)
            if not basic_valid:
                return False, error

            # Check revocation status
            revoked, revocation_error = self.check_revocation(cert)
            if revoked:
                return False, f"Certificate revoked: {revocation_error}"

            return True, None

        except (ValueError, AttributeError) as e:
            return False, f"Validation error: {str(e)}"

    def _validate_basic(self, cert: x509.Certificate) -> Tuple[bool, Optional[str]]:
        """Perform basic certificate validation."""
        now = datetime.utcnow()

        # Check validity period
        if now < cert.not_valid_before:
            return False, "Certificate not yet valid"
        if now > cert.not_valid_after:
            return False, "Certificate has expired"

        # Check key usage
        try:
            key_usage = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
            # Check if the extension value has digital_signature attribute
            if (
                hasattr(key_usage.value, "digital_signature")
                and not key_usage.value.digital_signature
            ):
                return False, "Certificate not valid for digital signatures"
        except x509.ExtensionNotFound:
            pass

        # Check basic constraints for CA certificates
        try:
            basic_constraints = cert.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS
            )
            # Check if the extension value has ca attribute
            if hasattr(basic_constraints.value, "ca") and basic_constraints.value.ca:
                if (
                    hasattr(basic_constraints.value, "path_length")
                    and basic_constraints.value.path_length is not None
                ):
                    # Validate path length constraint
                    pass
        except x509.ExtensionNotFound:
            pass

        return True, None

    def check_revocation(self, cert: x509.Certificate) -> Tuple[bool, Optional[str]]:
        """
        Check certificate revocation status via OCSP.

        Args:
            cert: Certificate to check

        Returns:
            Tuple of (is_revoked, reason)
        """
        # Check cache first
        cert_serial = str(cert.serial_number)
        if cert_serial in self.ocsp_cache:
            cached_result = self.ocsp_cache[cert_serial]
            if cached_result["expires"] > datetime.utcnow():
                return cached_result["revoked"], cached_result["reason"]

        # Try OCSP checking
        try:
            ocsp_url = self._get_ocsp_url(cert)
            if ocsp_url:
                is_revoked, reason = self._check_ocsp(cert, ocsp_url)

                # Cache result
                self.ocsp_cache[cert_serial] = {
                    "revoked": is_revoked,
                    "reason": reason,
                    "expires": datetime.utcnow() + timedelta(hours=1),
                }

                return is_revoked, reason
        except (ValueError, x509.ExtensionNotFound, AttributeError) as e:
            logger.warning("OCSP check failed: %s", e)

        # Fall back to CRL if OCSP fails
        return self._check_crl(cert)

    def _get_ocsp_url(self, cert: x509.Certificate) -> Optional[str]:
        """Extract OCSP URL from certificate."""
        try:
            aia = cert.extensions.get_extension_for_oid(
                ExtensionOID.AUTHORITY_INFORMATION_ACCESS
            )
            # Check if aia.value is iterable
            if hasattr(aia.value, "__iter__"):
                for access in aia.value:
                    if (
                        hasattr(access, "access_method")
                        and access.access_method
                        == x509.AuthorityInformationAccessOID.OCSP
                    ):
                        if hasattr(access, "access_location"):
                            return str(access.access_location.value)
        except x509.ExtensionNotFound:
            pass
        return None

    def _check_ocsp(
        self, cert: x509.Certificate, ocsp_url: str
    ) -> Tuple[bool, Optional[str]]:
        """Check certificate revocation via OCSP."""
        try:
            # Get issuer certificate (in production, this would be from the chain)
            # For now, we'll use a simplified approach
            issuer_cert = self._get_issuer_certificate(cert)
            if not issuer_cert:
                logger.warning("Cannot perform OCSP check without issuer certificate")
                return False, None

            # Build OCSP request
            builder = OCSPRequestBuilder()
            builder = builder.add_certificate(cert, issuer_cert, hashes.SHA256())
            request = builder.build()

            # Serialize request
            request_data = request.public_bytes(serialization.Encoding.DER)

            # Send OCSP request
            headers = {"Content-Type": "application/ocsp-request"}
            response = requests.post(
                ocsp_url, data=request_data, headers=headers, timeout=10
            )

            if response.status_code != 200:
                logger.error("OCSP request failed with status %s", response.status_code)
                return False, None

            # Parse OCSP response
            ocsp_response = x509.ocsp.load_der_ocsp_response(response.content)

            # Check response status
            if ocsp_response.response_status != OCSPResponseStatus.SUCCESSFUL:
                logger.error("OCSP response status: %s", ocsp_response.response_status)
                return False, None

            # Check certificate status
            cert_status = ocsp_response.certificate_status

            if cert_status == x509.ocsp.OCSPCertStatus.GOOD:
                return False, None
            elif cert_status == x509.ocsp.OCSPCertStatus.REVOKED:
                revocation_reason = ocsp_response.revocation_reason
                if revocation_reason:
                    return True, f"Certificate revoked: {revocation_reason.name}"
                return True, "Certificate revoked"
            else:
                # Unknown status
                return False, "Unknown certificate status"

        except (RuntimeError, TypeError, ValueError) as e:
            logger.error("OCSP check failed: %s", e)
            # If OCSP fails, we don't assume revocation
            return False, None

    def _check_crl(self, cert: x509.Certificate) -> Tuple[bool, Optional[str]]:
        """Check certificate revocation via CRL."""
        try:
            # Get CRL distribution points
            crl_urls = self._get_crl_urls(cert)
            if not crl_urls:
                logger.info("No CRL distribution points found in certificate")
                return False, None

            # Try each CRL URL
            for crl_url in crl_urls:
                try:
                    # Check cache first
                    if crl_url in self.crl_cache:
                        cached_crl = self.crl_cache[crl_url]
                        if cached_crl["expires"] > datetime.utcnow():
                            crl = cached_crl["crl"]
                        else:
                            # Cache expired, fetch new CRL
                            crl = self._fetch_crl(crl_url)
                    else:
                        crl = self._fetch_crl(crl_url)

                    # Check if certificate is revoked
                    revoked_cert = crl.get_revoked_certificate_by_serial_number(
                        cert.serial_number
                    )

                    if revoked_cert:
                        revocation_date = revoked_cert.revocation_date
                        reason = "Unknown reason"

                        # Try to get revocation reason
                        try:
                            # CRL reason code OID: 2.5.29.21
                            crl_reason_oid = ObjectIdentifier("2.5.29.21")
                            reason_ext = revoked_cert.extensions.get_extension_for_oid(
                                crl_reason_oid
                            )
                            reason = reason_ext.value.name
                        except x509.ExtensionNotFound:
                            pass

                        return True, f"Revoked on {revocation_date}: {reason}"

                except (RuntimeError, TypeError, ValueError) as e:
                    logger.warning("Failed to check CRL at %s: %s", crl_url, e)
                    continue

            # Certificate not found in any CRL
            return False, None

        except (RuntimeError, TypeError, ValueError) as e:
            logger.error("CRL check failed: %s", e)
            return False, None

    def _get_issuer_certificate(
        self, cert: x509.Certificate
    ) -> Optional[x509.Certificate]:
        """Get issuer certificate for OCSP checking."""
        # In production, this would retrieve the issuer cert from the chain
        # or from the Authority Information Access extension
        try:
            # Check if we have a CA bundle
            if self.ca_bundle_path:
                with open(self.ca_bundle_path, "rb") as f:
                    ca_data = f.read()

                # Parse all certificates in the bundle
                ca_certs = []
                for cert_data in ca_data.split(b"-----END CERTIFICATE-----"):
                    if b"-----BEGIN CERTIFICATE-----" in cert_data:
                        cert_pem = cert_data + b"-----END CERTIFICATE-----"
                        try:
                            ca_cert = x509.load_pem_x509_certificate(
                                cert_pem, default_backend()
                            )
                            ca_certs.append(ca_cert)
                        except (
                            AttributeError,
                            KeyError,
                            OSError,
                            TypeError,
                            ValueError,
                        ):
                            continue

                # Find the issuer
                for ca_cert in ca_certs:
                    if ca_cert.subject == cert.issuer:
                        return ca_cert

        except (
            AttributeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            logger.error("Failed to get issuer certificate: %s", e)

        return None

    def _get_crl_urls(self, cert: x509.Certificate) -> List[str]:
        """Extract CRL distribution points from certificate."""
        urls = []
        try:
            cdp_ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.CRL_DISTRIBUTION_POINTS
            )
            # Check if cdp_ext.value is iterable
            if hasattr(cdp_ext.value, "__iter__"):
                for dp in cdp_ext.value:
                    if hasattr(dp, "full_name") and dp.full_name:
                        for name in dp.full_name:
                            if isinstance(name, x509.UniformResourceIdentifier):
                                urls.append(name.value)
        except x509.ExtensionNotFound:
            pass
        return urls

    def _fetch_crl(self, crl_url: str) -> x509.CertificateRevocationList:
        """Fetch and cache CRL from URL."""
        response = requests.get(crl_url, timeout=30)
        response.raise_for_status()

        # Parse CRL
        crl = x509.load_der_x509_crl(response.content, default_backend())

        # Cache it
        self.crl_cache[crl_url] = {
            "crl": crl,
            "expires": datetime.utcnow() + timedelta(hours=24),  # Cache for 24 hours
        }

        return crl
