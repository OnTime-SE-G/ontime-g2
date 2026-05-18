FROM python:3.11-slim

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies (for psycopg2 and ML packages)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/eta-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared schemas into /app/schemas (if needed for standardization)
COPY schemas /app/schemas

# Copy the service code into /app
COPY services/eta-service /app

# Shared ML package (MLflow loader, contracts) — required by models/ml_eta_xgb.py
COPY ml /opt/ontime/ml
ENV PYTHONPATH=/app:/opt/ontime

# Expose port
EXPOSE 8005

# Start FastAPI with runtime-configurable port
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${ETA_SERVICE_PORT:-8005}"]
