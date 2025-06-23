-- Migration: Add risk assessment logs table
-- Description: Create table for tracking authentication risk assessments

CREATE TABLE IF NOT EXISTS risk_assessment_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_auth(id),
    email VARCHAR(255) NOT NULL,

    -- Risk assessment results
    risk_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    risk_factors JSONB DEFAULT '[]'::jsonb,

    -- Context information
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(500),
    device_fingerprint VARCHAR(255),

    -- Location data
    country_code VARCHAR(2),
    city VARCHAR(100),
    latitude FLOAT,
    longitude FLOAT,

    -- Assessment details
    assessment_details JSONB,
    recommended_actions JSONB DEFAULT '[]'::jsonb,

    -- Authentication outcome
    auth_allowed VARCHAR(20),
    mfa_methods_required JSONB,
    additional_requirements JSONB,

    -- Timestamps
    assessed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX idx_risk_assessment_user ON risk_assessment_logs(user_id, assessed_at DESC);
CREATE INDEX idx_risk_assessment_email ON risk_assessment_logs(email, assessed_at DESC);
CREATE INDEX idx_risk_assessment_ip ON risk_assessment_logs(ip_address, assessed_at DESC);
CREATE INDEX idx_risk_assessment_level ON risk_assessment_logs(risk_level, assessed_at DESC);
CREATE INDEX idx_risk_assessment_id ON risk_assessment_logs(assessment_id);

-- Add comment to table
COMMENT ON TABLE risk_assessment_logs IS 'Audit log of all authentication risk assessments';
