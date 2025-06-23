-- Migration: Add virus scan records table
-- Description: Track virus scan results for uploaded files
-- Date: 2024-01-01

-- Create virus scan records table
CREATE TABLE IF NOT EXISTS virus_scan_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- File information
    file_id VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,

    -- Scan information
    scan_provider VARCHAR(50) NOT NULL,
    scan_status VARCHAR(20) NOT NULL,
    threat_level VARCHAR(20) NOT NULL,
    is_clean BOOLEAN NOT NULL DEFAULT false,
    threats_found JSONB DEFAULT '[]'::jsonb,
    scan_duration REAL NOT NULL, -- seconds
    error_message TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    scanned_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Indexes
    CONSTRAINT check_scan_status CHECK (scan_status IN ('pending', 'scanning', 'completed', 'failed', 'timeout')),
    CONSTRAINT check_threat_level CHECK (threat_level IN ('clean', 'suspicious', 'malicious', 'unknown')),
    CONSTRAINT check_scan_provider CHECK (scan_provider IN ('clamav', 'aws_macie', 'virustotal', 'metadefender', 'windows_defender', 'hybrid_analysis'))
);

-- Create indexes
CREATE INDEX idx_virus_scan_file_id ON virus_scan_records(file_id);
CREATE INDEX idx_virus_scan_file_hash ON virus_scan_records(file_hash);
CREATE INDEX idx_virus_scan_is_clean ON virus_scan_records(is_clean);
CREATE INDEX idx_virus_scan_threat_level ON virus_scan_records(threat_level);
CREATE INDEX idx_virus_scan_provider ON virus_scan_records(scan_provider);
CREATE INDEX idx_virus_scan_scanned_at ON virus_scan_records(scanned_at DESC);

-- Create composite index for common queries
CREATE INDEX idx_virus_scan_file_clean ON virus_scan_records(file_id, is_clean, scanned_at DESC);

-- Create trigger for updated_at
CREATE TRIGGER update_virus_scan_records_updated_at
    BEFORE UPDATE ON virus_scan_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create virus scan statistics view
CREATE OR REPLACE VIEW virus_scan_statistics AS
SELECT
    COUNT(*) as total_scans,
    COUNT(CASE WHEN is_clean = true THEN 1 END) as clean_scans,
    COUNT(CASE WHEN is_clean = false THEN 1 END) as infected_scans,
    COUNT(CASE WHEN threat_level = 'malicious' THEN 1 END) as malicious_files,
    COUNT(CASE WHEN threat_level = 'suspicious' THEN 1 END) as suspicious_files,
    COUNT(CASE WHEN scan_status = 'failed' THEN 1 END) as failed_scans,
    AVG(scan_duration)::NUMERIC(10,2) as avg_scan_duration,
    MAX(scan_duration)::NUMERIC(10,2) as max_scan_duration,
    MIN(scan_duration)::NUMERIC(10,2) as min_scan_duration
FROM virus_scan_records;

-- Create function to get latest scan for a file
CREATE OR REPLACE FUNCTION get_latest_virus_scan(p_file_id VARCHAR)
RETURNS TABLE (
    file_id VARCHAR,
    is_clean BOOLEAN,
    threat_level VARCHAR,
    threats_found JSONB,
    scan_provider VARCHAR,
    scanned_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        vsr.file_id,
        vsr.is_clean,
        vsr.threat_level,
        vsr.threats_found,
        vsr.scan_provider,
        vsr.scanned_at
    FROM virus_scan_records vsr
    WHERE vsr.file_id = p_file_id
    ORDER BY vsr.scanned_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Create function to check if file needs rescan
CREATE OR REPLACE FUNCTION needs_virus_rescan(
    p_file_id VARCHAR,
    p_max_age_hours INTEGER DEFAULT 168 -- 7 days
) RETURNS BOOLEAN AS $$
DECLARE
    v_last_scan TIMESTAMP WITH TIME ZONE;
    v_is_clean BOOLEAN;
BEGIN
    -- Get last scan info
    SELECT scanned_at, is_clean
    INTO v_last_scan, v_is_clean
    FROM virus_scan_records
    WHERE file_id = p_file_id
    ORDER BY scanned_at DESC
    LIMIT 1;

    -- If never scanned, needs scan
    IF v_last_scan IS NULL THEN
        RETURN TRUE;
    END IF;

    -- If last scan found threats, always rescan
    IF NOT v_is_clean THEN
        RETURN TRUE;
    END IF;

    -- Check if scan is too old
    RETURN (CURRENT_TIMESTAMP - v_last_scan) > INTERVAL '1 hour' * p_max_age_hours;
END;
$$ LANGUAGE plpgsql;

-- Add virus scan fields to file_attachments if they don't exist
DO $$
BEGIN
    -- Add last_virus_scan column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'file_attachments'
                   AND column_name = 'last_virus_scan') THEN
        ALTER TABLE file_attachments
        ADD COLUMN last_virus_scan TIMESTAMP WITH TIME ZONE;
    END IF;

    -- Add virus_scan_status column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'file_attachments'
                   AND column_name = 'virus_scan_status') THEN
        ALTER TABLE file_attachments
        ADD COLUMN virus_scan_status VARCHAR(20) DEFAULT 'pending';
    END IF;

    -- Add is_quarantined column if not exists
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'file_attachments'
                   AND column_name = 'is_quarantined') THEN
        ALTER TABLE file_attachments
        ADD COLUMN is_quarantined BOOLEAN DEFAULT false;
    END IF;
