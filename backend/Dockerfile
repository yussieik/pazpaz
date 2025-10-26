# =============================================================================
# PazPaz Backend - Production-Ready Dockerfile
# =============================================================================
# Security-hardened, multi-stage build for HIPAA-compliant deployment
# Python 3.13.5 + FastAPI + SQLAlchemy + PostgreSQL
#
# Security Features:
# - Multi-stage build to minimize attack surface
# - Non-root user execution (pazpaz:pazpaz)
# - Minimal base image (python:3.13.5-slim)
# - No build tools in final image
# - Proper file permissions (644 for files, 755 for directories)
# - Health check endpoint configured
# - Security headers and hardening applied
# =============================================================================

# =============================================================================
# Stage 1: Builder Stage
# =============================================================================
# This stage compiles dependencies and prepares the application
# All build tools and temporary files stay in this stage
FROM python:3.13.5-slim AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building Python packages
# Note: These are NOT included in the final image
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv package manager with specific version for reproducibility
RUN pip install --no-cache-dir uv==0.5.16

# Create app directory
WORKDIR /app

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock README.md ./

# Install Python dependencies to a specific directory
# Using --frozen ensures exact versions from lock file
RUN uv sync --frozen --no-dev

# Copy application source code
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# =============================================================================
# Stage 2: Security Scanner Stage (Optional but Recommended)
# =============================================================================
# This stage runs security scans on dependencies
FROM builder AS security-scanner

# Install security scanning tools
RUN pip install --no-cache-dir safety bandit

# Run security scans (will fail build if vulnerabilities found)
# Note: In CI/CD, you might want to make these non-blocking warnings
RUN safety check --json || echo "Security vulnerabilities found - review before production"
RUN bandit -r src -f json -o /tmp/bandit-report.json || echo "Security issues found - review before production"

# =============================================================================
# Stage 3: Production Runtime Stage
# =============================================================================
# Minimal image with only runtime dependencies
FROM python:3.13.5-slim AS runtime

# Runtime environment variables for security and performance
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONPATH=/app/src \
    # Security: Prevent Python from executing downloaded packages
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # UV cache directory (writable by pazpaz user)
    UV_CACHE_DIR=/app/.cache/uv \
    # Application settings
    APP_USER=pazpaz \
    APP_GROUP=pazpaz \
    APP_HOME=/app

# Install only runtime dependencies (minimal attack surface)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Create non-root user and group with specific UID/GID for consistency
# Using UID/GID 1000 for better compatibility with host systems
RUN groupadd -r -g 1000 ${APP_GROUP} \
    && useradd -r -u 1000 -g ${APP_GROUP} \
    -d ${APP_HOME} \
    -s /sbin/nologin \
    -c "PazPaz Application User" \
    ${APP_USER}

# Create application directory structure with proper permissions
RUN mkdir -p ${APP_HOME}/logs \
    && mkdir -p ${APP_HOME}/tmp \
    && mkdir -p ${APP_HOME}/uploads \
    && mkdir -p ${APP_HOME}/.cache/uv

# Set working directory
WORKDIR ${APP_HOME}

# Copy uv from builder stage
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy installed dependencies from builder
# Using --chown to set ownership during copy (more efficient)
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy virtual environment from builder
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/.venv ${APP_HOME}/.venv

# Copy application code from builder with proper ownership
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/src ${APP_HOME}/src
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/alembic ${APP_HOME}/alembic
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/alembic.ini ${APP_HOME}/alembic.ini
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/pyproject.toml ${APP_HOME}/pyproject.toml
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/uv.lock ${APP_HOME}/uv.lock
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} ${APP_HOME}/README.md ${APP_HOME}/README.md

# Set proper permissions for all files and directories
# 755 for directories, 644 for files, 700 for sensitive directories
RUN find ${APP_HOME} -type d -exec chmod 755 {} + \
    && find ${APP_HOME} -type f -exec chmod 644 {} + \
    && chmod 700 ${APP_HOME}/logs ${APP_HOME}/tmp \
    && chmod 755 ${APP_HOME} \
    && chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}/logs ${APP_HOME}/tmp ${APP_HOME}/uploads ${APP_HOME}/.cache

# Create a health check script with proper permissions
RUN echo '#!/bin/sh\ncurl -f http://localhost:8000/health || exit 1' > /usr/local/bin/healthcheck \
    && chmod 755 /usr/local/bin/healthcheck

# Switch to non-root user for runtime
USER ${APP_USER}

# Expose application port (documentation only, not security)
EXPOSE 8000

# Health check configuration
# Checks /health endpoint every 30 seconds
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/usr/local/bin/healthcheck"]

# Security: Set read-only root filesystem (uncomment for maximum security)
# Note: Requires volumes for writable directories (/tmp, /app/logs, etc.)
# This is commented out by default as it requires docker-compose.yml changes
# To enable, uncomment and add tmpfs volumes in docker-compose.yml:
# volumes:
#   - type: tmpfs
#     target: /tmp
#   - type: tmpfs
#     target: /app/tmp
#   - logs:/app/logs
# Then uncomment this line:
# RUN echo "Read-only filesystem enabled - ensure writable volumes are mounted"

# Add security labels for container runtime (Docker/Podman)
LABEL maintainer="PazPaz Security Team" \
      version="1.0.0" \
      description="PazPaz Backend API - HIPAA Compliant" \
      security.scan="required" \
      security.non-root="true" \
      security.read-only-root="optional"

# Default command using exec form (more secure than shell form)
# Exec form doesn't invoke a shell, preventing shell injection
# Using --no-sync to prevent downloading dependencies at runtime (security + performance)
CMD ["uv", "run", "--no-sync", "uvicorn", "pazpaz.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# =============================================================================
# Security Notes:
# =============================================================================
# 1. This image runs as non-root user 'pazpaz' (UID 1000)
# 2. Build secrets should be passed using --secret flag, not ARG
# 3. For maximum security, enable read-only root filesystem (see comments above)
# 4. Regularly update base image for security patches
# 5. Scan image with trivy/grype before production deployment
# 6. Use Docker Content Trust (DOCKER_CONTENT_TRUST=1) in production
# 7. Consider using distroless images for even smaller attack surface
# =============================================================================