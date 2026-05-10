# Driver Auth Integration Plan

**Status:** Draft for G2/G3/G4 alignment
**Scope:** Admin-created driver accounts, driver login, RBAC routing, and G2 Fleet driver profile linking
**Goal:** Let Fleet Admin create and deactivate drivers from the UI while keeping password/login ownership in Auth.

---

## 1. Final Decision

G2 will support admin-created driver accounts through a combined API Gateway flow, but G2 will not own passwords or token validation.

```text
Authentication, passwords, roles, tokens = G4 Auth / Keycloak
Route protection and RBAC enforcement     = Kong + Keycloak claims
Driver profile, trips, assignments        = G2 Fleet Management
Combined admin convenience endpoint       = G2 API Gateway
```

For deadline/testing, G2 can provide a temporary Auth wrapper using the same contract that G4 will later expose through Keycloak/Kong. This lets G3 test the UI now and lets G4 replace the backend auth implementation later without changing the UI contract.

---

## 2. Data Ownership

### Auth Service / Keycloak Owns

```text
auth_user_id
username
password_hash
roles
enabled / disabled
must_change_password
token/session state
```

Passwords are stored only as hashes. Plaintext passwords are never stored or returned.

### G2 Fleet Service Owns

```text
driver.id
driver.name
driver.license_number
driver.phone
driver.auth_user_id
driver.username        # optional display/search copy
driver.is_active
```

`auth_user_id` is the stable link between Fleet and Auth. Username may be stored for display, but it should not be the primary link because usernames can change.

---

## 3. User Access Model

### Passenger

Passengers are public/anonymous for the current scope.

Allowed without login through Kong:

```text
GET /api/v1/routes
GET /api/v1/routes/search
GET /api/v1/routes/{routeId}
GET /api/v1/routes/{routeId}/stops
GET /api/v1/stops
GET /api/v1/eta/{tripId}/{stopId}
WS  /v1/live
```

Gateway controls should still apply:

```text
rate limiting
CORS policy
request size limits
WebSocket connection limits
monitoring
```

Passenger auth can be added later if the product needs saved favorites, notifications, payments, or personalized alerts.

### Driver

Driver endpoints require `DRIVER` role.

```text
/api/v1/driver/*
```

Driver login flow:

```text
Driver UI
  -> Kong/Auth login route
  -> Auth validates username/password
  -> Auth returns JWT/token with DRIVER role
  -> Driver UI calls G2 driver APIs with token
  -> Kong validates token + role
  -> Kong forwards to G2 API Gateway
```

G2 does not validate the password. G2 may later read trusted user claims/headers from Kong, such as `auth_user_id`, to return only that driver's trips.

### Admin

Admin endpoints require `ADMIN` role.

```text
/api/v1/admin/*
/auth/admin/*
```

Admin creates drivers and other admins only after Kong/Auth authorizes the admin token.

---

## 4. RBAC Boundary

RBAC should be enforced before traffic reaches G2 business services.

```text
Keycloak
  stores users, roles, password hashes
  issues JWT/access token

Kong
  validates JWT/access token
  checks route-level role policy
  forwards allowed traffic to G2 API Gateway

G2 API Gateway
  handles transport business orchestration
  calls Auth only for admin user-management actions
```

Recommended Kong route policy:

| Route | Required Role |
|---|---|
| `/auth/login` | public |
| `/auth/admin/*` | `ADMIN` |
| `/api/v1/admin/*` | `ADMIN` |
| `/api/v1/driver/*` | `DRIVER` |
| Passenger route/search/ETA/live APIs | public for current scope |
| `/health`, `/metrics` | internal/G4 monitoring only |

After login, G2 should not call Auth on every normal request. Kong already validates the token and role. G2 calls Auth only for admin user-management operations like create user, disable user, and reset password.

---

## 5. Current Repo State

Already available:

- `services/api-gateway/app/routers/admin_fleet.py`
  - `POST /api/v1/admin/fleet/drivers`
  - `GET /api/v1/admin/fleet/drivers`
- `services/api-gateway/app/routers/driver.py`
  - driver trip lifecycle endpoints
  - comments already state G4/Kong must enforce driver auth
- `services/fleet-management-service/app/routers/trips.py`
  - `POST /api/v1/fleet/drivers`
  - `GET /api/v1/fleet/drivers`
- `services/fleet-management-service/app/models/db_fleet.py`
  - `DriverORM` currently stores `name`, `license_number`, `phone`

Missing:

