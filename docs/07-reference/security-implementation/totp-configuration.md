# TOTP Configuration Implementation

## Overview

The Haven Health Passport TOTP (Time-based One-Time Password) configuration system provides a comprehensive, configurable, and secure implementation of two-factor authentication using authenticator apps.

## Features

### Enhanced Security
- **Anti-Replay Protection**: Prevents reuse of codes within 90-second window
- **Configurable Algorithms**: Support for SHA1, SHA256, and SHA512
- **Adjustable Time Windows**: Configure tolerance for clock drift
- **Rate Limiting**: Maximum 5 attempts per time window

### User Experience
- **QR Code Generation**: Built-in QR code generation for easy setup
- **Multiple App Support**: Compatible with all major authenticator apps
- **Setup Instructions**: Clear, step-by-step guidance for users
- **Manual Entry Option**: Secret key display for manual configuration

### Configuration Options
- **Issuer Customization**: Configurable app name and logo
- **Code Parameters**: 6 or 8 digit codes with 15-60 second intervals
- **QR Code Settings**: Adjustable size, border, and error correction
- **Recovery Options**: Configurable number of backup codes

## Implementation Details

### Core Components

1. **TOTPConfig** (`src/auth/totp_config.py`)
   - Pydantic model for TOTP settings
   - Built-in validation for all parameters
   - Type-safe configuration

2. **TOTPManager** (`src/auth/totp_config.py`)
   - Handles secret generation with metadata
   - QR code generation with customizable settings
   - Code verification with anti-replay protection
   - Used code tracking and cleanup

3. **TOTPSettings** (`src/config/totp_settings.py`)
   - Environment-based configuration
   - All settings configurable via environment variables
   - Sensible defaults for production use


## Configuration

### Environment Variables

```bash
# Basic TOTP Settings
TOTP_ISSUER_NAME="Haven Health Passport"
TOTP_ISSUER_LOGO_URL="https://example.com/logo.png"

# Algorithm Settings
TOTP_ALGORITHM="SHA1"  # SHA1, SHA256, or SHA512
TOTP_DIGITS=6          # 6 or 8
TOTP_INTERVAL=30       # 15-60 seconds

# Security Settings
TOTP_WINDOW=1          # Time window tolerance
TOTP_REUSE_INTERVAL=90 # Code reuse prevention (seconds)
TOTP_MAX_ATTEMPTS=5    # Max verification attempts

# QR Code Settings
TOTP_QR_VERSION=5      # QR code version (size)
TOTP_QR_BOX_SIZE=10    # Pixels per box
TOTP_QR_BORDER=4       # Border size in boxes
TOTP_QR_ERROR_CORRECTION="M"  # L, M, Q, or H

# User Experience
TOTP_SETUP_TIMEOUT_MINUTES=10
TOTP_RECOVERY_CODES_COUNT=10
TOTP_SHOW_SECRET_ON_SETUP=true
```

### API Usage

#### Generate TOTP Secret
```python
from src.auth.totp_config import get_totp_manager

manager = get_totp_manager()
secret, uri, metadata = manager.generate_secret("user@example.com")
```

#### Generate QR Code
```python
qr_bytes = manager.generate_qr_code(uri)
# Returns PNG image bytes
```

#### Verify Code with Anti-Replay
```python
is_valid, error = manager.verify_code("user_id", secret, "123456")
if not is_valid:
    print(f"Verification failed: {error}")
```


## Security Considerations

### Anti-Replay Protection
- Codes are tracked for 90 seconds after use
- Prevents replay attacks even within valid time window
- Automatic cleanup of expired tracking data

### Algorithm Selection
- **SHA1**: Default, maximum compatibility
- **SHA256**: Enhanced security, good support
- **SHA512**: Maximum security, limited app support

### Time Synchronization
- Window tolerance handles minor clock drift
- Default ±30 seconds (1 interval) tolerance
- Configurable based on deployment environment

## Supported Authenticator Apps

The system is tested and compatible with:
- Google Authenticator (iOS, Android)
- Microsoft Authenticator (iOS, Android)
- Authy (iOS, Android, Desktop)
- 1Password (iOS, Android, Desktop)
- LastPass Authenticator (iOS, Android)
- Aegis Authenticator (Android)
- Raivo OTP (iOS)

## Compliance

This TOTP implementation meets requirements for:
- **NIST SP 800-63B**: AAL2 authentication
- **HIPAA**: Strong authentication for PHI access
- **ISO 27001**: Multi-factor authentication controls
- **PCI DSS**: Two-factor authentication requirements

## Monitoring

All TOTP events are logged for security monitoring:
- Secret generation attempts
- QR code generation
- Verification attempts (success/failure)
- Anti-replay blocks
- Configuration changes

## Next Steps

1. Configure SMS backup support
2. Implement biometric authentication
3. Add WebAuthn/FIDO2 support
4. Enable risk-based authentication
