import logging
from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import KeycloakError
from fastapi import HTTPException, status
from ..config import settings

logger = logging.getLogger(__name__)

class KeycloakClient:
    def __init__(self):
        # We only strictly need Admin, but OpenID can be useful for token validation if needed
        self.keycloak_admin = None
        if settings.keycloak_admin_username and settings.keycloak_admin_password:
            try:
                self.keycloak_admin = KeycloakAdmin(
                    server_url=settings.keycloak_base_url,
                    username=settings.keycloak_admin_username,
                    password=settings.keycloak_admin_password,
                    realm_name=settings.keycloak_realm,
                    user_realm_name="master",  # Admin user is usually in master realm
                    verify=True
                )
                logger.info("Keycloak Admin Client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Keycloak Admin: {e}")

    def create_user(self, username: str, password: str, first_name: str, last_name: str, role: str = "DRIVER") -> str:
        if not self.keycloak_admin:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Keycloak Admin API not configured"
            )
        try:
            # Create the user
            new_user_id = self.keycloak_admin.create_user({
                "email": f"{username}@on-time.live",
                "username": username,
                "enabled": True,
                "emailVerified": True,
                "firstName": first_name,
                "lastName": last_name,
                "credentials": [{"value": password, "type": "password", "temporary": False}]
            }, exist_ok=False)
            
            # Assign the role
            self._assign_role(new_user_id, role)
            
            return new_user_id
        except KeycloakError as e:
            logger.error(f"Failed to create Keycloak user: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User creation failed: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            )

    def disable_user(self, auth_user_id: str):
        if not self.keycloak_admin:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Keycloak Admin API not configured"
            )
        try:
            self.keycloak_admin.update_user(user_id=auth_user_id, payload={"enabled": False})
        except KeycloakError as e:
            logger.error(f"Failed to disable Keycloak user {auth_user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User disable failed: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            )

    def _assign_role(self, user_id: str, role_name: str):
        try:
            # Get the role ID
            role = self.keycloak_admin.get_realm_role(role_name)
            # Assign it to the user
            self.keycloak_admin.assign_realm_roles(user_id=user_id, roles=[role])
        except KeycloakError as e:
            # Cleanup user if role assignment fails
            try:
                self.keycloak_admin.delete_user(user_id)
            except Exception:
                pass
            logger.error(f"Failed to assign role {role_name} to user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to assign role: {e.error_message if hasattr(e, 'error_message') else str(e)}"
            )

keycloak_client = KeycloakClient()
