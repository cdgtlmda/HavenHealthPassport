-- Verifications table
CREATE TABLE haven_health.verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Subject of verification
    patient_id UUID NOT NULL REFERENCES haven_health.patients(id) ON DELETE CASCADE,

    -- Verification details
    verification_type VARCHAR(50) NOT NULL,
    verification_method VARCHAR(50) NOT NULL,
    verification_level VARCHAR(20) NOT NULL,
    status verification_status_enum NOT NULL DEFAULT 'pending',

    -- Verifier information
    verifier_id UUID NOT NULL,
    verifier_name VARCHAR(200) NOT NULL,
    verifier_organization VARCHAR(200),
    verifier_role VARCHAR(100),
    verifier_credentials JSONB DEFAULT '{}',

    -- Verification process
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Evidence and documentation
    evidence_provided JSONB DEFAULT '[]',
    documents_verified JSONB DEFAULT '[]',
    biometric_data_hash VARCHAR(255),
    verification_notes TEXT,

    -- Multi-factor verification
    factors_required INTEGER DEFAULT 1,
    factors_completed JSONB DEFAULT '[]',

    -- Blockchain integration
    blockchain_hash VARCHAR(255) UNIQUE,
    blockchain_tx_id VARCHAR(255),
    blockchain_network VARCHAR(50),
    smart_contract_address VARCHAR(255),

    -- Witness/reference information
    witnesses JSONB DEFAULT '[]',
    reference_verifications JSONB DEFAULT '[]',

    -- Scoring and confidence
    confidence_score INTEGER CHECK (confidence_score >= 0 AND confidence_score <= 100),
    risk_indicators JSONB DEFAULT '[]',
    verification_strength VARCHAR(20),

    -- Revocation
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_by UUID,
    revocation_reason TEXT,

    -- Cross-border recognition
    recognized_countries JSONB DEFAULT '[]',
    international_standard VARCHAR(100),

    -- Audit trail
    verification_log JSONB DEFAULT '[]',
    ip_address INET,
    device_fingerprint VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by UUID
);

-- Create indexes for verifications
CREATE INDEX idx_verifications_patient ON haven_health.verifications(patient_id);
CREATE INDEX idx_verifications_type ON haven_health.verifications(verification_type);
CREATE INDEX idx_verifications_status ON haven_health.verifications(status);
CREATE INDEX idx_verifications_expires ON haven_health.verifications(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_verifications_blockchain ON haven_health.verifications(blockchain_hash) WHERE blockchain_hash IS NOT NULL;

-- Create trigger for updated_at
CREATE TRIGGER update_verifications_updated_at BEFORE UPDATE ON haven_health.verifications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
