# GitHub Branch Protection Rules Documentation

**Last Updated:** 2025-10-23
**Status:** ✅ ACTIVE
**Branch:** main
**Repository:** yussieik/pazpaz

## Overview

This document outlines the comprehensive branch protection rules configured for the PazPaz repository's main branch. These rules enforce code quality, security scanning, and HIPAA compliance requirements for all changes to production code.

## Current Protection Rules

### ✅ Required Status Checks

**Status:** ENABLED
**Strict Mode:** YES (branch must be up-to-date before merging)

#### Required CI/CD Checks:
| Check Name | Purpose | Required | HIPAA Relevance |
|------------|---------|----------|-----------------|
| `test` | Test & Quality Checks | ✅ Yes | Ensures code reliability |
| `security` | Security Scanning | ✅ Yes | Validates security controls |
| `openapi-validation` | API Contract Validation | ✅ Yes | Maintains API integrity |
| `codeql` | CodeQL Security Analysis | ✅ Yes | Identifies vulnerabilities |
| `dependency-check` | Dependency Security | ✅ Yes | Prevents vulnerable dependencies |
| `ci-success` | Overall CI Success | ✅ Yes | Comprehensive validation |

### ✅ Pull Request Reviews

**Status:** ENABLED
**Configuration:**
- **Required Approvals:** 1 reviewer minimum
- **Dismiss Stale Reviews:** YES (new commits invalidate approvals)
- **Require Code Owner Review:** NO (CODEOWNERS file not configured)
- **Require Last Push Approval:** NO (author can merge after approval)

### ✅ Conversation Resolution

**Status:** ENABLED
- All pull request conversations must be resolved before merging
- Ensures all feedback is addressed

### ✅ Force Push Protection

**Status:** ENABLED
- **Allow Force Pushes:** NO ❌
- **Allow Deletions:** NO ❌
- Protects commit history integrity

### ✅ Additional Settings

| Setting | Status | Purpose |
|---------|--------|---------|
| Enforce for Admins | NO ⚠️ | Owner can override in emergencies |
| Require Linear History | NO | Allows merge commits for clarity |
| Lock Branch | NO | Branch remains open for PRs |
| Block Creations | NO | Normal PR workflow allowed |
| Require Signed Commits | NO | Can be enabled later for enhanced security |

## Rationale for Each Rule

### 1. Required Status Checks
**Why:** Prevents untested or insecure code from reaching production
- **Test Suite:** Catches bugs before production deployment
- **Security Scans:** Identifies vulnerabilities early in development
- **API Validation:** Ensures frontend-backend contract remains valid
- **CodeQL:** Deep security analysis for code-level vulnerabilities
- **Dependency Check:** Prevents supply chain attacks through vulnerable dependencies

### 2. Pull Request Reviews
**Why:** Ensures code quality through peer review
- Catches logic errors automated tests might miss
- Knowledge sharing across team
- Maintains code consistency and standards
- Required for HIPAA audit trail

### 3. Dismiss Stale Reviews
**Why:** Ensures reviewed code hasn't changed
- Prevents sneaking in unreviewed changes after approval
- Maintains integrity of review process
- Critical for security-sensitive changes

### 4. Conversation Resolution
**Why:** Ensures all concerns are addressed
- No unresolved questions or issues
- Clear communication trail for auditing
- Prevents overlooking important feedback

### 5. No Force Pushes or Deletions
**Why:** Maintains audit trail integrity
- HIPAA requires complete audit history
- Prevents accidental or malicious history rewriting
- Preserves evidence for compliance audits

## HIPAA Compliance Mapping

These branch protection rules directly support HIPAA Technical Safeguards:

### Access Controls - 45 CFR §164.312(a)(1)
✅ **Implemented via:**
- Required pull request reviews
- No direct pushes to main branch
- All changes tracked through PRs

### Audit Controls - 45 CFR §164.312(b)
✅ **Implemented via:**
- Complete git history preservation (no force pushes)
- Pull request review trail
- All conversations preserved
- Linked to audit logging system

### Integrity Controls - 45 CFR §164.312(c)(1)
✅ **Implemented via:**
- Required status checks ensure code integrity
- Security scanning prevents vulnerabilities
- Peer review catches logical errors
- No branch deletions allowed

### Person or Entity Authentication - 45 CFR §164.312(d)
✅ **Implemented via:**
- GitHub account authentication required
- Review approvals tied to authenticated users
- Audit trail shows who made each change

## Emergency Override Procedures

### When Override is Permitted

Emergency overrides should ONLY be used for:

1. **Critical Security Hotfix**
   - Active exploitation in production
   - Zero-day vulnerability patch
   - Data breach prevention

2. **Production Outage**
   - Service completely down
   - Data corruption risk
   - Patient safety impact

3. **Compliance Emergency**
   - Regulatory deadline
   - Audit finding requiring immediate fix

### Override Process

**⚠️ WARNING:** Only repository owner (yussieik) can override

1. **Document the emergency:**
   ```bash
   echo "Emergency: [Description]" > emergency-override-$(date +%Y%m%d-%H%M%S).md
   echo "Justification: [Why override needed]" >> emergency-override-*.md
   echo "Risk Assessment: [Potential impacts]" >> emergency-override-*.md
   ```

2. **Temporarily disable protection (if absolutely necessary):**
   ```bash
   # Save current rules first
   gh api repos/yussieik/pazpaz/branches/main/protection > protection-backup-$(date +%Y%m%d).json

   # Disable protection
   gh api -X DELETE repos/yussieik/pazpaz/branches/main/protection
   ```

3. **Apply emergency fix:**
   ```bash
   # Make your emergency changes
   git add .
   git commit -m "EMERGENCY: [Description] - Override authorized by [Name]"
   git push origin main
   ```

