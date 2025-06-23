"""Test configuration settings for Haven Health Passport.

This configuration is used during test execution and overrides
default settings to ensure tests run in isolation without affecting
production systems.
"""

import os
import tempfile
from typing import Any, Dict

from .default import DEFAULT_CONFIG

# Start with default configuration
TEST_CONFIG: Dict[str, Any] = DEFAULT_CONFIG.copy()

# Override settings for testing
TEST_CONFIG.update(
    {
        # Application Settings
        "DEBUG": True,
        "TESTING": True,
        # API Settings
        "API_HOST": "127.0.0.1",
        "API_PORT": 8001,  # Different port to avoid conflicts
        "API_WORKERS": 1,  # Single worker for predictable testing
        "API_LOG_LEVEL": "debug",
        # Security Settings - Test keys only
        "SECRET_KEY": "test-secret-key-do-not-use-in-production",
        "JWT_EXPIRE_MINUTES": 5,  # Short expiry for testing
        "PASSWORD_MIN_LENGTH": 8,  # Relaxed for test users
        # Database Settings - Test database
        "DATABASE_URL": os.getenv(
            "TEST_DATABASE_URL", "postgresql://test:test@localhost/haven_test"
        ),
        "DATABASE_POOL_SIZE": 5,  # Smaller pool for tests
        "DATABASE_ECHO": True,  # Log SQL for debugging
        # Redis Settings - Test instance
        "REDIS_URL": os.getenv(
            "TEST_REDIS_URL", "redis://localhost:6379/1"  # Use database 1 for tests
        ),
        "REDIS_MAX_CONNECTIONS": 10,  # Smaller pool for tests
        # AWS Settings - LocalStack or mocks
        "AWS_ENDPOINT_URL": os.getenv(
            "AWS_ENDPOINT_URL", "http://localhost:4566"  # LocalStack endpoint
        ),
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_REGION": "us-east-1",
        "S3_BUCKET": "test-haven-health",
        # Healthcare Standards - Relaxed for testing
        "FHIR_VALIDATION_ENABLED": False,  # Speed up tests
        # Blockchain Settings - Test network
        "BLOCKCHAIN_NETWORK": "test",
        "BLOCKCHAIN_ENABLED": False,  # Disable by default in tests
        "BLOCKCHAIN_CONFIRMATION_BLOCKS": 1,  # Faster confirmations
        # AI/ML Settings - Mock models
        "AI_MODEL_PATH": os.path.join(tempfile.gettempdir(), "test-models"),
        "AI_USE_MOCK_MODELS": True,
        "TRANSLATION_CACHE_TTL": 60,  # Short cache for tests
        # Offline Sync Settings - Faster for tests
        "OFFLINE_SYNC_INTERVAL": 10,  # 10 seconds
        "OFFLINE_SYNC_BATCH_SIZE": 10,  # Smaller batches
        # Rate Limiting - Disabled for tests
        "RATE_LIMIT_ENABLED": False,
        # Monitoring - Minimal for tests
        "METRICS_ENABLED": False,
        "TRACING_ENABLED": False,
        "LOG_LEVEL": "DEBUG",
        # File Upload Settings
        "MAX_UPLOAD_SIZE": 1 * 1024 * 1024,  # 1MB for tests
        "UPLOAD_DIRECTORY": os.path.join(tempfile.gettempdir(), "test-uploads"),
        # Session Settings - Shorter for tests
        "SESSION_LIFETIME": 3600,  # 1 hour
        "SESSION_REFRESH_THRESHOLD": 300,  # 5 minutes
        # Compliance Settings - Relaxed for speed
        "AUDIT_LOGS_ENABLED": True,  # Keep for testing audit functionality
        "AUDIT_LOG_DIRECTORY": os.path.join(tempfile.gettempdir(), "test-audit-logs"),
        # External Services - Use mocks
        "SMS_PROVIDER": "mock",
        "EMAIL_PROVIDER": "mock",
        "TRANSLATION_PROVIDER": "mock",
        # Test-specific settings
        "TEST_USER_EMAIL": "test@example.com",
        "TEST_USER_PASSWORD": "TestPass123!",
        "TEST_ADMIN_EMAIL": "admin@example.com",
        "TEST_ADMIN_PASSWORD": "AdminPass123!",
        "TEST_FIXTURES_PATH": "tests/fixtures",
        # Feature Flags - Enable all for testing
        "FEATURE_BLOCKCHAIN_VERIFICATION": True,
        "FEATURE_AI_TRANSLATION": True,
        "FEATURE_OFFLINE_MODE": True,
        "FEATURE_VOICE_INPUT": True,
        "FEATURE_BIOMETRIC_AUTH": True,
    }
)

# Test database migrations
TEST_CONFIG["RUN_MIGRATIONS_ON_STARTUP"] = True
TEST_CONFIG["CREATE_TEST_DATA"] = True

# Disable external service calls
TEST_CONFIG["MOCK_EXTERNAL_SERVICES"] = True
TEST_CONFIG["MOCK_BLOCKCHAIN"] = True
TEST_CONFIG["MOCK_AI_SERVICES"] = True

# Performance settings for tests
TEST_CONFIG["CACHE_ENABLED"] = False  # Disable caching for predictable tests
TEST_CONFIG["BACKGROUND_TASKS_ENABLED"] = False  # Run tasks synchronously

# Validation overrides
TEST_CONFIG["SKIP_EMAIL_VERIFICATION"] = True  # For test user creation
TEST_CONFIG["ALLOW_TEST_ENDPOINTS"] = True  # Enable test-only API endpoints
