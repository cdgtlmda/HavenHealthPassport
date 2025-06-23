-- Medical Glossary table for WHO/UN standard medical terminology
-- This migration creates tables for storing and managing medical terms

-- Create medical glossary table
CREATE TABLE IF NOT EXISTS medical_glossary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Term identification
    term_normalized VARCHAR(255) NOT NULL,
    term_display VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,

    -- Classification
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(50),

    -- Source and codes
    source VARCHAR(50) NOT NULL,
    source_code VARCHAR(50),
    who_code VARCHAR(50),
    un_code VARCHAR(50),

    -- Term details
    definition TEXT,
    synonyms JSONB DEFAULT '[]'::jsonb,
    abbreviations JSONB DEFAULT '[]'::jsonb,
    related_terms JSONB DEFAULT '[]'::jsonb,

    -- Usage information
    context_notes TEXT,
    usage_frequency VARCHAR(20) DEFAULT 'common',
    refugee_health_relevant BOOLEAN DEFAULT true,
    emergency_relevant BOOLEAN DEFAULT false,

    -- Translations
    translations JSONB DEFAULT '{}'::jsonb,
    verified_translations JSONB DEFAULT '[]'::jsonb,

    -- Metadata
    added_by VARCHAR(36),
    verified BOOLEAN DEFAULT false,
    verified_by VARCHAR(36),
    verified_date TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0,

    -- Constraints
    CONSTRAINT usage_frequency_check CHECK (usage_frequency IN ('common', 'rare', 'specialized'))
);

-- Create indexes for performance
CREATE INDEX idx_glossary_term_lang ON medical_glossary(term_normalized, language);
CREATE INDEX idx_glossary_category ON medical_glossary(category, subcategory);
CREATE INDEX idx_glossary_codes ON medical_glossary(who_code, un_code);
CREATE INDEX idx_glossary_frequency ON medical_glossary(usage_frequency, refugee_health_relevant);
CREATE INDEX idx_glossary_emergency ON medical_glossary(emergency_relevant) WHERE emergency_relevant = true;
CREATE INDEX idx_glossary_verified ON medical_glossary(verified) WHERE verified = true;
CREATE INDEX idx_glossary_deleted_at ON medical_glossary(deleted_at);

-- Create unique constraint for term + language
CREATE UNIQUE INDEX idx_glossary_unique_term
ON medical_glossary(term_normalized, language)
WHERE deleted_at IS NULL;

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_medical_glossary_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_medical_glossary_updated_at
    BEFORE UPDATE ON medical_glossary
    FOR EACH ROW
    EXECUTE FUNCTION update_medical_glossary_updated_at();

-- Create medical glossary audit log
CREATE TABLE IF NOT EXISTS medical_glossary_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Reference to glossary entry
    glossary_id UUID NOT NULL REFERENCES medical_glossary(id) ON DELETE CASCADE,

    -- Audit information
    action VARCHAR(50) NOT NULL, -- create, update, delete, verify, translate
    user_id VARCHAR(36),

    -- Change details
    field_changed VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    notes TEXT
);

-- Create indexes for audit
CREATE INDEX idx_glossary_audit_glossary_id ON medical_glossary_audit(glossary_id);
CREATE INDEX idx_glossary_audit_user_id ON medical_glossary_audit(user_id);
CREATE INDEX idx_glossary_audit_created_at ON medical_glossary_audit(created_at DESC);

-- Create view for commonly used emergency terms
CREATE OR REPLACE VIEW emergency_medical_terms AS
SELECT
    term_display,
    language,
    category,
    translations,
    usage_count
FROM medical_glossary
WHERE emergency_relevant = true
  AND deleted_at IS NULL
ORDER BY usage_count DESC;

-- Create view for translation coverage statistics
CREATE OR REPLACE VIEW medical_glossary_translation_stats AS
SELECT
    language,
    category,
    COUNT(*) as total_terms,
    COUNT(CASE WHEN jsonb_array_length(translations) > 0 THEN 1 END) as translated_terms,
    COUNT(CASE WHEN verified = true THEN 1 END) as verified_terms,
    ROUND(
        COUNT(CASE WHEN jsonb_array_length(translations) > 0 THEN 1 END)::numeric /
        COUNT(*)::numeric * 100, 2
    ) as translation_coverage_percent
FROM medical_glossary
WHERE deleted_at IS NULL
GROUP BY language, category;

