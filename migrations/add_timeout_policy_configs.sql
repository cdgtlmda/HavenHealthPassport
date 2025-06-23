-- Add timeout policy configuration table
-- This migration creates the timeout_policy_configs table for managing
-- dynamic session timeout policies based on various criteria

-- Create timeout_policy_configs table
CREATE TABLE IF NOT EXISTS timeout_policy_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(500),

    -- Policy settings (JSON)
    settings JSONB NOT NULL CHECK (
        settings ? 'idle_timeout' AND
        settings ? 'absolute_timeout' AND
        settings ? 'renewal_window' AND
        settings ? 'warning_time' AND
        settings ? 'grace_period'
    ),

    -- Applicability arrays (JSON)
    user_roles JSONB DEFAULT '[]'::JSONB,
    session_types JSONB DEFAULT '[]'::JSONB,
    risk_levels JSONB DEFAULT '[]'::JSONB,
    compliance_levels JSONB DEFAULT '[]'::JSONB,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    created_by VARCHAR(255),

    -- Constraints
    CONSTRAINT valid_settings CHECK (
        (settings->>'idle_timeout')::INTEGER > 0 AND
        (settings->>'absolute_timeout')::INTEGER > 0 AND
        (settings->>'renewal_window')::INTEGER > 0 AND
        (settings->>'warning_time')::INTEGER > 0 AND
        (settings->>'grace_period')::INTEGER >= 0
    )
);

