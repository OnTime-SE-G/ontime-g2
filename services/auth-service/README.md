# Auth Service Integration

This folder documents the agreed authentication boundary between G2 and G4.
G4 owns the final Auth implementation with Keycloak and Kong. G2 may provide a
temporary contract-compatible Auth wrapper only so G3 can test admin-created
driver accounts before final G4 Auth is ready.

## Ownership Boundary

| Concern | Owner |
|---|---|
| users, passwords, password hashes, roles, tokens | G4 Auth / Keycloak |
| JWT validation and RBAC routing | G4 Kong |
| driver transport profile, trips, assignments | G2 Fleet |
| combined create/deactivate flow for Admin UI | G2 API Gateway |

G2 must not store plaintext passwords and should not validate passwords during
normal driver/admin requests. Kong validates role access before forwarding to
G2.

## Planned Auth Routes

Routes exposed through Kong/Auth:

| Method | Path | Required Role | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | public | username/password login |
| `POST` | `/auth/admin/users` | `ADMIN` | create admin or driver auth user |
| `PATCH` | `/auth/admin/users/{authUserId}/disable` | `ADMIN` | disable auth user |
| `PATCH` | `/auth/users/{authUserId}/change-password` | authenticated user | first-login password reset |

G2 API Gateway will use the admin Auth routes only for user-management
orchestration. Normal G2 API requests should rely on Kong's validated claims.

## G2 Driver Flow

```text
Admin UI
  -> Kong validates ADMIN
  -> G2 API Gateway POST /api/v1/admin/fleet/drivers
      -> Auth creates DRIVER credentials
      -> Fleet creates driver profile linked by auth_user_id

Driver UI
  -> POST /auth/login
  -> receives token
  -> calls /api/v1/driver/*
  -> Kong validates DRIVER
  -> G2 API Gateway forwards to Fleet
```

## Planned Environment Variables

| Variable | Suggested Default | Meaning |
|---|---|---|
| `AUTH_SERVICE_PORT` | `8005` | temporary Auth wrapper port |
| `AUTH_BOOTSTRAP_ADMIN_USERNAME` | `admin` | first local/demo admin |
| `AUTH_BOOTSTRAP_ADMIN_PASSWORD` | secret | first admin password; never commit real value |
| `AUTH_BOOTSTRAP_ADMIN_EMAIL` | `admin@ontime.local` | first admin email |
| `AUTH_TOKEN_SECRET` | secret | dev token/JWT signing secret if wrapper is built |
| `AUTH_TOKEN_TTL_SECONDS` | `3600` | token expiry |

API Gateway should use:

| Variable | Suggested Default | Meaning |
|---|---|---|
| `AUTH_SERVICE_URL` | `http://auth-service:8005` | Auth wrapper/G4 Auth base URL |

## Kafka, MQTT, Redis

Auth Service does not use Kafka, MQTT, or Redis in the current plan.

## Read More

See [DRIVER_AUTH_INTEGRATION_PLAN.md](DRIVER_AUTH_INTEGRATION_PLAN.md) for the
full phased plan, bootstrap-admin decision, and RBAC notes.
