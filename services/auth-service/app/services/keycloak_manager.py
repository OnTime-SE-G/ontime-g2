from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import KeycloakError
from fastapi import HTTPException, status
from ..config import settings

class KeycloakManager:
    def __init__(self):
        self.keycloak_openid = KeycloakOpenID(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            realm_name=settings.KEYCLOAK_REALM,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET
        )
        
        # Admin connection is optional, only needed for user management (create/delete)
        self.keycloak_admin = None
        if settings.KEYCLOAK_ADMIN_USERNAME and settings.KEYCLOAK_ADMIN_PASSWORD:
            try:
                self.keycloak_admin = KeycloakAdmin(
                    server_url=settings.KEYCLOAK_URL,
                    username=settings.KEYCLOAK_ADMIN_USERNAME,
                    password=settings.KEYCLOAK_ADMIN_PASSWORD,
                    realm_name=settings.KEYCLOAK_REALM,
                    user_realm_name="master",  # Admin user is usually in master realm
                    verify=True
                )
            except Exception as e:
                print(f"Warning: Failed to initialize Keycloak Admin: {e}")

    def get_token(self, username, password):
        try:
            return self.keycloak_openid.token(username, password)
        except KeycloakError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Login failed: {str(e)}"
            )

    def refresh_token(self, refresh_token):
        try:
            return self.keycloak_openid.refresh_token(refresh_token)
        except KeycloakError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {str(e)}"
            )

    def create_user(self, user_data):
        if not self.keycloak_admin:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Keycloak Admin API not configured"
            )
        try:
            new_user_id = self.keycloak_admin.create_user({
                "email": user_data.email,
                "username": user_data.username,
                "enabled": True,
                "firstName": user_data.first_name,
                "lastName": user_data.last_name,
                "credentials": [{"value": user_data.password, "type": "password", "temporary": False}]
            }, exist_ok=False)

            if hasattr(user_data, 'role') and user_data.role:
                self.assign_user_role(new_user_id, user_data.role)

            return new_user_id
        except KeycloakError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User creation failed: {str(e)}"
            )

    def assign_user_role(self, user_id, role_name):
        try:
            role = self.keycloak_admin.get_realm_role(role_name)
            self.keycloak_admin.assign_realm_roles(user_id=user_id, roles=[role])
        except KeycloakError as e:
            print(f"Failed to assign role {role_name} to user {user_id}: {e}")
            # Optionally raise HTTP exception, or just log it


    def logout(self, refresh_token):
        try:
            self.keycloak_openid.logout(refresh_token)
        except KeycloakError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Logout failed: {str(e)}"
            )

keycloak_manager = KeycloakManager()
