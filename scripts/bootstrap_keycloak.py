import sys
import os
import logging

# Add current directory to path to allow imports if run from root
sys.path.append(os.path.join(os.getcwd(), "services", "api-gateway"))

from app.services.keycloak_client import keycloak_client
from keycloak.exceptions import KeycloakError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def bootstrap():
    admin = keycloak_client.keycloak_admin
    if not admin:
        logger.error("Keycloak Admin Client not initialized. Check your environment variables.")
        return

    realm = "ontime"
    
    # 1. Create Realm if it doesn't exist
    try:
        admin.get_realm(realm)
        logger.info(f"Realm '{realm}' already exists.")
    except KeycloakError:
        logger.info(f"Creating realm '{realm}'...")
        admin.create_realm({"realm": realm, "enabled": True})

    # 2. Switch to the realm context for subsequent operations
    admin.realm_name = realm
    
    # 3. Create Roles
    roles = ["ADMIN", "DRIVER"]
    for role in roles:
        try:
            admin.get_realm_role(role)
            logger.info(f"Role '{role}' already exists.")
        except KeycloakError:
            logger.info(f"Creating role '{role}'...")
            admin.create_realm_role({"name": role})

    # 4. Create API Client for Kong/Gateway validation
    client_id = "ontime-api"
    try:
        admin.get_client_id(client_id)
        logger.info(f"Client '{client_id}' already exists.")
    except Exception:
        logger.info(f"Creating client '{client_id}'...")
        admin.create_client({
            "clientId": client_id,
            "publicClient": False,
            "secret": "secret",  # Matches default in config.py
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": True,
            "authorizationServicesEnabled": True,
            "redirectUris": ["*"]
        })

    logger.info("Keycloak bootstrap complete!")

if __name__ == "__main__":
    bootstrap()
