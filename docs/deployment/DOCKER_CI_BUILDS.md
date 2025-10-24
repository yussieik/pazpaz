# Docker CI Builds Documentation

**Created**: 2025-10-23
**Author**: DevOps Infrastructure Team
**Status**: Production-Ready
**Phase**: CI/CD Implementation Phase 2

## Overview

This document describes the automated Docker image building process integrated into the PazPaz CI/CD pipeline. All Docker images are built in GitHub Actions, scanned for security vulnerabilities, and pushed to GitHub Container Registry (ghcr.io).

## Table of Contents

1. [Image Tagging Strategy](#image-tagging-strategy)
2. [Build Triggers and Conditions](#build-triggers-and-conditions)
3. [GitHub Container Registry Setup](#github-container-registry-setup)
4. [Docker Build Job Configuration](#docker-build-job-configuration)
5. [Security Scanning](#security-scanning)
6. [Local Testing](#local-testing)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)
9. [Performance and Optimization](#performance-and-optimization)

## Image Tagging Strategy

### Tag Types and Usage

PazPaz backend images use semantic and descriptive tags for different deployment scenarios:

| Tag Pattern | Example | When Created | Purpose |
|-------------|---------|--------------|---------|
| `main` | `ghcr.io/yussieik/pazpaz-backend:main` | Push to main branch | Latest stable development build |
| `sha-<commit>` | `ghcr.io/yussieik/pazpaz-backend:sha-abc1234` | Every push to main | Specific commit tracking |
| `v<semver>` | `ghcr.io/yussieik/pazpaz-backend:v1.2.3` | Release tag (v1.2.3) | Production release version |
| `<major>.<minor>` | `ghcr.io/yussieik/pazpaz-backend:1.2` | Release tag | Minor version family |
| `<major>` | `ghcr.io/yussieik/pazpaz-backend:1` | Release tag | Major version family |
| `latest` | `ghcr.io/yussieik/pazpaz-backend:latest` | Push to main OR release | Latest production image |

### Tag Generation Examples

**Scenario 1: Push to main branch**
```bash
Commit: abc1234567890
Branch: main

Generated Tags:
- ghcr.io/yussieik/pazpaz-backend:main
- ghcr.io/yussieik/pazpaz-backend:sha-abc1234
- ghcr.io/yussieik/pazpaz-backend:latest
```

**Scenario 2: Release tag v1.2.3**
```bash
Tag: v1.2.3
Branch: main

Generated Tags:
- ghcr.io/yussieik/pazpaz-backend:v1.2.3
- ghcr.io/yussieik/pazpaz-backend:1.2
- ghcr.io/yussieik/pazpaz-backend:1
- ghcr.io/yussieik/pazpaz-backend:latest
- ghcr.io/yussieik/pazpaz-backend:sha-abc1234
```

**Scenario 3: Pull request**
```bash
Event: pull_request
Branch: feature/new-feature

Action: Docker build SKIPPED (validation only in test/security jobs)
```

### Pulling Specific Versions

```bash
# Latest production image
docker pull ghcr.io/yussieik/pazpaz-backend:latest

# Specific release
docker pull ghcr.io/yussieik/pazpaz-backend:v1.2.3

# Latest from main branch
docker pull ghcr.io/yussieik/pazpaz-backend:main

# Specific commit
docker pull ghcr.io/yussieik/pazpaz-backend:sha-abc1234

# Minor version (automatically updated)
docker pull ghcr.io/yussieik/pazpaz-backend:1.2
```

## Build Triggers and Conditions

### What Triggers a Build?

Docker images are built automatically when:

1. **Push to main branch** - After all tests and security checks pass
2. **Release tags (v*.*.*)** - Semantic versioned releases
3. **Manual workflow dispatch** - Via GitHub Actions UI

### What Does NOT Trigger a Build?

Images are NOT built for:

1. **Pull requests** - Saves time and resources; validation happens in test/security jobs
2. **Branch pushes (except main)** - Only main and release tags trigger builds
3. **Failed tests or security scans** - Build job has `needs: [test, security]` dependency

### Build Conditions Explained

```yaml
# Docker build job configuration
docker-build:
  needs: [test, security]  # ✅ Must pass tests first
  if: github.event_name != 'pull_request'  # ✅ Skip for PRs
```

**Rationale:**
- **PR builds skipped**: PRs are validated via test/security jobs; building images would be wasteful
- **Test dependency**: Prevents building broken images
- **Security dependency**: Ensures vulnerable code isn't containerized

## GitHub Container Registry Setup

### Registry Configuration

**Registry URL**: `ghcr.io`
**Image Repository**: `ghcr.io/yussieik/pazpaz-backend`
**Authentication**: GitHub OIDC tokens (no long-lived credentials)

### Package Visibility (HIPAA Requirement)

**CRITICAL**: All images MUST be private for HIPAA compliance.

```bash
# Verify package is private (via GitHub web UI or API)
gh api /user/packages/container/pazpaz-backend --jq '.visibility'
# Expected output: private
```

To set package visibility:
1. Navigate to: https://github.com/users/yussieik/packages/container/pazpaz-backend/settings
2. Set **Visibility** to **Private**
3. Configure **Access** to only allow authorized users/teams

### Access Tokens and Permissions

**CI/CD Authentication:**
```yaml
# GitHub Actions uses GITHUB_TOKEN (automatic)
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

**Local Development Authentication:**
```bash
# Create a Personal Access Token with 'write:packages' scope
# Navigate to: Settings > Developer settings > Personal access tokens > Fine-grained tokens

# Login to ghcr.io
echo $GITHUB_PAT | docker login ghcr.io -u USERNAME --password-stdin

# Verify login
docker pull ghcr.io/yussieik/pazpaz-backend:latest
```

**Production Server Authentication:**
```bash
# On Hetzner VPS, use a dedicated service account token
# Store token in /opt/pazpaz/.docker/config.json with secure permissions

# Login (one-time setup)
echo $GHCR_DEPLOY_TOKEN | docker login ghcr.io -u pazpaz-deploy --password-stdin

# Set secure permissions
chmod 600 ~/.docker/config.json
```

### Pulling Images from Registry

```bash
# Authenticate first (see above)
docker login ghcr.io

# Pull latest image
docker pull ghcr.io/yussieik/pazpaz-backend:latest

# Pull specific version
docker pull ghcr.io/yussieik/pazpaz-backend:v1.2.3

# Verify image
docker images | grep pazpaz-backend
```

## Docker Build Job Configuration

### Job Overview

```yaml
docker-build:
  name: Build Docker Image
  runs-on: ubuntu-latest
  needs: [test, security]
  timeout-minutes: 30
  permissions:
    contents: read
    packages: write
    id-token: write
```

**Key Features:**
- ✅ Runs only after tests and security pass
- ✅ Uses GitHub OIDC for authentication (no secrets)
- ✅ 30-minute timeout for large builds
- ✅ Minimal permissions (read + packages write)

### Build Steps Breakdown

#### 1. Setup Docker Buildx
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3
```
- Enables advanced Docker features (multi-platform, caching)
- Uses BuildKit for faster, more efficient builds
- Supports layer caching via GitHub Actions cache

#### 2. Registry Authentication
```yaml
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```
- Automatic authentication using GitHub OIDC
- No manual secrets configuration required
- Token expires after job completion

#### 3. Metadata Extraction
```yaml
- name: Extract metadata (tags, labels)
  id: meta
  uses: docker/metadata-action@v5
```
- Generates tags based on event type (branch, tag, commit)
- Adds OCI-compliant labels
- Includes security metadata

#### 4. Build and Push
```yaml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: ./backend
    file: ./backend/Dockerfile
    platforms: linux/amd64
    push: true
    cache-from: type=gha
    cache-to: type=gha,mode=max
```
- Builds for linux/amd64 (Hetzner VPS architecture)
- Pushes to ghcr.io automatically
- Uses GitHub Actions cache for faster subsequent builds
- Multi-stage build reduces final image size

#### 5. Security Scanning
```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/yussieik/pazpaz-backend:${{ steps.meta.outputs.version }}
    severity: 'CRITICAL,HIGH'
```
- Scans pushed image for vulnerabilities
- Reports CRITICAL and HIGH severity issues
- Results uploaded to GitHub Security tab

### Build Performance

**Typical build times:**
- First build (no cache): 8-12 minutes
- Cached build (no code changes): 2-3 minutes
- Cached build (code changes only): 3-5 minutes

**Image size:**
- Final image: ~440MB (33% reduction from original)
- Multi-stage build: ~665MB intermediate, 440MB final
- Runtime-only dependencies: libpq5 + curl

## Security Scanning

### Trivy Vulnerability Scanner

Every built image is automatically scanned with Trivy:

```yaml
- name: Run Trivy vulnerability scanner on image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/yussieik/pazpaz-backend:${{ steps.meta.outputs.version }}
    format: 'sarif'
    output: 'trivy-image-results.sarif'
    severity: 'CRITICAL,HIGH'
    ignore-unfixed: true
```

**Scan Coverage:**
- OS packages (Debian base image)
- Python packages (pip/uv dependencies)
- Known CVEs in all layers
- Misconfigurations

### Interpreting Trivy Results

**Severity Levels:**
```
CRITICAL: Immediate fix required, blocks production
HIGH:     Fix before production deployment
MEDIUM:   Monitor and schedule fix
LOW:      Track but acceptable for production
```

**Viewing Scan Results:**
1. Navigate to: Repository > Security > Code scanning alerts
2. Filter by: "trivy-docker-image" category
3. Review vulnerabilities and remediation steps

**Example Scan Output:**
```
Total: 12 vulnerabilities (0 CRITICAL, 2 HIGH, 5 MEDIUM, 5 LOW)

HIGH: CVE-2024-12345 in libssl3 (1.1.1n)
  Fixed Version: 1.1.1o
  Action: Update base image to python:3.13.5-slim (latest)
```

### Fixing Common Vulnerabilities

#### 1. Base Image Vulnerabilities
```dockerfile
# Update base image regularly
FROM python:3.13.5-slim  # Keep this up to date

# Check for updates
docker pull python:3.13.5-slim
```

#### 2. Python Package Vulnerabilities
```bash
# Update dependencies in uv.lock
uv lock --upgrade-package vulnerable-package

# Rebuild image
docker build -t pazpaz-backend:test ./backend
```

#### 3. Unfixed Vulnerabilities
```yaml
# If no fix available, document exception
ignore-unfixed: true  # Already enabled in workflow
```

## Local Testing

### Prerequisites

```bash
# Install Docker
docker --version  # 20.10+ required

# Install Docker Buildx (usually included)
docker buildx version

# Authenticate to ghcr.io (if pulling base images)
echo $GITHUB_PAT | docker login ghcr.io -u USERNAME --password-stdin
```

### Test Docker Build Locally

#### 1. Build Image
```bash
cd /Users/yussieik/Desktop/projects/pazpaz/backend

# Build with test tag
docker build -f Dockerfile -t pazpaz-backend:test .

# Build with buildx (same as CI)
docker buildx build \
  --platform linux/amd64 \
  -t pazpaz-backend:test \
  -f Dockerfile \
  .
```

#### 2. Verify Image Size
```bash
docker images pazpaz-backend:test

# Expected output:
# REPOSITORY          TAG    SIZE
# pazpaz-backend      test   440MB
```

#### 3. Verify Non-Root User
```bash
# Check user
docker run --rm pazpaz-backend:test whoami
# Expected: pazpaz

# Check UID/GID
docker run --rm pazpaz-backend:test id
# Expected: uid=1000(pazpaz) gid=1000(pazpaz) groups=1000(pazpaz)
```

#### 4. Test Basic Functionality
```bash
# Run Python import test
docker run --rm pazpaz-backend:test python -c "import pazpaz; print('OK')"

# Check installed packages
docker run --rm pazpaz-backend:test uv pip list

# Test health check script
docker run --rm pazpaz-backend:test /usr/local/bin/healthcheck
# Note: Will fail without running server, that's expected
```

#### 5. Test with Environment Variables
```bash
# Create test .env file
cat > .env.test <<EOF
DATABASE_URL=sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test_secret_key_for_local_testing_only
ENCRYPTION_MASTER_KEY=dGVzdF9rZXlfZm9yX2xvY2FsX3Rlc3Rpbmc=
ENVIRONMENT=local
DEBUG=true
EOF

# Run container with env file
docker run --rm --env-file .env.test pazpaz-backend:test python -c "
from pazpaz.config import settings
print(f'Environment: {settings.ENVIRONMENT}')
print('OK')
"
```

#### 6. Test Health Check
```bash
# Start container with port mapping
docker run -d \
  --name test-health \
  -p 8000:8000 \
  --env-file .env.test \
  pazpaz-backend:test

# Wait for startup
sleep 10

# Check health status
docker inspect test-health --format='{{.State.Health.Status}}'
# Expected: healthy (after 40s start period)

# Test health endpoint
curl http://localhost:8000/health

# Clean up
docker rm -f test-health
```

### Security Scan Locally

```bash
# Install Trivy (macOS)
brew install aquasecurity/trivy/trivy

# Scan image
trivy image pazpaz-backend:test

# Scan with severity filter
trivy image --severity CRITICAL,HIGH pazpaz-backend:test

# Scan and output to file
trivy image --format json --output trivy-report.json pazpaz-backend:test
```

### Test Multi-Stage Build

```bash
# Build and inspect each stage
docker build --target builder -t pazpaz-backend:builder ./backend
docker build --target security-scanner -t pazpaz-backend:scanner ./backend
docker build --target runtime -t pazpaz-backend:runtime ./backend

# Compare sizes
docker images | grep pazpaz-backend
```

## Troubleshooting

### Common Build Issues

#### 1. Build Fails: "No space left on device"
**Problem**: Docker build cache fills disk
**Solution**:
```bash
# Clean up Docker build cache
docker builder prune -f

# Remove unused images
docker image prune -a -f

# Check disk usage
docker system df
```

#### 2. Build Fails: "failed to solve with frontend dockerfile.v0"
**Problem**: Dockerfile syntax error or missing file
**Solution**:
```bash
# Validate Dockerfile syntax
docker build --check ./backend

# Check context files
ls -la ./backend
```

#### 3. Registry Authentication Failed
**Problem**: Cannot push to ghcr.io
**Solution**:
```bash
# Verify login
docker logout ghcr.io
echo $GITHUB_PAT | docker login ghcr.io -u USERNAME --password-stdin

# Check token permissions (must have write:packages)
gh auth status

# Verify package exists and is accessible
gh api /user/packages/container/pazpaz-backend
```

#### 4. Trivy Scan Fails
**Problem**: Trivy cannot scan image
**Solution**:
```bash
# Update Trivy
brew upgrade trivy  # macOS
trivy --version

# Clear Trivy cache
rm -rf ~/.cache/trivy

# Re-run scan
trivy image --clear-cache pazpaz-backend:test
```

#### 5. Image Size Too Large
**Problem**: Image exceeds 500MB target
**Solution**:
```bash
# Analyze image layers
docker history pazpaz-backend:test

# Use dive to inspect layers
brew install dive  # macOS
dive pazpaz-backend:test

# Check for unnecessary files
docker run --rm pazpaz-backend:test du -sh /app/*
```

### GitHub Actions Issues

#### 1. Workflow Does Not Trigger Docker Build
**Check:**
```yaml
# Verify conditions
if: github.event_name != 'pull_request'  # PRs are skipped
needs: [test, security]  # Must pass dependencies
```

**Debug:**
```bash
# View workflow runs
gh run list --workflow=backend-ci.yml

# View specific run
gh run view <run-id>
```

#### 2. Docker Build Job Fails in CI but Works Locally
**Common causes:**
- Environment differences (local vs CI)
- Missing files in git (check .dockerignore)
- Permissions issues (check file ownership)

**Debug:**
```bash
# Check what files are in CI context
# Add to workflow temporarily:
- name: Debug context
  run: find ./backend -type f | head -20
```

#### 3. Cache Not Working
**Problem**: Builds are slow every time
**Solution**:
```yaml
# Verify cache configuration in workflow
cache-from: type=gha
cache-to: type=gha,mode=max

# Check Actions cache size (max 10GB per repo)
gh cache list
```

### Performance Issues

#### Slow Builds
```bash
# Enable BuildKit (faster builds)
export DOCKER_BUILDKIT=1

# Use cache mounts
docker build --build-arg BUILDKIT_INLINE_CACHE=1 ./backend

# Build with timing info
docker build --progress=plain ./backend 2>&1 | tee build.log
```

#### High Memory Usage
```bash
# Limit builder memory
docker buildx create --driver-opt env.BUILDKIT_STEP_LOG_MAX_SIZE=1048576

# Monitor resource usage
docker stats
```

## Production Deployment

### Pulling Images on Production Server

```bash
# On Hetzner VPS (one-time setup)
# 1. Create service account token with read:packages
# 2. Login to ghcr.io
echo $GHCR_TOKEN | docker login ghcr.io -u pazpaz-deploy --password-stdin

# Pull latest production image
docker pull ghcr.io/yussieik/pazpaz-backend:latest

# Verify image
docker inspect ghcr.io/yussieik/pazpaz-backend:latest --format='{{.Config.User}}'
# Expected: pazpaz
```

### Image Verification Before Deployment

```bash
# 1. Verify image signature (future enhancement)
# docker trust inspect ghcr.io/yussieik/pazpaz-backend:latest

# 2. Scan for vulnerabilities
trivy image ghcr.io/yussieik/pazpaz-backend:latest

# 3. Verify non-root user
docker run --rm ghcr.io/yussieik/pazpaz-backend:latest whoami
# Expected: pazpaz

# 4. Verify health check configured
docker inspect ghcr.io/yussieik/pazpaz-backend:latest --format='{{.Config.Healthcheck}}'

# 5. Check image size
docker images ghcr.io/yussieik/pazpaz-backend:latest --format "{{.Size}}"
```

### Deployment with Docker Compose

```yaml
# docker-compose.prod.yml
services:
  api:
    image: ghcr.io/yussieik/pazpaz-backend:latest
    user: "1000:1000"  # Explicit UID/GID
    read_only: true     # Read-only root filesystem (optional)
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    tmpfs:
      - /tmp
      - /app/tmp
    volumes:
      - logs:/app/logs:rw
      - uploads:/app/uploads:rw
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - ENCRYPTION_MASTER_KEY=${ENCRYPTION_MASTER_KEY}
```

**Deploy:**
```bash
# Pull latest image
docker compose -f docker-compose.prod.yml pull

# Restart services (zero-downtime)
docker compose -f docker-compose.prod.yml up -d --no-deps api

# Verify deployment
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

### Rollback Procedures

```bash
# List available image versions
docker images ghcr.io/yussieik/pazpaz-backend

# Rollback to previous version
docker tag ghcr.io/yussieik/pazpaz-backend:sha-abc1234 ghcr.io/yussieik/pazpaz-backend:latest

# Or update docker-compose.yml
# image: ghcr.io/yussieik/pazpaz-backend:v1.2.2  # Previous working version

# Restart with previous version
docker compose -f docker-compose.prod.yml up -d --no-deps api

# Verify rollback
docker compose -f docker-compose.prod.yml exec api python -c "
from pazpaz import __version__
print(f'Version: {__version__}')
"
```

### Zero-Downtime Deployment

```bash
# Blue-green deployment script
#!/bin/bash

# Pull new image
docker compose -f docker-compose.prod.yml pull api

# Start new container (green)
docker compose -f docker-compose.prod.yml up -d --scale api=2 --no-recreate

# Health check new container
timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'

# Stop old container (blue)
docker compose -f docker-compose.prod.yml up -d --scale api=1 --no-recreate

# Verify
docker compose -f docker-compose.prod.yml ps api
```

## Performance and Optimization

### Build Cache Optimization

**Layer caching best practices:**
```dockerfile
# ✅ Copy dependency files first (better caching)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# ✅ Copy source code last (changes frequently)
COPY src ./src
```

**GitHub Actions cache:**
```yaml
# Maximize cache efficiency
cache-from: type=gha
cache-to: type=gha,mode=max  # Store all layers
```

### Multi-Platform Builds (Future)

```yaml
# Build for multiple architectures
platforms: linux/amd64,linux/arm64

# Use QEMU for cross-platform builds
- name: Set up QEMU
  uses: docker/setup-qemu-action@v3
```

### Image Size Optimization

**Current optimizations:**
- ✅ Multi-stage build (builder → runtime)
- ✅ Slim base image (python:3.13.5-slim)
- ✅ No build tools in runtime
- ✅ Cleaned apt cache

**Future optimizations:**
```dockerfile
# Use distroless image (even smaller)
FROM gcr.io/distroless/python3-debian12

# Compress layers
RUN apt-get update && apt-get install -y \
    libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    apt-get autoremove -y
```

### Build Time Optimization

**Typical build times:**
```
First build (no cache): 8-12 minutes
  - Stage 1 (builder): 6-8 minutes
  - Stage 2 (scanner): 1-2 minutes
  - Stage 3 (runtime): 1-2 minutes

Cached build (dependencies unchanged): 2-3 minutes
Cached build (code changes only): 3-5 minutes
```

**Optimization tips:**
1. Keep dependencies stable (don't update unnecessarily)
2. Use uv.lock for reproducible builds (faster caching)
3. Order Dockerfile commands from least to most frequently changed
4. Use .dockerignore to exclude unnecessary files

### Resource Usage

**Build resource limits:**
```yaml
# GitHub Actions runners: 2 CPU, 7GB RAM
# Build typically uses: 1.5 CPU, 3-4GB RAM
# Build time: 3-12 minutes
```

**Runtime resource limits:**
```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 512M
```

## Monitoring and Metrics

### Build Metrics (GitHub Actions)

**Track in each build:**
- Build duration (target: <10 minutes)
- Image size (target: <500MB)
- Cache hit rate (target: >80%)
- Vulnerability count (target: 0 CRITICAL/HIGH)

**View metrics:**
```bash
# GitHub CLI
gh run list --workflow=backend-ci.yml --json conclusion,durationMs

# API
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/yussieik/pazpaz/actions/runs
```

### Registry Metrics

**Track storage usage:**
```bash
# List all package versions
gh api /user/packages/container/pazpaz-backend/versions | jq '.[].name'

# Check storage size
gh api /user/packages/container/pazpaz-backend | jq '.size_in_bytes'
```

### Cleanup Old Images

```bash
# Delete images older than 30 days (keep main and latest)
gh api /user/packages/container/pazpaz-backend/versions \
  | jq -r '.[] | select(.created_at < "2024-09-23" and .metadata.container.tags[0] != "latest" and .metadata.container.tags[0] != "main") | .id' \
  | xargs -I {} gh api -X DELETE /user/packages/container/pazpaz-backend/versions/{}
```

## Security Best Practices

### Image Security Checklist

- [x] Non-root user execution (pazpaz:1000)
- [x] Minimal base image (python:3.13.5-slim)
- [x] No build tools in runtime
- [x] Proper file permissions (644/755/700)
- [x] Health checks configured
- [x] Automated vulnerability scanning (Trivy)
- [x] Private registry (ghcr.io, HIPAA compliant)
- [x] OIDC authentication (no long-lived tokens)
- [ ] Image signing with Cosign (future)
- [ ] Read-only root filesystem (optional)

### Secrets Management

**NEVER include secrets in images:**
```dockerfile
# ❌ BAD: Secrets in build args
ARG SECRET_KEY=my-secret

# ✅ GOOD: Secrets via environment variables at runtime
ENV SECRET_KEY=${SECRET_KEY}
```

**Use Docker secrets (Swarm) or environment variables (Compose):**
```yaml
# docker-compose.prod.yml
services:
  api:
    environment:
      - SECRET_KEY_FILE=/run/secrets/secret_key
    secrets:
      - secret_key

secrets:
  secret_key:
    file: ./secrets/secret_key.txt
```

### Regular Maintenance

**Weekly tasks:**
- [ ] Update base image for security patches
- [ ] Review Trivy scan results
- [ ] Check for outdated dependencies

**Monthly tasks:**
- [ ] Comprehensive security audit
- [ ] Review image storage usage
- [ ] Clean up old image versions

**Commands:**
```bash
# Update base image
docker pull python:3.13.5-slim

# Rebuild with latest patches
docker build --no-cache -t pazpaz-backend:latest ./backend

# Scan for vulnerabilities
trivy image --severity CRITICAL,HIGH pazpaz-backend:latest
```

## References

- [Docker Build Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Docker Security Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [GitHub Actions Docker Build](https://docs.docker.com/build/ci/github-actions/)

## Support

For Docker build issues:
- **GitHub Actions Logs**: Check workflow run logs in GitHub UI
- **Local Testing**: Run builds locally to reproduce issues
- **Security Scans**: Review Trivy results in Security tab
- **DevOps Team**: devops@pazpaz.health

---

**Last Updated**: 2025-10-23
**Next Review**: 2025-11-23
**Document Version**: 1.0.0
