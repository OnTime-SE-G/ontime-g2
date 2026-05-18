# Keycloak Admin Role Implementation Plan

## Purpose

This implementation plan defines how the system will create and manage `ADMIN` and `DRIVER` roles using Keycloak while keeping authentication ownership under G4/Auth and business orchestration under G2.

---

# 1. Objective

The system must support:

* Admin login
* Driver login
* Role-based access control (RBAC)
* Admin-created driver accounts
* Secure JWT-based authorization through Kong
* Separation between authentication and Fleet business data

Authentication, JWT generation, password management, and role ownership will be handled directly by Keycloak.

Kong will enforce JWT validation and RBAC before requests reach G2 services.

G2 services will orchestrate business flows and communicate directly with Keycloak Admin APIs when administrative identity operations are required.

---

# 2. Architecture Boundary

| Responsibility             | Owner            |
| -------------------------- | ---------------- |
| User authentication        | Keycloak / G4    |
| Password management        | Keycloak / G4    |
| JWT generation             | Keycloak / G4    |
| RBAC enforcement           | Kong + Keycloak  |
| Driver profile data        | G2 Fleet Service |
| Keycloak admin integration | G2 API Gateway   |
| Driver assignment/trips    | G2 Fleet Service |

---

# 3. Realm Configuration

## 3.1 Create Realm

Create a dedicated realm for the project.

Example:

```text
Realm Name: ontime
```

Purpose:

* Isolate authentication configuration
* Manage project-specific users and roles
* Support JWT generation for the platform

---

# 4. Role Configuration

## 4.1 Required Roles

The following roles must be created inside Keycloak:

```text
ADMIN
DRIVER
```

## 4.2 Role Creation Steps

Navigate to:

```text
Keycloak Admin Console
→ Realm Roles
→ Create Role
```

Create:

```text
Role Name: ADMIN
```

Create:

```text
Role Name: DRIVER
```

## 4.3 Role Usage

| Role   | Access                         |
| ------ | ------------------------------ |
| ADMIN  | Admin APIs and user management |
| DRIVER | Driver trip lifecycle APIs     |

---

# 5. Bootstrap Admin User

## 5.1 Purpose

The first admin user cannot be created through the UI because no admin exists yet.

A bootstrap admin account must therefore be seeded during deployment.

---

## 5.2 Environment Variables

Example:

```text
AUTH_BOOTSTRAP_ADMIN_USERNAME=admin
AUTH_BOOTSTRAP_ADMIN_PASSWORD=<secret>
AUTH_BOOTSTRAP_ADMIN_EMAIL=admin@ontime.local
```

---

## 5.3 Admin User Creation

Navigate to:

```text
Users
→ Add User
```

Create:

```text
Username: admin
Enabled: ON
```

---

## 5.4 Password Setup

Navigate to:

```text
Credentials
→ Set Password
```

Configuration:

```text
Temporary Password: ON
```

This forces password reset during first login.

---

## 5.5 Assign ADMIN Role

Navigate to:

```text
Role Mapping
→ Assign Role
→ ADMIN
```

Result:

The bootstrap user becomes a platform administrator.

---

# 6. Client Configuration

## 6.1 Create API Client

Create a Keycloak client for API authentication.

Example:

```text
Client ID: ontime-api
```

---

## 6.2 Recommended Settings

| Setting              | Value                                  |
| -------------------- | -------------------------------------- |
| Access Type          | confidential                           |
| Standard Flow        | enabled                                |
| Direct Access Grants | enabled (development only if required) |
| Service Accounts     | optional                               |

---

# 7. JWT Requirements

## 7.1 Required Claims

Generated JWTs should include:

```json
{
  "sub": "auth-user-123",
  "preferred_username": "alice.driver",
  "realm_access": {
    "roles": ["DRIVER"]
  }
}
```

---

## 7.2 Claim Usage

| Claim              | Purpose                     |
| ------------------ | --------------------------- |
| sub                | Stable auth user identifier |
| preferred_username | Display/login username      |
| realm_access.roles | RBAC enforcement            |

---

# 8. Kong RBAC Enforcement

Kong will validate JWTs before requests reach G2 services.

## 8.1 Route Protection Rules

