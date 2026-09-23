FROM python:3.11-slim

# Avoid buffering stdout/stderr and prevent .pyc generation
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies needed for compiling or running network tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source, runbooks, scripts
COPY app/ app/
COPY runbooks/ runbooks/
COPY scripts/ scripts/

# Expose default port
EXPOSE 8000

# Execute FastAPI via Uvicorn honoring dynamic $PORT environment variable provided by Render or container runners
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
