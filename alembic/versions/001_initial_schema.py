"""Initial migration - Full production schema with medical compliance

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-06-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """
    Create all tables with full production constraints, indexes, and triggers.
    This is the REAL schema used in production for refugee healthcare.
    """
    
    # Create custom types
    op.execute("""
        CREATE TYPE access_level AS ENUM (
            'PUBLIC', 'HEALTHCARE_PROVIDER', 'EMERGENCY_ONLY', 
            'PATIENT_ONLY', 'RESTRICTED'
        );
        
        CREATE TYPE audit_action AS ENUM (
            'CREATE', 'READ', 'UPDATE', 'DELETE', 
            'EMERGENCY_ACCESS', 'EXPORT', 'PRINT', 'SHARE'
        );
    """)
    
    # Create patients table with encrypted PHI
    op.create_table('patients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Encrypted PHI fields - REQUIRED for HIPAA compliance
        sa.Column('first_name_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('last_name_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('date_of_birth_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('ssn_encrypted', sa.LargeBinary(), nullable=True),
        
        # Non-PHI identifiers
        sa.Column('medical_record_number', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('refugee_id', sa.String(100), unique=True, index=True, nullable=False),
        sa.Column('unhcr_number', sa.String(50), unique=True, nullable=True),
        
        # Contact info (encrypted)
        sa.Column('phone_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('email_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('address_encrypted', sa.LargeBinary(), nullable=True),
        
        # Demographics
        sa.Column('gender', sa.String(20), nullable=False),
        sa.Column('nationality', sa.String(100), nullable=True),
        sa.Column('preferred_language', sa.String(10), default='en', nullable=False),
        
        # Medical metadata
        sa.Column('blood_type', sa.String(10), nullable=True),
        sa.Column('allergies_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('emergency_contact_encrypted', sa.LargeBinary(), nullable=True),
        
        # Blockchain verification
        sa.Column('blockchain_hash', sa.String(66), unique=True, nullable=True),
        sa.Column('blockchain_tx_hash', sa.String(66), nullable=True),
        sa.Column('blockchain_verified', sa.Boolean(), default=False),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_accessed_at', sa.TIMESTAMP(), nullable=True),
        
        # Compliance fields
        sa.Column('consent_given', sa.Boolean(), default=False, nullable=False),
        sa.Column('consent_date', sa.TIMESTAMP(), nullable=True),
        sa.Column('data_retention_date', sa.TIMESTAMP(), nullable=True),
        sa.Column('deletion_requested', sa.Boolean(), default=False),
        sa.Column('deletion_date', sa.TIMESTAMP(), nullable=True),
        
        # Constraints
        sa.CheckConstraint("gender IN ('male', 'female', 'other', 'unknown')", name='check_gender'),
        sa.CheckConstraint("preferred_language ~ '^[a-z]{2}(-[A-Z]{2})?$'", name='check_language_code'),
    )
    
    # Create indexes for performance
    op.create_index('idx_patient_mrn', 'patients', ['medical_record_number'])
    op.create_index('idx_patient_refugee_id', 'patients', ['refugee_id'])
    op.create_index('idx_patient_created', 'patients', ['created_at'])
    op.create_index('idx_patient_blockchain', 'patients', ['blockchain_hash'])
    op.create_index('idx_patient_nationality', 'patients', ['nationality'])
    
    # Create providers table
    op.create_table('providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Provider info (encrypted where sensitive)
        sa.Column('license_number_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('first_name_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('last_name_encrypted', sa.LargeBinary(), nullable=False),
        
        # Professional info
        sa.Column('specialization', sa.String(100), nullable=True),
        sa.Column('facility_name', sa.String(200), nullable=True),
        sa.Column('facility_country', sa.String(100), nullable=True),
        
        # Verification
        sa.Column('verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('verification_date', sa.TIMESTAMP(), nullable=True),
        sa.Column('verification_authority', sa.String(200), nullable=True),
        
        # Access
        sa.Column('active', sa.Boolean(), default=True, nullable=False),
        sa.Column('role', sa.String(50), default='physician', nullable=False),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login_at', sa.TIMESTAMP(), nullable=True),
        
        # Constraints
        sa.CheckConstraint("role IN ('physician', 'nurse', 'pharmacist', 'technician', 'admin')", 
                         name='check_provider_role'),
    )
    
    op.create_index('idx_provider_facility', 'providers', ['facility_name', 'facility_country'])
    op.create_index('idx_provider_active', 'providers', ['active'])
    
    # Create health_records table
    op.create_table('health_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        
        # Record metadata
        sa.Column('record_type', sa.String(50), nullable=False),
        sa.Column('record_date', sa.TIMESTAMP(), nullable=False),
        
        # Encrypted medical data
        sa.Column('data_encrypted', sa.LargeBinary(), nullable=False),
        
        # FHIR compliance
        sa.Column('fhir_resource_type', sa.String(50), nullable=True),
        sa.Column('fhir_resource_id', sa.String(100), nullable=True),
        sa.Column('fhir_version', sa.String(10), default='R4'),
        
        # Access control
        sa.Column('access_level', postgresql.ENUM('PUBLIC', 'HEALTHCARE_PROVIDER', 'EMERGENCY_ONLY', 
                                                 'PATIENT_ONLY', 'RESTRICTED', name='access_level'),
                default='HEALTHCARE_PROVIDER'),
        
        # Provider information
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('providers.id'), nullable=True),
        sa.Column('provider_name_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('facility_name', sa.String(200), nullable=True),
        sa.Column('facility_country', sa.String(100), nullable=True),
        
        # Verification
        sa.Column('verified', sa.Boolean(), default=False),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('providers.id'), nullable=True),
        sa.Column('verified_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        
        # Blockchain
        sa.Column('blockchain_hash', sa.String(66), unique=True, nullable=True),
        sa.Column('blockchain_tx_hash', sa.String(66), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        # Constraints
        sa.CheckConstraint("""record_type IN ('diagnosis', 'medication', 'procedure', 'lab_result',
                           'imaging', 'immunization', 'allergy', 'vital_signs', 'clinical_note')""",
                         name='check_record_type'),
        sa.CheckConstraint("record_date <= NOW()", name='check_record_date_not_future'),
    )
    
    op.create_index('idx_record_patient', 'health_records', ['patient_id'])
    op.create_index('idx_record_type_date', 'health_records', ['record_type', 'record_date'])
    op.create_index('idx_record_provider', 'health_records', ['provider_id'])
    op.create_index('idx_record_blockchain', 'health_records', ['blockchain_hash'])
    
    # Create audit_logs table - CRITICAL for HIPAA compliance
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Who
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_type', sa.String(50), nullable=True),
        
        # What
        sa.Column('action', postgresql.ENUM('CREATE', 'READ', 'UPDATE', 'DELETE', 
                                          'EMERGENCY_ACCESS', 'EXPORT', 'PRINT', 'SHARE',
                                          name='audit_action'), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # When
        sa.Column('timestamp', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        
        # Where
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('location', sa.String(100), nullable=True),
        
        # Why
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('emergency_override', sa.Boolean(), default=False),
        
        # Additional context
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('success', sa.Boolean(), default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Patient reference
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=True),
        
        # Retention (7 years for HIPAA)
        sa.Column('retention_date', sa.TIMESTAMP(), nullable=True),
    )
    
    # Comprehensive indexes for audit queries
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('idx_audit_patient', 'audit_logs', ['patient_id'])
    op.create_index('idx_audit_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_emergency', 'audit_logs', ['emergency_override'], postgresql_where=sa.text('emergency_override = true'))
    
    # Create access_logs table
    op.create_table('access_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Access details
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('accessor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('accessor_type', sa.String(50), nullable=True),
        
        # What was accessed
        sa.Column('fields_accessed', postgresql.JSONB(), nullable=True),
        sa.Column('records_accessed', postgresql.JSONB(), nullable=True),
        
        # Context
        sa.Column('access_reason', sa.String(200), nullable=True),
        sa.Column('access_timestamp', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('access_duration_seconds', sa.Integer(), nullable=True),
    )
    
    op.create_index('idx_access_patient_time', 'access_logs', ['patient_id', 'access_timestamp'])
    op.create_index('idx_access_accessor', 'access_logs', ['accessor_id'])
    
    # Create emergency_access table
    op.create_table('emergency_access',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Emergency details
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('providers.id'), nullable=False),
        
        # Justification
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=True),
        
        # Approval
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approval_timestamp', sa.TIMESTAMP(), nullable=True),
        
        # Access window
        sa.Column('access_granted_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('access_expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('access_revoked_at', sa.TIMESTAMP(), nullable=True),
        
        # Audit
        sa.Column('actions_performed', postgresql.JSONB(), nullable=True),
        
        # Constraints
        sa.CheckConstraint("severity IN ('critical', 'urgent', 'moderate')", name='check_severity'),
        sa.CheckConstraint("access_expires_at > access_granted_at", name='check_expiry_after_grant'),
    )
    
    op.create_index('idx_emergency_patient', 'emergency_access', ['patient_id'])
    op.create_index('idx_emergency_provider', 'emergency_access', ['provider_id'])
    op.create_index('idx_emergency_time', 'emergency_access', ['access_granted_at', 'access_expires_at'])
    
    # Create encryption_keys table
    op.create_table('encryption_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Key info
        sa.Column('key_id', sa.String(100), nullable=False, unique=True),
        sa.Column('key_version', sa.Integer(), default=1, nullable=False),
        sa.Column('algorithm', sa.String(50), default='AES-256-GCM', nullable=False),
        
        # Key data (encrypted with master key)
        sa.Column('encrypted_key', sa.LargeBinary(), nullable=False),
        
        # Usage
        sa.Column('purpose', sa.String(50), nullable=True),
        sa.Column('active', sa.Boolean(), default=True, nullable=False),
        
        # Rotation
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('rotated_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=True),
        
        # Unique constraint on key_id + version
        sa.UniqueConstraint('key_id', 'key_version', name='uq_key_version'),
    )
    
    op.create_index('idx_key_active', 'encryption_keys', ['active', 'purpose'])
    
    # Create database functions for medical compliance
    
    # Function to automatically update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Function to validate no PHI in certain fields
    op.execute("""
        CREATE OR REPLACE FUNCTION check_no_phi()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Check blockchain_hash doesn't contain patterns that look like PHI
            IF NEW.blockchain_hash IS NOT NULL AND (
                NEW.blockchain_hash ~ '\d{3}-\d{2}-\d{4}' OR  -- SSN pattern
                NEW.blockchain_hash ~ '\d{4}-\d{2}-\d{2}' OR  -- Date pattern
                LENGTH(NEW.blockchain_hash) > 66              -- Too long for hash
            ) THEN
                RAISE EXCEPTION 'PHI detected in blockchain_hash field';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Function for comprehensive audit logging
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger_function()
        RETURNS TRIGGER AS $$
        DECLARE
            audit_user_id UUID;
            audit_details JSONB;
        BEGIN
            -- Get current user from session
            BEGIN
                audit_user_id := current_setting('app.current_user_id')::UUID;
            EXCEPTION WHEN OTHERS THEN
                audit_user_id := '00000000-0000-0000-0000-000000000000'::UUID;
            END;
            
            -- Build audit details
            IF TG_OP = 'DELETE' THEN
                audit_details := jsonb_build_object(
                    'table', TG_TABLE_NAME,
                    'old_data', to_jsonb(OLD)
                );
            ELSIF TG_OP = 'UPDATE' THEN
                audit_details := jsonb_build_object(
                    'table', TG_TABLE_NAME,
                    'old_data', to_jsonb(OLD),
                    'new_data', to_jsonb(NEW),
                    'changed_fields', (
                        SELECT jsonb_object_agg(key, value)
                        FROM jsonb_each(to_jsonb(NEW))
                        WHERE value IS DISTINCT FROM (to_jsonb(OLD) -> key)
                    )
                );
            ELSE
                audit_details := jsonb_build_object(
                    'table', TG_TABLE_NAME,
                    'new_data', to_jsonb(NEW)
                );
            END IF;
            
            -- Insert audit log
            INSERT INTO audit_logs (
                user_id, action, resource_type, resource_id,
                timestamp, details, patient_id
            ) VALUES (
                audit_user_id,
                TG_OP::audit_action,
                TG_TABLE_NAME,
                CASE 
                    WHEN TG_OP = 'DELETE' THEN OLD.id
                    ELSE NEW.id
                END,
                NOW(),
                audit_details,
                CASE 
                    WHEN TG_TABLE_NAME = 'patients' THEN 
                        CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END
                    WHEN TG_TABLE_NAME = 'health_records' THEN 
                        CASE WHEN TG_OP = 'DELETE' THEN OLD.patient_id ELSE NEW.patient_id END
                    ELSE NULL
                END
            );
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create triggers
    
    # Update triggers for updated_at
    for table in ['patients', 'health_records']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # PHI validation triggers
    for table in ['patients', 'health_records']:
        op.execute(f"""
            CREATE TRIGGER check_{table}_no_phi
            BEFORE INSERT OR UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION check_no_phi();
        """)
    
    # Audit triggers for all sensitive tables
    for table in ['patients', 'health_records', 'providers', 'emergency_access']:
        op.execute(f"""
            CREATE TRIGGER audit_{table}
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
        """)
    
    # Enable Row Level Security
    op.execute("ALTER TABLE patients ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE health_records ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE providers ENABLE ROW LEVEL SECURITY;")
    
    # Create RLS policies (basic examples - expand based on requirements)
    op.execute("""
        CREATE POLICY patient_access_own_data ON patients
        FOR SELECT
        USING (
            id = current_setting('app.current_patient_id', true)::UUID OR
            current_setting('app.current_user_role', true) IN ('provider', 'admin')
        );
    """)
    
    op.execute("""
        CREATE POLICY health_record_access ON health_records
        FOR SELECT
        USING (
            patient_id = current_setting('app.current_patient_id', true)::UUID OR
            current_setting('app.current_user_role', true) = 'provider' OR
            (current_setting('app.emergency_access', true)::BOOLEAN = true AND
             access_level != 'PATIENT_ONLY')
        );
    """)

def downgrade() -> None:
    """Drop all tables and types"""
    
    # Drop triggers first
    for table in ['patients', 'health_records', 'providers', 'emergency_access']:
        op.execute(f"DROP TRIGGER IF EXISTS audit_{table} ON {table};")
        
    for table in ['patients', 'health_records']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS check_{table}_no_phi ON {table};")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS audit_trigger_function();")
    op.execute("DROP FUNCTION IF EXISTS check_no_phi();")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables
    op.drop_table('encryption_keys')
    op.drop_table('emergency_access')
    op.drop_table('access_logs')
    op.drop_table('audit_logs')
    op.drop_table('health_records')
    op.drop_table('providers')
    op.drop_table('patients')
    
    # Drop types
    op.execute("DROP TYPE IF EXISTS audit_action;")
    op.execute("DROP TYPE IF EXISTS access_level;")
