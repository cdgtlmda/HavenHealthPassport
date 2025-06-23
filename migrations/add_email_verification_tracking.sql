-- Migration: Add email verification sent timestamp
-- Purpose: Track when verification emails are sent to handle token expiry

-- Add email_verification_sent_at column to user_auth table
ALTER TABLE user_auth 
ADD COLUMN IF NOT EXISTS email_verification_sent_at TIMESTAMP;

-- Add index for efficient token lookup
CREATE INDEX IF NOT EXISTS idx_user_auth_email_verification_token 
ON user_auth(email_verification_token) 
WHERE email_verification_token IS NOT NULL;

-- Add index for finding unverified users
CREATE INDEX IF NOT EXISTS idx_user_auth_email_verification_status 
ON user_auth(email_verified, email_verification_sent_at) 
WHERE email_verified = false;

-- Update any existing records to have a sent timestamp if they have a token
UPDATE user_auth 
SET email_verification_sent_at = created_at 
WHERE email_verification_token IS NOT NULL 
  AND email_verification_sent_at IS NULL;

-- Add comment to column
COMMENT ON COLUMN user_auth.email_verification_sent_at IS 'Timestamp when verification email was sent for token expiry tracking';
