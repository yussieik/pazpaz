# Multi-stage build for PazPaz Backend
# Base image with Python 3.13.5
FROM python:3.13.5-slim AS base

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv==0.5.16

# Set working directory
WORKDIR /app

# Copy dependency files and README (required by hatchling build)
COPY pyproject.toml uv.lock README.md ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy application source code
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app/src

# Expose port for FastAPI application (not needed for worker, but good to have)
EXPOSE 8000

# Default command (can be overridden in docker-compose.yml)
CMD ["uv", "run", "uvicorn", "pazpaz.main:app", "--host", "0.0.0.0", "--port", "8000"]
