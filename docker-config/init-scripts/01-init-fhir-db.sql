-- Initialize Haven Health FHIR Database
-- This script creates the necessary database for HAPI FHIR Server

-- Create FHIR database if it doesn't exist
CREATE DATABASE haven_health_fhir;

-- Grant privileges to the haven_user
GRANT ALL PRIVILEGES ON DATABASE haven_health_fhir TO haven_user;

-- Connect to the FHIR database
\c haven_health_fhir;

-- Create schema
CREATE SCHEMA IF NOT EXISTS fhir;

-- Grant privileges on schema
GRANT ALL ON SCHEMA fhir TO haven_user;

-- Set search path
ALTER DATABASE haven_health_fhir SET search_path TO fhir,public;
