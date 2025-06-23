-- Add session management fields to support comprehensive timeout policies
-- Migration: session_management_001
-- Date: 2025-05-31

-- Add new columns to user_sessions table
ALTER TABLE user_sessions
ADD COLUMN IF NOT EXISTS session_type VARCHAR(50) NOT NULL DEFAULT 'web',
ADD COLUMN IF NOT EXISTS timeout_policy VARCHAR(50) NOT NULL DEFAULT 'sliding',
ADD COLUMN IF NOT EXISTS absolute_expires_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS device_fingerprint VARCHAR(255),
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Add metadata column to login_attempts table for session event logging
ALTER TABLE login_attempts
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_session_type ON user_sessions(session_type);
CREATE INDEX IF NOT EXISTS idx_session_absolute_expires ON user_sessions(absolute_expires_at);
CREATE INDEX IF NOT EXISTS idx_session_user_type ON user_sessions(user_id, session_type) WHERE is_active = true;

-- Add comments for documentation
COMMENT ON COLUMN user_sessions.session_type IS 'Type of session: web, mobile, api, admin';
COMMENT ON COLUMN user_sessions.timeout_policy IS 'Timeout policy: fixed, sliding, absolute, adaptive';
COMMENT ON COLUMN user_sessions.absolute_expires_at IS 'Absolute maximum lifetime of the session';
COMMENT ON COLUMN user_sessions.device_fingerprint IS 'Unique device identifier';
COMMENT ON COLUMN user_sessions.metadata IS 'Additional session metadata including timeout configuration';

COMMENT ON COLUMN login_attempts.metadata IS 'Additional event metadata for session-related events';
