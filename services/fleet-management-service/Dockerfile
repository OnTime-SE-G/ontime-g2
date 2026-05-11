FROM python:3.11-slim

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies (for psycopg2)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/fleet-management-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared schemas into /app/schemas
COPY schemas /app/schemas

# Copy the service code into /app
# This ensures that 'app' is a top-level module inside /app
COPY services/fleet-management-service /app

# Expose port
EXPOSE 8003

# Start FastAPI with runtime-configurable port
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${FLEET_SERVICE_PORT:-8003}"]
