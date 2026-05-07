# Keycloak Connection Guide

This service integrates with Keycloak for authentication and user management. Use this guide to configure the connection between the `auth-service` and your Keycloak instance.

## 1. Keycloak Configuration Requirements

Before connecting, ensure the following are configured in your Keycloak Admin Console:

### Create a Realm
- Recommended Name: `ontime`

### Create a Client
- **Client ID**: `ontime-auth-service` (or your preferred name)
- **Client Protocol**: `openid-connect`
- **Access Type**: `confidential`
- **Service Accounts Enabled**: `ON` (Required if the service needs to manage users via Admin API)
- **Valid Redirect URIs**: `*` (or your specific frontend/gateway URLs)

### Get Client Secret
- Go to the **Credentials** tab of your client and copy the **Secret**.

### Admin User (Optional but Recommended)
For user registration (`/users/register`) to work, the service needs credentials for a user with `manage-users` permissions. This is typically done via:
1. A dedicated service account.
2. Or using an admin user's credentials (not recommended for production).

## 2. Environment Variables

Set the following variables in your `.env` file or container environment:

| Variable | Description | Example |
|----------|-------------|---------|
| `KEYCLOAK_URL` | Base URL of your Keycloak server | `https://auth.ontime.lk` |
| `KEYCLOAK_REALM` | The realm name created above | `ontime` |
| `KEYCLOAK_CLIENT_ID` | The Client ID created above | `ontime-auth-service` |
| `KEYCLOAK_CLIENT_SECRET` | The secret from the Credentials tab | `abc123...` |
| `KEYCLOAK_ADMIN_USERNAME`| Username with admin/manage-users permissions | `admin` |
| `KEYCLOAK_ADMIN_PASSWORD`| Password for the admin user | `password123` |

## 3. How it Works

1. **Authentication**: The service uses the `KeycloakOpenID` library to exchange usernames/passwords for JWT tokens.
2. **User Management**: When a user registers, the service uses the `KeycloakAdmin` API to create the user in Keycloak and then saves the resulting Keycloak UUID into the local `auth_db`.
3. **Token Validation**: In future updates, the `api-gateway` or individual services will validate the JWT by calling Keycloak's public key endpoint or introspection endpoint.

## 4. Troubleshooting

- **Connection Refused**: Ensure `KEYCLOAK_URL` is accessible from within the Docker network. Use the container name (e.g., `http://keycloak:8080`) if running in the same Docker Compose.
- **Unauthorized**: Check that the `CLIENT_SECRET` and `REALM` are exact matches.
- **403 Forbidden on Register**: Ensure the `KEYCLOAK_ADMIN_USERNAME` has the `manage-users` role assigned in the realm.
