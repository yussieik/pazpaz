# PazPaz Secrets Quick Reference Card

## 🚀 Quick Start

```bash
# Generate all secrets
./scripts/generate-secrets.sh

# Validate secrets configuration
./scripts/validate-secrets.sh .env.production

# Check GitHub secrets
./scripts/validate-secrets.sh --github
```

## 🔑 Most Common Secret Generation Commands

### Critical - PHI Encryption Key (NEVER LOSE THIS!)
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Database Password (32 chars)
```bash
openssl rand -base64 48 | tr -d '/+=' | cut -c1-32
```

### Application Secret Key (64 hex chars)
```bash
openssl rand -hex 32
```

### JWT/CSRF Keys (base64)
```bash
openssl rand -base64 32
```

### Complete DATABASE_URL
```bash
PASSWORD=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-32)
echo "postgresql+asyncpg://pazpaz:${PASSWORD}@db:5432/pazpaz?ssl=require"
```

## 📦 GitHub Actions Setup

### Add Secret via Web UI
1. Go to: `Settings → Secrets and variables → Actions`
2. Click: `New repository secret`
3. Add name and value
4. Click: `Add secret`

### Add Secret via CLI
```bash
# Single line secret
gh secret set SECRET_NAME --body "secret-value"

# From file
gh secret set SSH_PRIVATE_KEY < ~/.ssh/pazpaz-deploy

# Interactive prompt
gh secret set ENCRYPTION_MASTER_KEY

# List all secrets
gh secret list
```

## 🔄 Secret Rotation

### Rotate Encryption Key (CRITICAL - FOLLOW EXACTLY)
```bash
# 1. Generate new key
NEW_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name pazpaz/encryption-key-v2 \
  --secret-string "$NEW_KEY"

# 3. Update GitHub Secret
gh secret set ENCRYPTION_MASTER_KEY --body "$NEW_KEY"

# 4. Deploy with dual-key support
# 5. Run re-encryption script
# 6. Remove old key after verification
```

### Rotate Database Password
```bash
# 1. Generate new password
NEW_PASS=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-32)

# 2. Update PostgreSQL
psql -U postgres -c "ALTER USER pazpaz PASSWORD '$NEW_PASS';"

# 3. Update GitHub Secret
gh secret set POSTGRES_PASSWORD --body "$NEW_PASS"

# 4. Restart application
docker-compose restart api
```

## 🚨 Emergency Procedures

### If Encryption Key Exposed
```bash
# IMMEDIATE ACTION REQUIRED!
# 1. Generate emergency key
EMERGENCY_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Update immediately
gh secret set ENCRYPTION_MASTER_KEY --body "$EMERGENCY_KEY"

# 3. Deploy and start re-encryption
# 4. Assess HIPAA breach notification requirements
```

### If GitHub Secrets Exposed
```bash
# Rotate ALL secrets immediately
./scripts/generate-secrets.sh > new-secrets.txt
# Manually update each secret in GitHub
# Clear shell history
history -c && rm ~/.bash_history
```

## 🧪 Testing & Validation

### Test Encryption Key
```bash
python3 -c "
from cryptography.fernet import Fernet
key = b'YOUR_KEY_HERE'
f = Fernet(key)
test = f.encrypt(b'test')
assert f.decrypt(test) == b'test'
print('✅ Key is valid')
"
```

### Test Database Connection
```bash
psql "$DATABASE_URL" -c "SELECT 1;"
```

### Test Redis Connection
```bash
redis-cli -u "$REDIS_URL" ping
```

## 📋 Complete Secret Checklist

### Required for Production
- [ ] `ENCRYPTION_MASTER_KEY` - 44 chars Fernet key
- [ ] `DATABASE_URL` - PostgreSQL connection with SSL
- [ ] `POSTGRES_PASSWORD` - 32+ chars
- [ ] `SECRET_KEY` - 64 hex chars
- [ ] `JWT_SECRET_KEY` - Base64 32 bytes
- [ ] `REDIS_PASSWORD` - 32+ chars
- [ ] `MINIO_ACCESS_KEY` - 16+ chars
- [ ] `MINIO_SECRET_KEY` - 32+ chars

### Required for CI/CD
- [ ] `SSH_HOST` - Server IP/hostname
- [ ] `SSH_USER` - Deployment user
- [ ] `SSH_PRIVATE_KEY` - Ed25519 or RSA key

### Optional Services
- [ ] `RESEND_API_KEY` - Email service
- [ ] `SENTRY_DSN` - Error tracking
- [ ] `DOCKER_REGISTRY_TOKEN` - Container registry

## 🛡️ Security Best Practices

### DO ✅
- Generate secrets with proper entropy
- Store in password manager immediately
- Use different secrets per environment
- Rotate every 90 days (critical) or 180 days (standard)
- Clear shell history after generating
- Use GitHub Secrets for CI/CD
- Use AWS Secrets Manager for production

### DON'T ❌
- Commit secrets to git (even in private repos)
- Share secrets via email or Slack
- Use weak/guessable passwords
- Reuse secrets across environments
- Log secret values
- Store secrets in plain text files
- Use default/example values in production

## 📞 Emergency Contacts

- **Security Issues**: security@pazpaz.com
- **HIPAA Compliance**: compliance@pazpaz.com
- **DevOps On-Call**: [Phone number]
- **AWS Support**: https://console.aws.amazon.com/support

## 📚 Full Documentation

- [Complete Secrets Management Guide](./secrets-management.md)
- [CI/CD Implementation Plan](./CI_CD_IMPLEMENTATION_PLAN.md)
- [Key Management Procedures](/docs/security/KEY_MANAGEMENT.md)
- [AWS Secrets Manager Setup](./AWS_SECRETS_MANAGER.md)