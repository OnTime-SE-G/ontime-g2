from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "OnTime Auth Service"
    
    # Database
    AUTH_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/auth_db"
    
    # Keycloak
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "ontime"
    KEYCLOAK_CLIENT_ID: str = "ontime-auth-service"
    KEYCLOAK_CLIENT_SECRET: str = "your-client-secret"
    KEYCLOAK_ADMIN_USERNAME: Optional[str] = "admin"
    KEYCLOAK_ADMIN_PASSWORD: Optional[str] = "admin"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
