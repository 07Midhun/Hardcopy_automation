# ==============================================================================
# AI Document Intelligence - Production Dockerfile
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for PyMuPDF, OpenCV, and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application codebase
COPY backend /app/backend
COPY frontend /app/frontend
COPY storage /app/storage
COPY .env.example /app/.env.example

# Create storage directories
RUN mkdir -p /app/storage/uploads /app/storage/temp /app/storage/exports

# Default port (Render injects $PORT dynamically)
EXPOSE 5000

# Launch Gunicorn WSGI server binding to $PORT (1 worker + 4 threads stays safely under 512MB Free Tier RAM)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 300 backend.wsgi:app"]

