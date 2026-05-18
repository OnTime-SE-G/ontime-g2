FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and XGBoost if needed
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY services/crowd-sensing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/crowd-sensing /app

COPY ml /opt/ontime/ml
ENV PYTHONPATH=/app:/opt/ontime

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
