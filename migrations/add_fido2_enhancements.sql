-- Migration: Add FIDO2-specific fields to WebAuthn credentials
-- Description: Enhance WebAuthn credentials table for better FIDO2 key support

-- Add FIDO2-specific columns if they don't exist
ALTER TABLE webauthn_credentials
ADD COLUMN IF NOT EXISTS attestation_format VARCHAR(50),
ADD COLUMN IF NOT EXISTS attestation_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS credential_backup_eligible BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS credential_backup_state BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS authenticator_extension_outputs JSONB,
ADD COLUMN IF NOT EXISTS certification_level INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS metadata_statement JSONB;

-- Add index for FIDO2 keys (cross-platform authenticators)
CREATE INDEX IF NOT EXISTS idx_webauthn_fido2_keys
ON webauthn_credentials(user_id, authenticator_attachment)
WHERE authenticator_attachment = 'cross-platform' AND is_active = TRUE;

-- Add index for certification level queries
CREATE INDEX IF NOT EXISTS idx_webauthn_cert_level
ON webauthn_credentials(certification_level)
WHERE certification_level > 0;

-- Update existing cross-platform keys to have default certification level
UPDATE webauthn_credentials
SET certification_level = 1
WHERE authenticator_attachment = 'cross-platform'
AND certification_level = 0;

-- Add comment to table
COMMENT ON COLUMN webauthn_credentials.attestation_format IS 'Attestation format used during registration';
COMMENT ON COLUMN webauthn_credentials.attestation_type IS 'Type of attestation (none, self, attestation, etc.)';
COMMENT ON COLUMN webauthn_credentials.credential_backup_eligible IS 'Whether credential can be backed up';
COMMENT ON COLUMN webauthn_credentials.credential_backup_state IS 'Whether credential is currently backed up';
COMMENT ON COLUMN webauthn_credentials.authenticator_extension_outputs IS 'Extension outputs from authenticator';
COMMENT ON COLUMN webauthn_credentials.certification_level IS 'FIDO certification level (0=unknown, 1=L1, 2=L2, etc.)';
COMMENT ON COLUMN webauthn_credentials.metadata_statement IS 'Cached metadata statement from FIDO MDS';
