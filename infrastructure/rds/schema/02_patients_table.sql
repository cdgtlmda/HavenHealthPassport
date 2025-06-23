-- Patients table
CREATE TABLE haven_health.patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Basic demographics
    given_name VARCHAR(100) NOT NULL,
    family_name VARCHAR(100) NOT NULL,
    middle_names VARCHAR(200),
    preferred_name VARCHAR(100),
    names_in_languages JSONB DEFAULT '{}',

    -- Identification
    date_of_birth DATE,
    estimated_birth_year INTEGER,
    place_of_birth VARCHAR(200),
    gender gender_enum NOT NULL DEFAULT 'unknown',

    -- Refugee-specific
    refugee_status refugee_status_enum,
    unhcr_number VARCHAR(50) UNIQUE,
    displacement_date DATE,
    origin_country CHAR(2),
    current_camp VARCHAR(200),
    camp_section VARCHAR(50),

    -- Contact
    phone_number VARCHAR(20),
    alternate_phone VARCHAR(20),
    email VARCHAR(255),
    current_address TEXT,
    gps_coordinates JSONB,

    -- Emergency contact
    emergency_contact_name VARCHAR(200),
    emergency_contact_phone VARCHAR(20),
    emergency_contact_relationship VARCHAR(50),

    -- Language and communication
    primary_language VARCHAR(10),
    languages_spoken JSONB DEFAULT '[]',
    communication_preferences JSONB DEFAULT '{}',
    requires_interpreter BOOLEAN DEFAULT FALSE,

    -- Cultural context
    cultural_dietary_restrictions JSONB DEFAULT '[]',
    religious_affiliation VARCHAR(100),
    cultural_considerations TEXT,

    -- Medical summary
    blood_type VARCHAR(5),
    allergies JSONB DEFAULT '[]',
    chronic_conditions JSONB DEFAULT '[]',
    current_medications JSONB DEFAULT '[]',

    -- Verification
    verification_status verification_status_enum NOT NULL DEFAULT 'unverified',
    identity_documents JSONB DEFAULT '[]',
    biometric_data_hash VARCHAR(255),
    photo_url VARCHAR(500),

    -- Access control
    access_permissions JSONB DEFAULT '{}',
    cross_border_permissions JSONB DEFAULT '{}',
    data_sharing_consent JSONB DEFAULT '{}',

    -- Metadata
    created_by_organization VARCHAR(200),
    managing_organization VARCHAR(200),
    last_updated_by UUID,
    import_source VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by UUID,

    -- Constraints
    CONSTRAINT check_birth_date CHECK (
        (date_of_birth IS NOT NULL) OR (estimated_birth_year IS NOT NULL)
    )
);

-- Create indexes for patients
CREATE INDEX idx_patients_name ON haven_health.patients(family_name, given_name);
CREATE INDEX idx_patients_unhcr ON haven_health.patients(unhcr_number) WHERE unhcr_number IS NOT NULL;
CREATE INDEX idx_patients_phone ON haven_health.patients(phone_number) WHERE phone_number IS NOT NULL;
CREATE INDEX idx_patients_camp ON haven_health.patients(current_camp, camp_section) WHERE current_camp IS NOT NULL;
CREATE INDEX idx_patients_verification ON haven_health.patients(verification_status);
CREATE INDEX idx_patients_deleted ON haven_health.patients(deleted_at) WHERE deleted_at IS NULL;

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_patients_updated_at BEFORE UPDATE ON haven_health.patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
