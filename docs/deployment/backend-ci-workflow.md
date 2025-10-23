# Backend CI Workflow Documentation

## Overview

The backend CI workflow (`/.github/workflows/backend-ci.yml`) provides comprehensive automated testing, quality checks, and security scanning for the PazPaz backend codebase.

## Workflow Triggers

The workflow is triggered on:
- **Push to main branch** - When backend code changes are merged
- **Pull requests to main** - For code review and validation
- **Manual dispatch** - For testing on feature branches
- **Path filtering** - Only runs when backend files or workflow itself changes

## Jobs and Checks

### 1. Test & Quality Checks Job

Primary testing and code quality validation:

- **Python Setup**: Uses Python 3.13.5 with uv package manager
- **Services**: PostgreSQL 16 and Redis 7 for integration tests
- **Test Coverage**: Enforces 80% minimum coverage with pytest
- **Code Formatting**: Validates with ruff formatter
- **Linting**: Checks code style with ruff linter
- **Type Checking**: Static type analysis with mypy (non-blocking)
- **Dependency Audit**: Security check with safety (non-blocking)
- **Coverage Reporting**: Uploads to Codecov and artifacts

### 2. Security Scanning Job

Comprehensive vulnerability assessment:

- **Trivy Scanner**: Filesystem scan for critical/high vulnerabilities
  - Checks OS packages, libraries, secrets, and misconfigurations
  - Results uploaded to GitHub Security tab
  - Table format for PR comments
- **SARIF Upload**: Security findings integrated into GitHub Security

### 3. OpenAPI Validation Job

API specification validation:

- **Spec Generation**: Extracts OpenAPI spec from FastAPI app
- **Schema Validation**: Validates with swagger-cli
- **Breaking Change Detection**: Compares against base branch (PRs only)
- **Artifact Upload**: Saves generated spec for reference

### 4. CodeQL Analysis Job

Advanced security analysis:

- **Languages**: Python code analysis
- **Query Suites**: security-extended and security-and-quality
- **Scope**: Analyzes backend/src, excludes tests and migrations
- **Integration**: Results in GitHub Security tab

### 5. Dependency Check Job

Supply chain security:

- **Outdated Check**: Lists packages needing updates
- **Vulnerability Audit**: Uses pip-audit for known CVEs
- **JSON Report**: Detailed audit results saved as artifact

### 6. Performance Tests Job (Optional)

Performance validation (non-blocking):

- **Trigger**: Only on PRs and main branch
- **Target**: p95 < 150ms for schedule endpoints
- **Test Suite**: Runs tests marked with `@pytest.mark.performance`
- **Report**: Performance metrics saved as artifact

### 7. CI Success Gate

Final validation job that ensures all required checks pass before allowing merge.

## Environment Variables

The workflow uses test-specific environment variables:

```yaml
DATABASE_URL: postgresql+asyncpg://test_user:test_password@localhost:5432/pazpaz_test
REDIS_URL: redis://localhost:6379/0
ENCRYPTION_MASTER_KEY: test_key_for_ci_only_32_bytes_long!!
SECRET_KEY: test_secret_for_ci_only_must_be_long_enough
ENVIRONMENT: test
```

## Caching Strategy

- **uv cache**: Dependencies cached based on pyproject.toml and uv.lock
- **Python environment**: .venv cached to speed up installations

## Artifacts

The workflow generates several artifacts:

- **coverage-report**: HTML coverage report (7-day retention)
- **openapi-spec**: Generated OpenAPI specification
- **dependency-audit**: Security audit results
- **performance-report**: Performance test metrics

## Non-Blocking Checks

The following checks are currently non-blocking (continue-on-error):

- **mypy**: Type checking (gradual typing adoption)
- **safety**: Security audit (allowing time to address issues)
- **Performance tests**: Don't block PRs on performance
- **Codecov upload**: External service shouldn't block CI

## Security Considerations

- Test credentials are CI-only, never production secrets
- SARIF integration provides security findings in PR reviews
- Multiple scanning tools for defense in depth
- Secrets never logged or exposed in outputs

## Maintenance

### Adding New Checks

To add a new check:
1. Add as a new step in the appropriate job
2. Consider if it should be blocking or non-blocking
3. Update this documentation
4. Test on a feature branch first

### Updating Dependencies

- Python version: Update `PYTHON_VERSION` env variable
- PostgreSQL/Redis: Update service image versions
- Tool versions: Update action versions (e.g., `actions/checkout@v4`)

### Troubleshooting

Common issues and solutions:

1. **Coverage failure**: Run `uv run pytest --cov` locally to check coverage
2. **Ruff failures**: Run `uv run ruff format` and `uv run ruff check --fix`
3. **Service connection issues**: Check service health checks and ports
4. **Timeout issues**: Adjust job `timeout-minutes` if needed

## Related Documentation

- [CI/CD Implementation Plan](/docs/deployment/CI_CD_IMPLEMENTATION_PLAN.md)
- [Testing Strategy](/docs/testing/backend/README.md)
- [Security Requirements](/docs/security/README.md)