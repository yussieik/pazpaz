# Infrastructure CI/CD Documentation

## Overview

The Infrastructure CI workflow (`.github/workflows/infrastructure-ci.yml`) validates all infrastructure components including Docker Compose configurations, Nginx setup, shell scripts, and environment templates. This ensures infrastructure changes are validated before deployment.

## Workflow Triggers

The workflow runs automatically when:

1. **Push to main branch** affecting:
   - `docker-compose*.yml` files
   - `nginx/**` directory
   - `scripts/**` directory
   - `.env.production.example` or `.env.example`
   - The workflow file itself

2. **Pull requests to main** with the same path filters

3. **Manual dispatch** via GitHub Actions UI (with optional debug logging)

## Jobs

### 1. Validate Docker Compose

**Purpose**: Ensures Docker Compose files are syntactically correct and follow security best practices.

**Test Environment Setup**:
- Creates temporary `.env.production` file with test values for CI validation
- All environment variables use dummy/test values (never real secrets)
- Test file is automatically cleaned up after validation

**Validations**:
- ✅ Syntax validation for `docker-compose.yml` and `docker-compose.prod.yml`
- ✅ Required network isolation (frontend, backend, database networks)
- ✅ Health checks for critical services (api, db, redis, nginx)
- ✅ Port exposure verification (only nginx should expose ports in production)
- ✅ Database isolation (no exposed database ports in production)
- ✅ All required environment variables present and valid

**Key Security Checks**:
- Ensures database ports are NOT exposed to host
- Verifies proper network segmentation
- Validates health check configurations
- Confirms test environment file contains no real secrets

### 2. Validate Nginx Configuration

**Purpose**: Validates Nginx reverse proxy configuration for syntax and security.

**CI Environment Setup**:
- Creates `nginx` user if not present (required for `user nginx;` directive)
- Sets up test directories and dummy SSL certificates for validation
- Handles both `nginx.conf` and `nginx-ssl.conf` configurations

**Validations**:
- ✅ Nginx configuration syntax (`nginx -t`)
- ✅ Security headers (X-Frame-Options, HSTS, etc.)
- ✅ SSL/TLS configuration (TLS 1.2+ only)
- ✅ Rate limiting configuration
- ✅ Dockerfile best practices
- ✅ User directive validation (`user nginx;`)

**Security Features Checked**:
- Strong SSL protocols (TLS 1.2 and 1.3)
- Security headers implementation
- Rate limiting for DDoS protection
- Non-root user in Docker container
- Proper user permissions for nginx process

### 3. Validate Shell Scripts

**Purpose**: Ensures shell scripts are safe, syntactically correct, and follow best practices.

**Scripts Validated**:
```
scripts/
├── setup-ssl.sh            # SSL certificate setup
├── validate-env.sh         # Environment validation
├── test-production-local.sh # Local production testing
├── generate-secrets.sh     # Secret generation
├── validate-secrets.sh     # Secret validation
├── setup-github-secrets.sh # GitHub secrets setup
├── manage-branch-protection.sh # Branch protection
├── verify-docker-limits.sh # Docker resource limits
nginx/
└── enable-ssl.sh          # Enable SSL in Nginx
```

**Validations**:
- ✅ Bash syntax validation (`bash -n`)
- ✅ ShellCheck static analysis
- ✅ Executable permissions check
- ✅ Dangerous command detection (rm -rf /, etc.)

### 4. Validate Environment Templates

**Purpose**: Validates environment variable templates and ensures no secrets are exposed.

**Files Checked**:
- `.env.example` - Development template
- `.env.production.example` - Production template

**Validations**:
- ✅ Required variables present
- ✅ No exposed secrets in templates
- ✅ Validation script functionality test
- ✅ Suspicious pattern detection (API keys, tokens)

**Required Variables**:
- DATABASE_URL
- REDIS_URL
- SECRET_KEY
- ENCRYPTION_MASTER_KEY
- JWT_SECRET_KEY
- ENVIRONMENT
- DEBUG
- LOG_LEVEL

### 5. Docker Build Test (Optional)

**Purpose**: Tests Docker image builds and scans for vulnerabilities.

**When It Runs**: Only on main branch or manual dispatch to save resources.

**Actions**:
- 🔨 Builds Nginx Docker image
- 🔍 Scans image with Trivy for vulnerabilities
- 📊 Checks image size (warns if >100MB)
- ✅ Validates Docker Compose with built images

## Success Criteria

All jobs must pass for the workflow to succeed:

