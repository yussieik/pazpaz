# CI Pipeline Documentation

> Last Updated: 2025-10-23

Comprehensive documentation for the PazPaz continuous integration pipeline, covering all workflows, developer guidelines, and maintenance procedures.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Backend CI Workflow](#backend-ci-workflow)
- [Frontend CI Workflow](#frontend-ci-workflow)
- [Secrets Management](#secrets-management)
- [Developer Workflow](#developer-workflow)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Maintenance](#maintenance)
- [Performance Optimization](#performance-optimization)

## Overview

The PazPaz CI pipeline ensures code quality, security, and reliability through automated testing and validation. Our pipeline is built on GitHub Actions and follows a multi-stage validation approach.

### Key Features
- **Parallel Execution**: Multiple jobs run simultaneously for faster feedback
- **Comprehensive Testing**: Unit, integration, and performance tests
- **Security Scanning**: Vulnerability detection with Trivy, CodeQL, and dependency audits
- **Quality Gates**: Enforced code formatting, linting, and type checking
- **Smart Caching**: Dependency and build caching for improved performance
- **Path Filtering**: Only runs relevant workflows based on changed files

### Design Principles
1. **Fast Feedback**: Developers get results within 5-10 minutes
2. **Fail Fast**: Critical checks run first, optional checks last
3. **Clear Reporting**: Detailed summaries and artifacts for debugging
4. **Security First**: Multiple layers of security scanning
5. **Cost Efficient**: Optimized for minimal GitHub Actions minutes

## Architecture

### CI/CD Pipeline Flow

```
Developer Push/PR
       │
       ├─── Path Filter ─── Backend Changes ─┐
       │                                      │
       └─── Path Filter ─── Frontend Changes ─┤
                                             │
                    ┌────────────────────────┘
                    │
       ┌────────────▼────────────┐
       │   Parallel Workflows    │
       ├─────────────────────────┤
       │  Backend CI:            │
       │  - Test & Quality       │
       │  - Security Scanning    │
       │  - OpenAPI Validation   │
       │  - CodeQL Analysis      │
       │  - Dependency Check     │
       │  - Performance Tests    │
       │                         │
       │  Frontend CI:           │
       │  - Test & Quality       │
       │  - Security Scanning    │
       │  - License Check        │
       │  - Bundle Analysis      │
       └───────────┬─────────────┘
                   │
                   ▼
           Status Checks
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
    CI Success           CI Success Gate
    (Backend)             (Frontend)
        │                     │
        └──────────┬──────────┘
                   │
                   ▼
            Merge Allowed
```

### Workflow Relationships

| Workflow | Trigger | Purpose | Required |
|----------|---------|---------|----------|
| backend-ci.yml | Push/PR to main | Backend validation | Yes |
| frontend-ci.yml | Push/PR to main | Frontend validation | Yes |
| secrets-validation.yml | Weekly/Manual | Verify secrets configured | No |
| dependabot updates | Weekly | Dependency updates | No |

## Backend CI Workflow

### Overview
Location: `.github/workflows/backend-ci.yml`

The backend CI workflow validates Python code quality, runs tests, and performs security scanning.

### Jobs and Purposes

#### 1. Test & Quality Checks (`test`)
**Purpose**: Core testing and code quality validation

**Steps**:
1. Setup Python 3.13.5 environment with uv
2. Install dependencies with caching
3. Run pytest with coverage (minimum 80%)
4. Check code formatting with ruff
5. Validate linting rules with ruff
6. Type checking with mypy (non-blocking)
7. Security audit with safety (non-blocking)

**Environment Variables Required**:
```yaml
DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/pazpaz_test
REDIS_URL: redis://localhost:6379/0
ENCRYPTION_MASTER_KEY: test_key_for_ci_only_32_bytes_long!!
SECRET_KEY: test_secret_for_ci_only_must_be_long_enough
JWT_SECRET_KEY: test_jwt_secret_for_ci_only
ENVIRONMENT: test
DEBUG: false
CORS_ORIGINS: '["http://localhost:3000"]'
SESSION_SECRET_KEY: test_session_secret_for_ci_only
COOKIE_DOMAIN: localhost
SECURE_COOKIES: false
SENTRY_DSN: ""
LOG_LEVEL: INFO
STORAGE_BACKEND: filesystem
STORAGE_PATH: /tmp/test_storage
EMAIL_BACKEND: console
WORKSPACE_ISOLATION_ENABLED: true
AUDIT_LOGGING_ENABLED: true
```

**Services**:
- PostgreSQL 16 (for integration tests)
- Redis 7 (for caching/queues)

#### 2. Security Scanning (`security`)
**Purpose**: Detect vulnerabilities in code and dependencies

**Tools**:
- **Trivy**: Scans for OS and library vulnerabilities
- Outputs SARIF format for GitHub Security tab
- Generates table format for PR comments

**Severity Levels**: CRITICAL, HIGH (blocking), MEDIUM (warning)

#### 3. OpenAPI Validation (`openapi-validation`)
**Purpose**: Ensure API specification is valid and detect breaking changes

**Steps**:
1. Generate OpenAPI spec from FastAPI app
2. Validate with @apidevtools/swagger-cli
3. Check for breaking changes (PR only)
4. Upload spec as artifact

#### 4. CodeQL Analysis (`codeql`)
**Purpose**: Static application security testing (SAST)

**Configuration**:
- Language: Python
- Queries: security-extended, security-and-quality
- Paths: backend/src (excludes tests and migrations)

#### 5. Dependency Check (`dependency-check`)
**Purpose**: Identify outdated and vulnerable dependencies

**Tools**:
- uv pip list --outdated
- pip-audit for vulnerability scanning
- Results uploaded as artifacts

#### 6. Performance Tests (`performance-tests`)
**Purpose**: Validate p95 < 150ms requirement for schedule endpoints

**Characteristics**:
- Optional (non-blocking)
- Runs on PRs and main branch
- Tests marked with `@pytest.mark.performance`

### Running Locally

```bash
# Run all tests
cd backend
uv sync --dev
uv run pytest

# Run with coverage
uv run pytest --cov=pazpaz --cov-report=html --cov-fail-under=80

# Format code
uv run ruff format src/ tests/

# Lint code
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/pazpaz

# Security audit
uv run safety check

# Performance tests only
uv run pytest -m performance
```

### Coverage Thresholds

- **Minimum Coverage**: 80%
- **Enforcement**: CI fails if coverage drops below threshold
- **Reports**: XML (Codecov), HTML (artifact), Terminal output

## Frontend CI Workflow

### Overview
Location: `.github/workflows/frontend-ci.yml`

The frontend CI workflow validates TypeScript/Vue code, runs tests, and analyzes bundle size.

### Jobs and Purposes

#### 1. Test & Quality Checks (`test`)
**Purpose**: Comprehensive frontend validation

**Steps**:
1. Setup Node.js 20 with npm caching
2. Install dependencies with `npm ci`
3. ESLint checking
4. Prettier format validation
5. TypeScript type checking
6. Vitest unit tests
7. Coverage generation (if tests pass)
8. Production build
9. Bundle size analysis

**Quality Gates** (all required):
- ESLint must pass
- Prettier formatting must be correct
- TypeScript must compile without errors
- All unit tests must pass
- Production build must succeed

#### 2. Security Scanning (`security`)
**Purpose**: Identify vulnerabilities in npm packages

**npm audit**:
- Severity threshold: moderate
- Fails on CRITICAL or HIGH vulnerabilities
- Warns on MODERATE vulnerabilities
- Generates JSON report

**Trivy scanning**:
- Filesystem scan of frontend directory
- Excludes node_modules, dist, coverage
- SARIF output for GitHub Security tab

#### 3. License Compliance (`license-check`)
**Purpose**: Ensure dependency licenses are acceptable

**Process**:
- Uses license-checker tool
- Generates summary of all production dependencies
- Excludes private packages
- Non-blocking (informational only)

#### 4. Bundle Analysis (`bundle-analysis`)
**Purpose**: Track bundle size changes in PRs

**Metrics**:
- Compare PR bundle size vs base branch
- Alert if size increases >10%
- Generate size comparison table

### npm Scripts Used

```json
{
  "scripts": {
    "lint:check": "eslint . --ext .vue,.js,.jsx,.ts,.tsx",
    "format:check": "prettier --check \"**/*.{js,jsx,ts,tsx,vue,css,md}\"",
    "type-check": "vue-tsc --noEmit",
    "test:unit": "vitest run",
    "test:coverage": "vitest run --coverage",
    "build": "vite build"
  }
}
```

### Running Locally

```bash
# Run all checks
cd frontend
npm ci

# Linting
npm run lint:check
npm run lint:fix  # Auto-fix issues

# Formatting
npm run format:check
npm run format      # Auto-format

# Type checking
npm run type-check

# Unit tests
npm run test:unit
npm run test:unit -- --watch  # Watch mode
npm run test:coverage          # With coverage

# Build
npm run build
npm run preview  # Preview production build

# Security audit
npm audit
npm audit fix  # Auto-fix vulnerabilities
```

## Secrets Management

### Required GitHub Secrets

No secrets are required for basic CI operation. Optional secrets include:

| Secret | Purpose | Required | Default |
|--------|---------|----------|---------|
| CODECOV_TOKEN | Upload coverage to Codecov | No | Skips upload |

### Environment-Specific Variables

CI uses test-specific values that are NOT secrets:
- Database: In-memory or containerized test DB
- Redis: Containerized test instance
- Encryption keys: Test-only values (not for production)

For production secrets setup, see [GitHub Secrets Setup](./github-secrets-setup.md).

## Developer Workflow

### Creating a Pull Request

1. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes and test locally**:
   ```bash
   # Backend
   cd backend && uv run pytest

   # Frontend
   cd frontend && npm test
   ```

3. **Commit with conventional commits**:
   ```bash
   git add .
   git commit -m "feat(backend): add new endpoint for appointments"
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature/your-feature
   # Open PR on GitHub
   ```

### What Happens During CI

1. **Immediate** (0-30s):
   - Workflows triggered based on changed paths
   - Jobs queued in parallel

2. **Quick Feedback** (1-3 min):
   - Linting and formatting checks
   - TypeScript compilation
   - Unit tests start

3. **Full Validation** (3-7 min):
   - Integration tests complete
   - Security scans run
   - Coverage calculated

4. **Final Steps** (5-10 min):
   - CodeQL analysis (backend)
   - Bundle size comparison (frontend PRs)
   - Status checks updated

### Understanding CI Status

**GitHub PR Status Indicators**:
- 🟡 **Yellow dot**: Checks are running
- ✅ **Green check**: All required checks passed
- ❌ **Red X**: One or more checks failed
- ⏭️ **Skipped**: Job was skipped (path filtering)

**Merge Button States**:
- "Waiting for status checks": CI is running
- "Required checks must pass": CI failed
- "This branch is out-of-date": Needs rebase/merge
- "Merge" (green): Ready to merge!

### Fixing CI Failures

#### Backend Failures

**Test Failures**:
```bash
# Run specific failing test locally
uv run pytest tests/test_appointments.py::test_create_appointment -vv

# Check test database
docker-compose up -d db
uv run pytest --no-cov
```

**Formatting Issues**:
```bash
# Auto-fix formatting
uv run ruff format src/ tests/
git add . && git commit -m "style: fix formatting"
```

**Linting Issues**:
```bash
# View issues
uv run ruff check src/ tests/

# Auto-fix where possible
uv run ruff check src/ tests/ --fix
```

**Type Checking Issues**:
```bash
# Run mypy locally
uv run mypy src/pazpaz --show-error-codes

# Common fixes:
# - Add type hints
# - Use Optional[] for nullable values
# - Add # type: ignore for third-party issues
```

#### Frontend Failures

**ESLint Errors**:
```bash
# View all issues
npm run lint:check

# Auto-fix
npm run lint:fix
```

**Prettier Formatting**:
```bash
# Check formatting
npm run format:check

# Auto-format
npm run format
```

**TypeScript Errors**:
```bash
# Check types
npm run type-check

# Common fixes:
# - Add missing type annotations
# - Fix type mismatches
# - Update @types packages
```

**Test Failures**:
```bash
# Run with details
npm run test:unit -- --reporter=verbose

# Debug specific test
npm run test:unit -- MyComponent.spec.ts
```

### Re-running Failed Jobs

**Via GitHub UI**:
1. Go to PR "Checks" tab
2. Click "Re-run jobs" → "Re-run failed jobs"
3. Or re-run specific job

**Via Git Push** (triggers full re-run):
```bash
# Empty commit to trigger CI
git commit --allow-empty -m "chore: trigger CI"
git push
```

## Troubleshooting Guide

### Common Issues and Solutions

#### "No jobs were run"
**Cause**: Path filtering excluded all jobs

**Solution**: Check if your changes match path filters in workflows

#### "Resource not accessible by integration"
**Cause**: Missing permissions for GITHUB_TOKEN

**Solution**: Check workflow permissions block includes necessary permissions

#### Test Database Connection Failed
**Cause**: PostgreSQL service not ready

**Solution**:
- Ensure health checks are configured
- Add retry logic to database connections
- Check service logs in Actions UI

#### Coverage Decreased Below Threshold
**Cause**: New code without tests

**Solution**:
```bash
# Generate coverage report locally
uv run pytest --cov=pazpaz --cov-report=html
# Open htmlcov/index.html to see uncovered lines
```

#### npm audit Found Vulnerabilities
**Cause**: Dependencies have known vulnerabilities

**Solution**:
```bash
# Try automatic fix
npm audit fix

# If that doesn't work, manual update
npm update [package-name]

# Or use resolution in package.json for transitive deps
```

#### Bundle Size Increased Significantly
**Cause**: Large dependency added or imports not tree-shaken

**Solution**:
```bash
# Analyze bundle
npm run build -- --analyze

# Consider:
# - Dynamic imports for large components
# - Lighter alternatives to heavy libraries
# - Tree-shaking configuration
```

#### CodeQL Timing Out
**Cause**: Analysis taking too long

**Solution**:
- Reduce paths in CodeQL config
- Exclude generated code
- Increase timeout in workflow

### Debugging CI Locally

#### Using Act for Local GitHub Actions

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run backend CI locally
act -W .github/workflows/backend-ci.yml

# Run specific job
act -W .github/workflows/backend-ci.yml -j test
```

#### Docker Compose for Services

```bash
# Start CI services locally
docker-compose -f docker-compose.ci.yml up -d

# Run tests against local services
export DATABASE_URL=postgresql+asyncpg://test_user:test_password@localhost:5432/pazpaz_test
export REDIS_URL=redis://localhost:6379/0
uv run pytest
```

## Maintenance

### Updating Dependencies

#### Python Dependencies
```bash
# Update all packages
cd backend
uv update

# Update specific package
uv add package@latest

# After updating, test locally
uv run pytest
```

#### npm Dependencies
```bash
# Check outdated
npm outdated

# Update all
npm update

# Update specific
npm install package@latest

# Audit after updates
npm audit
```

#### GitHub Actions
Dependabot will create PRs for Action updates automatically.

### Adjusting Coverage Thresholds

Edit `backend-ci.yml`:
```yaml
- name: Run pytest with coverage
  run: |
    uv run pytest \
      --cov-fail-under=85  # Increase from 80 to 85
```

### Adding New Checks

#### Add to Backend CI
1. Add new job in `backend-ci.yml`
2. Update `ci-success` job dependencies
3. Update branch protection if check is required

#### Add to Frontend CI
1. Add new job in `frontend-ci.yml`
2. Update `ci-success` job dependencies
3. Update branch protection if check is required

Example new job:
```yaml
accessibility:
  name: Accessibility Testing
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run axe accessibility tests
      run: npm run test:a11y
```

### Performance Optimization

#### Cache Optimization

**Python/uv caching**:
```yaml
- uses: actions/cache@v4
  with:
    path: |
      ~/.cache/uv
      ./backend/.venv
    key: ${{ runner.os }}-uv-${{ hashFiles('backend/pyproject.toml', 'backend/uv.lock') }}
```

**npm caching** (built into setup-node):
```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
    cache-dependency-path: frontend/package-lock.json
```

#### Parallel Execution

Structure jobs to run in parallel when possible:
```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    # ...

  test:
    runs-on: ubuntu-latest
    # ...

  security:
    runs-on: ubuntu-latest
    # ...

  # Wait for all
  ci-success:
    needs: [lint, test, security]
```

#### Matrix Builds

For multiple versions/configurations:
```yaml
strategy:
  matrix:
    python-version: [3.11, 3.12, 3.13]
    os: [ubuntu-latest, windows-latest]
```

#### Conditional Execution

Skip expensive checks on certain conditions:
```yaml
if: |
  github.event_name == 'pull_request' ||
  github.ref == 'refs/heads/main'
```

### Monitoring CI Performance

#### GitHub Insights
1. Go to Actions tab
2. Click on workflow
3. View "Usage" for execution times and costs

#### Optimization Targets
- Backend CI: < 7 minutes
- Frontend CI: < 5 minutes
- Total PR feedback: < 10 minutes

## Security Considerations

### Secret Scanning
- Never commit secrets to repository
- Use GitHub secret scanning
- Rotate any exposed credentials immediately

### Dependency Updates
- Review Dependabot PRs carefully
- Check breaking changes in CHANGELOG
- Run full test suite before merging

### Security Tool Results
- Address CRITICAL and HIGH vulnerabilities immediately
- Document accepted risks for false positives
- Regular security review meetings

## Future Enhancements

### Planned Improvements
- [ ] Add E2E testing with Playwright
- [ ] Implement visual regression testing
- [ ] Add performance benchmarking trends
- [ ] Create deployment workflows (Phase 2)
- [ ] Add container scanning for Docker images
- [ ] Implement DAST security testing
- [ ] Add mutation testing for better coverage
- [ ] Create PR preview environments

### Optional Status Badges
Status badges can be added to README.md to show CI status:

```markdown
![Backend CI](https://github.com/USERNAME/REPO/workflows/Backend%20CI/badge.svg)
![Frontend CI](https://github.com/USERNAME/REPO/workflows/Frontend%20CI/badge.svg)
![Coverage](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)
```

## Related Documentation

- [Branch Protection Setup](./BRANCH_PROTECTION_SETUP.md) - Configure required status checks
- [GitHub Secrets Setup](./github-secrets-setup.md) - Production secrets configuration
- [CI/CD Implementation Plan](./CI_CD_IMPLEMENTATION_PLAN.md) - Overall strategy
- [Backend CI Workflow Details](./backend-ci-workflow.md) - Deep dive into backend CI
- [Frontend CI Implementation](./FRONTEND_CI_IMPLEMENTATION.md) - Frontend CI details

## Support

For CI/CD issues or questions:
1. Check this documentation and troubleshooting guide
2. Review workflow logs in GitHub Actions
3. Search existing issues in the repository
4. Contact the DevOps team or create an issue