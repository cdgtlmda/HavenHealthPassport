-- Migration: Add verification fields to family_groups table
-- Date: 2025-06-08
-- Purpose: Store verification information for patient family groups

-- Add verification tracking columns to family_groups table
ALTER TABLE family_groups 
ADD COLUMN verified_by VARCHAR(255),
ADD COLUMN verified_at TIMESTAMP,
ADD COLUMN verification_method VARCHAR(50),
ADD COLUMN verification_evidence JSONB;

-- Create index on verified_by for audit queries
CREATE INDEX idx_family_groups_verified_by ON family_groups(verified_by);

-- Create index on verified_at for time-based queries
CREATE INDEX idx_family_groups_verified_at ON family_groups(verified_at);

-- Create index on verification_method for filtering
CREATE INDEX idx_family_groups_verification_method ON family_groups(verification_method);

-- Add comment explaining the columns
COMMENT ON COLUMN family_groups.verified_by IS 'User ID of the person who verified the family composition';
COMMENT ON COLUMN family_groups.verified_at IS 'Timestamp when the family composition was verified';
COMMENT ON COLUMN family_groups.verification_method IS 'Method used for verification (manual_verification, document_verification, biometric_verification, etc.)';
COMMENT ON COLUMN family_groups.verification_evidence IS 'JSON object containing evidence details for the verification';

-- Create verification audit table for detailed tracking
CREATE TABLE family_verification_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_group_id VARCHAR(255) NOT NULL,
    verified_by VARCHAR(255) NOT NULL,
    verified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verification_method VARCHAR(50) NOT NULL,
    verification_evidence JSONB,
    previous_verification_date DATE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_group_id) REFERENCES family_groups(group_id) ON DELETE CASCADE
);

-- Create indexes for audit table
CREATE INDEX idx_family_verification_audit_family_group_id ON family_verification_audit(family_group_id);
CREATE INDEX idx_family_verification_audit_verified_by ON family_verification_audit(verified_by);
CREATE INDEX idx_family_verification_audit_verified_at ON family_verification_audit(verified_at);

-- Add trigger to automatically create audit record on verification
CREATE OR REPLACE FUNCTION create_family_verification_audit()
RETURNS TRIGGER AS $$
BEGIN
    -- Only create audit record if verified_by is being set
    IF NEW.verified_by IS NOT NULL AND (OLD.verified_by IS NULL OR NEW.verified_by != OLD.verified_by) THEN
        INSERT INTO family_verification_audit (
            family_group_id,
            verified_by,
            verified_at,
            verification_method,
            verification_evidence,
            previous_verification_date
        ) VALUES (
            NEW.group_id,
            NEW.verified_by,
            NEW.verified_at,
            NEW.verification_method,
            NEW.verification_evidence,
            OLD.last_verified
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER family_verification_audit_trigger
AFTER INSERT OR UPDATE ON family_groups
FOR EACH ROW
EXECUTE FUNCTION create_family_verification_audit();

-- Grant appropriate permissions
GRANT SELECT, INSERT ON family_verification_audit TO haven_app_role;
GRANT UPDATE (verified_by, verified_at, verification_method, verification_evidence) ON family_groups TO haven_app_role;