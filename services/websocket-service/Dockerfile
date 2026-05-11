FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run Uvicorn with runtime-configurable port
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${WEBSOCKET_SERVICE_PORT:-8004}"]
