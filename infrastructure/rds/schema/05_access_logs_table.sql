-- Access Logs table for audit trail
CREATE TABLE audit.access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Access subject (who is accessing)
    user_id UUID NOT NULL,
    user_name VARCHAR(200),
    user_role VARCHAR(50),
    organization_id UUID,
    organization_name VARCHAR(200),

    -- Access object (what is being accessed)
    patient_id UUID REFERENCES haven_health.patients(id) ON DELETE SET NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    resource_details JSONB DEFAULT '{}',

    -- Access details
    access_type access_type_enum NOT NULL,
    access_context access_context_enum NOT NULL,
    access_result access_result_enum NOT NULL DEFAULT 'success',
    access_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Purpose and justification
    purpose_of_access VARCHAR(255) NOT NULL,
    access_justification TEXT,
    emergency_override BOOLEAN DEFAULT FALSE,
    consent_reference UUID,

    -- Technical details
    ip_address INET,
    user_agent TEXT,
    session_id UUID,
    request_id UUID,

    -- Response information
    response_time_ms INTEGER,
    data_returned JSONB,
    error_details JSONB,

    -- Compliance
    data_minimization_applied BOOLEAN DEFAULT TRUE,
    sensitive_data_accessed JSONB DEFAULT '[]',
    cross_border_transfer BOOLEAN DEFAULT FALSE,
    destination_country CHAR(2),

    -- No soft delete for audit logs - they are immutable
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for access logs
CREATE INDEX idx_access_logs_user ON audit.access_logs(user_id);
CREATE INDEX idx_access_logs_patient ON audit.access_logs(patient_id) WHERE patient_id IS NOT NULL;
CREATE INDEX idx_access_logs_timestamp ON audit.access_logs(access_timestamp DESC);
CREATE INDEX idx_access_logs_type ON audit.access_logs(access_type, access_context);
CREATE INDEX idx_access_logs_resource ON audit.access_logs(resource_type, resource_id);

-- Partition by month for better performance
CREATE TABLE audit.access_logs_template (LIKE audit.access_logs INCLUDING ALL);
