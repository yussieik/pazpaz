# CI/CD Quick Start Guide

This guide helps you get started with the optimized PazPaz CI/CD pipeline.

---

## 🚀 **Quick Setup (5 minutes)**

### Step 1: Add Required Secrets

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

```bash
# Production SSH Access (REQUIRED)
PRODUCTION_SSH_HOST=5.161.241.81
PRODUCTION_SSH_USER=root
PRODUCTION_SSH_KEY=<paste-your-ed25519-private-key>

# Optional (has defaults)
PRODUCTION_SSH_PORT=22

# Optional: Code Coverage
CODECOV_TOKEN=<your-codecov-token>
```

### Step 2: Verify Workflows

```bash
# Clone the repo
git clone https://github.com/yussieik/pazpaz.git
cd pazpaz

# Test infrastructure validation locally
./scripts/validate-infrastructure.sh --check=all

# Test backend
cd backend && uv run pytest

# Test frontend
cd ../frontend && npm run test:unit
```

### Step 3: Test in CI

1. Create a test branch: `git checkout -b test-ci-optimization`
2. Make a small change: `touch test.txt`
3. Commit and push: `git add . && git commit -m "test: verify CI" && git push`
4. Open PR and watch workflows run ✅

---

## 📁 **Project Structure**

```
.github/
├── actions/                    # Reusable composite actions
│   ├── setup-python/          # Python 3.13.5 + uv setup
│   ├── setup-node/            # Node 20 + npm setup
│   └── setup-docker/          # Docker Buildx setup
│
└── workflows/
    ├── backend-ci.yml         # Backend testing & deployment
    ├── frontend-ci.yml        # Frontend testing & deployment
    ├── infrastructure-ci.yml  # Infrastructure validation
    └── validate-secrets.yml   # Secret compliance checking

scripts/
└── validate-infrastructure.sh # Infrastructure validation script
```

---

## 🔄 **How Workflows Trigger**

### Backend CI (`backend-ci.yml`)

**Triggers on:**
- Push to `main` (auto-deploys to production)
- Pull requests to `main`
- Changes to `backend/**` or workflow files
- Manual trigger via GitHub Actions UI

**Jobs:**
1. `test` - Run pytest with 90% pass rate requirement
2. `security` - Trivy vulnerability scanning
3. `codeql` - Static analysis
4. `openapi` - OpenAPI spec validation
5. `performance` - P95 < 150ms performance tests
6. `docker-build` - Build & push Docker image
7. `deploy-production` - Deploy to production (main only)

### Frontend CI (`frontend-ci.yml`)

**Triggers on:**
- Push to `main` (auto-deploys to production)
- Pull requests to `main`
- Changes to `frontend/**` or workflow files
- Manual trigger

**Jobs:**
1. `quality-checks` - ESLint, Prettier, TypeScript
2. `test` - Unit tests with coverage
3. `build` - Production bundle build
4. `security` - npm audit + Trivy
5. `docker-build` - Build & push Docker image
6. `deploy-production` - Deploy to production (main only)

### Infrastructure CI (`infrastructure-ci.yml`)

**Triggers on:**
- Changes to `docker-compose*.yml`, `nginx/**`, `scripts/**`
- Pull requests
- Manual trigger

**Jobs:**
1. `validate` - Run validation script
2. `docker-build-test` - Test Docker builds
3. `success` - Final status check

---

## 🛠️ **Common Tasks**

### Run CI Checks Locally

```bash
# Backend
cd backend
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run pytest --cov=pazpaz --cov-fail-under=35

# Frontend
cd frontend
npm run lint:check
npm run format:check
npm run type-check
npm run test:unit

# Infrastructure
./scripts/validate-infrastructure.sh --check=all
```

### Manually Trigger Workflow

1. Go to **Actions** tab
2. Select workflow (e.g., "Backend CI")
3. Click **Run workflow**
4. Select branch and options
5. Click **Run workflow**

