# app/config.py
# Shared configuration for API Gateway

import os
from dotenv import load_dotenv
load_dotenv()

ROUTE_SERVICE_URL = os.getenv("ROUTE_SERVICE_URL", "http://route-service:8002")
FLEET_SERVICE_URL = os.getenv("FLEET_SERVICE_URL", "http://fleet-management-service:8003")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")