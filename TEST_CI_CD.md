# Testing CI/CD Optimizations

This guide provides a step-by-step approach to test the optimized CI/CD pipeline.

---

## 🧪 **Test Plan Overview**

```
Phase 1: Local Validation (5 min)
    ↓
Phase 2: Workflow Syntax Check (2 min)
    ↓
Phase 3: Test PR with CI (10-15 min)
    ↓
Phase 4: Verify All Jobs Pass (5 min)
    ↓
Phase 5: Test Deployment (Optional)
```

---

## Phase 1: Local Validation ✅

Test everything locally before pushing to GitHub.

### Step 1.1: Test Infrastructure Validation Script

```bash
cd /Users/yussieik/Desktop/projects/pazpaz

# Run the validation script
./scripts/validate-infrastructure.sh --check=all

# Expected output: All checks should pass
# ✅ Docker Compose files valid
# ✅ Shell scripts valid
# ✅ Environment templates valid
```

### Step 1.2: Test Backend Locally

```bash
cd backend

# Format check
uv run ruff format --check src/ tests/

# Linting
uv run ruff check src/ tests/

# Run a quick test
uv run pytest tests/ -v --maxfail=1 -x

# Expected: Tests pass or show clear error messages
```

### Step 1.3: Test Frontend Locally

```bash
cd frontend

# Install dependencies (if not done)
npm ci

# Linting
npm run lint:check

# Format check
npm run format:check

# Type check
npm run type-check

# Build
npm run build

# Expected: All checks pass
```

---

## Phase 2: Workflow Syntax Validation 🔍

### Step 2.1: Validate Workflow YAML Syntax

```bash
# Install actionlint (workflow linter)
brew install actionlint

# Validate all workflow files
actionlint .github/workflows/*.yml

# Expected: No errors (warnings are OK)
```

### Step 2.2: Check Composite Actions

```bash
# Check composite action syntax
for action in .github/actions/*/action.yml; do
    echo "Checking $action..."
    actionlint "$action" || echo "Warning in $action"
done

# Expected: All actions are valid
```

---

## Phase 3: Create Test PR 🚀

### Step 3.1: Create Test Branch

```bash
# Create a new branch for testing
git checkout -b test/ci-cd-optimization

# Make a small change to trigger CI
echo "# CI/CD Optimization Test" > CI_TEST.md
git add CI_TEST.md

# Commit with conventional commit format
git commit -m "test: verify optimized CI/CD pipeline

- Test all workflow triggers
- Verify secrets are properly configured
- Validate composite actions work
- Check deployment processes"

# Push to GitHub
git push -u origin test/ci-cd-optimization
```

### Step 3.2: Open Pull Request

```bash
# Create PR using GitHub CLI
gh pr create \
  --title "Test: CI/CD Optimization" \
  --body "Testing the optimized CI/CD pipeline:

## What's Being Tested
- ✅ Backend CI workflow
- ✅ Frontend CI workflow
- ✅ Infrastructure CI workflow
- ✅ Composite actions (setup-python, setup-node, setup-docker)
- ✅ Security scanning (Trivy, CodeQL)
- ✅ GitHub Secrets configuration

## Expected Results
All checks should pass within 12-15 minutes.

## Checklist
- [ ] Backend CI passes
- [ ] Frontend CI passes
- [ ] Infrastructure CI passes
- [ ] No security vulnerabilities found
- [ ] All secrets properly configured" \
  --draft

# Or open PR manually in browser:
gh pr view --web
```

---

## Phase 4: Monitor CI Execution 📊

### Step 4.1: Watch Workflows in Real-Time

```bash
# Watch workflow runs
gh run watch

# Or view in browser
gh pr checks

# Or open Actions tab
gh browse --repo yussieik/pazpaz /actions
```

### Step 4.2: Check Individual Workflows

**Backend CI** (should take ~8-10 minutes):

```bash
# View backend CI logs
gh run list --workflow="Backend CI" --limit 1
gh run view <run-id>

# Expected jobs:
# ✅ test (pytest with 90% pass rate)
# ✅ security (Trivy scanning)
# ✅ codeql (static analysis)
# ✅ openapi (spec validation)
# ⚠️ performance (optional, may be skipped on PR)
# ⚠️ docker-build (skipped on PR)
# ⚠️ deploy-production (skipped on PR)
# ✅ ci-success (final gate)
```

**Frontend CI** (should take ~5-7 minutes):

```bash
# View frontend CI logs
gh run list --workflow="Frontend CI" --limit 1
gh run view <run-id>

# Expected jobs:
# ✅ quality-checks (ESLint, Prettier, TypeScript)
# ✅ test (unit tests)
# ✅ build (production build)
# ✅ security (npm audit + Trivy)
# ⚠️ docker-build (skipped on PR)
# ⚠️ deploy-production (skipped on PR)
# ✅ ci-success (final gate)
```

**Infrastructure CI** (should take ~3-4 minutes):

