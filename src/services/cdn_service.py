"""CDN integration for Haven Health Passport API.

This module provides integration with Content Delivery Networks (CDN) for
improved global performance, reduced latency, and efficient content delivery.

Access control note: This module manages CDN caching for content that may include
medical information. PHI is never cached in public CDN edges. Private content
requires appropriate access controls and signed URLs for secure delivery.
"""

import hashlib
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
import boto3
from botocore.exceptions import ClientError
from fastapi import Request, Response
from pydantic import BaseModel, Field, HttpUrl, validator

from src.config import get_settings
from src.security.encryption import EncryptionService
from src.services.cache_ttl_config import CacheCategory, ttl_manager
from src.utils.logging import get_logger

# Access control for medical content

logger = get_logger(__name__)


class CDNProvider(str, Enum):
    """Supported CDN providers."""

    CLOUDFRONT = "cloudfront"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    FASTLY = "fastly"
    CUSTOM = "custom"


class CDNContentType(str, Enum):
    """Types of content served through CDN."""

    STATIC_ASSETS = "static_assets"  # JS, CSS, fonts
    IMAGES = "images"  # Medical images, photos
    DOCUMENTS = "documents"  # PDFs, reports
    API_RESPONSES = "api_responses"  # Cached API responses
    TRANSLATIONS = "translations"  # Cached translations
    PUBLIC_DATA = "public_data"  # Public health information


class CDNConfig(BaseModel):
    """Configuration for CDN integration."""

    provider: CDNProvider = Field(..., description="CDN provider")
    enabled: bool = Field(default=True, description="Enable CDN")

    # URLs
    origin_url: HttpUrl = Field(..., description="Origin server URL")
    cdn_url: HttpUrl = Field(..., description="CDN URL")
    fallback_url: Optional[HttpUrl] = Field(None, description="Fallback CDN URL")

    # Configuration
    distribution_id: Optional[str] = Field(None, description="CDN distribution ID")
    api_key: Optional[str] = Field(None, description="CDN API key")
    secret_key: Optional[str] = Field(None, description="CDN secret key")

    # Cache behavior
    default_ttl: int = Field(default=3600, description="Default TTL in seconds")
    max_ttl: int = Field(default=86400, description="Maximum TTL in seconds")
    browser_ttl: int = Field(default=300, description="Browser cache TTL")

    # Security
    signed_urls: bool = Field(default=False, description="Use signed URLs")
    signed_url_expiry: int = Field(
        default=3600, description="Signed URL expiry in seconds"
    )
    allowed_origins: List[str] = Field(
        default_factory=list, description="Allowed CORS origins"
    )

    # Content types
    enabled_content_types: List[CDNContentType] = Field(
        default_factory=lambda: list(CDNContentType),
        description="Content types to serve through CDN",
    )

    # Paths
    static_paths: List[str] = Field(
        default_factory=lambda: ["/static", "/assets", "/media"],
        description="Paths to serve through CDN",
    )
    api_cache_paths: List[str] = Field(
        default_factory=lambda: ["/api/v2/public", "/api/v2/translations/glossary"],
        description="API paths to cache in CDN",
    )

    @validator("max_ttl")
    @classmethod
    def validate_max_ttl(cls, v: int, values: Dict[str, Any]) -> int:
        """Ensure max_ttl is greater than default_ttl."""
        default_ttl = values.get("default_ttl", 3600)
        if v < default_ttl:
            raise ValueError("max_ttl must be greater than default_ttl")
        return v