-- Create indexes for performance
CREATE INDEX idx_timeout_policy_active ON timeout_policy_configs(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_timeout_policy_priority ON timeout_policy_configs(priority DESC);
CREATE INDEX idx_timeout_policy_name ON timeout_policy_configs(name);
CREATE INDEX idx_timeout_policy_roles ON timeout_policy_configs USING GIN (user_roles);
CREATE INDEX idx_timeout_policy_types ON timeout_policy_configs USING GIN (session_types);
CREATE INDEX idx_timeout_policy_risk ON timeout_policy_configs USING GIN (risk_levels);
CREATE INDEX idx_timeout_policy_compliance ON timeout_policy_configs USING GIN (compliance_levels);

-- Add comments for documentation
COMMENT ON TABLE timeout_policy_configs IS 'Stores configurable timeout policies for different contexts';
COMMENT ON COLUMN timeout_policy_configs.name IS 'Unique name for the timeout policy';
COMMENT ON COLUMN timeout_policy_configs.settings IS 'JSON object containing timeout values in minutes';
COMMENT ON COLUMN timeout_policy_configs.user_roles IS 'Array of user roles this policy applies to';
COMMENT ON COLUMN timeout_policy_configs.session_types IS 'Array of session types this policy applies to';
COMMENT ON COLUMN timeout_policy_configs.risk_levels IS 'Array of risk levels this policy applies to';
COMMENT ON COLUMN timeout_policy_configs.compliance_levels IS 'Array of compliance levels this policy applies to';
COMMENT ON COLUMN timeout_policy_configs.priority IS 'Higher priority policies override lower ones when multiple match';

-- Insert default timeout policies
INSERT INTO timeout_policy_configs (name, description, settings, session_types, priority, created_by) VALUES
-- Standard web policy
('web_standard', 'Standard timeout policy for web sessions',
 '{"idle_timeout": 30, "absolute_timeout": 480, "renewal_window": 5, "warning_time": 3, "grace_period": 2}'::JSONB,
 '["web"]'::JSONB, 100, 'system'),

-- High security web policy
('web_high_security', 'High security timeout policy for web sessions',
 '{"idle_timeout": 15, "absolute_timeout": 120, "renewal_window": 3, "warning_time": 2, "grace_period": 1}'::JSONB,
 '["web"]'::JSONB, 200, 'system'),

-- Standard mobile policy
('mobile_standard', 'Standard timeout policy for mobile sessions',
 '{"idle_timeout": 720, "absolute_timeout": 10080, "renewal_window": 60, "warning_time": 30, "grace_period": 15}'::JSONB,
 '["mobile"]'::JSONB, 100, 'system'),

-- High security mobile policy
('mobile_high_security', 'High security timeout policy for mobile sessions',
 '{"idle_timeout": 60, "absolute_timeout": 480, "renewal_window": 10, "warning_time": 5, "grace_period": 3}'::JSONB,
 '["mobile"]'::JSONB, 200, 'system'),

-- API standard policy
('api_standard', 'Standard timeout policy for API sessions',
 '{"idle_timeout": 60, "absolute_timeout": 1440, "renewal_window": 10, "warning_time": 5, "grace_period": 2}'::JSONB,
 '["api"]'::JSONB, 100, 'system'),

-- Admin standard policy
('admin_standard', 'Standard timeout policy for admin sessions',
 '{"idle_timeout": 15, "absolute_timeout": 240, "renewal_window": 2, "warning_time": 2, "grace_period": 1}'::JSONB,
 '["admin"]'::JSONB, 100, 'system'),

-- HIPAA compliance policy
('hipaa_compliance', 'HIPAA-compliant timeout policy',
 '{"idle_timeout": 15, "absolute_timeout": 240, "renewal_window": 2, "warning_time": 2, "grace_period": 1}'::JSONB,
 '[]'::JSONB, 300, 'system'),

-- Government security policy
('government_security', 'Government-level security timeout policy',
 '{"idle_timeout": 10, "absolute_timeout": 120, "renewal_window": 2, "warning_time": 1, "grace_period": 1}'::JSONB,
 '[]'::JSONB, 400, 'system');

-- Update user_roles for specific policies
UPDATE timeout_policy_configs SET user_roles = '["admin", "super_admin"]'::JSONB WHERE name = 'admin_standard';
UPDATE timeout_policy_configs SET compliance_levels = '["hipaa"]'::JSONB WHERE name = 'hipaa_compliance';
UPDATE timeout_policy_configs SET compliance_levels = '["government"]'::JSONB WHERE name = 'government_security';

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_timeout_policy_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_timeout_policy_updated_at
    BEFORE UPDATE ON timeout_policy_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_timeout_policy_updated_at();

-- Create function to find best matching policy
CREATE OR REPLACE FUNCTION find_matching_timeout_policy(
    p_session_type VARCHAR,
    p_user_role VARCHAR,
    p_risk_level VARCHAR,
    p_compliance_level VARCHAR
) RETURNS JSONB AS $$
DECLARE
    v_policy RECORD;
BEGIN
    -- Find the highest priority matching policy
    SELECT * INTO v_policy
    FROM timeout_policy_configs
    WHERE is_active = TRUE
        AND (session_types = '[]'::JSONB OR session_types @> to_jsonb(ARRAY[p_session_type]))
        AND (user_roles = '[]'::JSONB OR user_roles @> to_jsonb(ARRAY[p_user_role]))
        AND (risk_levels = '[]'::JSONB OR risk_levels @> to_jsonb(ARRAY[p_risk_level]))
        AND (compliance_levels = '[]'::JSONB OR compliance_levels @> to_jsonb(ARRAY[p_compliance_level]))
    ORDER BY priority DESC
    LIMIT 1;

    IF FOUND THEN
        RETURN v_policy.settings;
    ELSE
        -- Return default settings if no match found
        RETURN '{"idle_timeout": 30, "absolute_timeout": 480, "renewal_window": 5, "warning_time": 3, "grace_period": 2}'::JSONB;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_matching_timeout_policy IS 'Finds the best matching timeout policy based on criteria';

-- Create view for policy effectiveness analysis
CREATE OR REPLACE VIEW timeout_policy_effectiveness AS
SELECT
    tp.name AS policy_name,
    tp.settings,
    COUNT(DISTINCT us.id) AS sessions_count,
    AVG(EXTRACT(EPOCH FROM (COALESCE(us.invalidated_at, CURRENT_TIMESTAMP) - us.created_at)) / 60) AS avg_duration_minutes,
    SUM(CASE WHEN us.invalidation_reason LIKE '%timeout%' THEN 1 ELSE 0 END) AS timeout_count,
    SUM(CASE WHEN us.invalidation_reason = 'User logout' THEN 1 ELSE 0 END) AS logout_count
FROM timeout_policy_configs tp
LEFT JOIN user_sessions us ON
    (tp.session_types = '[]'::JSONB OR tp.session_types @> to_jsonb(ARRAY[us.session_type]))
WHERE tp.is_active = TRUE
GROUP BY tp.name, tp.settings;

COMMENT ON VIEW timeout_policy_effectiveness IS 'Analyzes effectiveness of timeout policies based on session data';

-- Grant appropriate permissions
GRANT SELECT ON timeout_policy_configs TO haven_app_role;
GRANT INSERT, UPDATE ON timeout_policy_configs TO haven_admin_role;
GRANT EXECUTE ON FUNCTION find_matching_timeout_policy TO haven_app_role;
GRANT SELECT ON timeout_policy_effectiveness TO haven_admin_role;
