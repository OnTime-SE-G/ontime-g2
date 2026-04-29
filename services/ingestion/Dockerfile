FROM python:3.11-slim

WORKDIR /app

# Copy and install service-specific dependencies
COPY services/ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared schemas (used for GPS message validation)
COPY schemas/ /app/schemas/

# Copy service code
COPY services/ingestion/ /app/

# Health endpoint on port 8001
EXPOSE 8001

CMD ["python", "main.py"]
