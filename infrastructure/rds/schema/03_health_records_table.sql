-- Health Records table
CREATE TABLE haven_health.health_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Record identification
    record_type record_type_enum NOT NULL,
    record_subtype VARCHAR(50),
    title VARCHAR(255) NOT NULL,

    -- Patient relationship
    patient_id UUID NOT NULL REFERENCES haven_health.patients(id) ON DELETE CASCADE,

    -- Record content (encrypted)
    encrypted_content TEXT NOT NULL,
    content_type VARCHAR(50) DEFAULT 'application/json',
    encryption_key_id VARCHAR(100),

    -- Metadata
    record_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_date TIMESTAMP WITH TIME ZONE,
    status record_status_enum NOT NULL DEFAULT 'draft',
    priority record_priority_enum DEFAULT 'routine',

    -- Provider information
    provider_id UUID,
    provider_name VARCHAR(200),
    provider_organization VARCHAR(200),
    facility_name VARCHAR(200),
    facility_location VARCHAR(200),

    -- Categorization
    categories JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    icd_codes JSONB DEFAULT '[]',
    loinc_codes JSONB DEFAULT '[]',

    -- Attachments
    attachments JSONB DEFAULT '[]',
    thumbnail_url VARCHAR(500),

    -- Access control
    access_level VARCHAR(20) DEFAULT 'standard',
    authorized_viewers JSONB DEFAULT '[]',
    require_2fa_to_view BOOLEAN DEFAULT FALSE,

    -- Audit trail
    version INTEGER DEFAULT 1,
    previous_version_id UUID,
    change_reason TEXT,
    verified_by UUID,
    verified_at TIMESTAMP WITH TIME ZONE,

    -- Emergency access
    emergency_accessible BOOLEAN DEFAULT TRUE,
    emergency_contact_notified BOOLEAN DEFAULT FALSE,

    -- Integration fields
    source_system VARCHAR(100),
    external_id VARCHAR(200),
    import_timestamp TIMESTAMP WITH TIME ZONE,

    -- Blockchain reference
    blockchain_hash VARCHAR(255),
    blockchain_tx_id VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by UUID
);

-- Create indexes for health records
CREATE INDEX idx_health_records_patient ON haven_health.health_records(patient_id);
CREATE INDEX idx_health_records_type ON haven_health.health_records(record_type, record_subtype);
CREATE INDEX idx_health_records_date ON haven_health.health_records(record_date DESC);
CREATE INDEX idx_health_records_status ON haven_health.health_records(status);
CREATE INDEX idx_health_records_provider ON haven_health.health_records(provider_id) WHERE provider_id IS NOT NULL;
CREATE INDEX idx_health_records_deleted ON haven_health.health_records(deleted_at) WHERE deleted_at IS NULL;

-- Create trigger for updated_at
CREATE TRIGGER update_health_records_updated_at BEFORE UPDATE ON haven_health.health_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
