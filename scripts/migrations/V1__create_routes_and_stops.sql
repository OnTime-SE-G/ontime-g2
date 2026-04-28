-- V1__create_routes_and_stops.sql
-- Core route geometry tables.
-- Column names MUST match the SQLAlchemy ORM in scripts/models/db_route.py:
--   RouteORM  -> tablename="routes"  (id, name, geometry)
--   StopORM   -> tablename="stops"   (id, route_id, name, stop_order, location)

-- Enable PostGIS (idempotent)
CREATE EXTENSION IF NOT EXISTS postgis;

-- ─────────────────────────────────────────────
-- routes
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routes (
    id       SERIAL PRIMARY KEY,
    name     VARCHAR(150) NOT NULL UNIQUE,
    geometry geometry(LINESTRING, 4326)
);

CREATE INDEX IF NOT EXISTS idx_routes_geometry
    ON routes USING GIST (geometry);

-- ─────────────────────────────────────────────
-- stops
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stops (
    id         SERIAL PRIMARY KEY,
    route_id   INTEGER      NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    name       VARCHAR(120) NOT NULL,
    stop_order INTEGER      NOT NULL,
    location   geometry(POINT, 4326),
    UNIQUE (route_id, stop_order)
);

CREATE INDEX IF NOT EXISTS idx_stops_location
    ON stops USING GIST (location);

CREATE INDEX IF NOT EXISTS idx_stops_route_id
    ON stops (route_id);
