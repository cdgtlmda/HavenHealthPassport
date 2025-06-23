-- Migration: Add translation queue tables for human translation fallback
-- Created: 2025-01-29

-- Translation queue table for managing human translation requests
CREATE TABLE IF NOT EXISTS translation_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request information
    source_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    target_dialect VARCHAR(20),
    translation_type VARCHAR(50) NOT NULL,
    translation_context VARCHAR(50) NOT NULL,

    -- Queue metadata
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    queue_reason VARCHAR(50) NOT NULL,

    -- Bedrock attempt information
    bedrock_translation TEXT,
    bedrock_confidence_score FLOAT,
    bedrock_error TEXT,
    bedrock_medical_validation JSONB,

    -- Human translation
    human_translation TEXT,
    translator_id UUID,
    translation_notes TEXT,
    quality_score FLOAT,

    -- Processing information
    assigned_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,

    -- Context information
    patient_id UUID,
    document_id UUID,
    session_id VARCHAR(100),

    -- Medical context
    medical_terms_detected JSONB,
    medical_category VARCHAR(50),
    cultural_notes JSONB,

    -- User information
    requested_by UUID NOT NULL,
    organization_id UUID,

    -- Additional metadata
    metadata JSONB,
    callback_url VARCHAR(500),
    expires_at TIMESTAMPTZ,

    -- Common fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    deleted_by UUID
);

-- Create indexes for translation queue
CREATE INDEX idx_translation_queue_status ON translation_queue(status);
CREATE INDEX idx_translation_queue_priority ON translation_queue(priority);
CREATE INDEX idx_translation_queue_queue_reason ON translation_queue(queue_reason);
CREATE INDEX idx_translation_queue_patient_id ON translation_queue(patient_id);
CREATE INDEX idx_translation_queue_document_id ON translation_queue(document_id);
CREATE INDEX idx_translation_queue_session_id ON translation_queue(session_id);
CREATE INDEX idx_translation_queue_requested_by ON translation_queue(requested_by);
CREATE INDEX idx_translation_queue_organization_id ON translation_queue(organization_id);
CREATE INDEX idx_translation_queue_translator_id ON translation_queue(translator_id);
CREATE INDEX idx_translation_queue_expires_at ON translation_queue(expires_at);

-- Composite indexes for efficient queries
CREATE INDEX idx_queue_status_priority ON translation_queue(status, priority);
CREATE INDEX idx_queue_patient_status ON translation_queue(patient_id, status);
CREATE INDEX idx_queue_translator_status ON translation_queue(translator_id, status);
CREATE INDEX idx_queue_expires_status ON translation_queue(expires_at, status);

-- Translation queue feedback table
CREATE TABLE IF NOT EXISTS translation_queue_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference to queue entry
    queue_entry_id UUID NOT NULL REFERENCES translation_queue(id),

    -- Feedback information
    feedback_type VARCHAR(50) NOT NULL, -- accuracy, clarity, terminology
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5), -- 1-5 scale
    comments TEXT,

    -- Who provided feedback
    feedback_by UUID NOT NULL,
    feedback_role VARCHAR(50), -- patient, provider, reviewer

    -- Medical accuracy specific feedback
    terminology_issues JSONB,
    suggested_corrections JSONB,

    -- Common fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    deleted_by UUID
);

-- Create indexes for feedback table
CREATE INDEX idx_queue_feedback_queue_entry_id ON translation_queue_feedback(queue_entry_id);
CREATE INDEX idx_queue_feedback_feedback_by ON translation_queue_feedback(feedback_by);
CREATE INDEX idx_queue_feedback_rating ON translation_queue_feedback(rating);

-- Translation queue assignment table
CREATE TABLE IF NOT EXISTS translation_queue_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Queue and translator
    queue_entry_id UUID NOT NULL REFERENCES translation_queue(id),
    translator_id UUID NOT NULL,

    -- Assignment details
    assigned_by UUID NOT NULL,
    assignment_reason VARCHAR(200),

    -- Translator qualifications for this assignment
    language_pair_certified BOOLEAN DEFAULT FALSE,
    medical_specialty_match VARCHAR(100),
    dialect_expertise VARCHAR(50),

    -- Assignment status
    status VARCHAR(20) DEFAULT 'active', -- active, completed, reassigned
    completed_at TIMESTAMPTZ,
    reassigned_at TIMESTAMPTZ,
    reassignment_reason TEXT,

    -- Common fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    deleted_by UUID
);

