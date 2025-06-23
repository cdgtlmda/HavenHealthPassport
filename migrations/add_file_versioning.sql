-- Migration: Add file versioning support
-- Description: Create tables and functions for comprehensive file version management
-- Date: 2024-01-01

-- Create file versions table
CREATE TABLE IF NOT EXISTS file_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Version identification
    file_id VARCHAR(500) NOT NULL, -- Base file identifier
    version_id VARCHAR(500) UNIQUE NOT NULL, -- Unique version identifier
    version_number INTEGER NOT NULL,

    -- Version metadata
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(200) NOT NULL,
    size BIGINT NOT NULL,
    checksum VARCHAR(64) NOT NULL, -- SHA-256 hash
    storage_path VARCHAR(1000) NOT NULL,

    -- Version status
    status VARCHAR(50) NOT NULL DEFAULT 'current',
    change_type VARCHAR(50) NOT NULL DEFAULT 'minor',
    change_description TEXT,

    -- Relationships
    parent_version_id VARCHAR(500),
    created_by UUID NOT NULL,
    approved_by UUID,

    -- Timestamps
    approved_at TIMESTAMP WITH TIME ZONE,
    archived_at TIMESTAMP WITH TIME ZONE,

    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',

    -- Security
    is_locked BOOLEAN DEFAULT false,
    requires_approval BOOLEAN DEFAULT false,

    -- Constraints
    CONSTRAINT unique_file_version UNIQUE (file_id, version_number),
    CONSTRAINT check_status CHECK (status IN ('current', 'archived', 'deleted', 'draft', 'pending_review', 'superseded')),
    CONSTRAINT check_change_type CHECK (change_type IN ('minor', 'major', 'critical', 'format', 'metadata'))
);

-- Create indexes
CREATE INDEX idx_file_versions_file_id ON file_versions(file_id);
CREATE INDEX idx_file_versions_status ON file_versions(status);
CREATE INDEX idx_file_versions_created_by ON file_versions(created_by);
CREATE INDEX idx_file_versions_created_at ON file_versions(created_at DESC);
CREATE INDEX idx_file_versions_current ON file_versions(file_id, status) WHERE status = 'current';

-- Create file version history table
CREATE TABLE IF NOT EXISTS file_version_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    file_id VARCHAR(500) NOT NULL,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    changed_by UUID NOT NULL,
    change_reason TEXT,
    rollback_of VARCHAR(500), -- Version ID if this is a rollback
    metadata JSONB DEFAULT '{}'::jsonb,

    FOREIGN KEY (file_id, from_version) REFERENCES file_versions(file_id, version_number),
    FOREIGN KEY (file_id, to_version) REFERENCES file_versions(file_id, version_number)
);

-- Create indexes for history
CREATE INDEX idx_version_history_file ON file_version_history(file_id);
CREATE INDEX idx_version_history_changed_by ON file_version_history(changed_by);
CREATE INDEX idx_version_history_created ON file_version_history(created_at DESC);

