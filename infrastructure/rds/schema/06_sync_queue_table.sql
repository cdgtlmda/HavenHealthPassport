-- Sync Queue table for offline synchronization
CREATE TABLE haven_health.sync_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sync_id UUID NOT NULL UNIQUE,

    -- Device and sync information
    device_id VARCHAR(255) NOT NULL,
    record_type VARCHAR(50) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3,
    status sync_status_enum NOT NULL DEFAULT 'pending',
    direction sync_direction_enum NOT NULL DEFAULT 'upload',

    -- Version control
    local_version INTEGER,
    server_version INTEGER,
    local_updated_at TIMESTAMP WITH TIME ZONE,
    server_updated_at TIMESTAMP WITH TIME ZONE,

    -- Conflict handling
    has_conflict BOOLEAN DEFAULT FALSE,
    conflict_resolution VARCHAR(50),
    conflict_data JSONB,

    -- Sync attempts
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,

    -- Data payload
    data_payload JSONB NOT NULL,
    data_size INTEGER NOT NULL,

    -- Device information
    device_info JSONB DEFAULT '{}',
    network_type VARCHAR(20),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for sync queue
CREATE INDEX idx_sync_queue_device ON haven_health.sync_queue(device_id, status);
CREATE INDEX idx_sync_queue_status ON haven_health.sync_queue(status, priority);
CREATE INDEX idx_sync_queue_retry ON haven_health.sync_queue(next_retry_at) WHERE status = 'failed';
CREATE INDEX idx_sync_queue_record ON haven_health.sync_queue(record_type, record_id);

-- Create trigger for updated_at
CREATE TRIGGER update_sync_queue_updated_at BEFORE UPDATE ON haven_health.sync_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