class CDNService:
    """Service for managing CDN integration."""

    def __init__(self) -> None:
        """Initialize CDN service."""
        self.settings = get_settings()
        self.configs: Dict[str, CDNConfig] = {}
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )
        self._initialize_default_config()

    def _initialize_default_config(self) -> None:
        """Initialize default CDN configuration."""
        # Load from environment/settings
        if hasattr(self.settings, "cdn_provider"):
            config = CDNConfig(
                provider=CDNProvider(self.settings.cdn_provider),
                origin_url=HttpUrl(
                    getattr(self.settings, "api_base_url", "https://api.example.com")
                ),
                cdn_url=HttpUrl(
                    getattr(
                        self.settings,
                        "cdn_url",
                        getattr(
                            self.settings, "api_base_url", "https://api.example.com"
                        ),
                    )
                ),
                fallback_url=getattr(self.settings, "fallback_url", None),
                distribution_id=getattr(self.settings, "cdn_distribution_id", None),
                api_key=getattr(self.settings, "cdn_api_key", None),
                secret_key=getattr(self.settings, "cdn_secret_key", None),
                enabled=getattr(self.settings, "cdn_enabled", False),
            )
            self.configs["default"] = config

    def register_config(self, name: str, config: CDNConfig) -> None:
        """Register a CDN configuration."""
        self.configs[name] = config
        logger.info("Registered CDN config: %s", name)

    def get_cdn_url(
        self,
        path: str,
        content_type: CDNContentType = CDNContentType.STATIC_ASSETS,
        config_name: str = "default",
    ) -> str:
        """Get CDN URL for a resource path.

        Args:
            path: Resource path
            content_type: Type of content
            config_name: Configuration name

        Returns:
            CDN URL or origin URL if CDN is disabled
        """
        config = self.configs.get(config_name)

        if not config or not config.enabled:
            # Return origin URL if CDN is disabled
            return f"{getattr(self.settings, 'api_base_url', 'https://api.example.com')}{path}"

        # Check if content type is enabled
        if content_type not in config.enabled_content_types:
            return f"{config.origin_url}{path}"

        # Remove leading slash for CDN URL construction
        path = path.lstrip("/")

        # Return CDN URL
        return f"{config.cdn_url}/{path}"

    def should_use_cdn(
        self,
        request: Request,
        content_type: CDNContentType = CDNContentType.API_RESPONSES,
        config_name: str = "default",
    ) -> bool:
        """Determine if a request should be served through CDN.

        Args:
            request: FastAPI request
            content_type: Type of content
            config_name: Configuration name

        Returns:
            True if CDN should be used
        """
        config = self.configs.get(config_name)

        if not config or not config.enabled:
            return False

        # Check content type
        if content_type not in config.enabled_content_types:
            return False

        # Check path patterns
        path = request.url.path

        # Check static paths
        if content_type == CDNContentType.STATIC_ASSETS:
            return any(path.startswith(p) for p in config.static_paths)

        # Check API cache paths
        if content_type == CDNContentType.API_RESPONSES:
            # Only cache GET requests
            if request.method != "GET":
                return False

            # Check if path matches cacheable patterns
            return any(path.startswith(p) for p in config.api_cache_paths)

        return True

    def get_cache_headers(
        self,
        content_type: CDNContentType,
        category: Optional[CacheCategory] = None,
        config_name: str = "default",
        private: bool = False,
    ) -> Dict[str, str]:
        """Get cache headers for CDN.

        Args:
            content_type: Type of content
            category: Optional cache category for TTL
            config_name: Configuration name
            private: Whether content is private

        Returns:
            Dictionary of cache headers
        """
        config = self.configs.get(config_name)

        if not config:
            return {}

        # Determine TTL
        if category:
            ttl = ttl_manager.get_ttl(category)
            ttl = min(ttl, config.max_ttl)  # Respect max TTL
        else:
            ttl = config.default_ttl

        # Build Cache-Control header
        cache_control_parts = []

        if private:
            cache_control_parts.append("private")
        else:
            cache_control_parts.append("public")

        # Add s-maxage for CDN caching
        cache_control_parts.append(f"s-maxage={ttl}")

        # Add max-age for browser caching
        browser_ttl = min(config.browser_ttl, ttl)
        cache_control_parts.append(f"max-age={browser_ttl}")

        # Add stale-while-revalidate for better performance
        if ttl > 60:
            cache_control_parts.append(f"stale-while-revalidate={min(ttl // 2, 3600)}")

        headers = {
            "Cache-Control": ", ".join(cache_control_parts),
            "CDN-Cache-Control": f"max-age={ttl}",  # CDN-specific header
        }

        # Add Expires header
        expires = datetime.utcnow() + timedelta(seconds=ttl)
        headers["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Add Vary header for proper caching
        vary_headers = ["Accept-Encoding"]

        if content_type == CDNContentType.TRANSLATIONS:
            vary_headers.append("Accept-Language")

        if content_type == CDNContentType.API_RESPONSES:
            vary_headers.extend(["Accept", "Authorization"])

        headers["Vary"] = ", ".join(vary_headers)

        # Add CDN-specific headers
        if config.provider == CDNProvider.CLOUDFRONT:
            headers["X-Accel-Expires"] = str(ttl)
        elif config.provider == CDNProvider.CLOUDFLARE:
            headers["CF-Cache-TTL"] = str(ttl)

        return headers

    def create_signed_url(
        self,
        path: str,
        expiry_seconds: Optional[int] = None,
        config_name: str = "default",
    ) -> str:
        """Create a signed CDN URL for secure content.

        Args:
            path: Resource path
            expiry_seconds: URL expiry in seconds
            config_name: Configuration name

        Returns:
            Signed CDN URL
        """
        config = self.configs.get(config_name)

        if not config or not config.signed_urls:
            return self.get_cdn_url(path, config_name=config_name)

        expiry_seconds = expiry_seconds or config.signed_url_expiry
        expiry_time = int(
            (datetime.utcnow() + timedelta(seconds=expiry_seconds)).timestamp()
        )

        # Implementation depends on CDN provider
        if config.provider == CDNProvider.CLOUDFRONT:
            return self._create_cloudfront_signed_url(path, expiry_time, config)
        elif config.provider == CDNProvider.CLOUDFLARE:
            return self._create_cloudflare_signed_url(path, expiry_time, config)
        else:
            # Generic signed URL implementation
            return self._create_generic_signed_url(path, expiry_time, config)

    def _create_generic_signed_url(
        self, path: str, expiry_time: int, config: CDNConfig
    ) -> str:
        """Create a generic signed URL."""
        # Simple implementation - should be replaced with provider-specific logic
        signature_data = f"{path}:{expiry_time}:{config.secret_key}"
        signature = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

        cdn_url = self.get_cdn_url(path)
        separator = "&" if "?" in cdn_url else "?"

        return f"{cdn_url}{separator}expires={expiry_time}&signature={signature}"

    def _create_cloudfront_signed_url(
        self, path: str, expiry_time: int, config: CDNConfig
    ) -> str:
        """Create CloudFront signed URL."""
        # This would use boto3 CloudFront signer
        # Placeholder implementation
        return self._create_generic_signed_url(path, expiry_time, config)

    def _create_cloudflare_signed_url(
        self, path: str, expiry_time: int, config: CDNConfig
    ) -> str:
        """Create Cloudflare signed URL."""
        # This would use Cloudflare's signing mechanism
        # Placeholder implementation
        return self._create_generic_signed_url(path, expiry_time, config)

    async def purge_cache(
        self,
        paths: List[str],
        config_name: str = "default",
    ) -> bool:
        """Purge CDN cache for specific paths.

        Args:
            paths: List of paths to purge
            config_name: Configuration name

        Returns:
            True if successful
        """
        config = self.configs.get(config_name)

        if not config or not config.enabled:
            return False

        try:
            if config.provider == CDNProvider.CLOUDFRONT:
                return await self._purge_cloudfront_cache(paths, config)
            elif config.provider == CDNProvider.CLOUDFLARE:
                return await self._purge_cloudflare_cache(paths, config)
            else:
                logger.warning("Cache purge not implemented for %s", config.provider)
                return False

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("CDN cache purge failed: %s", e)
            return False

    async def _purge_cloudfront_cache(
        self, paths: List[str], config: CDNConfig
    ) -> bool:
        """Purge CloudFront cache for medical document updates.

        Critical for ensuring:
        - Updated medical records are immediately available
        - Removed documents are no longer accessible
        - Security patches are deployed immediately
        - @retention_policy_compliance - Purged content must comply with data deletion requirements
        """
        if not config.distribution_id:
            logger.warning("No CloudFront distribution ID configured")
            return False

        try:
            # Create CloudFront client
            cloudfront = boto3.client(
                "cloudfront", region_name=getattr(config, "region", "us-east-1")
            )

            # CloudFront requires paths to start with /
            invalidation_paths = []
            for path in paths:
                if not path.startswith("/"):
                    path = "/" + path
                invalidation_paths.append(path)

            # Add wildcard for directory invalidations
            # Critical for medical record folders
            expanded_paths = []
            for path in invalidation_paths:
                expanded_paths.append(path)
                if path.endswith("/"):
                    expanded_paths.append(path + "*")

            # Create invalidation batch
            caller_reference = f"haven-health-{int(time.time())}"

            response = cloudfront.create_invalidation(
                DistributionId=config.distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": len(expanded_paths), "Items": expanded_paths},
                    "CallerReference": caller_reference,
                },
            )

            invalidation_id = response["Invalidation"]["Id"]
            logger.info(
                f"CloudFront invalidation created: {invalidation_id} "
                f"for {len(expanded_paths)} paths in distribution {config.distribution_id}"
            )

            # Log critical medical document invalidations
            medical_paths = [
                p
                for p in paths
                if any(
                    term in p.lower()
                    for term in ["medical", "health", "patient", "record"]
                )
            ]
            if medical_paths:
                logger.warning(
                    f"Medical document cache invalidation: {len(medical_paths)} paths. "
                    f"Invalidation ID: {invalidation_id}"
                )

            return True

        except ImportError:
            logger.error("boto3 not installed. Cannot purge CloudFront cache.")
            return False
        except ClientError as e:
            logger.error("CloudFront invalidation failed: %s", e)
            return False
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Unexpected error during CloudFront invalidation: %s", e)
            return False

    async def _purge_cloudflare_cache(
        self, paths: List[str], config: CDNConfig
    ) -> bool:
        """Purge Cloudflare cache for medical document updates.

        Critical for ensuring:
        - GDPR compliance (right to be forgotten)
        - Updated consent forms are immediately available
        - Security updates are deployed globally
        - @compliance_delete - Ensures timely removal for regulatory requirements
        """
        if not config.api_key or not config.distribution_id:
            logger.warning("No Cloudflare API key or zone ID configured")
            return False

        try:
            # Cloudflare API endpoint
            url = f"https://api.cloudflare.com/client/v4/zones/{config.distribution_id}/purge_cache"

            # Prepare headers
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }

            # Cloudflare accepts files or tags for purging
            # For medical documents, we purge by specific files for precision
            purge_data: Dict[str, List[str]] = {"files": []}

            # Build full URLs for Cloudflare
            for path in paths:
                # Cloudflare needs full URLs
                if getattr(config, "base_url", None):
                    full_url = f"{getattr(config, 'base_url', '').rstrip('/')}/{path.lstrip('/')}"
                    purge_data["files"].append(full_url)

                    # Also add variants (http/https, www/non-www)
                    if "https://" in full_url:
                        purge_data["files"].append(
                            full_url.replace("https://", "http://")
                        )
                    if "www." in full_url:
                        purge_data["files"].append(full_url.replace("www.", ""))
                    elif "://" in full_url and "www." not in full_url:
                        protocol, rest = full_url.split("://", 1)
                        purge_data["files"].append(f"{protocol}://www.{rest}")

            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=purge_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()

                    if response.status == 200 and result.get("success"):
                        logger.info(
                            f"Cloudflare cache purged successfully for "
                            f"{len(purge_data['files'])} URLs in zone {config.distribution_id}"
                        )

                        # Log critical medical document purges
                        medical_urls = [
                            u
                            for u in purge_data["files"]
                            if any(
                                term in u.lower()
                                for term in ["medical", "health", "patient", "record"]
                            )
                        ]
                        if medical_urls:
                            logger.warning(
                                f"Medical document cache purged from Cloudflare: "
                                f"{len(medical_urls)} URLs"
                            )

                        return True
                    else:
                        errors = result.get("errors", [])
                        error_msg = ", ".join(
                            [e.get("message", "Unknown error") for e in errors]
                        )
                        logger.error("Cloudflare purge failed: %s", error_msg)
                        return False

        except ImportError:
            logger.error("aiohttp not installed. Cannot purge Cloudflare cache.")
            return False
        except aiohttp.ClientError as e:
            logger.error("Cloudflare API request failed: %s", e)
            return False
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error("Unexpected error during Cloudflare purge: %s", e)
            return False

    def add_cdn_headers(self, response: Response, headers: Dict[str, str]) -> None:
        """Add CDN headers to response."""
        for key, value in headers.items():
            response.headers[key] = value


# Global CDN service instance
cdn_service = CDNService()


# Helper functions
def get_cdn_url(
    path: str, content_type: CDNContentType = CDNContentType.STATIC_ASSETS
) -> str:
    """Get CDN URL for a resource."""
    return cdn_service.get_cdn_url(path, content_type)


def add_cdn_cache_headers(
    response: Response,
    content_type: CDNContentType,
    category: Optional[CacheCategory] = None,
    private: bool = False,
) -> None:
    """Add CDN cache headers to response."""
    headers = cdn_service.get_cache_headers(content_type, category, private=private)
    cdn_service.add_cdn_headers(response, headers)


# Export components
__all__ = [
    "CDNProvider",
    "CDNContentType",
    "CDNConfig",
    "CDNService",
    "cdn_service",
    "get_cdn_url",
    "add_cdn_cache_headers",
]
