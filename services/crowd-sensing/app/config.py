from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_port: int = 8007
    database_url: str = "postgresql://postgres:postgres@postgres:5432/crowd_sensing_db"
    kafka_broker_url: str = "broker:29092"
    kafka_reports_topic: str = "crowd-reports"
    kafka_consumer_group: str = "crowd-sensing-group"
    mlflow_tracking_uri: str = "http://mlflow:5000"
    route_service_url: str = "http://route-service:8002"

    class Config:
        env_prefix = "CROWD_"

settings = Settings()
