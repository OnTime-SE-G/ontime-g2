# Guide: Connecting to Kong & Keycloak

This guide explains how to set up the authentication and gateway infrastructure for the OnTime G2 platform.

## 1. Start G2 Infrastructure

Ensure your G2 microservices are running. Since Kong and Keycloak are managed by G4, you only need to start your local services.

```bash
docker-compose up -d
```

## 2. Initialize Keycloak

Configure your Keycloak credentials in `.env` (pointing to the G4 Keycloak instance). Then, run the bootstrap script to create the necessary roles and clients if they don't already exist.

```bash
python scripts/bootstrap_keycloak.py
```

## 3. Create the First Admin User (Manual)

To perform any administrative actions (like creating drivers), you need a user with the `ADMIN` role.

1.  Open the **Keycloak Admin Console** (URL provided by G4, e.g., `http://keycloak:8080`).
2.  Login with the credentials in your `.env` (Default: `admin` / `admin`).
3.  Select the **ontime** realm from the dropdown.
4.  Go to **Users** -> **Add user**.
    *   Username: `superadmin` (or any name you prefer).
5.  After saving, go to the **Credentials** tab and **Set password**. Turn off "Temporary" if you want to use it immediately.
6.  Go to the **Role mapping** tab -> **Assign role**.
    *   Filter by realm roles and select **ADMIN**.
    *   Assign the role.

## 4. Accessing Services via Kong

## 4. Accessing Services

Since Kong is managed by the G4 infrastructure, ensure you are routing your requests through the appropriate G4 gateway URL.

*   **Public Access:** No token required.
    *   `GET /health`
*   **Admin Access:** Requires a JWT with the `ADMIN` role.
    *   `POST /api/v1/admin/fleet/drivers`
*   **Driver Access:** Requires a JWT with the `DRIVER` role.
    *   `POST /api/v1/driver/trips/{id}/start`

## 5. Getting a JWT Token

To test protected routes, you can get a token directly from Keycloak:

```bash
curl --location 'http://localhost:8080/realms/ontime/protocol/openid-connect/token' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--data-urlencode 'username=superadmin' \
--data-urlencode 'password=yourpassword' \
--data-urlencode 'grant_type=password' \
--data-urlencode 'client_id=ontime-api' \
--data-urlencode 'client_secret=secret'
```

Copy the `access_token` and use it in your requests as an `Authorization: Bearer <token>` header.
