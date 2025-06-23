-- Migration: Add context preservation tables for translation consistency
-- Created: 2024-01-29

-- Translation context table for preserving translation consistency
CREATE TABLE IF NOT EXISTS translation_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id VARCHAR(16) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    context_type VARCHAR(50) NOT NULL,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    metadata JSONB,
    usage_count INTEGER DEFAULT 0,
    confidence_score FLOAT DEFAULT 1.0,
    expires_at TIMESTAMPTZ,
    session_id VARCHAR(255),
    patient_id UUID REFERENCES patients(id),
    document_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Indexes for translation context
CREATE INDEX idx_translation_context_id ON translation_context(context_id);
CREATE INDEX idx_translation_context_scope ON translation_context(scope);
CREATE INDEX idx_translation_context_type ON translation_context(context_type);
CREATE INDEX idx_translation_context_languages ON translation_context(source_language, target_language);
CREATE INDEX idx_translation_context_session ON translation_context(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_translation_context_patient ON translation_context(patient_id) WHERE patient_id IS NOT NULL;
CREATE INDEX idx_translation_context_document ON translation_context(document_id) WHERE document_id IS NOT NULL;
CREATE INDEX idx_translation_context_expires ON translation_context(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_translation_context_usage ON translation_context(usage_count DESC);

-- Unique constraint for context entries
ALTER TABLE translation_context
ADD CONSTRAINT unique_translation_context
UNIQUE (context_id, source_language, target_language);

-- Translation references table for tracking contextual references
CREATE TABLE IF NOT EXISTS translation_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id VARCHAR(16) NOT NULL,
    reference_type VARCHAR(50) NOT NULL, -- 'pronoun', 'name', 'term', 'abbreviation'
    original_form TEXT NOT NULL,
    context_form TEXT NOT NULL,
    scope VARCHAR(50) NOT NULL,
    positions JSONB, -- Array of position tuples
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for translation references
CREATE INDEX idx_translation_references_context ON translation_references(context_id);
CREATE INDEX idx_translation_references_type ON translation_references(reference_type);
CREATE INDEX idx_translation_references_scope ON translation_references(scope);

-- Translation consistency rules table
CREATE TABLE IF NOT EXISTS translation_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_type VARCHAR(50) NOT NULL, -- 'terminology', 'style', 'formatting'
    source_pattern TEXT NOT NULL,
    target_pattern TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for translation rules
CREATE INDEX idx_translation_rules_type ON translation_rules(rule_type);
CREATE INDEX idx_translation_rules_languages ON translation_rules(source_language, target_language);
CREATE INDEX idx_translation_rules_scope ON translation_rules(scope);
CREATE INDEX idx_translation_rules_active ON translation_rules(is_active);
CREATE INDEX idx_translation_rules_priority ON translation_rules(priority DESC);

-- Function to update usage count
CREATE OR REPLACE FUNCTION update_context_usage()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'SELECT' THEN
        UPDATE translation_context
        SET usage_count = usage_count + 1,
            updated_at = NOW()
        WHERE id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to clean expired contexts
CREATE OR REPLACE FUNCTION clean_expired_contexts()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM translation_context
    WHERE expires_at < NOW()
    AND deleted_at IS NULL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Insert some default translation rules
INSERT INTO translation_rules (rule_type, source_pattern, target_pattern, source_language, target_language, scope, priority, metadata) VALUES
-- Medical terminology consistency rules
('terminology', 'blood pressure', 'presión arterial', 'en', 'es', 'global', 100, '{"medical": true}'),
('terminology', 'blood pressure', 'pression artérielle', 'en', 'fr', 'global', 100, '{"medical": true}'),
('terminology', 'blood pressure', 'ضغط الدم', 'en', 'ar', 'global', 100, '{"medical": true}'),

-- Style rules for patient-facing content
('style', 'doctor', 'médico/a', 'en', 'es', 'patient', 50, '{"gender_neutral": true}'),
('style', 'nurse', 'enfermero/a', 'en', 'es', 'patient', 50, '{"gender_neutral": true}'),

-- Formatting rules for dates
('formatting', '\d{1,2}/\d{1,2}/\d{4}', '\d{1,2}/\d{1,2}/\d{4}', 'en', 'es', 'global', 20, '{"preserve_format": true}'),
('formatting', '\d{1,2}/\d{1,2}/\d{4}', '\d{1,2}/\d{1,2}/\d{4}', 'en', 'fr', 'global', 20, '{"preserve_format": true}');

-- Create a scheduled job to clean expired contexts (requires pg_cron extension)
-- This is a placeholder - actual scheduling depends on your setup
-- SELECT cron.schedule('clean-expired-contexts', '0 2 * * *', 'SELECT clean_expired_contexts();');
