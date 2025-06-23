-- Column Encryption Schema for Haven Health Passport
-- This schema implements column-level encryption for sensitive healthcare data

-- Create encryption key table for key management
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_id SERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    key_version INTEGER NOT NULL DEFAULT 1,
    encrypted_key TEXT NOT NULL,
    encryption_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(table_name, column_name, key_version)
);

-- Create index for key lookups
CREATE INDEX idx_encryption_keys_lookup ON encryption_keys(table_name, column_name, is_active);

-- Patients table with encrypted columns
CREATE TABLE IF NOT EXISTS patients (
    patient_id SERIAL PRIMARY KEY,

    -- Searchable encrypted fields (deterministic encryption)
    ssn TEXT, -- Encrypted
    medical_record_number TEXT, -- Encrypted
    email TEXT, -- Encrypted
    phone TEXT, -- Encrypted

    -- Non-searchable encrypted fields (randomized encryption)
    first_name TEXT, -- Encrypted
    last_name TEXT, -- Encrypted
    date_of_birth TEXT, -- Encrypted
    address TEXT, -- Encrypted
    insurance_id TEXT, -- Encrypted

    -- Protected fields (basic encryption)
    gender TEXT, -- Encrypted
    blood_type TEXT, -- Encrypted

    -- Public fields (no encryption)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for searchable encrypted fields
CREATE INDEX idx_patients_ssn ON patients(ssn);
CREATE INDEX idx_patients_mrn ON patients(medical_record_number);
-- Medical records table with encrypted columns
CREATE TABLE IF NOT EXISTS medical_records (
    record_id SERIAL PRIMARY KEY,

    -- Searchable fields
    patient_id TEXT, -- Encrypted reference
    record_number TEXT, -- Encrypted

    -- Sensitive medical data (randomized encryption)
    diagnosis TEXT, -- Encrypted
    treatment TEXT, -- Encrypted
    notes TEXT, -- Encrypted
    lab_results JSONB, -- Encrypted JSON
    medications JSONB, -- Encrypted JSON
    allergies JSONB, -- Encrypted JSON

    -- Protected fields
    record_type VARCHAR(50), -- Encrypted
    department VARCHAR(100), -- Encrypted
    provider_name TEXT, -- Encrypted

    -- Public metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for searchable fields
CREATE INDEX idx_medical_records_patient ON medical_records(patient_id);
CREATE INDEX idx_medical_records_number ON medical_records(record_number);

-- Test results table
CREATE TABLE IF NOT EXISTS test_results (
    result_id SERIAL PRIMARY KEY,

    -- Searchable fields
    patient_id TEXT, -- Encrypted
    test_code VARCHAR(50), -- Encrypted

    -- Sensitive results (randomized encryption)
    result_value TEXT, -- Encrypted
    result_text TEXT, -- Encrypted
    abnormal_flags TEXT, -- Encrypted
    reference_range TEXT, -- Encrypted

    -- Protected fields
    test_name VARCHAR(255), -- Encrypted
    unit VARCHAR(50), -- Encrypted

    -- Public fields
    test_date DATE,
    lab_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Function to rotate encryption keys
CREATE OR REPLACE FUNCTION rotate_encryption_key(
    p_table_name VARCHAR,
    p_column_name VARCHAR
) RETURNS VOID AS $$
DECLARE
    v_current_version INTEGER;
BEGIN
    -- Get current key version
    SELECT COALESCE(MAX(key_version), 0) INTO v_current_version
    FROM encryption_keys
    WHERE table_name = p_table_name AND column_name = p_column_name;

    -- Mark current key as inactive
    UPDATE encryption_keys
    SET is_active = FALSE,
        rotated_at = CURRENT_TIMESTAMP
    WHERE table_name = p_table_name
        AND column_name = p_column_name
        AND is_active = TRUE;

    -- New key would be inserted by application with new version
    RAISE NOTICE 'Key rotation initiated for %.%', p_table_name, p_column_name;
END;
$$ LANGUAGE plpgsql;

-- Audit table for encryption operations
CREATE TABLE IF NOT EXISTS encryption_audit (
    audit_id SERIAL PRIMARY KEY,
    operation VARCHAR(50) NOT NULL,
    table_name VARCHAR(255),
    column_name VARCHAR(255),
    user_id VARCHAR(255),
    operation_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    details JSONB
);

-- Create audit trigger function
CREATE OR REPLACE FUNCTION log_encryption_operation() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO encryption_audit (operation, table_name, column_name, user_id, details)
    VALUES (TG_OP, TG_TABLE_NAME, NULL, current_user, to_jsonb(NEW));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON TABLE patients IS 'Patient records with column-level encryption for PII';
COMMENT ON COLUMN patients.ssn IS 'Encrypted SSN using deterministic encryption for searching';
