-- Migration: Add translation cache and medical glossary tables
-- Created: 2024-01-29

-- Translation cache table
CREATE TABLE IF NOT EXISTS translation_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_text_hash VARCHAR(64) NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    translation_type VARCHAR(50) NOT NULL,
    translation_context VARCHAR(50) NOT NULL,
    translated_text TEXT NOT NULL,
    bedrock_model_used VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    medical_terms_detected JSONB,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    deleted_at TIMESTAMPTZ
);

-- Indexes for translation cache
CREATE INDEX idx_translation_cache_hash ON translation_cache(source_text_hash);
CREATE INDEX idx_translation_cache_languages ON translation_cache(source_language, target_language);
CREATE INDEX idx_translation_cache_expires ON translation_cache(expires_at);
CREATE INDEX idx_translation_cache_type_context ON translation_cache(translation_type, translation_context);

-- Medical glossary table
CREATE TABLE IF NOT EXISTS medical_glossary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,
    definition TEXT NOT NULL,
    context VARCHAR(100) NOT NULL,
    who_code VARCHAR(50),
    un_code VARCHAR(50),
    alternatives TEXT[],
    usage_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Indexes for medical glossary
CREATE INDEX idx_medical_glossary_term_lang ON medical_glossary(term, language);
CREATE INDEX idx_medical_glossary_who_code ON medical_glossary(who_code);
CREATE INDEX idx_medical_glossary_un_code ON medical_glossary(un_code);
CREATE INDEX idx_medical_glossary_context ON medical_glossary(context);

-- Add unique constraint for translation cache
ALTER TABLE translation_cache
ADD CONSTRAINT unique_translation_cache
UNIQUE (source_text_hash, source_language, target_language, translation_type, translation_context);

-- Add unique constraint for medical glossary
ALTER TABLE medical_glossary
ADD CONSTRAINT unique_medical_term
UNIQUE (term, language, context);

-- Insert some initial medical glossary entries
INSERT INTO medical_glossary (term, language, definition, context, who_code, alternatives, usage_notes) VALUES
-- English terms
('vaccine', 'en', 'A biological preparation that provides active acquired immunity to a particular infectious disease', 'clinical', 'WHO_VAC_001', ARRAY['vaccination', 'immunization'], 'Use in preventive care context'),
('diabetes', 'en', 'A group of metabolic disorders characterized by high blood sugar', 'clinical', 'WHO_DIA_001', ARRAY['diabetes mellitus'], 'Specify type when possible'),
('tuberculosis', 'en', 'An infectious disease usually caused by Mycobacterium tuberculosis bacteria', 'clinical', 'WHO_TB_001', ARRAY['TB'], 'Always screen for in refugee populations'),
('malaria', 'en', 'A mosquito-borne infectious disease', 'clinical', 'WHO_MAL_001', NULL, 'Endemic in many refugee origin countries'),

-- Arabic terms
('لقاح', 'ar', 'مستحضر بيولوجي يوفر المناعة المكتسبة النشطة لمرض معدي معين', 'clinical', 'WHO_VAC_001', ARRAY['تطعيم', 'تحصين'], 'استخدم في سياق الرعاية الوقائية'),
('السكري', 'ar', 'مجموعة من الاضطرابات الأيضية التي تتميز بارتفاع نسبة السكر في الدم', 'clinical', 'WHO_DIA_001', ARRAY['داء السكري'], 'حدد النوع عند الإمكان'),
('السل', 'ar', 'مرض معدي تسببه عادة بكتيريا المتفطرة السلية', 'clinical', 'WHO_TB_001', NULL, 'قم دائمًا بالفحص في مجموعات اللاجئين'),

-- French terms
('vaccin', 'fr', 'Une préparation biologique qui fournit une immunité acquise active à une maladie infectieuse particulière', 'clinical', 'WHO_VAC_001', ARRAY['vaccination', 'immunisation'], 'Utiliser dans le contexte des soins préventifs'),
('diabète', 'fr', 'Un groupe de troubles métaboliques caractérisés par une glycémie élevée', 'clinical', 'WHO_DIA_001', ARRAY['diabète sucré'], 'Préciser le type si possible'),

-- Spanish terms
('vacuna', 'es', 'Una preparación biológica que proporciona inmunidad adquirida activa a una enfermedad infecciosa particular', 'clinical', 'WHO_VAC_001', ARRAY['vacunación', 'inmunización'], 'Usar en contexto de atención preventiva'),
('diabetes', 'es', 'Un grupo de trastornos metabólicos caracterizados por niveles altos de azúcar en sangre', 'clinical', 'WHO_DIA_001', ARRAY['diabetes mellitus'], 'Especificar tipo cuando sea posible'),

-- Swahili terms
('chanjo', 'sw', 'Maandalizi ya kibiolojia yanayotoa kinga iliyopatikana ya mwili dhidi ya ugonjwa fulani wa kuambukiza', 'clinical', 'WHO_VAC_001', ARRAY['kuchanja'], 'Tumia katika muktadha wa huduma za kuzuia'),
('kisukari', 'sw', 'Kundi la matatizo ya kimetaboliki yanayoonyeshwa na sukari nyingi katika damu', 'clinical', 'WHO_DIA_001', ARRAY['ugonjwa wa kisukari'], 'Bainisha aina inapowezekana');

-- Create function to clean expired cache entries
CREATE OR REPLACE FUNCTION clean_expired_translation_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM translation_cache
    WHERE expires_at < NOW()
    AND deleted_at IS NULL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to clean cache (requires pg_cron extension)
-- This is a placeholder - actual scheduling depends on your setup
-- SELECT cron.schedule('clean-translation-cache', '0 * * * *', 'SELECT clean_expired_translation_cache();');
