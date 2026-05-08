from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "OnTime Auth Service"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/auth_db"
    
    # Keycloak
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "transit-system"
    KEYCLOAK_CLIENT_ID: str = "scheduler-web"
    KEYCLOAK_CLIENT_SECRET: str = "jQNjTtDUOhmLlprc9QCKAYMeJxuu6OMs"
    KEYCLOAK_ADMIN_USERNAME: Optional[str] = "admin"
    KEYCLOAK_ADMIN_PASSWORD: Optional[str] = "admin"
    
    # Kafka
    KAFKA_BROKER_URL: str = "localhost:9092"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
