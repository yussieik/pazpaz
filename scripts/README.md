# PazPaz Scripts

This directory contains utility scripts for development, deployment, and operations.

## Available Scripts

### 🔐 Secret Management

#### `validate-secrets.py`
**Purpose**: Validate GitHub Secrets configuration for production deployment

```bash
# Basic validation
python3 validate-secrets.py

# Validate specific environment
python3 validate-secrets.py --env production

# Verbose output
python3 validate-secrets.py --verbose

# From file (testing only)
python3 validate-secrets.py --from-file .env.test
```

**Features**:
- Validates encryption key format (Fernet)
- Checks secret strength and complexity
- Detects weak/test values
- Environment-specific validation
- Color-coded output
- Exit codes for CI/CD integration

#### `generate-secrets.sh`
**Purpose**: Generate secure random values for secrets

```bash
# Generate all required secrets
./generate-secrets.sh

# Generate specific secret type
./generate-secrets.sh --type encryption
```

#### `setup-github-secrets.sh`
**Purpose**: Configure GitHub Secrets via GitHub CLI

```bash
# Interactive setup
./setup-github-secrets.sh

# Non-interactive with file
./setup-github-secrets.sh --from-file secrets.env
```

#### `validate-secrets.sh`
**Purpose**: Shell-based secret validation (legacy)

```bash
# Basic validation
./validate-secrets.sh
```

### 🐳 Docker & Infrastructure

#### `verify-docker-limits.sh`
**Purpose**: Verify Docker resource limits meet production requirements

```bash
# Check Docker daemon limits
./verify-docker-limits.sh

# Verbose output
./verify-docker-limits.sh --verbose
```

## Security Notes

⚠️ **IMPORTANT SECURITY GUIDELINES**:

1. **Never commit actual secret values** to the repository
2. **Use `.gitignore`** to exclude any generated secret files
3. **Run validation scripts** before deployment
4. **Rotate secrets regularly** (every 90 days for production)
5. **Use environment-specific prefixes** (PROD_, CI_, DEV_)
6. **Test with dummy values** in development

## Exit Codes

Scripts follow standard Unix exit code conventions:

- `0` - Success
- `1` - General failure or critical error
- `2` - Invalid arguments or configuration

## Integration with CI/CD

These scripts are designed to work with GitHub Actions:

```yaml
# Example: Validate secrets in CI
- name: Validate Secrets
  run: |
    python3 scripts/validate-secrets.py --env ci
```

## Adding New Scripts

When adding new scripts:

1. Make executable: `chmod +x script_name.sh`
2. Add shebang: `#!/usr/bin/env bash` or `#!/usr/bin/env python3`
3. Include help text: `--help` flag support
4. Document in this README
5. Follow naming convention: `action-target.ext`
6. Include error handling and validation
7. Use exit codes appropriately

## Related Documentation

- [GitHub Secrets Configuration](../docs/deployment/GITHUB_SECRETS.md)
- [Docker Security](../docs/deployment/DOCKER_SECURITY.md)
- [Production Deployment](../docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md)

---

**Last Updated**: 2024-10-23
**Maintained By**: DevOps Team