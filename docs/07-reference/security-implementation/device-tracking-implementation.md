# Device Tracking Implementation

## Overview

Haven Health Passport now implements comprehensive device tracking and management to enhance security through device recognition, trust management, and risk assessment integration.

## Features

### 1. Device Fingerprinting
- Browser-based fingerprinting using multiple characteristics
- Canvas fingerprinting for unique identification
- WebGL vendor information
- Screen resolution and timezone
- Plugin detection

### 2. Device Tracking
- Automatic device registration on login
- Device metadata collection (browser, OS, type)
- Login history tracking
- Last seen timestamps
- Device naming (e.g., "Chrome on Windows")

### 3. Device Trust Management
- Mark devices as trusted for reduced friction
- Configurable trust duration (default: 90 days)
- Maximum trusted devices limit (default: 10)
- Trust expiration handling
- Revoke trust capability

### 4. Risk Integration
- Device risk scoring based on:
  - Trust status
  - Device age
  - Login frequency
  - Time since last seen
- Integration with risk-based authentication
- New device notifications

### 5. Device Management
- List all devices with activity status
- Delete old/unused devices
- Current device identification
- Automatic cleanup of inactive devices

## Architecture

### Backend Components

1. **DeviceTrackingService** (`src/services/device_tracking_service.py`)
   - Device fingerprint generation
   - Device tracking and management
   - Trust operations
   - Risk scoring

2. **Device Endpoints** (`src/api/device_endpoints.py`)
   - REST API for device management
   - Trust/revoke operations
   - Device listing and deletion

3. **Database Model** (`src/models/auth.py - DeviceInfo`)
   - Existing model enhanced with tracking

### Frontend Components

1. **DeviceTrackingService** (`web/src/services/deviceTrackingService.ts`)
   - Client-side fingerprinting
   - Device management UI integration
   - Automatic header injection

## API Endpoints

### Device Management

- `GET /api/v2/auth/devices` - List user devices
- `POST /api/v2/auth/devices/{id}/trust` - Trust a device
- `POST /api/v2/auth/devices/{id}/revoke-trust` - Revoke trust
- `DELETE /api/v2/auth/devices/{id}` - Delete device
- `POST /api/v2/auth/devices/fingerprint` - Generate fingerprint

### Request/Response Examples

#### List Devices
```json
GET /api/v2/auth/devices

Response:
{
  "devices": [
    {
      "id": "uuid",
      "device_name": "Chrome on Windows",
      "device_type": "desktop",
      "platform": "Windows",
      "browser": "Chrome",
      "is_trusted": true,
      "trust_expires_at": "2024-03-01T00:00:00",
      "first_seen_at": "2023-12-01T00:00:00",
      "last_seen_at": "2024-01-15T10:30:00",
      "login_count": 45,
      "is_current": true
    }
  ],
  "total": 3,
  "trusted_count": 2
}
```

## Configuration

### Environment Variables
```bash
# Device tracking settings (optional)
DEVICE_TRUST_DURATION_DAYS=90
MAX_TRUSTED_DEVICES_PER_USER=10
DEVICE_INACTIVE_CLEANUP_DAYS=180
```

### Risk Weight Configuration
Device-related risk factors in risk assessment:
- New device: 0.3 weight
- Untrusted device: Additional 0.3
- Recently seen device: Lower risk
- High login count: Lower risk

## Security Benefits

1. **Device Recognition**: Identify returning vs new devices
2. **Trust Establishment**: Reduce friction for known devices
3. **Anomaly Detection**: Flag unusual device patterns
4. **Attack Prevention**: Detect device spoofing attempts
5. **Audit Trail**: Complete device history

## User Experience

### For Users
- See all devices that have accessed their account
- Manage trusted devices from security settings
- Receive notifications for new device logins
- Remove old/compromised devices

### For Administrators
- Monitor device patterns across users
- Identify suspicious device activities
- Set organization-wide device policies
- Generate device usage reports

## Integration with Authentication Flow

1. **Login Process**:
   - Device fingerprint generated/retrieved
   - Device tracked in database
   - Risk assessment includes device score
   - Session linked to device

2. **Risk Assessment**:
   - New devices increase risk score
   - Trusted devices reduce friction
   - Device history influences authentication requirements

3. **Session Management**:
   - Sessions tied to specific devices
   - Device changes trigger re-authentication
   - Trusted devices get longer sessions

## Privacy Considerations

- Device fingerprints are hashed
- No personally identifiable information in fingerprints
- Users can view and delete device history
- Compliance with privacy regulations

## Testing

```bash
# Run device tracking tests
pytest tests/services/test_device_tracking.py
pytest tests/api/test_device_endpoints.py
```

## Future Enhancements

1. **Machine Learning**: Behavioral analysis per device
2. **Geolocation**: Location-based device tracking
3. **Push Notifications**: Real-time new device alerts
4. **Device Certificates**: Cryptographic device binding
5. **Biometric Binding**: Link devices to biometric data