-- Create function to get current version
CREATE OR REPLACE FUNCTION get_current_file_version(p_file_id VARCHAR)
RETURNS TABLE (
    version_id VARCHAR,
    version_number INTEGER,
    filename VARCHAR,
    size BIGINT,
    checksum VARCHAR,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        fv.version_id,
        fv.version_number,
        fv.filename,
        fv.size,
        fv.checksum,
        fv.created_by,
        fv.created_at
    FROM file_versions fv
    WHERE fv.file_id = p_file_id
    AND fv.status = 'current'
    ORDER BY fv.version_number DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Create function to get version history
CREATE OR REPLACE FUNCTION get_file_version_history(
    p_file_id VARCHAR,
    p_limit INTEGER DEFAULT 50
)
RETURNS TABLE (
    version_number INTEGER,
    version_id VARCHAR,
    status VARCHAR,
    change_type VARCHAR,
    change_description TEXT,
    size BIGINT,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE,
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        fv.version_number,
        fv.version_id,
        fv.status,
        fv.change_type,
        fv.change_description,
        fv.size,
        fv.created_by,
        fv.created_at,
        fv.approved_by,
        fv.approved_at
    FROM file_versions fv
    WHERE fv.file_id = p_file_id
    ORDER BY fv.version_number DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Create function to compare versions
CREATE OR REPLACE FUNCTION compare_file_versions(
    p_file_id VARCHAR,
    p_version_a INTEGER,
    p_version_b INTEGER
)
RETURNS TABLE (
    attribute VARCHAR,
    version_a_value TEXT,
    version_b_value TEXT,
    changed BOOLEAN
) AS $$
DECLARE
    v_a RECORD;
    v_b RECORD;
BEGIN
    -- Get version A
    SELECT * INTO v_a
    FROM file_versions
    WHERE file_id = p_file_id AND version_number = p_version_a;

    -- Get version B
    SELECT * INTO v_b
    FROM file_versions
    WHERE file_id = p_file_id AND version_number = p_version_b;

    -- Compare attributes
    RETURN QUERY
    SELECT 'filename'::VARCHAR, v_a.filename::TEXT, v_b.filename::TEXT, v_a.filename != v_b.filename
    UNION ALL
    SELECT 'size'::VARCHAR, v_a.size::TEXT, v_b.size::TEXT, v_a.size != v_b.size
    UNION ALL
    SELECT 'checksum'::VARCHAR, v_a.checksum::TEXT, v_b.checksum::TEXT, v_a.checksum != v_b.checksum
    UNION ALL
    SELECT 'content_type'::VARCHAR, v_a.content_type::TEXT, v_b.content_type::TEXT, v_a.content_type != v_b.content_type;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to maintain version numbers
CREATE OR REPLACE FUNCTION maintain_version_numbers()
RETURNS TRIGGER AS $$
DECLARE
    v_max_version INTEGER;
BEGIN
    -- For new versions, ensure version number is sequential
    IF TG_OP = 'INSERT' THEN
        -- Get max version number for this file
        SELECT COALESCE(MAX(version_number), 0) INTO v_max_version
        FROM file_versions
        WHERE file_id = NEW.file_id;

        -- Set version number if not provided or invalid
        IF NEW.version_number IS NULL OR NEW.version_number <= v_max_version THEN
            NEW.version_number := v_max_version + 1;
        END IF;

        -- Update current version status
        IF NEW.status = 'current' AND NOT NEW.requires_approval THEN
            UPDATE file_versions
            SET status = 'superseded'
            WHERE file_id = NEW.file_id
            AND status = 'current'
            AND version_id != NEW.version_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_maintain_version_numbers
    BEFORE INSERT ON file_versions
    FOR EACH ROW
    EXECUTE FUNCTION maintain_version_numbers();

-- Create function to rollback to version
CREATE OR REPLACE FUNCTION rollback_to_version(
    p_file_id VARCHAR,
    p_target_version INTEGER,
    p_rolled_back_by UUID,
    p_reason TEXT
)
RETURNS file_versions AS $$
DECLARE
    v_target RECORD;
    v_new_version file_versions;
    v_new_version_number INTEGER;
BEGIN
    -- Get target version
    SELECT * INTO v_target
    FROM file_versions
    WHERE file_id = p_file_id AND version_number = p_target_version;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Target version % not found for file %', p_target_version, p_file_id;
    END IF;

    -- Get next version number
    SELECT COALESCE(MAX(version_number), 0) + 1 INTO v_new_version_number
    FROM file_versions
    WHERE file_id = p_file_id;

    -- Create new version from target
    INSERT INTO file_versions (
        file_id,
        version_id,
        version_number,
        filename,
        content_type,
        size,
        checksum,
        storage_path,
        status,
        change_type,
        change_description,
        parent_version_id,
        created_by,
        metadata
    ) VALUES (
        p_file_id,
        p_file_id || '_v' || v_new_version_number || '_rollback',
        v_new_version_number,
        v_target.filename,
        v_target.content_type,
        v_target.size,
        v_target.checksum,
        v_target.storage_path,
        'current',
        'major',
        'Rollback to version ' || p_target_version || ': ' || p_reason,
        v_target.version_id,
        p_rolled_back_by,
        jsonb_build_object(
            'rollback_from_version', (SELECT version_number FROM file_versions WHERE file_id = p_file_id AND status = 'current'),
            'rollback_to_version', p_target_version,
            'rollback_reason', p_reason,
            'original_metadata', v_target.metadata
        )
    ) RETURNING * INTO v_new_version;

    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql;

-- Create view for version statistics
CREATE OR REPLACE VIEW file_version_statistics AS
SELECT
    file_id,
    COUNT(*) as total_versions,
    COUNT(CASE WHEN status = 'current' THEN 1 END) as current_versions,
    COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived_versions,
    COUNT(CASE WHEN status = 'deleted' THEN 1 END) as deleted_versions,
    COUNT(CASE WHEN is_locked THEN 1 END) as locked_versions,
    SUM(size) as total_size_bytes,
    SUM(CASE WHEN status NOT IN ('deleted', 'archived') THEN size ELSE 0 END) as active_size_bytes,
    MAX(version_number) as latest_version_number,
    MAX(created_at) as last_modified
FROM file_versions
GROUP BY file_id;

-- Create function to clean up old versions
CREATE OR REPLACE FUNCTION cleanup_old_versions(
    p_file_id VARCHAR,
    p_keep_versions INTEGER DEFAULT 10,
    p_force BOOLEAN DEFAULT false
)
RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER := 0;
    v_version RECORD;
BEGIN
    -- Delete old versions keeping the most recent ones
    FOR v_version IN
        SELECT version_id, is_locked
        FROM file_versions
        WHERE file_id = p_file_id
        AND status NOT IN ('current', 'deleted')
        ORDER BY version_number DESC
        OFFSET p_keep_versions
    LOOP
        -- Skip locked versions unless forced
        IF v_version.is_locked AND NOT p_force THEN
            CONTINUE;
        END IF;

        -- Mark as deleted
        UPDATE file_versions
        SET status = 'deleted'
        WHERE version_id = v_version.version_id;

        v_deleted_count := v_deleted_count + 1;
    END LOOP;

    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create audit trigger for version changes
CREATE OR REPLACE FUNCTION audit_version_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Log status changes
        IF OLD.status != NEW.status THEN
            INSERT INTO file_version_history (
                file_id,
                from_version,
                to_version,
                change_type,
                changed_by,
                change_reason,
                metadata
            ) VALUES (
                NEW.file_id,
                NEW.version_number,
                NEW.version_number,
                'status_change',
                COALESCE(NEW.approved_by, NEW.created_by),
                'Status changed from ' || OLD.status || ' to ' || NEW.status,
                jsonb_build_object(
                    'old_status', OLD.status,
                    'new_status', NEW.status,
                    'timestamp', CURRENT_TIMESTAMP
                )
            );
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_audit_version_changes
    AFTER UPDATE ON file_versions
    FOR EACH ROW
    EXECUTE FUNCTION audit_version_changes();

-- Add version support to file_attachments table
ALTER TABLE file_attachments ADD COLUMN IF NOT EXISTS current_version_id VARCHAR(500);
ALTER TABLE file_attachments ADD COLUMN IF NOT EXISTS version_count INTEGER DEFAULT 1;
ALTER TABLE file_attachments ADD COLUMN IF NOT EXISTS versioning_enabled BOOLEAN DEFAULT true;

-- Create function to link file attachment with versions
CREATE OR REPLACE FUNCTION link_file_attachment_version()
RETURNS TRIGGER AS $$
BEGIN
    -- When a new current version is created, update file_attachments
    IF NEW.status = 'current' THEN
        UPDATE file_attachments
        SET
            current_version_id = NEW.version_id,
            version_count = (
                SELECT COUNT(*)
                FROM file_versions
                WHERE file_id = NEW.file_id
            ),
            updated_at = CURRENT_TIMESTAMP
        WHERE file_id = NEW.file_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_link_file_attachment_version
    AFTER INSERT OR UPDATE ON file_versions
    FOR EACH ROW
    WHEN (NEW.status = 'current')
    EXECUTE FUNCTION link_file_attachment_version();

-- Permissions
GRANT SELECT ON file_versions TO healthcare_app_read;
GRANT INSERT, UPDATE ON file_versions TO healthcare_app_write;
GRANT INSERT ON file_version_history TO healthcare_app_write;
GRANT SELECT ON file_version_statistics TO healthcare_app_read;

-- Comments
COMMENT ON TABLE file_versions IS 'Comprehensive file version management with history tracking';
COMMENT ON TABLE file_version_history IS 'Audit trail of version changes and transitions';
COMMENT ON VIEW file_version_statistics IS 'Aggregated statistics for file versions';
COMMENT ON FUNCTION get_current_file_version IS 'Get the current active version of a file';
COMMENT ON FUNCTION rollback_to_version IS 'Create a new version by rolling back to a previous version';
COMMENT ON FUNCTION cleanup_old_versions IS 'Clean up old versions keeping only recent ones';