-- Function to search medical terms with fuzzy matching
CREATE OR REPLACE FUNCTION search_medical_terms(
    p_query TEXT,
    p_language VARCHAR(10) DEFAULT 'en',
    p_category VARCHAR(50) DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
) RETURNS TABLE (
    term_id UUID,
    term_display VARCHAR(255),
    category VARCHAR(50),
    definition TEXT,
    translations JSONB,
    relevance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        mg.id,
        mg.term_display,
        mg.category,
        mg.definition,
        mg.translations,
        CASE
            -- Exact match
            WHEN lower(mg.term_normalized) = lower(p_query) THEN 1.0
            -- Starts with query
            WHEN lower(mg.term_normalized) LIKE lower(p_query) || '%' THEN 0.8
            -- Contains query
            WHEN lower(mg.term_normalized) LIKE '%' || lower(p_query) || '%' THEN 0.6
            -- Synonym match
            WHEN EXISTS (
                SELECT 1 FROM jsonb_array_elements_text(mg.synonyms) AS syn
                WHERE lower(syn) LIKE '%' || lower(p_query) || '%'
            ) THEN 0.5
            ELSE similarity(lower(mg.term_normalized), lower(p_query))
        END AS relevance_score
    FROM medical_glossary mg
    WHERE mg.language = p_language
      AND mg.deleted_at IS NULL
      AND (p_category IS NULL OR mg.category = p_category)
      AND (
          lower(mg.term_normalized) LIKE '%' || lower(p_query) || '%'
          OR EXISTS (
              SELECT 1 FROM jsonb_array_elements_text(mg.synonyms) AS syn
              WHERE lower(syn) LIKE '%' || lower(p_query) || '%'
          )
          OR similarity(lower(mg.term_normalized), lower(p_query)) > 0.3
      )
    ORDER BY relevance_score DESC, mg.usage_count DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get term with all translations
CREATE OR REPLACE FUNCTION get_term_translations(
    p_term VARCHAR(255),
    p_source_language VARCHAR(10) DEFAULT 'en'
) RETURNS TABLE (
    language VARCHAR(10),
    translation TEXT,
    verified BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH term_data AS (
        SELECT translations, verified_translations
        FROM medical_glossary
        WHERE term_normalized = lower(p_term)
          AND language = p_source_language
          AND deleted_at IS NULL
        LIMIT 1
    )
    SELECT
        key AS language,
        value::text AS translation,
        (verified_translations ? key)::boolean AS verified
    FROM term_data, jsonb_each(translations);
END;
$$ LANGUAGE plpgsql;

-- Initial data for critical emergency terms
INSERT INTO medical_glossary (
    term_normalized, term_display, language, category, source,
    emergency_relevant, translations, verified
) VALUES
    ('emergency', 'emergency', 'en', 'emergency_terms', 'sphere', true,
     '{"ar": "طوارئ", "fr": "urgence", "es": "emergencia", "sw": "dharura"}', true),
    ('help', 'help', 'en', 'emergency_terms', 'sphere', true,
     '{"ar": "مساعدة", "fr": "aide", "es": "ayuda", "sw": "msaada"}', true),
    ('pain', 'pain', 'en', 'symptoms_signs', 'who_icd11', true,
     '{"ar": "ألم", "fr": "douleur", "es": "dolor", "sw": "maumivu"}', true),
    ('bleeding', 'bleeding', 'en', 'emergency_terms', 'who_icd11', true,
     '{"ar": "نزيف", "fr": "saignement", "es": "sangrado", "sw": "kutokwa na damu"}', true),
    ('breathing difficulty', 'breathing difficulty', 'en', 'emergency_terms', 'who_icd11', true,
     '{"ar": "صعوبة في التنفس", "fr": "difficulté respiratoire", "es": "dificultad para respirar", "sw": "shida ya kupumua"}', true);

-- Add comments for documentation
COMMENT ON TABLE medical_glossary IS 'WHO/UN standard medical terminology for refugee health';
COMMENT ON COLUMN medical_glossary.who_code IS 'WHO International Classification code';
COMMENT ON COLUMN medical_glossary.un_code IS 'UN terminology code';
COMMENT ON COLUMN medical_glossary.refugee_health_relevant IS 'Term is relevant for refugee health contexts';
COMMENT ON COLUMN medical_glossary.emergency_relevant IS 'Term is critical for emergency situations';

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON medical_glossary TO haven_app;
GRANT SELECT ON emergency_medical_terms TO haven_app;
GRANT SELECT ON medical_glossary_translation_stats TO haven_app;
GRANT SELECT, INSERT ON medical_glossary_audit TO haven_app;
