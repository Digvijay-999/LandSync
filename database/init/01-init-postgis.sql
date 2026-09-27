-- PostGIS & Extensions Initialization Script
-- Executed on container creation when database volume is first initialized

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Output confirmation to postgres container logs
DO $$
BEGIN
    RAISE NOTICE 'LandSync PostGIS extensions initialized successfully. PostGIS version: %', postgis_version();
END $$;
