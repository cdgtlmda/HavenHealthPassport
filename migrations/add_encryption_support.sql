-- Migration: Add encryption support for sensitive data
-- Description: Add encryption key management and update sensitive fields
-- Date: 2024-01-01

-- Create encryption keys table
CREATE TABLE IF NOT EXISTS encryption_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Key identification
    key_id VARCHAR(255) UNIQUE NOT NULL,
    key_type VARCHAR(50) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,

    -- Key metadata
    key_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for verification
    encrypted_key TEXT, -- Master key encrypted version
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(255) NOT NULL,

    -- Lifecycle
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT check_key_type CHECK (key_type IN ('master', 'data', 'file', 'field', 'session', 'backup')),
    CONSTRAINT check_algorithm CHECK (algorithm IN ('aes_256_gcm', 'aes_256_cbc', 'fernet', 'rsa_4096', 'chacha20_poly1305'))
);

-- Create indexes
CREATE INDEX idx_encryption_keys_key_id ON encryption_keys(key_id);
CREATE INDEX idx_encryption_keys_type ON encryption_keys(key_type);
CREATE INDEX idx_encryption_keys_active ON encryption_keys(is_active) WHERE is_active = true;
CREATE INDEX idx_encryption_keys_expires ON encryption_keys(expires_at) WHERE expires_at IS NOT NULL;

-- Create key rotation history
CREATE TABLE IF NOT EXISTS encryption_key_rotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    old_key_id VARCHAR(255) NOT NULL,
    new_key_id VARCHAR(255) NOT NULL,
    rotation_reason VARCHAR(500),
    rotated_by VARCHAR(255) NOT NULL,

    -- Statistics
    records_affected INTEGER DEFAULT 0,
    rotation_started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    rotation_completed_at TIMESTAMP WITH TIME ZONE,
    rotation_status VARCHAR(50) DEFAULT 'in_progress',

    -- Error tracking
    errors JSONB DEFAULT '[]'::jsonb,

    FOREIGN KEY (old_key_id) REFERENCES encryption_keys(key_id),
    FOREIGN KEY (new_key_id) REFERENCES encryption_keys(key_id)
);

-- Update patient table for encrypted fields
-- Note: This preserves existing data structure but changes how data is stored
ALTER TABLE patients ADD COLUMN IF NOT EXISTS encryption_key_id VARCHAR(255);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS encrypted_fields JSONB DEFAULT '{}'::jsonb;

-- Add encryption tracking to health records
ALTER TABLE health_records ADD COLUMN IF NOT EXISTS encryption_key_id VARCHAR(255);
ALTER TABLE health_records ADD COLUMN IF NOT EXISTS is_encrypted BOOLEAN DEFAULT false;

