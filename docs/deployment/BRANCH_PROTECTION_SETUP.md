# Branch Protection Setup Guide

> Last Updated: 2025-10-23

This guide provides step-by-step instructions for configuring branch protection rules on the `main` branch to ensure code quality and security through required CI checks.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Step-by-Step Configuration](#step-by-step-configuration)
- [Configuration Checklist](#configuration-checklist)
- [Validation Steps](#validation-steps)
- [Troubleshooting](#troubleshooting)
- [Advanced Settings](#advanced-settings)

## Prerequisites

Before configuring branch protection, ensure you have:

1. **Repository Admin Access**: Branch protection requires admin or maintainer permissions
2. **CI Workflows Deployed**: Both backend and frontend CI workflows must be committed to the repository
3. **Initial Test Run**: Run both CI workflows at least once to register status checks with GitHub

## Step-by-Step Configuration

### 1. Navigate to Branch Protection Settings

1. Go to your repository on GitHub
2. Click on **Settings** tab (gear icon)
3. In the left sidebar, click **Branches** under the "Code and automation" section
4. Click **Add rule** or **Add branch protection rule** button

### 2. Configure Branch Name Pattern

In the "Branch name pattern" field, enter:
```
main
```

This will apply the protection rules specifically to the `main` branch.

### 3. Configure Required Status Checks

#### Enable Status Checks
1. ✅ Check **Require status checks to pass before merging**
2. ✅ Check **Require branches to be up to date before merging**

#### Add Required Status Checks
Search for and add these specific status checks:

**Backend CI Checks:**
- `CI Success` - The summary job from backend-ci.yml that ensures all backend checks pass

**Frontend CI Checks:**
- `CI Success Gate` - The summary job from frontend-ci.yml that ensures all frontend checks pass

> **Note**: If these checks don't appear in the search, trigger both CI workflows by pushing a small change. GitHub needs to see the checks run at least once.

### 4. Configure Pull Request Reviews

1. ✅ Check **Require a pull request before merging**
2. Configure review requirements:
   - **Required approving reviews**: Set to `1` (or more for larger teams)
   - ✅ Check **Dismiss stale pull request approvals when new commits are pushed**
   - ✅ Check **Require review from CODEOWNERS** (if CODEOWNERS file exists)
   - ✅ Check **Require approval of the most recent reviewable push**

### 5. Configure Additional Protection

#### Enforce for Administrators
- ⚠️ Consider checking **Include administrators** for maximum protection
- Leave unchecked if admins need emergency bypass capability

#### Restrict Push Access
1. ✅ Check **Restrict who can push to matching branches** (optional)
2. Add specific users or teams who can push directly to main
3. This prevents accidental direct pushes to main

#### Additional Security Settings
- ✅ Check **Require signed commits** (if team uses GPG signing)
- ✅ Check **Require linear history** (enforces rebasing over merge commits)
- ✅ Check **Require deployments to succeed** (if deployment workflows exist)
- ✅ Check **Lock branch** (prevents any changes - use only for archived branches)

### 6. Configure Force Push Protection

1. ✅ Check **Do not allow force pushes**
   - Prevents history rewriting on the main branch
   - Critical for maintaining audit trail

2. ✅ Check **Do not allow deletions**
   - Prevents accidental branch deletion
   - Ensures main branch persistence

### 7. Save Protection Rules

1. Review all settings
2. Click **Create** or **Save changes** button at the bottom
3. GitHub will validate and apply the rules immediately

## Configuration Checklist

Use this checklist to ensure all critical settings are configured:

### Essential Settings
- [ ] Branch name pattern set to `main`
- [ ] **Require status checks to pass** enabled
- [ ] Backend CI check (`CI Success`) added and required
- [ ] Frontend CI check (`CI Success Gate`) added and required
- [ ] **Require branches to be up to date** enabled
- [ ] **Require pull request reviews** enabled
- [ ] Minimum 1 approval required
- [ ] **Dismiss stale reviews** enabled
- [ ] **Do not allow force pushes** enabled
- [ ] **Do not allow deletions** enabled

### Recommended Settings
- [ ] **Require conversation resolution** before merging
- [ ] **Require linear history** (if team prefers rebase workflow)
- [ ] **Include administrators** (for maximum protection)
- [ ] **Restrict who can push** (limit to senior developers/leads)

### Optional Settings
- [ ] **Require signed commits** (if using GPG signing)
- [ ] **Require deployments to succeed** (if using GitHub deployments)
- [ ] **Require CODEOWNERS review** (if CODEOWNERS file exists)

## Validation Steps

After configuring branch protection, validate it's working correctly:

### 1. Test Protected Branch Block

1. Try to push directly to main (should fail):
   ```bash
   git checkout main
   echo "test" >> test.txt
   git add test.txt
   git commit -m "test: direct push"
   git push origin main
   ```

   Expected error:
   ```
   ! [remote rejected] main -> main (protected branch hook declined)
   ```

### 2. Test Pull Request Flow

1. Create a test branch and PR:
   ```bash
   git checkout -b test/branch-protection
   echo "test" >> test-protection.txt
   git add test-protection.txt
   git commit -m "test: branch protection"
   git push origin test/branch-protection
   ```

2. Open a pull request to main
3. Verify:
   - [ ] CI checks are running automatically
   - [ ] Merge button is disabled until checks pass
   - [ ] Review is required before merge
   - [ ] Cannot merge until branch is up to date

### 3. Test Force Push Protection

1. Attempt a force push (should fail):
   ```bash
   git checkout main
   git commit --amend -m "amended commit"
   git push --force origin main
   ```

   Expected error:
   ```
   ! [remote rejected] main -> main (protected branch hook declined)
   ```

### 4. Verify Status Checks

1. Open a PR that will fail CI (e.g., with a linting error)
2. Verify the merge button shows "Required checks must pass"
3. Fix the issue and push
4. Verify checks re-run and merge is allowed after passing

## Troubleshooting

### Status Checks Not Appearing

**Problem**: Required status checks don't appear in the search box

**Solutions**:
1. Trigger both CI workflows by pushing a change:
   ```bash
   git checkout -b trigger-ci
   echo "# Trigger CI" >> backend/README.md
   echo "# Trigger CI" >> frontend/README.md
   git add .
   git commit -m "chore: trigger CI workflows"
   git push origin trigger-ci
   ```
2. Open a PR and wait for checks to complete
3. Return to branch protection settings - checks should now appear

### Administrators Can Still Push

**Problem**: Admins can bypass protection rules

**Solution**: Enable "Include administrators" in the protection rules. Note this will apply to ALL administrators, including yourself.

### CI Checks Always Failing

**Problem**: Required checks consistently fail, blocking all merges

**Solutions**:
1. Review CI workflow logs to identify issues
2. Ensure all required secrets are configured (see [GitHub Secrets Setup](./github-secrets-setup.md))
3. Temporarily make failing checks non-required while fixing
4. Consider adding `continue-on-error: true` to flaky optional checks

### Wrong Status Check Names

**Problem**: Selected wrong status checks or check names changed

**Solution**:
1. Go to a recent PR and note exact check names
2. Update branch protection with correct names:
   - Backend: `CI Success`
   - Frontend: `CI Success Gate`

### Cannot Merge Despite Passing Checks

**Problem**: All checks pass but merge is still blocked

**Common Causes**:
1. **Branch out of date**: Click "Update branch" button in PR
2. **Awaiting reviews**: Ensure required reviews are approved
3. **Unresolved conversations**: Resolve all PR comments if required
4. **CODEOWNERS not approved**: Check if CODEOWNERS review is pending

## Advanced Settings

### Custom Status Check Patterns

For more granular control, you can require specific job checks:

**Backend Jobs**:
- `Test & Quality Checks` - Core testing and linting
- `Security Scanning` - Trivy vulnerability scanning
- `OpenAPI Specification Validation` - API contract validation
- `CodeQL Security Analysis` - Static analysis
- `Dependency Security Check` - Dependency vulnerabilities

**Frontend Jobs**:
- `Test & Quality Checks` - Linting, formatting, tests, build
- `Security Scanning` - npm audit and Trivy
- `License Compliance` - License checking

### Bypass Protection for Emergencies

If you need emergency bypass capability:

1. Create a separate `emergency-bypass` team
2. Grant this team admin access
3. Do NOT check "Include administrators"
4. Document emergency bypass procedures
5. Audit all emergency bypasses

### Automated Enforcement with CODEOWNERS

Create a `.github/CODEOWNERS` file to automatically request reviews:

```
# Global owners
* @lead-developer @senior-developer

# Backend specific
/backend/ @backend-team
/backend/src/pazpaz/security/ @security-team

# Frontend specific
/frontend/ @frontend-team
/frontend/src/components/ @ui-team

# Infrastructure
/.github/ @devops-team
/docs/deployment/ @devops-team
docker-compose*.yml @devops-team
```

### Branch Protection via API

For automation, use GitHub API to configure protection:

```bash
curl -X PUT \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/OWNER/REPO/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": ["CI Success", "CI Success Gate"]
    },
    "enforce_admins": false,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews": true
    },
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false
  }'
```

## Related Documentation

- [CI Pipeline Documentation](./CI_PIPELINE.md) - Detailed CI workflow information
- [GitHub Secrets Setup](./github-secrets-setup.md) - Required secrets configuration
- [CI/CD Implementation Plan](./CI_CD_IMPLEMENTATION_PLAN.md) - Overall CI/CD strategy

## Security Considerations

- **Never disable protection** on main branch in production
- **Audit bypass events** if administrators are excluded
- **Rotate tokens** used for automated protection updates
- **Monitor failed push attempts** as potential security events
- **Review protection settings** quarterly for compliance

## Next Steps

After configuring branch protection:

1. Document your team's specific settings in your README
2. Train team members on the PR workflow
3. Set up branch protection for other important branches (develop, release/*)
4. Configure automated security scanning with Dependabot
5. Implement deployment protection rules for production