-- Migration: Add Biometric Authentication Tables
-- Description: Creates tables for biometric authentication including templates and audit logs
-- Date: 2025-05-31

-- Create biometric_templates table
CREATE TABLE IF NOT EXISTS biometric_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES user_auth(id) ON DELETE CASCADE,

    -- Biometric details
    biometric_type VARCHAR(50) NOT NULL CHECK (biometric_type IN ('fingerprint', 'face', 'voice', 'iris', 'palm')),
    encrypted_template TEXT NOT NULL,
    quality_score FLOAT NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),

    -- Device information
    device_info JSONB,
    device_model VARCHAR(255),
    sdk_version VARCHAR(50),

    -- Status
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    deactivated_at TIMESTAMP WITH TIME ZONE,
    deactivation_reason VARCHAR(255),

    -- Usage tracking
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,
    last_match_score FLOAT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Add base model columns
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT chk_deactivation CHECK (
        (is_active = TRUE AND deactivated_at IS NULL AND deactivation_reason IS NULL) OR
        (is_active = FALSE AND deactivated_at IS NOT NULL AND deactivation_reason IS NOT NULL)
    ),
    CONSTRAINT chk_last_match_score CHECK (last_match_score IS NULL OR (last_match_score >= 0.0 AND last_match_score <= 1.0))
);

-- Create indexes for biometric_templates
CREATE INDEX idx_biometric_user_type ON biometric_templates(user_id, biometric_type, is_active);
CREATE INDEX idx_biometric_template_id ON biometric_templates(template_id);
CREATE INDEX idx_biometric_active ON biometric_templates(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_biometric_created ON biometric_templates(created_at);

-- Create biometric_audit_log table for tracking all biometric events
CREATE TABLE IF NOT EXISTS biometric_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_auth(id) ON DELETE CASCADE,
    template_id VARCHAR(100),

    -- Event details
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'enrolled', 'enrollment_failed', 'verified', 'verification_failed',
        'no_match', 'liveness_failed', 'spoof_detected', 'updated',
        'revoked', 'expired', 'rate_limited'
    )),
    biometric_type VARCHAR(50) NOT NULL,
    success BOOLEAN NOT NULL,

    -- Additional information
    match_score FLOAT,
    quality_score FLOAT,
    failure_reason VARCHAR(500),
    device_info JSONB,

    -- Request information
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    session_id UUID,

    -- Timestamps
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- Base model columns
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for biometric_audit_log
CREATE INDEX idx_biometric_audit_user ON biometric_audit_log(user_id, event_timestamp);
CREATE INDEX idx_biometric_audit_event ON biometric_audit_log(event_type, event_timestamp);
CREATE INDEX idx_biometric_audit_success ON biometric_audit_log(success, event_timestamp);
CREATE INDEX idx_biometric_audit_template ON biometric_audit_log(template_id) WHERE template_id IS NOT NULL;

-- Create webauthn_credentials table for FIDO2/WebAuthn support
CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_auth(id) ON DELETE CASCADE,

    -- Credential details
    credential_id TEXT UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    aaguid VARCHAR(100),  -- Authenticator Attestation GUID
    sign_count INTEGER DEFAULT 0 NOT NULL,

    -- Authenticator information
    authenticator_attachment VARCHAR(50) CHECK (authenticator_attachment IN ('platform', 'cross-platform')),
    credential_type VARCHAR(50) DEFAULT 'public-key' NOT NULL,
    transports TEXT[],  -- Array of transport types (usb, nfc, ble, internal)

    -- Device information
    device_name VARCHAR(255),
    last_used_device VARCHAR(255),
    last_used_ip VARCHAR(45),

    -- Status
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revocation_reason VARCHAR(255),

    -- Usage tracking
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,

    -- Base model columns
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT chk_revocation CHECK (
        (is_active = TRUE AND revoked_at IS NULL AND revocation_reason IS NULL) OR
        (is_active = FALSE AND revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)
    )
);

-- Create indexes for webauthn_credentials
CREATE INDEX idx_webauthn_user ON webauthn_credentials(user_id, is_active);
CREATE INDEX idx_webauthn_credential_id ON webauthn_credentials(credential_id);
CREATE INDEX idx_webauthn_active ON webauthn_credentials(is_active) WHERE is_active = TRUE;

-- Create biometric_enrollment_status view for easy status checking
CREATE OR REPLACE VIEW biometric_enrollment_status AS
SELECT
    u.id AS user_id,
    u.email,
    COUNT(DISTINCT bt.biometric_type) FILTER (WHERE bt.is_active = TRUE) AS active_biometric_types,
    MAX(bt.created_at) AS last_enrollment_date,
    MAX(bt.last_used_at) AS last_biometric_use,
    COUNT(wc.id) FILTER (WHERE wc.is_active = TRUE) AS active_webauthn_devices,
    CASE
        WHEN COUNT(bt.id) FILTER (WHERE bt.is_active = TRUE) > 0 OR
             COUNT(wc.id) FILTER (WHERE wc.is_active = TRUE) > 0
        THEN TRUE
        ELSE FALSE
    END AS has_biometric_auth
FROM user_auth u
LEFT JOIN biometric_templates bt ON u.id = bt.user_id
LEFT JOIN webauthn_credentials wc ON u.id = wc.user_id
GROUP BY u.id, u.email;

-- Add comments for documentation
COMMENT ON TABLE biometric_templates IS 'Stores encrypted biometric templates for user authentication';
COMMENT ON TABLE biometric_audit_log IS 'Audit log for all biometric authentication events';
COMMENT ON TABLE webauthn_credentials IS 'Stores WebAuthn/FIDO2 credentials for passwordless authentication';
COMMENT ON VIEW biometric_enrollment_status IS 'View showing biometric enrollment status for all users';

-- Add column comments
COMMENT ON COLUMN biometric_templates.template_id IS 'Unique identifier for the biometric template';
COMMENT ON COLUMN biometric_templates.encrypted_template IS 'Encrypted biometric template data';
COMMENT ON COLUMN biometric_templates.quality_score IS 'Quality score of the biometric sample (0.0-1.0)';
COMMENT ON COLUMN webauthn_credentials.credential_id IS 'WebAuthn credential ID';
COMMENT ON COLUMN webauthn_credentials.public_key IS 'Public key for credential verification';
COMMENT ON COLUMN webauthn_credentials.sign_count IS 'Signature counter for replay attack prevention';
