-- Initialize Haven Health Test Database
-- This script creates the necessary test database and user for running tests

-- Create test user if it doesn't exist
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'test_user') THEN
      CREATE ROLE test_user LOGIN PASSWORD 'test_password';
   END IF;
END
$do$;

-- Create test database if it doesn't exist
CREATE DATABASE haven_health_test;

-- Grant all privileges on test database to test user
GRANT ALL PRIVILEGES ON DATABASE haven_health_test TO test_user;

-- Also grant privileges to haven_user for administrative purposes
GRANT ALL PRIVILEGES ON DATABASE haven_health_test TO haven_user;

-- Connect to the test database
\c haven_health_test;

-- Create schema
CREATE SCHEMA IF NOT EXISTS public;

-- Grant privileges on schema
GRANT ALL ON SCHEMA public TO test_user;
GRANT ALL ON SCHEMA public TO haven_user;

-- Set search path
ALTER DATABASE haven_health_test SET search_path TO public;