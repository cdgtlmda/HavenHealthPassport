# Session Management Documentation

## Overview

The Haven Health Passport session management system provides comprehensive session handling with configurable timeout policies, activity tracking, and security features. This system ensures secure session management while providing flexibility for different types of sessions (web, mobile, API, admin).

## Features

### 1. Multiple Session Types
- **Web Sessions**: Standard browser-based sessions with 30-minute idle timeout
- **Mobile Sessions**: Extended sessions for mobile apps with 12-hour idle timeout
- **API Sessions**: For programmatic access with 1-hour idle timeout
- **Admin Sessions**: High-security sessions with 15-minute idle timeout

### 2. Timeout Policies
- **Fixed**: Session expires at a fixed time regardless of activity
- **Sliding**: Session timeout extends with each activity
- **Absolute**: Maximum lifetime regardless of activity
- **Adaptive**: Timeout adjusts based on user behavior patterns

### 3. Security Features
- Token rotation on renewal
- IP address tracking and validation
- Device fingerprinting
- Concurrent session limits
- Automatic cleanup of expired sessions
- Session event logging

## Implementation Guide

### Setting Up Session Management

#### FastAPI Integration

```python
from fastapi import FastAPI
from src.api.session_integration import setup_fastapi_session_management

app = FastAPI()

# Set up session management
session_deps = setup_fastapi_session_management(app)

# Use dependencies in routes
@app.get("/protected")
async def protected_route(
    user = Depends(session_deps["get_current_user"])
):
    return {"user": user.email}
```

#### Flask Integration

```python
from flask import Flask
from src.api.session_integration import setup_flask_session_management

app = Flask(__name__)

# Set up session management
setup_flask_session_management(app)

@app.route("/protected")
def protected_route():
    from flask import g
    return {"user": g.user.email}
```

### Configuration

#### Default Timeout Configuration

```python
# Web sessions (default)
{
    "idle_timeout": 30,        # 30 minutes of inactivity
    "absolute_timeout": 480,    # 8 hours maximum
    "renewal_window": 5,        # 5 minutes before expiry
    "warning_threshold": 2,     # 2 minutes warning
    "max_renewals": 10         # Maximum renewals
}

# Admin sessions (strict)
{
    "idle_timeout": 15,        # 15 minutes of inactivity
    "absolute_timeout": 240,    # 4 hours maximum
    "renewal_window": 2,        # 2 minutes before expiry
    "warning_threshold": 1,     # 1 minute warning
    "max_renewals": 3          # Maximum renewals
}
```

#### Customizing Configuration

```python
from src.config.session_config import SessionTimeoutConfig

# Update configuration for a session type
SessionTimeoutConfig.update_config("web", {
    "idle_timeout": 60,  # Extend to 1 hour
    "absolute_timeout": 720  # 12 hours
})

# Apply environment-specific overrides
from src.config.session_config import SessionConfigOverrides
SessionConfigOverrides.apply_overrides("production")
```

### Using the Session Manager

#### Creating Sessions

```python
from src.auth.session_manager import SessionManager, SessionType, TimeoutPolicy

session_manager = SessionManager(db)

# Create a web session with sliding timeout
session = session_manager.create_session(
    user=user,
    session_type=SessionType.WEB,
    device_fingerprint="unique-device-id",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    timeout_policy=TimeoutPolicy.SLIDING
)
```

#### Validating Sessions

```python
# Validate and update activity
try:
    session, user = session_manager.validate_session(
        session_token="token-value",
        update_activity=True,
        ip_address="192.168.1.1"
    )
except SessionExpiredException:
    # Handle expired session
    pass
except SessionInvalidException:
    # Handle invalid session
    pass
```

#### Renewing Sessions

```python
# Renew a session
renewed_session = session_manager.renew_session(
    session,
    extend_by_minutes=30  # Optional custom extension
)

# New tokens are generated
new_token = renewed_session.token
```

#### Terminating Sessions

