# Production Nginx Dockerfile for PazPaz
# Secure reverse proxy with minimal attack surface

FROM nginx:alpine

# Metadata
LABEL maintainer="PazPaz Team"
LABEL description="HIPAA-compliant reverse proxy for PazPaz"

# Install necessary packages and security updates
RUN apk update && \
    apk upgrade && \
    apk add --no-cache \
    curl \
    ca-certificates \
    tzdata && \
    rm -rf /var/cache/apk/*

# Set timezone (adjust as needed)
ENV TZ=America/New_York
RUN cp /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Remove default nginx configuration
RUN rm -rf /etc/nginx/conf.d/* && \
    rm -rf /usr/share/nginx/html/*

# Create necessary directories with proper permissions
RUN mkdir -p /var/log/nginx && \
    mkdir -p /var/cache/nginx && \
    mkdir -p /var/www/acme-challenge && \
    mkdir -p /usr/share/nginx/html/errors && \
    mkdir -p /etc/letsencrypt && \
    mkdir -p /var/run

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy custom error pages (now that directory exists with .gitkeep)
COPY error-pages /usr/share/nginx/html/errors/

# Create a health check file
RUN echo "healthy" > /usr/share/nginx/html/health

# Fix permissions for nginx user
RUN chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/www/acme-challenge && \
    chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /var/log/nginx && \
    chmod -R 755 /var/cache/nginx

# Expose HTTP and HTTPS ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Security: Don't run as root
# Note: The nginx:alpine image already runs nginx as the nginx user
# We ensure the master process runs as root (for binding to ports 80/443)
# but worker processes run as nginx user

# Use exec form to ensure proper signal handling
CMD ["nginx", "-g", "daemon off;"]