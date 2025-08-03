-- PostgreSQL initialization script for Car Assistant local development
-- This script runs when the PostgreSQL container starts for the first time

-- Create database if it doesn't exist (handled by POSTGRES_DB env var)
-- Ensure proper encoding and collation
ALTER DATABASE ${DATABASE_NAME} SET timezone TO 'UTC';

-- Create extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON DATABASE ${DATABASE_NAME} TO ${DATABASE_USER};
GRANT ALL PRIVILEGES ON SCHEMA public TO ${DATABASE_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DATABASE_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DATABASE_USER};

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DATABASE_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DATABASE_USER};

-- Create a simple health check function
CREATE OR REPLACE FUNCTION health_check()
RETURNS TEXT AS $$
BEGIN
    RETURN '${DATABASE_NAME} database is healthy';
END;
$$ LANGUAGE plpgsql;

-- Log the initialization
INSERT INTO pg_stat_statements_reset();
SELECT 'PostgreSQL database initialized for ${DATABASE_NAME}' as status;
