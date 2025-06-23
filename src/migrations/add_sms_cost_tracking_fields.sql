-- Migration: Add SMS cost tracking fields
-- Date: 2025-06-08
-- Purpose: Add cost, provider, and country code tracking to SMS logs for comprehensive rate limiting

-- Add new columns to sms_logs table
ALTER TABLE sms_logs 
ADD COLUMN IF NOT EXISTS cost VARCHAR(20),
ADD COLUMN IF NOT EXISTS provider VARCHAR(50),
ADD COLUMN IF NOT EXISTS country_code VARCHAR(5);

-- Create index on phone_number for phone-based rate limiting
CREATE INDEX IF NOT EXISTS idx_sms_logs_phone_number ON sms_logs(phone_number);

-- Create index on country_code for country-specific analysis
CREATE INDEX IF NOT EXISTS idx_sms_logs_country_code ON sms_logs(country_code);

-- Create composite index for efficient daily limit queries
CREATE INDEX IF NOT EXISTS idx_sms_logs_daily_limits 
ON sms_logs(created_at, user_id, phone_number, status);

-- Add comment for documentation
COMMENT ON COLUMN sms_logs.cost IS 'SMS cost in USD stored as decimal string';
COMMENT ON COLUMN sms_logs.provider IS 'SMS provider used (twilio, aws_sns, etc)';
COMMENT ON COLUMN sms_logs.country_code IS 'Country code for cost-based rate limiting';
