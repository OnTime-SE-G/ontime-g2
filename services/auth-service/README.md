# Auth Service Integration

This folder documents the agreed integration boundary for driver/admin authentication.
It is the single source of truth for the current driver-auth plan in this repo.

G4 owns the actual Auth Service implementation, password storage, login flow, token issuing, and Kong/JWT validation. G2 does not store driver passwords and does not issue login tokens.

For deadline testing, G2 may provide a temporary Auth wrapper with the same contract so G3 can test admin-created driver accounts before G4's final Keycloak/Kong deployment is ready.

G2 uses this integration contract so the API Gateway can coordinate admin driver creation:

```text
Admin UI
  -> Kong validates admin role
  -> G2 API Gateway
      -> G4 Auth Service creates DRIVER login credentials
      -> G2 Fleet Service creates driver profile linked by auth_user_id
```

Driver login remains owned by G4 Auth:

```text
Driver UI
  -> Kong/Auth login
  -> token
  -> Kong validates DRIVER role
  -> G2 API Gateway driver endpoints
```

See [DRIVER_AUTH_INTEGRATION_PLAN.md](DRIVER_AUTH_INTEGRATION_PLAN.md) for phases, contracts, and implementation details.