END $$;

-- Create trigger to quarantine infected files
CREATE OR REPLACE FUNCTION quarantine_infected_files()
RETURNS TRIGGER AS $$
BEGIN
    -- If scan shows file is infected, quarantine it
    IF NEW.is_clean = false AND NEW.scan_status = 'completed' THEN
        UPDATE file_attachments
        SET
            is_quarantined = true,
            virus_scan_status = 'infected',
            last_virus_scan = NEW.scanned_at,
            status = 'quarantined'
        WHERE file_id = NEW.file_id;
    ELSIF NEW.is_clean = true AND NEW.scan_status = 'completed' THEN
        -- Mark file as clean
        UPDATE file_attachments
        SET
            is_quarantined = false,
            virus_scan_status = 'clean',
            last_virus_scan = NEW.scanned_at
        WHERE file_id = NEW.file_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_quarantine_infected_files
    AFTER INSERT OR UPDATE ON virus_scan_records
    FOR EACH ROW
    EXECUTE FUNCTION quarantine_infected_files();

-- Create alert function for malicious files
CREATE OR REPLACE FUNCTION alert_on_malicious_file()
RETURNS TRIGGER AS $$
BEGIN
    -- If malicious file detected, log alert
    IF NEW.threat_level = 'malicious' AND NEW.scan_status = 'completed' THEN
        INSERT INTO system_alerts (
            alert_type,
            severity,
            title,
            message,
            context,
            created_at
        ) VALUES (
            'virus_detected',
            'critical',
            'Malicious File Detected',
            format('Malicious file detected: %s (Hash: %s)', NEW.filename, LEFT(NEW.file_hash, 16)),
            jsonb_build_object(
                'file_id', NEW.file_id,
                'file_hash', NEW.file_hash,
                'filename', NEW.filename,
                'threats', NEW.threats_found,
                'scan_provider', NEW.scan_provider
            ),
            CURRENT_TIMESTAMP
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_alert_malicious_files
    AFTER INSERT ON virus_scan_records
    FOR EACH ROW
    WHEN (NEW.threat_level = 'malicious')
    EXECUTE FUNCTION alert_on_malicious_file();

-- Grant permissions
GRANT SELECT ON virus_scan_records TO healthcare_app_read;
GRANT INSERT, UPDATE ON virus_scan_records TO healthcare_app_write;
GRANT SELECT ON virus_scan_statistics TO healthcare_app_read;

-- Comments
COMMENT ON TABLE virus_scan_records IS 'Records of virus scans performed on uploaded files';
COMMENT ON COLUMN virus_scan_records.file_id IS 'ID of the file that was scanned';
COMMENT ON COLUMN virus_scan_records.file_hash IS 'SHA-256 hash of the file content';
COMMENT ON COLUMN virus_scan_records.threat_level IS 'Classification of threat: clean, suspicious, malicious, unknown';
COMMENT ON COLUMN virus_scan_records.threats_found IS 'JSON array of detected threats with details';
COMMENT ON COLUMN virus_scan_records.scan_duration IS 'Time taken to scan file in seconds';
COMMENT ON VIEW virus_scan_statistics IS 'Aggregated statistics for virus scanning';
COMMENT ON FUNCTION get_latest_virus_scan IS 'Get the most recent virus scan result for a file';
COMMENT ON FUNCTION needs_virus_rescan IS 'Check if a file needs to be rescanned based on age and previous results';