### View CI Results

1. Open your PR
2. Scroll to **Checks** section
3. Click on failed check for details
4. Or go to **Actions** tab for full logs

---

## 🐛 **Troubleshooting**

### CI Fails with "Secret not found"

**Solution:** Add missing secret to repository settings

```bash
# Example: Add SSH host
Settings → Secrets → New secret
Name: PRODUCTION_SSH_HOST
Value: 5.161.241.81
```

### Docker Build Fails

**Solution:** Check Dockerfile syntax and base images

```bash
# Test locally
docker build -t test-backend ./backend
docker build -t test-frontend ./frontend
```

### Tests Fail in CI but Pass Locally

**Solution:** Check environment variables

```yaml
# CI uses these env vars (see workflow files)
DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/pazpaz_test
REDIS_URL: redis://localhost:6379/0
```

### Infrastructure Validation Fails

**Solution:** Run validation script locally

```bash
chmod +x scripts/validate-infrastructure.sh
./scripts/validate-infrastructure.sh --check=all

# Check specific components
./scripts/validate-infrastructure.sh --check=docker
./scripts/validate-infrastructure.sh --check=nginx
./scripts/validate-infrastructure.sh --check=scripts
```

---

## 📊 **CI/CD Pipeline Flow**

```
┌─────────────────────────────────────────────────────────────┐
│ Developer pushes to branch                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Path-based triggers determine which workflows run            │
│ - backend/** → backend-ci.yml                               │
│ - frontend/** → frontend-ci.yml                             │
│ - docker-compose*.yml → infrastructure-ci.yml               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Workflows run in parallel (where possible)                   │
│ - Linting & formatting                                       │
│ - Testing (unit, integration, performance)                   │
│ - Security scanning (Trivy, CodeQL, npm audit)              │
│ - Docker build & scan                                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ If branch = main AND all checks pass:                        │
│ → Auto-deploy to production                                  │
│ → Run smoke tests                                            │
│ → Verify deployment                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 **Best Practices**

### For Developers

✅ **DO:**
- Run linters/tests locally before pushing
- Use descriptive commit messages
- Keep PRs small and focused
- Wait for CI to pass before requesting review

❌ **DON'T:**
- Force push to `main`
- Merge without green CI
- Commit `node_modules/` or `.venv/`
- Hardcode secrets in code

### For Reviewers

✅ **DO:**
- Check CI status before approving
- Review security scan results
- Verify test coverage hasn't dropped
- Test deployment in staging (if available)

❌ **DON'T:**
- Approve failed CI
- Override security warnings without investigation
- Skip code review for "small" changes

---

## 📈 **Performance Tips**

### Speed Up CI

1. **Use caching** - Workflows already cache dependencies
2. **Run tests in parallel** - Already configured
3. **Skip unnecessary jobs** - Use `paths:` filters
4. **Use sparse checkout** - Already used in deploy jobs

### Reduce Costs

- Pull requests skip Docker builds
- Performance tests are optional
- Security scans use free tier
- Deployments only on `main` branch

---

## 🆘 **Getting Help**

### Resources

- **Workflow files:** `.github/workflows/`
- **Composite actions:** `.github/actions/`
- **Validation script:** `scripts/validate-infrastructure.sh`
- **Summary:** `CI_CD_OPTIMIZATION_SUMMARY.md`

### Support Channels

- **GitHub Issues:** For bugs or feature requests
- **Pull Requests:** For improvements
- **GitHub Discussions:** For questions

---

## 📚 **Learn More**

### GitHub Actions Documentation

- [Composite Actions](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Caching Dependencies](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)

### Tools Used

- [Trivy](https://github.com/aquasecurity/trivy) - Vulnerability scanner
- [CodeQL](https://codeql.github.com/) - Static analysis
- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Docker Buildx](https://github.com/docker/buildx) - Multi-platform builds

---

**Last Updated:** 2025-11-10
**Status:** ✅ Production Ready