```python
# Terminate a single session
session_manager.terminate_session(session, "User logout")

# Terminate all user sessions
count = session_manager.terminate_all_user_sessions(user)

# Terminate all except current
count = session_manager.terminate_all_user_sessions(
    user,
    except_session=current_session
)
```

### Session Lifecycle

1. **Creation**: Session created with initial timeout values
2. **Validation**: Each request validates session and updates activity
3. **Activity Update**: Sliding sessions extend timeout on activity
4. **Renewal**: Sessions can be explicitly renewed near expiry
5. **Termination**: Sessions terminated on logout or security events
6. **Cleanup**: Expired sessions automatically cleaned up

### Security Considerations

#### Concurrent Session Limits
- Web: 3 concurrent sessions
- Mobile: 2 concurrent sessions
- API: 5 concurrent sessions
- Admin: 1 concurrent session

#### Session Security Settings
```python
SECURITY_SETTINGS = {
    "require_ip_consistency": False,      # Allow IP changes
    "require_device_consistency": True,   # Same device required
    "log_all_activity": True,            # Comprehensive logging
    "alert_on_suspicious_activity": True, # Security alerts
    "auto_logout_on_suspicious": False,  # Manual review
}
```

### API Endpoints

#### Session Management Endpoints

- `POST /api/v1/sessions/renew` - Renew current session
- `GET /api/v1/sessions/active` - List active sessions
- `DELETE /api/v1/sessions/{id}` - Terminate specific session
- `POST /api/v1/sessions/terminate-all` - Terminate all sessions

### Database Schema

#### UserSession Table
```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_auth(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    session_type VARCHAR(50) NOT NULL DEFAULT 'web',
    timeout_policy VARCHAR(50) NOT NULL DEFAULT 'sliding',
    device_fingerprint VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    absolute_expires_at TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    invalidated_at TIMESTAMP,
    invalidation_reason VARCHAR(255),
    metadata JSONB DEFAULT '{}'
);
```

### Monitoring and Analytics

#### Session Metrics
```python
# Get session analytics
analytics = session_manager.get_session_analytics(
    user=user,  # Optional user filter
    days=7      # Analysis period
)

# Returns:
{
    "total_sessions": 150,
    "active_sessions": 45,
    "expired_sessions": 105,
    "average_duration": 125.5,  # minutes
    "by_type": {
        "web": 100,
        "mobile": 30,
        "api": 20
    },
    "by_day": [...]
}
```

### Best Practices

1. **Use Appropriate Session Types**: Choose the right session type for your use case
2. **Configure Timeouts**: Adjust timeouts based on security requirements
3. **Monitor Sessions**: Regularly review session analytics
4. **Handle Expiration**: Gracefully handle session expiration in UI
5. **Secure Storage**: Never store session tokens in localStorage
6. **Token Rotation**: Renew tokens periodically for security
7. **Cleanup**: Run periodic cleanup of expired sessions

### Troubleshooting

#### Common Issues

1. **Session Expired Unexpectedly**
   - Check idle timeout configuration
   - Verify activity updates are working
   - Review absolute timeout settings

2. **Too Many Sessions Error**
   - Check concurrent session limits
   - Clean up expired sessions
   - Review session termination logic

3. **Session Not Found**
   - Verify token is being sent correctly
   - Check database connectivity
   - Review session creation logs

### Migration Guide

To migrate existing sessions to the new system:

1. Run the database migration:
   ```sql
   psql -d haven_health -f migrations/add_session_management_fields.sql
   ```

2. Update existing sessions with default values:
   ```sql
   UPDATE user_sessions
   SET session_type = 'web',
       timeout_policy = 'sliding',
       metadata = '{}'
   WHERE session_type IS NULL;
   ```

3. Deploy the new session management code

4. Monitor for any issues during transition

## Security Compliance

The session management system complies with:
- HIPAA security requirements
- GDPR session handling guidelines
- OWASP session management best practices
- ISO 27001 access control requirements
