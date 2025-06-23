#!/usr/bin/env python3
"""Initialize Test Database with Real Production Schema.

This script sets up the test database with all required extensions,
schemas, and configurations for medical-compliant testing.

NO SHORTCUTS - This creates the FULL production database structure
"""

import logging
import os
import sys
import time

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from .real_test_config import RealTestConfig
from .test_database_schema import create_test_schema

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestDatabaseInitializer:
    """Initialize test database with production-grade setup."""

    def __init__(self):
        """Initialize database configuration."""
        self.db_host = os.getenv("TEST_DB_HOST", "localhost")
        self.db_port = os.getenv("TEST_DB_PORT", "5433")
        self.db_name = "haven_test"
        self.db_user = "test"
        self.db_password = "test"
        self.admin_user = os.getenv("POSTGRES_ADMIN_USER", "postgres")
        self.admin_password = os.getenv("POSTGRES_ADMIN_PASSWORD", "postgres")

    def wait_for_postgres(self, max_attempts=30):
        """Wait for PostgreSQL to be ready."""
        logger.info("Waiting for PostgreSQL at %s:%s...", self.db_host, self.db_port)

        for attempt in range(max_attempts):
            try:
                conn = psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    user=self.admin_user,
                    password=self.admin_password,
                    database="postgres",
                    connect_timeout=5,
                )
                conn.close()
                logger.info("PostgreSQL is ready!")
                return True
            except (psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                if attempt < max_attempts - 1:
                    logger.debug("Attempt %s failed: %s", attempt + 1, e)
                    time.sleep(1)
                else:
                    logger.error("PostgreSQL not ready after %s attempts", max_attempts)
                    return False

        return False

    def create_database(self):
        """Create test database if it doesn't exist."""
        try:
            # Connect to postgres database to create our test database
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.admin_user,
                password=self.admin_password,
                database="postgres",
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (self.db_name,)
            )
            exists = cursor.fetchone()

            if exists:
                logger.info("Database '%s' already exists", self.db_name)
                # Drop and recreate for clean testing
                logger.info("Dropping existing database for clean test environment...")
                cursor.execute(f"DROP DATABASE IF EXISTS {self.db_name}")

            # Create database with proper encoding
            logger.info("Creating database '%s'...", self.db_name)
            cursor.execute(
                f"""
                CREATE DATABASE {self.db_name}
                WITH
                OWNER = {self.admin_user}
                ENCODING = 'UTF8'
                LC_COLLATE = 'en_US.utf8'
                LC_CTYPE = 'en_US.utf8'
                TABLESPACE = pg_default
                CONNECTION LIMIT = -1
            """
            )

            # Create test user if doesn't exist
            cursor.execute("SELECT 1 FROM pg_user WHERE usename = %s", (self.db_user,))
            if not cursor.fetchone():
                cursor.execute(
                    f"""
                    CREATE USER {self.db_user}
                    WITH PASSWORD '{self.db_password}'
                """
                )

            # Grant all privileges
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON DATABASE {self.db_name} TO {self.db_user}"
            )

            cursor.close()
            conn.close()

            logger.info("Database created successfully")

        except (psycopg2.Error, ValueError) as e:
            logger.error("Failed to create database: %s", e)
            raise

    def setup_extensions(self):
        """Install required PostgreSQL extensions."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.admin_user,
                password=self.admin_password,
                database=self.db_name,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Required extensions for medical compliance
            extensions = [
                "uuid-ossp",  # UUID generation
                "pgcrypto",  # Encryption functions
                "pg_trgm",  # Fuzzy text search
                "btree_gin",  # Better indexing
                "pg_stat_statements",  # Query monitoring
            ]

            for ext in extensions:
                logger.info("Creating extension: %s", ext)
                cursor.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')

            # Create custom functions for medical data
            logger.info("Creating medical compliance functions...")

            # PHI masking function
            cursor.execute(
                """
                CREATE OR REPLACE FUNCTION mask_phi(text)
                RETURNS text AS $$
                BEGIN
                    IF $1 IS NULL THEN
                        RETURN NULL;
                    END IF;
                    RETURN CONCAT(
                        SUBSTRING($1 FROM 1 FOR 1),
                        REPEAT('*', LENGTH($1) - 2),
                        SUBSTRING($1 FROM LENGTH($1))
                    );
                END;
                $$ LANGUAGE plpgsql IMMUTABLE;
            """
            )

            # Audit trigger function
            cursor.execute(
                """
                CREATE OR REPLACE FUNCTION log_phi_access()
                RETURNS TRIGGER AS $$
                BEGIN
                    INSERT INTO phi_access_log (
                        table_name,
                        operation,
                        user_id,
                        accessed_at,
                        row_data
                    ) VALUES (
                        TG_TABLE_NAME,
                        TG_OP,
                        current_user,
                        NOW(),
                        to_jsonb(NEW)
                    );
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """
            )

            cursor.close()
            conn.close()

            logger.info("Extensions and functions created successfully")

        except (psycopg2.Error, ValueError) as e:
            logger.error("Failed to setup extensions: %s", e)
            raise

    def create_schemas(self):
        """Create database schemas for organization."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Create schemas
            schemas = [
                "healthcare",  # FHIR resources and medical data
                "blockchain",  # Blockchain verification data
                "audit",  # Audit and compliance data
                "cache",  # Cached data for performance
            ]

            for schema in schemas:
                logger.info("Creating schema: %s", schema)
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                cursor.execute(f"GRANT ALL ON SCHEMA {schema} TO {self.db_user}")

            cursor.close()
            conn.close()

            logger.info("Schemas created successfully")

        except (psycopg2.Error, ValueError) as e:
            logger.error("Failed to create schemas: %s", e)
            raise

    def apply_security_settings(self):
        """Apply security settings for HIPAA compliance."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.admin_user,
                password=self.admin_password,
                database=self.db_name,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            logger.info("Applying security settings...")

            # Enable SSL requirement (in production)
            # cursor.execute("ALTER DATABASE haven_test SET ssl = on")

            # Set password encryption
            cursor.execute(
                "ALTER DATABASE haven_test SET password_encryption = 'scram-sha-256'"
            )

            # Enable row security policies
            cursor.execute("ALTER DATABASE haven_test SET row_security = on")

            # Set statement timeout to prevent long-running queries
            cursor.execute("ALTER DATABASE haven_test SET statement_timeout = '30s'")

            # Enable logging for audit
            cursor.execute("ALTER DATABASE haven_test SET log_statement = 'mod'")
            cursor.execute("ALTER DATABASE haven_test SET log_connections = on")
            cursor.execute("ALTER DATABASE haven_test SET log_disconnections = on")

            cursor.close()
            conn.close()

            logger.info("Security settings applied successfully")

        except (psycopg2.Error, ValueError) as e:
            logger.error("Failed to apply security settings: %s", e)
            raise

    def create_test_tables(self):
        """Create the actual database tables."""
        logger.info("Creating database tables...")

        # Import and run the schema creation
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        # Create engine with test user
        engine = RealTestConfig.create_real_database_engine()

        # Create all tables
        create_test_schema(engine)

        logger.info("All tables created successfully")

    def verify_setup(self):
        """Verify the database is properly set up."""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_password,
                database=self.db_name,
            )
            cursor = conn.cursor()

            # Check tables exist
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """
            )
            tables = cursor.fetchall()

            expected_tables = [
                "access_logs",
                "audit_logs",
                "emergency_access",
                "encryption_keys",
                "health_records",
                "patients",
                "providers",
            ]

            actual_tables = [t[0] for t in tables]

            logger.info("Found tables: %s", actual_tables)

            for table in expected_tables:
                if table not in actual_tables:
                    raise RuntimeError(f"Missing required table: {table}")

            # Check extensions
            cursor.execute(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname IN ('uuid-ossp', 'pgcrypto', 'pg_trgm')
            """
            )
            extensions = [e[0] for e in cursor.fetchall()]

            logger.info("Found extensions: %s", extensions)

            cursor.close()
            conn.close()

            logger.info("Database verification completed successfully!")

        except (psycopg2.Error, ValueError) as e:
            logger.error("Database verification failed: %s", e)
            raise

    def initialize(self):
        """Run the complete initialization process."""
        logger.info("Starting test database initialization...")

        # Wait for PostgreSQL
        if not self.wait_for_postgres():
            raise RuntimeError("PostgreSQL is not available")

        # Create database
        self.create_database()

        # Setup extensions
        self.setup_extensions()

        # Create schemas
        self.create_schemas()

        # Apply security settings
        self.apply_security_settings()

        # Create tables
        self.create_test_tables()

        # Verify setup
        self.verify_setup()

        logger.info("Test database initialization completed successfully!")

        # Print connection info
        print("\n" + "=" * 60)
        print("TEST DATABASE READY")
        print("=" * 60)
        print(f"Host: {self.db_host}")
        print(f"Port: {self.db_port}")
        print(f"Database: {self.db_name}")
        print(f"User: {self.db_user}")
        print(f"Password: {self.db_password}")
        print(
            f"Connection URL: postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        print("=" * 60 + "\n")


if __name__ == "__main__":
    initializer = TestDatabaseInitializer()
    try:
        initializer.initialize()
    except (psycopg2.Error, ValueError, RuntimeError) as e:
        logger.error("Initialization failed: %s", e)
        sys.exit(1)
