-- V3__create_anomaly_schema.sql
-- Anomaly detection and delay reporting tables.
-- Depends on V2 (buses, trips must exist).

-- ─────────────────────────────────────────────
-- ENUMs
-- ─────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incident_code') THEN
        CREATE TYPE incident_code AS ENUM (
            'STATIONARY_BUS',
            'OFF_ROUTE_DEVIATION',
            'COMMS_LOSS',
            'DRIVER_REPORTED',
            'SPEED_ANOMALY'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'delay_reason') THEN
        CREATE TYPE delay_reason AS ENUM (
            'TRAFFIC',
            'BREAKDOWN',
            'PASSENGER_INCIDENT',
            'WEATHER',
            'OTHER'
        );
    END IF;
END$$;

-- ─────────────────────────────────────────────
-- anomalies
-- ─────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS anomalies (
    id           SERIAL PRIMARY KEY,
    trip_id      INTEGER        REFERENCES trips(id) ON DELETE SET NULL,
    bus_id       INTEGER        REFERENCES buses(id) ON DELETE SET NULL,
    code         incident_code  NOT NULL,
    description  TEXT,
    location     geometry(POINT, 4326),
    detected_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    resolved_at  TIMESTAMPTZ,
    is_resolved  BOOLEAN        NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_anomalies_trip_id    ON anomalies (trip_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_bus_id     ON anomalies (bus_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_code       ON anomalies (code);
CREATE INDEX IF NOT EXISTS idx_anomalies_location   ON anomalies USING GIST (location);

-- ─────────────────────────────────────────────
-- delay_reports
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS delay_reports (
    id                       SERIAL PRIMARY KEY,
    trip_id                  INTEGER      NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    reason                   delay_reason NOT NULL,
    estimated_delay_minutes  INTEGER      NOT NULL,
    reported_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    reported_by              VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_delay_reports_trip_id
    ON delay_reports (trip_id);
