-- V2__create_fleet_schema.sql
-- Fleet management: buses, trips, stop_arrivals.
-- Depends on V1 (routes, stops must exist).

-- ─────────────────────────────────────────────
-- ENUMs
-- ─────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bus_state') THEN
        CREATE TYPE bus_state AS ENUM (
            'WAITING_AT_DEPOT',
            'DEPARTED_ORIGIN',
            'EN_ROUTE',
            'ARRIVED_DESTINATION',
            'INCIDENT_REPORTED',
            'OUT_OF_SERVICE'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'crowd_status') THEN
        CREATE TYPE crowd_status AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'FULL');
    END IF;
END$$;

-- ─────────────────────────────────────────────
-- buses
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS buses (
    id                SERIAL PRIMARY KEY,
    bus_number        VARCHAR(50)  NOT NULL UNIQUE,
    capacity          INTEGER      NOT NULL DEFAULT 40,
    current_state     bus_state    NOT NULL DEFAULT 'WAITING_AT_DEPOT',
    current_route_id  INTEGER      REFERENCES routes(id) ON DELETE SET NULL,
    last_seen_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_buses_state
    ON buses (current_state);

-- ─────────────────────────────────────────────
-- trips
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trips (
    id          SERIAL PRIMARY KEY,
    bus_id      INTEGER      NOT NULL REFERENCES buses(id),
    route_id    INTEGER      NOT NULL REFERENCES routes(id),
    driver_id   VARCHAR(100),
    state       bus_state    NOT NULL DEFAULT 'WAITING_AT_DEPOT',
    crowd       crowd_status NOT NULL DEFAULT 'LOW',
    started_at  TIMESTAMPTZ,
    ended_at    TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trips_bus_id   ON trips (bus_id);
CREATE INDEX IF NOT EXISTS idx_trips_route_id ON trips (route_id);
CREATE INDEX IF NOT EXISTS idx_trips_state    ON trips (state);

-- ─────────────────────────────────────────────
-- stop_arrivals
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stop_arrivals (
    id            SERIAL PRIMARY KEY,
    trip_id       INTEGER     NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    stop_id       INTEGER     NOT NULL REFERENCES stops(id),
    arrived_at    TIMESTAMPTZ,
    departed_at   TIMESTAMPTZ,
    estimated_at  TIMESTAMPTZ,
    UNIQUE (trip_id, stop_id)
);

CREATE INDEX IF NOT EXISTS idx_stop_arrivals_trip_id
    ON stop_arrivals (trip_id);
