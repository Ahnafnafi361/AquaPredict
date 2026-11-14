# =====================================================================
# AquaPredict Milestone 10 (M10) — Production Container Configuration
# =====================================================================

FROM python:3.12-slim AS base

# System metadata & environment
LABEL maintainer="AquaPredict Team" \
      project="AquaPredict" \
      version="0.10.0" \
      pilot="Downtown Houston / Buffalo Bayou"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Install essential runtime system dependencies (for rasterio/gdal if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and public assets
COPY serve.py .
COPY public/ ./public/
COPY scripts/ ./scripts/
COPY ml/ ./ml/
COPY i18n/ ./i18n/

# Create non-root system user for security hardening
RUN useradd -u 1001 -m -s /bin/bash appuser && \
    chown -R appuser:appuser ${APP_HOME}

USER appuser

EXPOSE 8000

# Docker Healthcheck targeting M10 /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

# Production startup command
CMD ["python", "serve.py", "8000"]