- `auth_user_id` link from Fleet driver profile to Auth user
- optional `username` display field in Fleet driver profile
- `is_active` deactivation state
- admin deactivate/delete endpoint
- API Gateway client for Auth Service
- combined `create auth user + create Fleet driver profile` flow
- bootstrap admin seed for local/demo

---

## 6. Target API Contracts

### 6.1 Admin Creates Driver

Used by G3 Admin UI through Kong.

```http
POST /api/v1/admin/fleet/drivers
```

Request:

```json
{
  "name": "Alice Perera",
  "license_number": "B1234567",
  "phone": "0771234567",
  "username": "alice.driver",
  "password": "TemporaryPassword123"
}
```

Response:

```json
{
  "id": 1,
  "name": "Alice Perera",
  "license_number": "B1234567",
  "phone": "0771234567",
  "username": "alice.driver",
  "auth_user_id": "auth-user-123",
  "is_active": true,
  "must_change_password": true
}
```

Rules:

- Password is forwarded to Auth only.
- Password is never stored in Fleet.
- Response never includes password.
- Driver username is admin-entered.
- `must_change_password=true` should be used if feasible.

### 6.2 Admin Deactivates Driver

Canonical endpoint:

```http
PATCH /api/v1/admin/fleet/drivers/{driverId}/deactivate
```

Response:

```json
{
  "id": 1,
  "auth_user_id": "auth-user-123",
  "is_active": false,
  "message": "Driver deactivated"
}
```

Optional UI-compatible alias:

```http
DELETE /api/v1/admin/fleet/drivers/{driverId}
```

This must perform the same soft-deactivate behavior. Hard delete should be avoided because planned trips and history may reference the driver.

### 6.3 Auth Wrapper Contract

Until G4 finalizes route naming, G2 uses these provisional internal Auth wrapper routes:

```http
POST /auth/login
POST /auth/admin/users
PATCH /auth/admin/users/{authUserId}/disable
PATCH /auth/users/{authUserId}/change-password
```

Create user request:

```json
{
  "username": "alice.driver",
  "password": "TemporaryPassword123",
  "role": "DRIVER",
  "display_name": "Alice Perera",
  "phone": "0771234567",
  "must_change_password": true
}
```

Create user response:

```json
{
  "auth_user_id": "auth-user-123",
  "username": "alice.driver",
  "role": "DRIVER",
  "status": "active",
  "must_change_password": true
}
```

---

## 7. First Admin Bootstrap

The first admin cannot be created from the Admin UI because no admin exists yet to authorize that action.

Recommended local/demo bootstrap:

```text
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=<secret>
AUTH_BOOTSTRAP_ADMIN_EMAIL=admin@ontime.local
```

On first startup, Auth/Keycloak seed creates one `ADMIN` user from environment variables or deployment secrets. After first login, that admin should be forced to change the bootstrap password.

Production expectation:

- G4 owns real Keycloak bootstrap using deployment secrets.
- No public admin self-registration.
- Additional admins are created later by an existing admin.

Local/demo expectation:

- G2 temporary Auth wrapper may seed one default admin.
- Do not commit real production passwords.

---

## 8. Implementation Phases

### Phase 0 - Confirm G4/G3 Contract

Owner: G2 + G3 + G4

- G4 confirmed Keycloak will be used.
- Use provisional Auth wrapper routes in this plan until G4 provides final Kong paths.
- Driver username is admin-entered.
- Driver password reset on first login should be enabled if feasible.
- Driver removal is soft deactivate.
- `PATCH deactivate` is canonical; `DELETE` can be an alias only if G3 requires it.

### Phase 1 - Temporary Auth Wrapper For G3 Testing

Owner: G2, replaceable by G4 later

Create a small Auth wrapper under `services/auth-service/` so G3 can test immediately.

Required behavior:

- seed bootstrap admin from env vars
- create users with role `ADMIN` or `DRIVER`
- hash passwords
- login and return a dev token/JWT-like payload
- support `must_change_password`
- disable users

Important:

- This is a contract-compatible wrapper, not G2 permanently owning auth.
- Keep `AUTH_SERVICE_URL` configurable so API Gateway can later point to G4 Auth/Keycloak.

### Phase 2 - Fleet Driver Profile Extension

Owner: G2 Fleet

Files:

- `services/fleet-management-service/app/models/db_fleet.py`
- `services/fleet-management-service/app/schemas/fleet.py`
- `services/fleet-management-service/app/routers/trips.py`
- Fleet tests

Changes:

- Add `auth_user_id: str | None`
- Add `username: str | None`
- Add `is_active: bool = true`
- Extend `DriverCreate` and `DriverResponse`
- Add:

```http
GET   /api/v1/fleet/drivers/{driverId}
PATCH /api/v1/fleet/drivers/{driverId}/deactivate
```

Rules:

- Existing old drivers can have `auth_user_id = null`.
- Deactivated drivers should not be assignable to new trips.
- Do not hard delete drivers with planned trip history.

Tests:

- create driver with `auth_user_id`
- list includes username and active status
- deactivate driver
- cannot assign inactive driver to planned trip

### Phase 3 - API Gateway Auth Client

Owner: G2 API Gateway

Files:

- `services/api-gateway/app/services/auth_client.py`
- `services/api-gateway/app/config.py`
- API Gateway tests

Add env var:

```text
AUTH_SERVICE_URL=http://auth-service:8005
```

Add helper methods:

```text
create_auth_user(username, password, role, display_name, phone, must_change_password)
disable_auth_user(auth_user_id)
```

Rules:

- Forward password only to Auth.
- Do not log password.
- Do not return password.

### Phase 4 - Combined Admin Driver Create

Owner: G2 API Gateway

Files:

- `services/api-gateway/app/routers/admin_fleet.py`
- `services/api-gateway/app/schemas.py`
- `services/api-gateway/app/services/fleet_client.py`
- API Gateway tests

Flow:

```text
POST /api/v1/admin/fleet/drivers
  1. Auth create user role=DRIVER, must_change_password=true
  2. Fleet create driver profile with auth_user_id + username
  3. Return Fleet driver profile
```

Failure handling:

- If Auth creation fails, do not create Fleet driver.
- If Fleet creation fails after Auth succeeds, disable the newly created Auth user as compensation.
- Return a clear error if compensation fails.

### Phase 5 - Combined Driver Deactivate

Owner: G2 API Gateway + Fleet

Flow:

```text
PATCH /api/v1/admin/fleet/drivers/{driverId}/deactivate
  1. Get Fleet driver profile
  2. Disable Auth user if auth_user_id exists
  3. Mark Fleet driver is_active=false
  4. Return deactivated profile/status
```

Optional alias:

```text
DELETE /api/v1/admin/fleet/drivers/{driverId}
```

This should call the same soft-deactivate logic.

### Phase 6 - Kong/G4 Swap

Owner: G4 with G2 support

When G4 Keycloak/Kong is ready:

```text
AUTH_SERVICE_URL=<G4 Auth wrapper or Keycloak adapter URL>
```

Kong routes:

```text
POST /auth/login
POST /auth/admin/users
PATCH /auth/admin/users/{authUserId}/disable
  -> G4 Auth

/api/v1/admin/*
/api/v1/driver/*
  -> G2 API Gateway after Kong JWT/role validation

Passenger read-only APIs
  -> public through Kong with rate limits
```

G2 Fleet, Route, ETA, Anomaly, and internal services remain private.

---

## 9. Recommended Delivery Order

Fastest safe path:

1. Implement temporary Auth wrapper with bootstrap admin.
2. Add Fleet `auth_user_id`, optional `username`, and `is_active`.
3. Add Fleet driver deactivate endpoint.
4. Add API Gateway `auth_client`.
5. Update admin driver create to combined Auth + Fleet.
6. Add admin driver deactivate endpoint.
7. Add focused unit tests.
8. Ask G3 to test Admin UI create/deactivate/assign driver.
9. Later switch `AUTH_SERVICE_URL` and Kong routing to G4 Keycloak-backed Auth.

---

## 10. Decisions Locked So Far

- G4 will use Keycloak.
- G4 has not finalized Auth base URL/route names, so G2 uses provisional wrapper routes for now.
- Driver username is admin-entered.
- Driver password should be reset on first login if feasible.
- Driver removal is soft deactivate.
- Passenger read-only APIs are public for now.
- RBAC for admin/driver APIs is handled by Kong + Keycloak before traffic reaches G2.
- G2 API Gateway calls Auth only for admin user-management actions, not for every normal request.
- G3 can test driver creation/assignment before final G4 Keycloak if G2 provides the temporary Auth wrapper.

---

## 11. Final Boundary Rule

```text
Password/login/token     = G4 Auth / Keycloak
RBAC route enforcement   = Kong + Keycloak claims
Driver profile/trips     = G2 Fleet
Create/deactivate flow   = G2 API Gateway orchestration
Passenger read-only APIs = public through Kong with limits
```
