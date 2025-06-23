"""
TLS Configuration for Haven Health Passport.

This module provides TLS configuration including cipher suites,
protocols, and certificate management.
"""

import ssl
from typing import Optional


class TLSConfig:
    """Manages TLS configuration for secure connections."""

    # Recommended cipher suites for TLS 1.3 and 1.2
    CIPHER_SUITES = [
        # TLS 1.3 cipher suites (automatically selected for TLS 1.3)
        "TLS_AES_256_GCM_SHA384",
        "TLS_AES_128_GCM_SHA256",
        "TLS_CHACHA20_POLY1305_SHA256",
        # TLS 1.2 cipher suites (perfect forward secrecy)
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
    ]

    def __init__(self, cert_path: Optional[str] = None, key_path: Optional[str] = None):
        """
        Initialize TLS configuration.

        Args:
            cert_path: Path to SSL certificate
            key_path: Path to private key
        """
        self.cert_path = cert_path
        self.key_path = key_path

    def create_ssl_context(
        self, purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH
    ) -> ssl.SSLContext:
        """
        Create SSL context with secure configuration.

        Args:
            purpose: SSL purpose (SERVER_AUTH or CLIENT_AUTH)

        Returns:
            Configured SSL context
        """
        # Create context with secure defaults
        context = ssl.create_default_context(purpose)

        # Set minimum TLS version to 1.2
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        # Disable weak protocols
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1

        # Enable perfect forward secrecy
        context.options |= ssl.OP_SINGLE_DH_USE
        context.options |= ssl.OP_SINGLE_ECDH_USE

        # Disable compression (CRIME attack)
        context.options |= ssl.OP_NO_COMPRESSION

        # Set cipher suites
        context.set_ciphers(":".join(self.CIPHER_SUITES))

        # Load certificate and key if provided
        if self.cert_path and self.key_path:
            context.load_cert_chain(self.cert_path, self.key_path)

        # Enable OCSP stapling
        if hasattr(ssl, "OP_ENABLE_OCSP_STAPLING"):
            context.options |= ssl.OP_ENABLE_OCSP_STAPLING

        return context

    def get_nginx_config(self) -> str:
        """
        Get Nginx SSL configuration.

        Returns:
            Nginx SSL configuration string
        """
        return f"""
# SSL Configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers '{':'.join(self.CIPHER_SUITES)}';
ssl_prefer_server_ciphers on;
ssl_ecdh_curve secp384r1;

# SSL session configuration
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
ssl_session_tickets off;

# OCSP stapling
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;

# Security headers
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        """

    def get_apache_config(self) -> str:
        """
        Get Apache SSL configuration.

        Returns:
            Apache SSL configuration string
        """
        return f"""
# SSL Configuration
SSLEngine on
SSLProtocol -all +TLSv1.2 +TLSv1.3
SSLCipherSuite {':'.join(self.CIPHER_SUITES)}
SSLHonorCipherOrder on

# Security headers
Header always set Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
Header always set X-Frame-Options "DENY"
Header always set X-Content-Type-Options "nosniff"
        """