| Job | Required | Description |
|-----|----------|-------------|
| validate-docker-compose | ✅ Yes | Docker Compose syntax and security |
| validate-nginx | ✅ Yes | Nginx configuration validation |
| validate-scripts | ✅ Yes | Shell script safety and syntax |
| validate-environment | ✅ Yes | Environment template validation |
| docker-build-test | ⚠️ No | Optional image build and scan |

## Security Best Practices

1. **No Real Secrets**: CI uses only test/example values
2. **Validation Only**: Scripts are validated but not executed
3. **Network Isolation**: Verifies production network segmentation
4. **Port Security**: Ensures only nginx exposes ports
5. **SSL/TLS**: Validates strong cryptographic protocols

## Troubleshooting

### Common Issues

**Docker Compose Validation Fails with "env file not found"**:
- **Issue**: Missing `.env.production` file in CI environment
- **Solution**: The workflow now automatically creates a test `.env.production` with dummy values
- **Local Test**:
```bash
# Create test environment file locally
cp .env.production.example .env.production
# Edit with test values, then validate
docker-compose -f docker-compose.prod.yml config
```

**Nginx Configuration Error "getpwnam('nginx') failed"**:
- **Issue**: Ubuntu CI runners don't have nginx user by default
- **Solution**: The workflow now creates the nginx user before validation
- **Local Test**:
```bash
# Test nginx config locally (may need sudo)
sudo useradd -r -s /bin/false nginx  # Create user if missing
nginx -t -c /path/to/nginx.conf
```

**ShellCheck Warnings**:
```bash
# Run shellcheck locally
shellcheck scripts/*.sh
# Exclude specific warnings if acceptable
shellcheck -e SC2086,SC2181 scripts/*.sh
```

**Environment Validation Fails**:
```bash
# Test validation script
./scripts/validate-env.sh .env.production.example
```

**Missing Environment Variables**:
- **Issue**: Docker Compose references variables not in `.env.production`
- **Solution**: Add all required variables to test environment file in CI
- **Check Required Variables**:
```bash
# Find all variable references in docker-compose
grep -oE '\$\{[A-Z_]+[^}]*\}' docker-compose.prod.yml | sort -u
```

### Manual Workflow Trigger

To manually run the workflow:

1. Go to Actions tab in GitHub
2. Select "Infrastructure CI"
3. Click "Run workflow"
4. Optionally enable debug logging
5. Click "Run workflow" button

## Workflow Outputs

Each job generates a summary in GitHub Actions including:

- **Docker Compose**: Network isolation status, health check verification
- **Nginx**: Security headers status, SSL configuration
- **Scripts**: Syntax validation results, ShellCheck findings
- **Environment**: Required variables check, secret detection
- **Docker Build**: Image size, vulnerability scan results

## Integration with Other Workflows

This workflow complements:
- `backend-ci.yml` - Backend code validation
- `frontend-ci.yml` - Frontend code validation
- Future `deployment.yml` - Production deployment pipeline

## Monitoring and Alerts

Workflow failures trigger:
- ❌ GitHub status checks on PRs
- 📧 Email notifications to repository watchers
- 🔔 GitHub Actions notifications

## Performance

- **Timeout**: Each job has 10-20 minute timeout
- **Parallelization**: Jobs run in parallel for speed
- **Caching**: Docker layer caching for build jobs
- **Resource Usage**: Minimal (no database/Redis needed)

## Maintenance

### Adding New Scripts

When adding new shell scripts:
1. Add to the `scripts` array in validate-scripts job
2. Ensure script has proper shebang (`#!/bin/bash`)
3. Make script executable (`chmod +x`)
4. Test with `shellcheck` locally first

### Adding New Docker Services

When adding services to docker-compose:
1. Add health check configuration
2. Configure proper network isolation
3. Avoid exposing unnecessary ports
4. Update this documentation

### Updating Nginx Configuration

When modifying Nginx:
1. Test locally with `nginx -t`
2. Ensure security headers remain
3. Maintain SSL/TLS best practices
4. Update rate limiting if needed

## Recent Updates

### October 24, 2024
- ✅ **Fixed CI Validation Errors**:
  - Added automatic creation of test `.env.production` file with all required variables
  - Fixed nginx user creation for Ubuntu CI runners
  - Improved nginx-ssl.conf validation to handle expected warnings
  - Added cleanup steps for test environment files
  - Enhanced validation summaries with clearer pass/fail indicators

## Future Enhancements

Planned improvements:
- [ ] Add OWASP dependency check for scripts
- [ ] Implement configuration drift detection
- [ ] Add infrastructure cost estimation
- [ ] Integrate with security scanning platform
- [ ] Add performance benchmarking for Nginx
- [ ] Implement automated rollback testing

---

**Last Updated:** October 24, 2024
**Status:** Production-Ready