-- Migration: Add A/B Testing Tables for Translation Improvements
-- Date: January 2025
-- Purpose: Track A/B tests with actual start/end times for medical translation improvements
-- CRITICAL: This is for a healthcare project - complete audit trails are mandatory

-- Create A/B tests table
CREATE TABLE IF NOT EXISTS ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id VARCHAR(36) UNIQUE NOT NULL,
    proposal_id VARCHAR(36) NOT NULL,
    
    -- Test configuration
    improvement_type VARCHAR(50) NOT NULL,
    traffic_split FLOAT NOT NULL DEFAULT 0.5 CHECK (traffic_split >= 0 AND traffic_split <= 1),
    minimum_sample_size INTEGER NOT NULL DEFAULT 100 CHECK (minimum_sample_size > 0),
    maximum_duration_hours INTEGER NOT NULL DEFAULT 72,
    confidence_threshold FLOAT NOT NULL DEFAULT 0.95 CHECK (confidence_threshold >= 0.9 AND confidence_threshold <= 0.99),
    minimum_effect_size FLOAT NOT NULL DEFAULT 0.05,
    
    -- Safety configuration for medical context
    safety_metrics JSONB NOT NULL DEFAULT '["accuracy", "medical_term_preservation"]'::jsonb,
    safety_thresholds JSONB NOT NULL DEFAULT '{"accuracy": 0.95, "medical_term_preservation": 0.99}'::jsonb,
    
    -- CRITICAL: Track actual start and end times for audit trail
    start_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    
    -- Test status
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'aborted', 'failed')),
    
    -- Test configuration data
    control_config JSONB NOT NULL,
    treatment_config JSONB NOT NULL,
    
    -- Sample size tracking
    control_sample_size INTEGER NOT NULL DEFAULT 0,
    treatment_sample_size INTEGER NOT NULL DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_ab_test_test_id ON ab_tests(test_id);
CREATE INDEX idx_ab_test_proposal_id ON ab_tests(proposal_id);
CREATE INDEX idx_ab_test_status_start ON ab_tests(status, start_time);
CREATE INDEX idx_ab_test_created ON ab_tests(created_at);

-- Create A/B test metrics table
CREATE TABLE IF NOT EXISTS ab_test_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES ab_tests(id) ON DELETE CASCADE,
    
    -- Metric identification
    variant VARCHAR(20) NOT NULL CHECK (variant IN ('control', 'treatment')),
    iteration_id VARCHAR(36) NOT NULL,
    
    -- Core metrics
    accuracy_score FLOAT NOT NULL CHECK (accuracy_score >= 0 AND accuracy_score <= 1),
    fluency_score FLOAT NOT NULL,
    adequacy_score FLOAT NOT NULL,
    
    -- Medical-specific metrics (CRITICAL for patient safety)
    medical_term_preservation FLOAT NOT NULL CHECK (medical_term_preservation >= 0 AND medical_term_preservation <= 1),
    cultural_appropriateness FLOAT NOT NULL,
    
    -- Performance metrics
    translation_time_ms INTEGER NOT NULL,
    model_tokens_used INTEGER,
    
    -- Context data
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    domain VARCHAR(50),
    
    -- User feedback and error tracking
    user_feedback_score FLOAT,
    error_occurred BOOLEAN NOT NULL DEFAULT FALSE,
    error_details JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for metrics analysis
CREATE INDEX idx_ab_metric_test_variant ON ab_test_metrics(test_id, variant);
CREATE INDEX idx_ab_metric_created ON ab_test_metrics(created_at);
CREATE INDEX idx_ab_metric_error ON ab_test_metrics(error_occurred) WHERE error_occurred = TRUE;

-- Create A/B test results table
CREATE TABLE IF NOT EXISTS ab_test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL UNIQUE REFERENCES ab_tests(id) ON DELETE CASCADE,
    
    -- Aggregated metrics summaries
    control_metrics_summary JSONB NOT NULL,
    treatment_metrics_summary JSONB NOT NULL,
    
    -- Statistical analysis results
    statistical_significance JSONB NOT NULL,
    p_values JSONB NOT NULL,
    effect_sizes JSONB NOT NULL,
    confidence_intervals JSONB NOT NULL,
    
    -- Safety analysis (CRITICAL for healthcare)
    safety_violations JSONB NOT NULL DEFAULT '{}'::jsonb,
    medical_accuracy_maintained BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Recommendation
    recommendation VARCHAR(20) NOT NULL CHECK (recommendation IN ('adopt', 'reject', 'inconclusive')),
    recommendation_confidence FLOAT NOT NULL CHECK (recommendation_confidence >= 0 AND recommendation_confidence <= 1),
    recommendation_rationale JSONB NOT NULL,
    
    -- Implementation tracking
    implemented BOOLEAN NOT NULL DEFAULT FALSE,
    implementation_date TIMESTAMP WITH TIME ZONE,
    implementation_notes JSONB,
    
    -- Medical review and approval (CRITICAL for patient safety)
    reviewed_by UUID,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes JSONB,
    approved_by UUID,
    approved_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure medical review before implementation
    CONSTRAINT require_review_before_implementation 
        CHECK (NOT (implemented = TRUE AND reviewed_by IS NULL))
);

-- Create index for results lookup
CREATE INDEX idx_ab_result_test_id ON ab_test_results(test_id);

-- Create update timestamp triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_ab_tests_updated_at BEFORE UPDATE ON ab_tests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ab_test_metrics_updated_at BEFORE UPDATE ON ab_test_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ab_test_results_updated_at BEFORE UPDATE ON ab_test_results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE ab_tests IS 'A/B tests for medical translation improvements - tracks actual start/end times';
COMMENT ON COLUMN ab_tests.start_time IS 'CRITICAL: Actual test start time - replaces TODO comment in code';
COMMENT ON COLUMN ab_tests.safety_metrics IS 'Medical safety metrics that must not degrade';
COMMENT ON TABLE ab_test_metrics IS 'Individual metric measurements for each A/B test iteration';
COMMENT ON COLUMN ab_test_metrics.medical_term_preservation IS 'CRITICAL: Ensures medical terminology accuracy';
COMMENT ON TABLE ab_test_results IS 'Aggregated results requiring medical review before implementation';
COMMENT ON COLUMN ab_test_results.medical_accuracy_maintained IS 'Must be TRUE for implementation approval';