| Route                 | Required Role |
| --------------------- | ------------- |
| /api/v1/admin/*       | ADMIN         |
| /api/v1/driver/*      | DRIVER        |
| Public passenger APIs | Public        |

---

## 8.2 Kong Responsibilities

Kong must:

* Validate JWT signatures
* Validate token expiration
* Validate role claims
* Reject unauthorized requests
* Forward trusted claims to G2 services

---

# 9. G2 API Gateway Responsibilities

The G2 API Gateway orchestrates business flows involving Auth and Fleet services.

---

## 9.1 Driver Creation Flow

### Endpoint

```http
POST /api/v1/admin/fleet/drivers
```

### Flow

```text
1. Admin request arrives through Kong
2. Kong validates ADMIN role
3. API Gateway calls Keycloak Admin API
4. Keycloak creates DRIVER user
5. API Gateway creates Fleet driver profile
6. API Gateway returns combined response
```

---

## 9.2 Driver Creation Request

```json
{
  "name": "Alice Perera",
  "license_number": "B1234567",
  "phone": "0771234567",
  "username": "alice.driver",
  "password": "TemporaryPassword123"
}
```

---

## 9.3 Keycloak User Creation Request

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

---

## 9.4 Keycloak User Creation Response

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

# 10. Fleet Service Responsibilities

The Fleet Service owns operational driver profile data.

---

## 10.1 Driver Model Fields

```text
id
name
license_number
phone
auth_user_id
username
is_active
```

---

## 10.2 Important Rules

Fleet Service must never store:

* passwords
* password hashes
* refresh tokens
* login sessions

These belong exclusively to Keycloak.

---

# 11. Driver Deactivation Flow

## 11.1 Endpoint

```http
PATCH /api/v1/admin/fleet/drivers/{driverId}/deactivate
```

---

## 11.2 Flow

```text
1. Admin request reaches API Gateway
2. API Gateway retrieves Fleet driver
3. API Gateway disables Keycloak/Auth user
4. Fleet driver is marked inactive
5. Response returned to Admin UI
```

---

## 11.3 Rules

* Drivers must be soft-deactivated
* Historical trip data must remain intact
* Inactive drivers cannot receive new assignments

---

# 12. Database Changes

## 12.1 Fleet Schema Extension

Add:

```text
auth_user_id: string
username: string
is_active: boolean
```

---

## 12.2 Purpose

| Field        | Purpose                    |
| ------------ | -------------------------- |
| auth_user_id | Stable Keycloak linkage    |
| username     | Search/display convenience |
| is_active    | Soft deactivation state    |

---

# 13. API Gateway Keycloak Client

## 13.1 Purpose

The API Gateway will communicate directly with Keycloak Admin APIs.

A separate Auth Service will not be used.

This simplifies deployment and removes unnecessary service duplication because Kong and Keycloak already provide authentication and authorization infrastructure.

---

## 13.2 Required Methods

The API Gateway Keycloak client should support:

```text
create_user()
assign_role()
disable_user()
change_password()
```

---

## 13.3 Suggested Implementation

Example:

```text
services/api-gateway/app/services/keycloak_client.py
```

This module should isolate all Keycloak-specific logic from the rest of the G2 codebase.

---

## 13.4 Responsibilities

The Keycloak client should:

* Authenticate with Keycloak Admin APIs
* Create users
* Assign ADMIN or DRIVER roles
* Disable users
* Trigger password reset requirements
* Handle Keycloak access tokens internally

---

## 13.5 Configuration

Environment variables:

```text
KEYCLOAK_BASE_URL=http://keycloak:8080
KEYCLOAK_REALM=ontime
KEYCLOAK_CLIENT_ID=ontime-api
KEYCLOAK_CLIENT_SECRET=<secret>
KEYCLOAK_ADMIN_USERNAME=admin
KEYCLOAK_ADMIN_PASSWORD=<secret>
```

---

# 14. Security Rules

## 14.1 Password Handling

Rules:

* Passwords must only be forwarded to Keycloak
* Passwords must never be logged
* Passwords must never be returned in responses
* Passwords must never be stored in Fleet Service

---

## 14.2 Trust Boundary

```text
Keycloak = identity authority
Kong = authorization gatekeeper
G2 = transport business orchestration
```

---

# 15. Implementation Phases

## Phase 1

Setup Keycloak realm and roles.

Deliverables:

* Realm created
* ADMIN role created
* DRIVER role created
* Bootstrap admin created

---

## Phase 2

Extend Fleet database schema.

Deliverables:

* auth_user_id added
* username added
* is_active added

---

## Phase 3

Implement API Gateway Keycloak integration.

Deliverables:

* create_user()
* assign_role()
* disable_user()
* change_password()

---

## Phase 4

Implement combined admin driver creation.

Deliverables:

* Driver creation orchestration
* Compensation rollback handling
* Integration tests

---

## Phase 5

Implement driver deactivation.

Deliverables:

* Soft deactivate flow
* Keycloak disable integration
* Assignment prevention for inactive drivers

---

## Phase 6

Integrate Kong RBAC enforcement.

Deliverables:

* JWT validation
* Role validation
* Route protection policies

---

# 16. Final Boundary Summary

```text
Authentication/passwords/tokens = Keycloak
JWT/RBAC enforcement            = Kong
Driver business profiles        = G2 Fleet Service
Keycloak orchestration          = G2 API Gateway
```

This boundary keeps authentication centralized while allowing G2 services to remain focused on transport business logic.
