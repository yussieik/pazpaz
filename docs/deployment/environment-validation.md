# Environment Variable Validation Guide

## Overview

The `scripts/validate-env.sh` script ensures that your production environment configuration meets all security and operational requirements before deployment. This is a critical step in maintaining HIPAA compliance and preventing configuration errors in production.

## Quick Start

1. **Create your production environment file:**
   ```bash
   cp .env.production.example .env.production
   ```

2. **Fill in all required values** in `.env.production`

3. **Run the validation script:**
   ```bash
   ./scripts/validate-env.sh
   ```

## What the Script Validates

### 1. Required Variables
- Checks that all required environment variables are present
- Ensures no variables have empty values
- Lists any missing variables with clear descriptions

### 2. Secret Strength
- **Passwords**: Minimum length requirements (20+ chars for database/Redis)
- **API Keys**: Appropriate length for each service
- **Encryption Keys**: Valid base64 encoding with 32+ byte decoded length
- **Weak Patterns**: Detects common weak passwords like "password", "123456", "admin"

### 3. Example/Placeholder Values
- Detects placeholder text like "CHANGE_ME", "your-", "example.com"
- Prevents accidental deployment with template values
- Lists all variables containing example text

### 4. Format Validation
- **URLs**: Valid URL format, HTTPS required for production
- **Emails**: Valid email address format
- **Domains**: Proper domain format without spaces or invalid characters
- **Ports**: Numeric values only
- **Base64**: Valid encoding for encryption keys

### 5. Security Checks
- Encryption keys are unique (not reused)
- Passwords are unique across services
- SSL/TLS enabled for database and SMTP
- HTTPS used for all production URLs

## Exit Codes

| Code | Meaning | Action Required |
|------|---------|-----------------|
| 0 | All validations passed | Safe to deploy |
| 1 | Missing variables or format errors | Add missing variables or fix formats |
| 2 | Weak secrets detected | Generate stronger secrets |
| 3 | Example/placeholder values found | Replace with real values |

## Common Issues and Solutions

### Missing Variables
**Error:** `POSTGRES_PASSWORD (not found)`

**Solution:** Add the missing variable to `.env.production`:
```bash
POSTGRES_PASSWORD=$(openssl rand -base64 32)
```

### Weak Secrets
**Error:** `POSTGRES_PASSWORD is only 10 characters (minimum: 20)`

**Solution:** Generate a stronger password:
```bash
openssl rand -base64 32
```

### Invalid Base64
**Error:** `ENCRYPTION_MASTER_KEY is not valid base64`

**Solution:** Generate proper base64-encoded key:
```bash
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Example Values
**Error:** `REDIS_PASSWORD contains 'CHANGE_ME'`

**Solution:** Replace with actual value using generation command from `.env.production.example`

### Format Errors
**Error:** `FRONTEND_URL is not a valid URL`

**Solution:** Use proper URL format with protocol:
```
FRONTEND_URL=https://app.pazpaz.com
```

## Generating Secure Values

### Passwords (20+ characters)
```bash
# For PostgreSQL, Redis, etc.
openssl rand -base64 32
```

### API Keys
```bash
# For S3/MinIO access key (20 chars)
openssl rand -base64 16 | tr -d '/+=' | cut -c1-20

# For S3/MinIO secret key (40 chars)
openssl rand -base64 32 | tr -d '/+=' | cut -c1-40
```

### Encryption Keys (base64, 32 bytes)
```bash
# For MINIO_ENCRYPTION_KEY, ENCRYPTION_MASTER_KEY
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Application Secrets
```bash
# For SECRET_KEY (64+ chars)
openssl rand -base64 64

# For JWT_SECRET_KEY (32+ chars)
openssl rand -base64 32
```

## Best Practices

1. **Never commit `.env.production`** to version control
2. **Use different secrets** for each environment (dev, staging, prod)
3. **Rotate secrets regularly** (every 90 days for production)
4. **Store backup copies** of production secrets in a secure password manager
5. **Run validation** before every deployment
6. **Document any custom variables** added beyond the template

## Integration with CI/CD

Add this validation step to your deployment pipeline:

```yaml
# GitHub Actions example
- name: Validate Production Environment
  run: |
    cp .env.production.example .env.production
    # Inject secrets from GitHub Secrets
    echo "POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}" >> .env.production
    # ... add other secrets ...
    ./scripts/validate-env.sh
```

## Troubleshooting

### Script Not Found
```bash
chmod +x scripts/validate-env.sh
```

### Syntax Errors
```bash
# Check script syntax
bash -n scripts/validate-env.sh
```

### Debug Output
```bash
# Run with debug output
bash -x scripts/validate-env.sh
```

## Security Considerations

- The script **never logs secret values**, only validation results
- Safe to run in CI/CD pipelines
- Exit codes allow automated decision making
- All checks are read-only (no modifications to files)

## Related Documentation

- [Production Deployment Guide](./production-deployment.md)
- [Secrets Management](./secrets-management.md)
- [Docker Compose Production](./docker-compose-production.md)