-- Create indexes for assignment table
CREATE INDEX idx_queue_assignment_queue_entry_id ON translation_queue_assignment(queue_entry_id);
CREATE INDEX idx_queue_assignment_translator_id ON translation_queue_assignment(translator_id);
CREATE INDEX idx_queue_assignment_assigned_by ON translation_queue_assignment(assigned_by);
CREATE INDEX idx_queue_assignment_status ON translation_queue_assignment(status);

-- Add triggers for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_translation_queue_updated_at BEFORE UPDATE ON translation_queue
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_translation_queue_feedback_updated_at BEFORE UPDATE ON translation_queue_feedback
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_translation_queue_assignment_updated_at BEFORE UPDATE ON translation_queue_assignment
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Add constraints
ALTER TABLE translation_queue
ADD CONSTRAINT check_status CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled', 'expired'));

ALTER TABLE translation_queue
ADD CONSTRAINT check_priority CHECK (priority IN ('low', 'normal', 'high', 'critical'));

ALTER TABLE translation_queue
ADD CONSTRAINT check_queue_reason CHECK (queue_reason IN ('low_confidence', 'bedrock_error', 'complex_medical', 'user_request', 'validation_failed', 'dialect_unavailable'));

ALTER TABLE translation_queue_feedback
ADD CONSTRAINT check_feedback_type CHECK (feedback_type IN ('accuracy', 'clarity', 'terminology'));

ALTER TABLE translation_queue_assignment
ADD CONSTRAINT check_assignment_status CHECK (status IN ('active', 'completed', 'reassigned'));

-- Function to expire old queue entries
CREATE OR REPLACE FUNCTION expire_old_queue_entries()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE translation_queue
    SET status = 'expired',
        updated_at = NOW()
    WHERE status IN ('pending', 'in_progress')
    AND expires_at < NOW()
    AND deleted_at IS NULL;

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get queue statistics
CREATE OR REPLACE FUNCTION get_queue_statistics()
RETURNS TABLE (
    status VARCHAR(20),
    priority VARCHAR(20),
    count BIGINT,
    avg_wait_time INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tq.status,
        tq.priority,
        COUNT(*) as count,
        AVG(
            CASE
                WHEN tq.completed_at IS NOT NULL THEN tq.completed_at - tq.created_at
                ELSE NOW() - tq.created_at
            END
        ) as avg_wait_time
    FROM translation_queue tq
    WHERE tq.deleted_at IS NULL
    GROUP BY tq.status, tq.priority
    ORDER BY tq.status, tq.priority;
END;
$$ LANGUAGE plpgsql;

-- Function to assign translator to queue entry
CREATE OR REPLACE FUNCTION assign_translator(
    p_queue_entry_id UUID,
    p_translator_id UUID,
    p_assigned_by UUID,
    p_assignment_reason VARCHAR(200) DEFAULT NULL,
    p_language_pair_certified BOOLEAN DEFAULT FALSE,
    p_medical_specialty_match VARCHAR(100) DEFAULT NULL,
    p_dialect_expertise VARCHAR(50) DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_assignment_id UUID;
BEGIN
    -- Update queue entry status
    UPDATE translation_queue
    SET status = 'in_progress',
        translator_id = p_translator_id,
        assigned_at = NOW(),
        updated_at = NOW()
    WHERE id = p_queue_entry_id
    AND status = 'pending'
    AND deleted_at IS NULL;

    -- Create assignment record
    INSERT INTO translation_queue_assignment (
        queue_entry_id,
        translator_id,
        assigned_by,
        assignment_reason,
        language_pair_certified,
        medical_specialty_match,
        dialect_expertise
    ) VALUES (
        p_queue_entry_id,
        p_translator_id,
        p_assigned_by,
        p_assignment_reason,
        p_language_pair_certified,
        p_medical_specialty_match,
        p_dialect_expertise
    ) RETURNING id INTO v_assignment_id;

    RETURN v_assignment_id;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed for your user roles)
-- GRANT SELECT, INSERT, UPDATE ON translation_queue TO api_user;
-- GRANT SELECT, INSERT, UPDATE ON translation_queue_feedback TO api_user;
-- GRANT SELECT, INSERT, UPDATE ON translation_queue_assignment TO api_user;
-- GRANT EXECUTE ON FUNCTION expire_old_queue_entries() TO api_user;
-- GRANT EXECUTE ON FUNCTION get_queue_statistics() TO api_user;
-- GRANT EXECUTE ON FUNCTION assign_translator TO api_user;
