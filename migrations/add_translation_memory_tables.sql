-- Translation Memory tables for Haven Health Passport
-- This migration creates tables for storing and managing translation memory

-- Create translation memory table
CREATE TABLE IF NOT EXISTS translation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Segment identification
    segment_hash VARCHAR(64) NOT NULL,
    source_text TEXT NOT NULL,
    target_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,

    -- Segment metadata
    segment_type VARCHAR(20) NOT NULL,
    context_hash VARCHAR(64),
    context_text TEXT,

    -- Quality and usage tracking
    quality_score FLOAT NOT NULL DEFAULT 1.0,
    usage_count INTEGER NOT NULL DEFAULT 0,
    last_used TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Source tracking
    source_type VARCHAR(50),
    source_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Constraints
    CONSTRAINT quality_score_range CHECK (quality_score >= 0 AND quality_score <= 1)
);

-- Create indexes for performance
CREATE INDEX idx_tm_segment_hash ON translation_memory(segment_hash);
CREATE INDEX idx_tm_language_pair ON translation_memory(source_language, target_language);
CREATE INDEX idx_tm_segment_context ON translation_memory(segment_hash, context_hash);
CREATE INDEX idx_tm_quality_usage ON translation_memory(quality_score DESC, usage_count DESC);
CREATE INDEX idx_tm_last_used ON translation_memory(last_used DESC);
CREATE INDEX idx_tm_source_type ON translation_memory(source_type);
CREATE INDEX idx_tm_deleted_at ON translation_memory(deleted_at);

-- Create composite unique constraint for exact duplicates
CREATE UNIQUE INDEX idx_tm_unique_segment
ON translation_memory(segment_hash, context_hash, source_language, target_language)
WHERE deleted_at IS NULL;

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_translation_memory_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_translation_memory_updated_at
    BEFORE UPDATE ON translation_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_translation_memory_updated_at();

-- Create translation memory audit log table
CREATE TABLE IF NOT EXISTS translation_memory_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Reference to TM entry
    tm_id UUID NOT NULL REFERENCES translation_memory(id) ON DELETE CASCADE,

    -- Audit information
    action VARCHAR(50) NOT NULL, -- create, update, delete, quality_change, verify
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Change details
    old_values JSONB,
    new_values JSONB,
    reason TEXT,

    -- Additional context
    ip_address INET,
    user_agent TEXT
);

-- Create index for audit lookups
CREATE INDEX idx_tm_audit_tm_id ON translation_memory_audit(tm_id);
CREATE INDEX idx_tm_audit_user_id ON translation_memory_audit(user_id);
CREATE INDEX idx_tm_audit_created_at ON translation_memory_audit(created_at DESC);

-- Create translation memory import tracking table
CREATE TABLE IF NOT EXISTS translation_memory_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Import metadata
    import_type VARCHAR(50) NOT NULL, -- tmx, json, csv, manual
    file_name TEXT,
    file_size INTEGER,

    -- Import statistics
    total_segments INTEGER NOT NULL DEFAULT 0,
    imported_segments INTEGER NOT NULL DEFAULT 0,
    failed_segments INTEGER NOT NULL DEFAULT 0,
    duplicate_segments INTEGER NOT NULL DEFAULT 0,

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,

    -- User tracking
    imported_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Import configuration
    configuration JSONB DEFAULT '{}'::jsonb
);

-- Create index for import tracking
CREATE INDEX idx_tm_imports_status ON translation_memory_imports(status);
CREATE INDEX idx_tm_imports_imported_by ON translation_memory_imports(imported_by);
CREATE INDEX idx_tm_imports_created_at ON translation_memory_imports(created_at DESC);

-- Create function to calculate TM coverage for a text
CREATE OR REPLACE FUNCTION calculate_tm_coverage(
    p_text TEXT,
    p_source_language VARCHAR(10),
    p_target_language VARCHAR(10),
    p_min_score FLOAT DEFAULT 0.7
) RETURNS TABLE (
    coverage_percentage FLOAT,
    exact_matches INTEGER,
    fuzzy_matches INTEGER,
    no_matches INTEGER,
    total_segments INTEGER
) AS $$
DECLARE
    v_segments TEXT[];
    v_segment TEXT;
    v_exact_count INTEGER := 0;
    v_fuzzy_count INTEGER := 0;
    v_no_match_count INTEGER := 0;
    v_total_count INTEGER;
    v_similarity FLOAT;
BEGIN
    -- Split text into segments (simple sentence splitting)
    v_segments := string_to_array(
        regexp_replace(p_text, '([.!?])\s+', '\1|', 'g'),
        '|'
    );

    v_total_count := array_length(v_segments, 1);

    -- Check each segment
    FOREACH v_segment IN ARRAY v_segments
    LOOP
        -- Find best match in TM
        SELECT MAX(
            similarity(
                lower(trim(v_segment)),
                lower(tm.source_text)
            )
        ) INTO v_similarity
        FROM translation_memory tm
        WHERE tm.source_language = p_source_language
          AND tm.target_language = p_target_language
          AND tm.deleted_at IS NULL;

        IF v_similarity >= 1.0 THEN
            v_exact_count := v_exact_count + 1;
        ELSIF v_similarity >= p_min_score THEN
            v_fuzzy_count := v_fuzzy_count + 1;
        ELSE
            v_no_match_count := v_no_match_count + 1;
        END IF;
    END LOOP;

    RETURN QUERY
    SELECT
        CASE
            WHEN v_total_count > 0
            THEN ((v_exact_count + v_fuzzy_count)::FLOAT / v_total_count) * 100
            ELSE 0
        END,
        v_exact_count,
        v_fuzzy_count,
        v_no_match_count,
        v_total_count;
END;
$$ LANGUAGE plpgsql;

-- Create view for TM statistics
CREATE OR REPLACE VIEW translation_memory_statistics AS
SELECT
    source_language,
    target_language,
    COUNT(*) as segment_count,
    AVG(quality_score) as avg_quality,
    SUM(usage_count) as total_usage,
    MAX(last_used) as last_activity,
    COUNT(DISTINCT source_user_id) as contributor_count
FROM translation_memory
WHERE deleted_at IS NULL
GROUP BY source_language, target_language;

-- Add comments for documentation
COMMENT ON TABLE translation_memory IS 'Stores translation memory segments for reuse and consistency';
COMMENT ON COLUMN translation_memory.segment_hash IS 'SHA-256 hash of normalized source text for fast lookup';
COMMENT ON COLUMN translation_memory.context_hash IS 'MD5 hash of context for context-aware matching';
COMMENT ON COLUMN translation_memory.quality_score IS 'Quality score from 0 to 1, affected by usage and verification';
COMMENT ON COLUMN translation_memory.source_type IS 'Origin of translation: manual, machine, verified, import';

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON translation_memory TO haven_app;
GRANT SELECT ON translation_memory_statistics TO haven_app;
GRANT SELECT, INSERT ON translation_memory_audit TO haven_app;
GRANT SELECT, INSERT, UPDATE ON translation_memory_imports TO haven_app;
