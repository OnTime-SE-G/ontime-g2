# Migrations

SQL migration files for OnTime's PostgreSQL (PostGIS) schema, applied in order by `run_migrations.py`.

## Naming convention

Files must be named `V<N>__<description>.sql` where `N` is the sequential migration number:

```
V1__create_routes_and_stops.sql
V2__create_fleet_schema.sql
V3__create_anomaly_schema.sql
```

The `run_migrations.py` script discovers files by the glob `V*.sql` and applies them in lexicographic order. Applied versions are tracked in the `schema_migrations` table — already-applied migrations are always skipped (idempotent).

## Current migrations

| File | Creates |
|---|---|
| `V1__create_routes_and_stops.sql` | `routes`, `stops` (PostGIS geometry, GIST indexes) |
| `V2__create_fleet_schema.sql` | `buses`, `trips`, `stop_arrivals` + `bus_state` / `crowd_status` ENUMs |
| `V3__create_anomaly_schema.sql` | `anomalies`, `delay_reports` + `incident_code` / `delay_reason` ENUMs |

## Running migrations

```bash
# Load environment variables
set -a && source docker/.env && set +a

# Apply against local Docker PostgreSQL
python scripts/migrations/run_migrations.py

# Apply against Neon cloud (set DATABASE_URL explicitly)
DATABASE_URL="$NEON_DATABASE_URL" python scripts/migrations/run_migrations.py
```

## Adding a new migration

1. Create `V<N+1>__<short_description>.sql` in this directory
2. Write idempotent SQL (`CREATE TABLE IF NOT EXISTS`, `IF NOT EXISTS` guards on ENUMs)
3. Test locally, then apply to Neon
4. Commit both the SQL file and any ORM model changes together

## Ownership and Review

- Owner: Kusal
- Required reviewer: Nathasha
