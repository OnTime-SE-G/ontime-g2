FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set PYTHONPATH to ensure 'app' package is discoverable
ENV PYTHONPATH=/app

# Copy requirements first to leverage Docker layer caching
# Assuming build context is the repo root
COPY services/api-gateway/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared schemas into /app/schemas
COPY schemas /app/schemas

# Copy the service code into /app
COPY services/api-gateway /app

# Run Uvicorn in development mode
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
