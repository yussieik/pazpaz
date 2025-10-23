# Branch Protection Migration Guide

**Effective Date:** 2025-10-23
**Impact:** All contributors to PazPaz repository

## What's Changed?

Branch protection rules are now active on the `main` branch. This means:

### ❌ You CAN NO LONGER:
- Push directly to main branch
- Force push to main
- Delete the main branch
- Merge without CI checks passing
- Merge without at least 1 approval
- Merge with unresolved conversations

### ✅ You MUST NOW:
- Create a feature branch for all changes
- Submit changes via pull request
- Wait for all CI checks to pass
- Get at least 1 approval from a reviewer
- Resolve all PR conversations
- Keep your branch up-to-date with main

## Quick Start Guide

### 1. Create Your Feature Branch

```bash
# Start from updated main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name
# OR for fixes:
git checkout -b fix/issue-description
```

### 2. Make Your Changes

```bash
# Work on your feature
code .  # or your preferred editor

# Commit your changes
git add .
git commit -m "feat: add new feature"
```

### 3. Push Your Branch

```bash
# Push to GitHub
git push origin feature/your-feature-name
```

### 4. Create Pull Request

#### Option A: Using GitHub CLI
```bash
gh pr create \
  --title "feat: your feature title" \
  --body "Description of changes"
```

#### Option B: Using GitHub Web
1. Go to https://github.com/yussieik/pazpaz
2. Click "Pull requests" → "New pull request"
3. Select your branch
4. Add title and description
5. Click "Create pull request"

### 5. Monitor CI Checks

```bash
# Watch CI status
gh pr checks --watch

# Or view in browser
gh pr view --web
```

### 6. Request Review

```bash
# Request review from specific person
gh pr review --request @yussieik

# Or use GitHub web interface
```

### 7. Address Feedback

If reviewers request changes:
```bash
# Make requested changes
git add .
git commit -m "fix: address review feedback"
git push origin feature/your-feature-name
```

### 8. Merge Your PR

Once approved and all checks pass:
```bash
# Squash and merge (recommended)
gh pr merge --squash --delete-branch

# Or use GitHub web interface
```

## Common Scenarios

### Updating Your Branch with Latest Main

```bash
# Option 1: Rebase (cleaner history)
git checkout feature/your-branch
git fetch origin
git rebase origin/main
git push --force-with-lease

# Option 2: Merge (simpler)
git checkout feature/your-branch
git fetch origin
git merge origin/main
git push
```

### Checking Why CI Failed

```bash
# View all check results
gh pr checks

# View specific workflow run
gh run view

# View logs for failed job
gh run view --log-failed
```

### Resolving Merge Conflicts

```bash
# Update your branch first
git fetch origin
git rebase origin/main

# Fix conflicts in your editor
# Then continue rebase
git add .
git rebase --continue

# Push resolved branch
git push --force-with-lease
```

## CI Checks Explained

Your PR must pass these checks:

| Check | Purpose | Typical Fix |
|-------|---------|------------|
| `test` | Unit & integration tests | Fix failing tests |
| `security` | Security scanning | Address vulnerabilities |
| `openapi-validation` | API contract validation | Update OpenAPI spec |
| `codeql` | Code security analysis | Fix security issues |
| `dependency-check` | Vulnerable dependencies | Update dependencies |
| `ci-success` | Overall CI status | Fix other failing checks |

## FAQ

### Q: I accidentally committed to main locally. What do I do?

```bash
# Create branch from your commits
git checkout -b feature/my-changes

# Reset main to origin
git checkout main
git reset --hard origin/main

# Push your feature branch
git push origin feature/my-changes

# Create PR
gh pr create
```

### Q: How do I update my PR after pushing more commits?

Just push to the same branch - the PR updates automatically:
```bash
git push origin feature/your-branch
```

### Q: Can I still work while waiting for review?

Yes! Create another branch for your next feature:
```bash
git checkout main
git pull origin main
git checkout -b feature/next-feature
```

### Q: What if I need to make an emergency fix?

Contact the repository owner (yussieik) who can temporarily disable protection if absolutely necessary. Document the emergency in `/docs/operations/incidents/`.

### Q: How long should I wait for a review?

- Target: Within 4 hours during business hours
- If urgent, message the reviewer directly
- For critical issues, escalate to repository owner

## Tips for Faster PR Approval

1. **Keep PRs small and focused** - One feature/fix per PR
2. **Write clear PR descriptions** - Explain what and why
3. **Include tests** - Show your code works
4. **Run checks locally first** - `uv run test` before pushing
5. **Respond to feedback quickly** - Keep momentum going
6. **Use draft PRs for WIP** - Get early feedback

## Getting Help

- **Documentation:** `/docs/deployment/BRANCH_PROTECTION.md`
- **Scripts:** `/scripts/manage-branch-protection.sh`
- **GitHub CLI Help:** `gh pr --help`
- **Repository Owner:** @yussieik

## Why This Change?

This change supports:
- **HIPAA Compliance** - Required audit trails and access controls
- **Code Quality** - Peer review catches issues early
- **Security** - Automated scanning prevents vulnerabilities
- **Stability** - CI checks prevent broken deployments
- **Knowledge Sharing** - Team learns from code reviews

---

*Remember: This change makes our codebase more secure and reliable. The initial adjustment period is worth the long-term benefits!*