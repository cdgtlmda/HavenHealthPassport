"""CDN integration for file delivery.

Note: This module handles PHI-related file delivery through CDN.
- Access Control: Implement strict access control for CDN operations and signed URL generation
"""

import base64
import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import boto3
from botocore.exceptions import ClientError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import (
    dsa,
    ec,
    ed448,
    ed25519,
    padding,
    rsa,
)

from src.core.config import default_aws_config as settings
from src.models.file_attachment import FileAttachment
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CDNIntegration:
    """Manages CDN integration for file delivery."""

    def __init__(self) -> None:
        """Initialize CDN integration."""
        self.cdn_base_url = os.getenv(
            "CDN_BASE_URL", "https://cdn.havenhealthpassport.org"
        )
        self.cloudfront_distribution_id = os.getenv("CLOUDFRONT_DISTRIBUTION_ID")
        self.cloudfront_key_pair_id = os.getenv("CLOUDFRONT_KEY_PAIR_ID")
        self.cloudfront_private_key = os.getenv("CLOUDFRONT_PRIVATE_KEY", "")

        # Initialize CloudFront client if AWS is configured
        if hasattr(settings, "aws_access_key_id"):
            self.cloudfront_client = boto3.client(
                "cloudfront",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
        else:
            self.cloudfront_client = None

        # Cache control settings by file type
        self.cache_policies = {
            "public": {
                "max_age": 31536000,  # 1 year
                "s_maxage": 31536000,
                "public": True,
            },
            "private": {
                "max_age": 0,
                "s_maxage": 0,
                "private": True,
                "no_cache": True,
            },
            "medical": {
                "max_age": 3600,  # 1 hour
                "s_maxage": 3600,
                "private": True,
            },
        }

    def get_cdn_url(
        self,
        file: FileAttachment,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """Get CDN URL for a file.

        Args:
            file: File attachment
            expires_in: Seconds until URL expires (for private files)
            download: Force download instead of inline display

        Returns:
            CDN URL for the file
        """
        # Determine if file should be served publicly
        is_public = self._is_public_file(file)

        if is_public:
            # Public URL without signing
            return f"{self.cdn_base_url}/{file.s3_key}"
        else:
            # Generate signed URL for private files
            return self._generate_signed_url(
                file.s3_key,
                expires_in=expires_in,
                download=download,
            )

    def _is_public_file(self, file: FileAttachment) -> bool:
        """Check if file should be served publicly.

        Args:
            file: File attachment

        Returns:
            True if file is public
        """
        # Only certain categories can be public
        public_categories = ["public_health_info", "educational_material"]

        # Check if file is marked as public and in allowed category
        return file.metadata.get("public", False) and file.category in public_categories

    def _generate_signed_url(
        self,
        s3_key: str,
        expires_in: int = 3600,
        download: bool = False,
    ) -> str:
        """Generate CloudFront signed URL.

        Args:
            s3_key: S3 object key
            expires_in: Seconds until expiration
            download: Force download

        Returns:
            Signed URL
        """
        if not self.cloudfront_private_key:
            # Fallback to unsigned URL if no private key
            return f"{self.cdn_base_url}/{s3_key}"

        # Create CloudFront signed URL
        url = f"{self.cdn_base_url}/{s3_key}"

        # Add query parameters
        params = {}
        if download:
            params["response-content-disposition"] = "attachment"

        if params:
            url += "?" + urlencode(params)

        # Calculate expiration time
        expire_time = int(time.time() + expires_in)

        # Create policy
        policy = {
            "Statement": [
                {
                    "Resource": url,
                    "Condition": {"DateLessThan": {"AWS:EpochTime": expire_time}},
                }
            ]
        }

        # Sign the policy
        policy_str = json.dumps(policy, separators=(",", ":"))
        signature = self._create_signature(policy_str)

        # Create signed URL parameters
        signed_params = {
            "Policy": self._url_safe_base64_encode(policy_str),
            "Signature": signature,
            "Key-Pair-Id": self.cloudfront_key_pair_id,
        }

        # Add signed parameters to URL
        separator = "&" if "?" in url else "?"
        signed_url = url + separator + urlencode(signed_params)

        return signed_url

    def _create_signature(self, message: str) -> str:
        """Create RSA signature for CloudFront.

        Args:
            message: Message to sign

        Returns:
            Base64 encoded signature
        """
        # Load private key
        private_key = serialization.load_pem_private_key(
            self.cloudfront_private_key.encode(),
            password=None,
            backend=default_backend(),
        )

        # Sign the message - handle different key types

        message_bytes = message.encode()

        if isinstance(private_key, rsa.RSAPrivateKey):
            signature = private_key.sign(
                message_bytes, padding.PKCS1v15(), hashes.SHA256()
            )
        elif isinstance(private_key, dsa.DSAPrivateKey):
            signature = private_key.sign(message_bytes, hashes.SHA256())
        elif isinstance(private_key, ec.EllipticCurvePrivateKey):
            signature = private_key.sign(message_bytes, ec.ECDSA(hashes.SHA256()))
        elif isinstance(
            private_key, (ed25519.Ed25519PrivateKey, ed448.Ed448PrivateKey)
        ):
            signature = private_key.sign(message_bytes)
        else:
            raise ValueError(f"Unsupported key type: {type(private_key)}")

        return self._url_safe_base64_encode(signature)

    def _url_safe_base64_encode(self, data: Any) -> str:
        """URL-safe base64 encode data.

        Args:
            data: Data to encode

        Returns:
            URL-safe base64 encoded string
        """
        if isinstance(data, str):
            data = data.encode()

        encoded = base64.b64encode(data).decode()
        # Make URL-safe
        return encoded.replace("+", "-").replace("/", "_").replace("=", "~")

    def get_cache_headers(self, file: FileAttachment) -> Dict[str, str]:
        """Get cache control headers for a file.

        Args:
            file: File attachment

        Returns:
            Dictionary of cache headers
        """
        # Determine cache policy
        if self._is_public_file(file):
            policy = self.cache_policies["public"]
        elif file.category in ["medical_record", "lab_result", "prescription"]:
            policy = self.cache_policies["medical"]
        else:
            policy = self.cache_policies["private"]

        # Build cache control header
        cache_parts = []

        if policy.get("public"):
            cache_parts.append("public")
        elif policy.get("private"):
            cache_parts.append("private")

        if policy.get("no_cache"):
            cache_parts.append("no-cache")

        if policy.get("max_age") is not None:
            cache_parts.append(f"max-age={policy['max_age']}")

        if policy.get("s_maxage") is not None:
            cache_parts.append(f"s-maxage={policy['s_maxage']}")

        headers = {
            "Cache-Control": ", ".join(cache_parts),
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }

        # Add content type
        if file.content_type:
            headers["Content-Type"] = str(file.content_type)

        return headers

    def invalidate_cache(self, file_keys: List[str]) -> Optional[str]:
        """Invalidate CDN cache for specific files.

        Args:
            file_keys: List of S3 keys to invalidate

        Returns:
            Invalidation ID if successful
        """
        if not self.cloudfront_client or not self.cloudfront_distribution_id:
            logger.warning("CloudFront not configured for cache invalidation")
            return None

        try:
            # Create invalidation paths
            paths = [f"/{key}" for key in file_keys]

            response = self.cloudfront_client.create_invalidation(
                DistributionId=self.cloudfront_distribution_id,
                InvalidationBatch={
                    "Paths": {
                        "Quantity": len(paths),
                        "Items": paths,
                    },
                    "CallerReference": str(int(time.time())),
                },
            )

            invalidation_id: str = response["Invalidation"]["Id"]
            logger.info(f"Created CloudFront invalidation: {invalidation_id}")
            return invalidation_id

        except ClientError as e:
            logger.error(f"Failed to create CloudFront invalidation: {e}")
            return None

    def prefetch_to_edge(self, file_keys: List[str]) -> bool:
        """Prefetch files to CDN edge locations.

        Args:
            file_keys: List of S3 keys to prefetch

        Returns:
            True if prefetch initiated
        """
        # This would typically involve:
        # 1. Warming the cache by requesting files from multiple edge locations
        # 2. Using CloudFront APIs to push content
        # For now, this is a placeholder
        logger.info(f"Prefetching {len(file_keys)} files to CDN edge locations")
        return True
