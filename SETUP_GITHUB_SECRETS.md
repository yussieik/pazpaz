# Setup GitHub Secrets - Step by Step

I cannot directly set GitHub secrets (requires repository admin access), but here's exactly how to do it:

---

## 🚀 **Quick Setup (Choose One Method)**

### Method 1: Automatic (GitHub CLI - Recommended) ⚡

**Step 1: Install GitHub CLI (if not already installed)**

```bash
# macOS
brew install gh

# Or download from: https://cli.github.com
```

**Step 2: Authenticate**

```bash
gh auth login
# Follow the prompts to authenticate with GitHub
```

**Step 3: Run the helper script**

```bash
cd /Users/yussieik/Desktop/projects/pazpaz
./scripts/generate-github-secrets.sh
```

This script will:
- ✅ Generate secure random values for CI secrets
- ✅ Detect your existing SSH keys
- ✅ Prompt for production server details
- ✅ Optionally set secrets automatically via GitHub CLI

---

### Method 2: Manual (Web UI) 🌐

**Step 1: Go to GitHub Repository Settings**

Open: https://github.com/yussieik/pazpaz/settings/secrets/actions

**Step 2: Click "New repository secret"**

**Step 3: Add these secrets one by one:**

#### Required Secrets

1. **PRODUCTION_SSH_HOST**
   - Click "New repository secret"
   - Name: `PRODUCTION_SSH_HOST`
   - Value: `5.161.241.81` (your production server IP)
   - Click "Add secret"

2. **PRODUCTION_SSH_USER**
   - Name: `PRODUCTION_SSH_USER`
   - Value: `root` (or your SSH username)
   - Click "Add secret"

3. **PRODUCTION_SSH_KEY**
   - Name: `PRODUCTION_SSH_KEY`
   - Value: Copy your entire SSH private key (see below)
   - Click "Add secret"

4. **CI_ENCRYPTION_KEY**
   - Name: `CI_ENCRYPTION_KEY`
   - Value: Generate with: `openssl rand -base64 32`
   - Click "Add secret"

5. **CI_SECRET_KEY**
   - Name: `CI_SECRET_KEY`
   - Value: Generate with: `openssl rand -base64 64`
   - Click "Add secret"

6. **CI_JWT_SECRET_KEY**
   - Name: `CI_JWT_SECRET_KEY`
   - Value: Generate with: `openssl rand -base64 32`
   - Click "Add secret"

#### Optional Secrets

7. **PRODUCTION_SSH_PORT** (optional, defaults to 22)
   - Name: `PRODUCTION_SSH_PORT`
   - Value: `22`

8. **CODECOV_TOKEN** (optional, for code coverage)
   - Get from: https://codecov.io
   - Add if you want coverage reports

---

## 🔑 **Getting Your SSH Key**

### Option A: Use Existing Key

```bash
# Check for ED25519 key (recommended)
cat ~/.ssh/id_ed25519

# Or RSA key (also works)
cat ~/.ssh/id_rsa
```

Copy the entire output (including `-----BEGIN ... KEY-----` and `-----END ... KEY-----`)

### Option B: Generate New Key for GitHub Actions

```bash
# Generate dedicated key for GitHub Actions
ssh-keygen -t ed25519 -f ~/.ssh/pazpaz_deploy_key -N "" -C "github-actions-pazpaz"

# Display the private key (to add to GitHub Secrets)
cat ~/.ssh/pazpaz_deploy_key

# Display the public key (to add to server)
cat ~/.ssh/pazpaz_deploy_key.pub
```

**Then add public key to your server:**

```bash
# SSH into your production server
ssh root@5.161.241.81

# Add the public key
mkdir -p ~/.ssh
echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

---

## ✅ **Verify Setup**

After adding secrets, verify they're set:

```bash
# Using GitHub CLI
gh secret list

# Should show:
# PRODUCTION_SSH_HOST
# PRODUCTION_SSH_USER
# PRODUCTION_SSH_KEY
# CI_ENCRYPTION_KEY
# CI_SECRET_KEY
# CI_JWT_SECRET_KEY
```

Or check in web UI: https://github.com/yussieik/pazpaz/settings/secrets/actions

---

## 🧪 **Test CI/CD**

Once secrets are set, test the workflows:

```bash
# Create test branch
git checkout -b test-ci-secrets
echo "test" > test.txt
git add test.txt
git commit -m "test: verify CI secrets"
git push -u origin test-ci-secrets

# Open PR and check Actions tab
# Workflows should run without "secret not found" errors
```

---

## 🆘 **Troubleshooting**

### "Secret not found" error

**Solution:** Check secret name matches exactly (case-sensitive)

```bash
# List all secrets
gh secret list

# If missing, add it:
gh secret set PRODUCTION_SSH_HOST --body "5.161.241.81"
```

### SSH connection fails in CI

**Solution:** Verify SSH key and server access

```bash
# Test SSH connection locally
ssh -i ~/.ssh/id_ed25519 root@5.161.241.81

# If it works locally, the private key in GitHub Secrets might be wrong
# Re-add PRODUCTION_SSH_KEY secret with correct key
```

### "Permission denied" when setting secrets

**Solution:** Ensure you have admin access to the repository

```bash
# Check your permissions
gh api repos/yussieik/pazpaz --jq '.permissions'

# Should show: "admin": true
```

---

## 📋 **Quick Reference Commands**

```bash
# Generate all CI secrets at once
openssl rand -base64 32  # For CI_ENCRYPTION_KEY
openssl rand -base64 64  # For CI_SECRET_KEY
openssl rand -base64 32  # For CI_JWT_SECRET_KEY

# Set secrets via CLI (after generating values)
gh secret set PRODUCTION_SSH_HOST --body "5.161.241.81"
gh secret set PRODUCTION_SSH_USER --body "root"
gh secret set PRODUCTION_SSH_KEY < ~/.ssh/id_ed25519
gh secret set CI_ENCRYPTION_KEY --body "$(openssl rand -base64 32)"
gh secret set CI_SECRET_KEY --body "$(openssl rand -base64 64)"
gh secret set CI_JWT_SECRET_KEY --body "$(openssl rand -base64 32)"

# Verify
gh secret list
```

---

## 🎯 **Next Steps After Setup**

1. ✅ All secrets added
2. Run validation: `./scripts/validate-infrastructure.sh --check=all`
3. Create test PR to verify CI works
4. Monitor Actions tab for successful runs

---

**Need Help?**
- Run the helper script: `./scripts/generate-github-secrets.sh`
- Check GitHub Actions docs: https://docs.github.com/en/actions/security-guides/encrypted-secrets

---

**Last Updated:** 2025-11-10
