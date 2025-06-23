-- Migration: Add JWT Key Rotation Audit Log Table
-- Purpose: Track all JWT key rotation events for security compliance

CREATE TABLE IF NOT EXISTS jwt_key_rotation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    old_kid VARCHAR(255) NOT NULL,
    new_kid VARCHAR(255) NOT NULL,
    rotation_type VARCHAR(50) NOT NULL CHECK (rotation_type IN ('SCHEDULED', 'COMPROMISE', 'POLICY')),
    rotation_reason TEXT,
    affected_tokens_count INTEGER DEFAULT 0,
    rotation_duration_ms FLOAT,
    
    -- User and system information
    rotated_by VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('completed', 'failed', 'rollback')),
    error_message TEXT,
    rollback_performed TIMESTAMP,
    
    -- Timestamps
    rotated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Notification tracking
    security_team_notified TIMESTAMP,
    admin_notified TIMESTAMP,
    jira_ticket_id VARCHAR(50)
);

-- Create indexes for common queries
CREATE INDEX idx_jwt_rotation_old_kid ON jwt_key_rotation_logs(old_kid);
CREATE INDEX idx_jwt_rotation_new_kid ON jwt_key_rotation_logs(new_kid);
CREATE INDEX idx_jwt_rotation_rotated_at ON jwt_key_rotation_logs(rotated_at);
CREATE INDEX idx_jwt_rotation_status ON jwt_key_rotation_logs(status);

-- Add comment for documentation
COMMENT ON TABLE jwt_key_rotation_logs IS 'Audit log for JWT signing key rotation events';
COMMENT ON COLUMN jwt_key_rotation_logs.rotation_type IS 'Type of rotation: SCHEDULED (regular rotation), COMPROMISE (security incident), POLICY (policy change)';
COMMENT ON COLUMN jwt_key_rotation_logs.rotated_by IS 'System or user ID that initiated the rotation';
COMMENT ON COLUMN jwt_key_rotation_logs.affected_tokens_count IS 'Number of active tokens affected by the rotation';