4. **Immediately re-enable protection:**
   ```bash
   gh api -X PUT repos/yussieik/pazpaz/branches/main/protection \
     --input scripts/branch-protection-rules.json
   ```

5. **Post-Emergency Audit:**
   - Create incident report in `/docs/operations/incidents/`
   - Review with team within 24 hours
   - Update runbooks if needed
   - Consider if emergency could have been avoided

### Post-Override Requirements

Within 24 hours of emergency override:

1. **Create Incident Report:**
   ```markdown
   # Incident Report: Emergency Override [Date]

   ## Timeline
   - Override initiated: [Time]
   - Fix applied: [Time]
   - Protection restored: [Time]

   ## Root Cause
   [What caused the emergency]

   ## Actions Taken
   [Detailed steps of override]

   ## Lessons Learned
   [How to prevent future occurrences]
   ```

2. **Retroactive Review:**
   - Create PR with emergency changes
   - Get post-facto review from team
   - Document in audit log

3. **Update Procedures:**
   - If emergency exposed gap in procedures
   - Update relevant runbooks
   - Consider adding automated tests

## Developer Workflow Changes

### Before Branch Protection

```bash
# Direct pushes were allowed
git push origin main
```

### After Branch Protection

All changes must go through pull requests:

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Make changes
git add .
git commit -m "feat: add new feature"

# 3. Push feature branch
git push origin feature/your-feature-name

# 4. Create pull request
gh pr create --title "feat: add new feature" \
  --body "Description of changes"

# 5. Wait for CI checks
gh pr checks

# 6. Request review
gh pr review --request @reviewer

# 7. After approval and checks pass, merge
gh pr merge --squash
```

### Common Scenarios

#### Updating Your Branch
When main has new commits:
```bash
git checkout main
git pull origin main
git checkout your-feature-branch
git rebase main
git push --force-with-lease origin your-feature-branch
```

#### Checking CI Status
```bash
# View all checks
gh pr checks

# View specific check details
gh pr checks --watch
```

#### Resolving Conversations
- Address all feedback in PR conversations
- Mark conversations as resolved in GitHub UI
- Cannot merge until all resolved

## Validation Checklist

### Pre-Merge Requirements
- [ ] All CI checks passing (green checkmarks)
- [ ] At least 1 approval from reviewer
- [ ] All PR conversations resolved
- [ ] Branch up-to-date with main
- [ ] No merge conflicts
- [ ] Security scans show no high/critical issues

### Post-Merge Validation
- [ ] Deployment successful
- [ ] Health checks passing
- [ ] No increase in error rates
- [ ] Performance metrics within targets
- [ ] Audit log entry created

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Branch out-of-date"
**Solution:** Rebase or merge main into your branch
```bash
git checkout your-branch
git rebase main
git push --force-with-lease
```

#### Issue: "Required status checks failing"
**Solution:** Check specific failing checks
```bash
gh pr checks
# Fix issues based on check output
```

#### Issue: "Waiting for approval"
**Solution:** Request review from team member
```bash
gh pr review --request @yussieik
```

#### Issue: "Conversations unresolved"
**Solution:** Address feedback and mark resolved in GitHub UI

#### Issue: "Cannot push to main"
**Solution:** This is expected! Create a pull request instead
```bash
gh pr create
```

## Monitoring and Metrics

### Success Metrics
- **PR Approval Time:** Target < 4 hours
- **CI Check Duration:** Target < 10 minutes
- **Override Frequency:** Target < 1 per month
- **Failed PR Percentage:** Target < 10%

### Monitoring Dashboard
Track branch protection effectiveness:
- Number of PRs merged per week
- Average time from PR to merge
- Number of failed status checks caught
- Emergency override frequency

## Team Communication

### Announcing Branch Protection

**Email/Slack Template:**
```
Subject: Branch Protection Enabled for Main Branch

Team,

As part of our security hardening and HIPAA compliance efforts,
branch protection rules are now active on the main branch.

Key Changes:
• All changes require pull requests (no direct pushes)
• CI checks must pass before merging
• 1 reviewer approval required
• All conversations must be resolved

See full documentation: docs/deployment/BRANCH_PROTECTION.md

Questions? Let me know!
```

### Training Resources
- GitHub's Pull Request Guide
- Our PR best practices
- CI/CD workflow documentation
- Emergency procedures training

## Maintenance

### Regular Reviews (Monthly)
- [ ] Review override incidents
- [ ] Analyze CI check effectiveness
- [ ] Update required checks list
- [ ] Review approval requirements
- [ ] Check for new GitHub features

### Updates Log

| Date | Change | Reason | Approved By |
|------|--------|--------|-------------|
| 2025-10-23 | Initial protection rules | HIPAA compliance, Task 3 of 4 | yussieik |

## Related Documentation

- [CI/CD Workflow Documentation](./backend-ci-workflow.md)
- [GitHub Secrets Management](./GITHUB_SECRETS.md)
- [Docker Security](./DOCKER_SECURITY.md)
- [Security Implementation Plan](/docs/SECURITY_FIRST_IMPLEMENTATION_PLAN.md)
- [HIPAA Compliance Guide](/docs/security/HIPAA_COMPLIANCE.md)

## Configuration Files

- **Branch Protection Rules:** `/scripts/branch-protection-rules.json`
- **CI Workflow:** `/.github/workflows/backend-ci.yml`
- **Security Scanning:** `/.github/workflows/security.yml`

## Contact

**Security Team:** security@pazpaz.health
**DevOps Lead:** yussieik@github
**Emergency Hotline:** [Configure in production]

---

*This document is part of PazPaz's HIPAA compliance documentation and must be kept up-to-date with any changes to branch protection rules.*