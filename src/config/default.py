"""Default configuration settings for Haven Health Passport."""

from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    # Application Settings
    "APP_NAME": "Haven Health Passport",
    "APP_VERSION": "0.1.0",
    "DEBUG": False,
    # API Settings
    "API_HOST": "127.0.0.1",
    "API_PORT": 8000,
    "API_WORKERS": 4,
    "API_RELOAD": False,
    "API_LOG_LEVEL": "info",
    # Security Settings
    "SECRET_KEY": None,  # Must be overridden in environment
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": 1440,  # 24 hours
    "PASSWORD_MIN_LENGTH": 12,
    "PASSWORD_REQUIRE_UPPERCASE": True,
    "PASSWORD_REQUIRE_LOWERCASE": True,
    "PASSWORD_REQUIRE_DIGITS": True,
    "PASSWORD_REQUIRE_SPECIAL": True,
    # Database Settings
    "DATABASE_POOL_SIZE": 10,
    "DATABASE_MAX_OVERFLOW": 20,
    "DATABASE_POOL_TIMEOUT": 30,
    "DATABASE_POOL_RECYCLE": 3600,
    # Redis Settings
    "REDIS_MAX_CONNECTIONS": 100,
    "REDIS_DECODE_RESPONSES": True,
    "REDIS_SOCKET_TIMEOUT": 5,
    "REDIS_SOCKET_CONNECT_TIMEOUT": 5,
    # Healthcare Standards
    "FHIR_VERSION": "R4",
    "FHIR_VALIDATION_ENABLED": True,
    "HL7_VERSION": "2.8",
    # Blockchain Settings
    "BLOCKCHAIN_CONFIRMATION_BLOCKS": 3,
    "BLOCKCHAIN_GAS_PRICE_MULTIPLIER": 1.2,
    "BLOCKCHAIN_TIMEOUT_SECONDS": 30,
    # AI/ML Settings
    "AI_MODEL_CACHE_SIZE": 1000,
    "AI_INFERENCE_TIMEOUT": 30,
    "AI_BATCH_SIZE": 32,
    "TRANSLATION_CACHE_TTL": 3600,
    # Offline Sync Settings
    "OFFLINE_SYNC_INTERVAL": 300,  # 5 minutes
    "OFFLINE_SYNC_BATCH_SIZE": 100,
    "OFFLINE_SYNC_MAX_RETRIES": 3,
    # Rate Limiting
    "RATE_LIMIT_ENABLED": True,
    "RATE_LIMIT_DEFAULT": "100/hour",
    "RATE_LIMIT_BURST": "10/minute",
    # Monitoring
    "METRICS_ENABLED": True,
    "TRACING_ENABLED": True,
    "LOG_FORMAT": "json",
    "LOG_LEVEL": "INFO",
    # File Upload Settings
    "MAX_UPLOAD_SIZE": 10 * 1024 * 1024,  # 10MB
    "ALLOWED_FILE_EXTENSIONS": [".pdf", ".jpg", ".jpeg", ".png", ".dcm"],
    # Session Settings
    "SESSION_LIFETIME": 86400,  # 24 hours
    "SESSION_REFRESH_THRESHOLD": 3600,  # 1 hour
    # Compliance Settings
    "HIPAA_COMPLIANT": True,
    "AUDIT_LOGS_ENABLED": True,
    "ENCRYPTION_AT_REST": True,
    "ENCRYPTION_IN_TRANSIT": True,
    # Feature Flags
    "FEATURE_BLOCKCHAIN_VERIFICATION": True,
    "FEATURE_AI_TRANSLATION": True,
    "FEATURE_OFFLINE_MODE": True,
    "FEATURE_VOICE_INPUT": True,
    "FEATURE_BIOMETRIC_AUTH": True,
}