-- Create function to track encryption key usage
CREATE OR REPLACE FUNCTION track_encryption_key_usage(p_key_id VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE encryption_keys
    SET
        last_used_at = CURRENT_TIMESTAMP,
        usage_count = usage_count + 1
    WHERE key_id = p_key_id;
END;
$$ LANGUAGE plpgsql;

-- Create function to check if key rotation is needed
CREATE OR REPLACE FUNCTION needs_key_rotation(p_key_id VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    v_created_at TIMESTAMP WITH TIME ZONE;
    v_usage_count INTEGER;
    v_is_active BOOLEAN;
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT created_at, usage_count, is_active, expires_at
    INTO v_created_at, v_usage_count, v_is_active, v_expires_at
    FROM encryption_keys
    WHERE key_id = p_key_id;

    -- Check if key exists and is active
    IF NOT FOUND OR NOT v_is_active THEN
        RETURN TRUE;
    END IF;

    -- Check expiration
    IF v_expires_at IS NOT NULL AND v_expires_at < CURRENT_TIMESTAMP THEN
        RETURN TRUE;
    END IF;

    -- Check age (rotate after 90 days)
    IF v_created_at < CURRENT_TIMESTAMP - INTERVAL '90 days' THEN
        RETURN TRUE;
    END IF;

    -- Check usage count (rotate after 1 million uses)
    IF v_usage_count > 1000000 THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Create view for active encryption keys
CREATE OR REPLACE VIEW active_encryption_keys AS
SELECT
    key_id,
    key_type,
    algorithm,
    created_at,
    expires_at,
    usage_count,
    last_used_at,
    CASE
        WHEN expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP THEN 'expired'
        WHEN created_at < CURRENT_TIMESTAMP - INTERVAL '90 days' THEN 'rotation_due'
        WHEN usage_count > 1000000 THEN 'high_usage'
        ELSE 'active'
    END as status
FROM encryption_keys
WHERE is_active = true;

-- Create audit trigger for encryption operations
CREATE TABLE IF NOT EXISTS encryption_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    operation VARCHAR(50) NOT NULL, -- encrypt, decrypt, rotate, backup, restore
    key_id VARCHAR(255),
    user_id UUID,
    table_name VARCHAR(255),
    record_id UUID,
    field_name VARCHAR(255),

    -- Performance metrics
    operation_duration_ms INTEGER,
    data_size_bytes INTEGER,

    -- Error tracking
    success BOOLEAN DEFAULT true,
    error_message TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_encryption_audit_operation ON encryption_audit_log(operation);
CREATE INDEX idx_encryption_audit_key ON encryption_audit_log(key_id);
CREATE INDEX idx_encryption_audit_user ON encryption_audit_log(user_id);
CREATE INDEX idx_encryption_audit_created ON encryption_audit_log(created_at DESC);

-- Function to log encryption operations
CREATE OR REPLACE FUNCTION log_encryption_operation(
    p_operation VARCHAR,
    p_key_id VARCHAR,
    p_user_id UUID,
    p_table_name VARCHAR DEFAULT NULL,
    p_record_id UUID DEFAULT NULL,
    p_field_name VARCHAR DEFAULT NULL,
    p_duration_ms INTEGER DEFAULT NULL,
    p_data_size INTEGER DEFAULT NULL,
    p_success BOOLEAN DEFAULT true,
    p_error_message TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS VOID AS $$
BEGIN
    INSERT INTO encryption_audit_log (
        operation,
        key_id,
        user_id,
        table_name,
        record_id,
        field_name,
        operation_duration_ms,
        data_size_bytes,
        success,
        error_message,
        metadata
    ) VALUES (
        p_operation,
        p_key_id,
        p_user_id,
        p_table_name,
        p_record_id,
        p_field_name,
        p_duration_ms,
        p_data_size,
        p_success,
        p_error_message,
        p_metadata
    );

    -- Track key usage
    IF p_success AND p_key_id IS NOT NULL THEN
        PERFORM track_encryption_key_usage(p_key_id);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create function to get encryption statistics
CREATE OR REPLACE FUNCTION get_encryption_statistics()
RETURNS TABLE (
    total_keys BIGINT,
    active_keys BIGINT,
    expired_keys BIGINT,
    keys_needing_rotation BIGINT,
    total_operations BIGINT,
    successful_operations BIGINT,
    failed_operations BIGINT,
    avg_operation_time_ms NUMERIC,
    total_data_encrypted_mb NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM encryption_keys) as total_keys,
        (SELECT COUNT(*) FROM encryption_keys WHERE is_active = true) as active_keys,
        (SELECT COUNT(*) FROM encryption_keys WHERE expires_at < CURRENT_TIMESTAMP) as expired_keys,
        (SELECT COUNT(*) FROM active_encryption_keys WHERE status != 'active') as keys_needing_rotation,
        (SELECT COUNT(*) FROM encryption_audit_log) as total_operations,
        (SELECT COUNT(*) FROM encryption_audit_log WHERE success = true) as successful_operations,
        (SELECT COUNT(*) FROM encryption_audit_log WHERE success = false) as failed_operations,
        (SELECT AVG(operation_duration_ms) FROM encryption_audit_log WHERE operation_duration_ms IS NOT NULL) as avg_operation_time_ms,
        (SELECT SUM(data_size_bytes) / 1024.0 / 1024.0 FROM encryption_audit_log WHERE data_size_bytes IS NOT NULL) as total_data_encrypted_mb;
END;
$$ LANGUAGE plpgsql;

-- Example: Prepare patients table for field-level encryption
-- This demonstrates how to handle encrypted fields without changing the schema
CREATE OR REPLACE FUNCTION prepare_patient_encryption()
RETURNS VOID AS $$
DECLARE
    v_key_id VARCHAR;
BEGIN
    -- Generate a default field encryption key (in practice, this would be done by the application)
    v_key_id := 'field_patient_data_' || gen_random_uuid()::text;

    -- Insert key metadata (actual key would be managed by application)
    INSERT INTO encryption_keys (
        key_id,
        key_type,
        algorithm,
        key_hash,
        created_by
    ) VALUES (
        v_key_id,
        'field',
        'aes_256_gcm',
        encode(sha256(v_key_id::bytea), 'hex'),
        'system'
    );

    -- Mark which fields should be encrypted
    UPDATE patients
    SET
        encryption_key_id = v_key_id,
        encrypted_fields = jsonb_build_object(
            'fields', ARRAY['name', 'date_of_birth', 'email', 'phone', 'address'],
            'encrypted_at', CURRENT_TIMESTAMP,
            'algorithm', 'aes_256_gcm'
        )
    WHERE encryption_key_id IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Indexes for encrypted data operations
CREATE INDEX idx_patients_encryption_key ON patients(encryption_key_id) WHERE encryption_key_id IS NOT NULL;
CREATE INDEX idx_health_records_encryption ON health_records(encryption_key_id) WHERE is_encrypted = true;

-- Permissions
GRANT SELECT ON encryption_keys TO healthcare_app_read;
GRANT INSERT, UPDATE ON encryption_keys TO healthcare_app_admin;
GRANT INSERT ON encryption_audit_log TO healthcare_app_write;
GRANT SELECT ON active_encryption_keys TO healthcare_app_read;

-- Comments
COMMENT ON TABLE encryption_keys IS 'Metadata for encryption keys used in the system';
COMMENT ON TABLE encryption_key_rotations IS 'History of key rotation operations';
COMMENT ON TABLE encryption_audit_log IS 'Audit log for all encryption/decryption operations';
COMMENT ON VIEW active_encryption_keys IS 'View of currently active encryption keys with status';
COMMENT ON FUNCTION needs_key_rotation IS 'Check if an encryption key needs to be rotated';
COMMENT ON FUNCTION get_encryption_statistics IS 'Get system-wide encryption usage statistics';