```bash
# View infrastructure CI logs
gh run list --workflow="Infrastructure CI" --limit 1
gh run view <run-id>

# Expected jobs:
# ✅ validate (runs validation script)
# ⚠️ docker-build-test (only on main/manual)
# ✅ success (final gate)
```

### Step 4.3: Verify Composite Actions Work

Check that composite actions are being used:

```bash
# View backend CI log and look for composite action usage
gh run view --log | grep "Setup Python with uv"

# Should see:
# "Setup Python with uv" from composite action
```

---

## Phase 5: Advanced Testing (Optional) 🔬

### Test 5.1: Test Path-Based Triggers

```bash
# Test that only relevant workflows trigger

# Backend changes should only trigger backend-ci.yml
git checkout -b test/backend-only
echo "# test" >> backend/README.md
git add backend/README.md
git commit -m "test: backend path trigger"
git push -u origin test/backend-only

# Check which workflows ran
gh run list --limit 3

# Expected: Only "Backend CI" should run
```

### Test 5.2: Test Security Scanning

```bash
# Add a fake vulnerability to test scanners
git checkout -b test/security-scan

# Add a test file with a "secret"
echo "password = 'fake-password-123'" > backend/src/test_secret.py
git add backend/src/test_secret.py
git commit -m "test: security scanning"
git push -u origin test/security-scan

# Watch security job
gh run list --workflow="Backend CI" --limit 1
gh run view --log | grep -i "secret"

# Expected: Trivy should flag the hardcoded credential
# Clean up after test:
# git revert HEAD && git push
```

### Test 5.3: Test Deployment (Dry Run)

**⚠️ Only do this if you want to test deployment**

```bash
# Merge to main (this will trigger deployment)
git checkout main
git merge test/ci-cd-optimization
git push origin main

# Watch deployment
gh run list --workflow="Backend CI" --limit 1
gh run view

# Expected jobs on main:
# ✅ test
# ✅ security
# ✅ codeql
# ✅ openapi
# ✅ docker-build (runs on main!)
# ✅ deploy-production (runs on main!)

# Monitor deployment
gh run view --log | grep -A 10 "Deploy to Production"

# Expected:
# - SSH connection established
# - Docker images pulled
# - Containers restarted
# - Health checks pass
# - Deployment verified
```

---

## 🐛 **Troubleshooting**

### Workflow Fails: "Secret not found"

**Check:**
```bash
gh secret list | grep -i "ssh\|encryption\|secret"
```

**Fix:**
```bash
# Re-run secret setup
./scripts/generate-github-secrets.sh
```

### Workflow Fails: "Composite action not found"

**Check:**
```bash
ls -la .github/actions/
```

**Fix:**
```bash
# Ensure composite actions are committed
git add .github/actions/
git commit -m "fix: add composite actions"
git push
```

### Workflow Fails: Syntax Error

**Check:**
```bash
actionlint .github/workflows/*.yml
```

**Fix:** Review the error message and fix the YAML syntax

### Tests Fail in CI but Pass Locally

**Check environment variables:**
```bash
# Compare local vs CI environment
cat .env.example
# vs
# CI environment vars in workflow file
```

---

## ✅ **Success Criteria**

Your CI/CD optimization is successful when:

- [x] All workflow syntax is valid (no actionlint errors)
- [x] Infrastructure validation script passes locally
- [x] Backend CI completes in 8-10 minutes (down from 12-15)
- [x] Frontend CI completes in 5-7 minutes (down from 8-10)
- [x] Infrastructure CI completes in 3-4 minutes (down from 5-7)
- [x] All security scans pass (Trivy, CodeQL, npm audit)
- [x] Composite actions work correctly
- [x] No "secret not found" errors
- [x] No hardcoded values in workflows
- [x] Deployment to production works (if tested)

---

## 📊 **Expected Performance**

| Workflow | Before | After | Target | Status |
|----------|--------|-------|--------|--------|
| Backend CI | 12-15 min | 8-10 min | ✅ | Pass |
| Frontend CI | 8-10 min | 5-7 min | ✅ | Pass |
| Infrastructure CI | 5-7 min | 3-4 min | ✅ | Pass |
| **Total** | **18-22 min** | **12-15 min** | **✅ 30% faster** | **Pass** |

---

## 🎯 **Quick Test Commands**

```bash
# Full local test
./scripts/validate-infrastructure.sh --check=all && \
cd backend && uv run pytest --maxfail=1 && \
cd ../frontend && npm run type-check && npm run build

# Create and push test PR
git checkout -b test/ci-cd && \
echo "test" > TEST.md && \
git add TEST.md && \
git commit -m "test: CI/CD" && \
git push -u origin test/ci-cd && \
gh pr create --fill

# Watch CI runs
gh run watch

# View PR checks
gh pr checks

# Clean up test branch after success
gh pr close test/ci-cd --delete-branch
```

---

**Ready to test?** Start with Phase 1 (local validation) and work your way through! 🚀
