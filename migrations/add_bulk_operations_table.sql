-- Add bulk operations table for scheduling and tracking bulk import/export/update operations

-- Create enum types
CREATE TYPE bulk_operation_type AS ENUM ('import', 'export', 'update', 'delete');
CREATE TYPE bulk_operation_status AS ENUM ('scheduled', 'processing', 'completed', 'failed', 'cancelled');

-- Create bulk_operations table
CREATE TABLE IF NOT EXISTS bulk_operations (
    id VARCHAR(255) PRIMARY KEY,
    type bulk_operation_type NOT NULL,
    status bulk_operation_status NOT NULL DEFAULT 'scheduled',
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parameters TEXT, -- JSON string of operation parameters
    result TEXT,     -- JSON string of operation results
    error_message TEXT,
    
    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX idx_bulk_operations_organization_id ON bulk_operations(organization_id);
CREATE INDEX idx_bulk_operations_status ON bulk_operations(status);
CREATE INDEX idx_bulk_operations_scheduled_at ON bulk_operations(scheduled_at);
CREATE INDEX idx_bulk_operations_user_id ON bulk_operations(user_id);
CREATE INDEX idx_bulk_operations_type ON bulk_operations(type);
CREATE INDEX idx_bulk_operations_created_at ON bulk_operations(created_at);

-- Add comment to table
COMMENT ON TABLE bulk_operations IS 'Tracks scheduled and executed bulk operations for import, export, and update of patient records';
