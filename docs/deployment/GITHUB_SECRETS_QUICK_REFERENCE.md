# GitHub Secrets Quick Reference Card

## 🚀 Quick Setup Commands

```bash
# Run interactive setup wizard
./scripts/setup-github-secrets.sh

# Validate existing secrets
./scripts/setup-github-secrets.sh --validate

# Test SSH connection
./scripts/setup-github-secrets.sh --test-ssh

# Trigger validation workflow
gh workflow run validate-secrets.yml
```

## 📝 Manual Secret Addition

```bash
# Add single-line secret
gh secret set SECRET_NAME --body "value"

# Add from file
gh secret set SSH_PRIVATE_KEY < ~/.ssh/id_rsa

# Add from command output
gh secret set DB_PASSWORD --body "$(openssl rand -base64 32)"

# List all secrets
gh secret list

# Delete a secret
gh secret delete SECRET_NAME
```

## 🔑 Secret Generation Commands

```bash
# PHI Encryption Key (CRITICAL - Fernet)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Strong Password (32 chars)
openssl rand -base64 32 | tr -d '/+=' | cut -c1-32

# Hex Key (64 chars for SECRET_KEY)
openssl rand -hex 32

# Base64 Key (for JWT)
openssl rand -base64 32

# SSH Key (Ed25519)
ssh-keygen -t ed25519 -C "pazpaz-github" -f deploy_key -N ""

# Database URL
echo "postgresql+asyncpg://pazpaz:$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)@localhost:5432/pazpaz?ssl=require"
```

## ✅ Required Secrets Checklist

### Critical (HIPAA Required)
- [ ] `PROD_ENCRYPTION_MASTER_KEY` - PHI encryption
- [ ] `PROD_DATABASE_URL` - Database connection
- [ ] `PROD_POSTGRES_PASSWORD` - Database auth

### Deployment
- [ ] `SSH_PRIVATE_KEY` - Server access
- [ ] `SSH_HOST` - Server IP/domain
- [ ] `SSH_USER` - SSH username
- [ ] `SSH_PORT` - SSH port (optional, default: 22)

### Application
- [ ] `PROD_SECRET_KEY` - Session signing
- [ ] `PROD_JWT_SECRET_KEY` - JWT tokens
- [ ] `PROD_CSRF_SECRET_KEY` - CSRF protection
- [ ] `PROD_REDIS_PASSWORD` - Redis auth

### Optional Services
- [ ] `PROD_MINIO_ACCESS_KEY` - Object storage
- [ ] `PROD_MINIO_SECRET_KEY` - Object storage
- [ ] `PROD_RESEND_API_KEY` - Email service
- [ ] `PROD_SENTRY_DSN` - Error tracking

## 🔄 Rotation Commands

```bash
# Rotate database password
NEW_PASS=$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)
gh secret set PROD_POSTGRES_PASSWORD --body "$NEW_PASS"

# Rotate all application secrets
gh secret set PROD_SECRET_KEY --body "$(openssl rand -hex 32)"
gh secret set PROD_JWT_SECRET_KEY --body "$(openssl rand -base64 32)"
gh secret set PROD_CSRF_SECRET_KEY --body "$(openssl rand -base64 32)"

# Rotate SSH key
ssh-keygen -t ed25519 -C "pazpaz-new" -f new_key -N ""
gh secret set SSH_PRIVATE_KEY < new_key
shred -vfz new_key*
```

## 🆘 Emergency Procedures

```bash
# If secrets exposed
./scripts/emergency-rotate-all-secrets.sh

# Disable GitHub Actions
gh api repos/yussieik/pazpaz/actions -X PUT -F enabled=false

# Re-enable after rotation
gh api repos/yussieik/pazpaz/actions -X PUT -F enabled=true

# Audit recent runs
gh run list --limit 50
```

## 📊 Status Checks

```bash
# Check if secret exists
gh secret list | grep SECRET_NAME

# Validate all secrets
gh workflow run validate-secrets.yml

# View workflow status
gh run watch

# Check latest run
gh run view
```

## 🔗 Important URLs

- **GitHub Secrets**: https://github.com/yussieik/pazpaz/settings/secrets/actions
- **Actions**: https://github.com/yussieik/pazpaz/actions
- **Security Settings**: https://github.com/yussieik/pazpaz/settings/security_analysis

## ⏰ Rotation Schedule

| Secret Type | Rotation Period | Next Rotation |
|------------|-----------------|---------------|
| Encryption Keys | 90 days | Set reminder |
| Database Passwords | 90 days | Set reminder |
| JWT/Session Keys | 180 days | Set reminder |
| API Keys | 180 days | Set reminder |
| SSH Keys | Annual | Set reminder |

## 📚 Documentation

- [Full Setup Guide](./github-secrets-setup.md)
- [Secrets Management](./secrets-management.md)
- [CI/CD Implementation](./CI_CD_IMPLEMENTATION_PLAN.md)

---

**Remember**: Never commit secrets to git! Always use GitHub Secrets or environment variables.