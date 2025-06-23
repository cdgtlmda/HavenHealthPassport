-- Initial database schema for Haven Health Passport
-- PostgreSQL 14+ required

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS haven_health;
CREATE SCHEMA IF NOT EXISTS audit;

-- Set search path
SET search_path TO haven_health, public;

-- Create custom types
CREATE TYPE gender_enum AS ENUM ('male', 'female', 'other', 'unknown');
CREATE TYPE verification_status_enum AS ENUM ('unverified', 'pending', 'verified', 'expired', 'revoked');
CREATE TYPE refugee_status_enum AS ENUM ('refugee', 'asylum_seeker', 'internally_displaced', 'stateless', 'returnee', 'other');
CREATE TYPE record_type_enum AS ENUM (
    'vital_signs', 'lab_result', 'immunization', 'medication',
    'procedure', 'diagnosis', 'allergy', 'clinical_note',
    'imaging', 'discharge_summary', 'referral', 'prescription',
    'vaccination_certificate', 'screening', 'emergency_contact'
);
CREATE TYPE record_status_enum AS ENUM ('draft', 'final', 'amended', 'corrected', 'cancelled', 'entered_in_error');
CREATE TYPE record_priority_enum AS ENUM ('routine', 'urgent', 'emergency', 'stat');
CREATE TYPE sync_status_enum AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'conflict');
CREATE TYPE sync_direction_enum AS ENUM ('upload', 'download', 'bidirectional');
CREATE TYPE file_status_enum AS ENUM ('uploading', 'scanning', 'ready', 'failed', 'archived', 'deleted');
CREATE TYPE access_type_enum AS ENUM ('view', 'create', 'update', 'delete', 'export', 'print', 'share', 'emergency', 'audit', 'sync');
CREATE TYPE access_result_enum AS ENUM ('success', 'denied', 'error', 'partial', 'timeout');
CREATE TYPE access_context_enum AS ENUM ('web_portal', 'mobile_app', 'api', 'emergency_system', 'sync_service', 'admin_console', 'integration');

-- Create base tables (will be added in next file)
