#!/bin/bash

# Branch Protection Management Script for PazPaz
# Purpose: Enable, disable, or check branch protection rules
# HIPAA Compliance: Maintains audit trail and security controls

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REPO="yussieik/pazpaz"
BRANCH="main"
RULES_FILE="scripts/branch-protection-rules.json"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Function to check current protection status
check_protection() {
    echo "Checking branch protection status for $BRANCH..."

    if gh api repos/$REPO/branches/$BRANCH/protection 2>/dev/null; then
        print_status "Branch protection is ENABLED"
        echo ""
        echo "Current configuration:"
        gh api repos/$REPO/branches/$BRANCH/protection 2>/dev/null | jq '{
            required_checks: .required_status_checks.contexts,
            require_pr_reviews: .required_pull_request_reviews.required_approving_review_count,
            dismiss_stale_reviews: .required_pull_request_reviews.dismiss_stale_reviews,
            conversation_resolution: .required_conversation_resolution.enabled,
            allow_force_pushes: .allow_force_pushes.enabled,
            allow_deletions: .allow_deletions.enabled
        }'
    else
        print_warning "Branch protection is DISABLED"
    fi
}

# Function to enable protection
enable_protection() {
    echo "Enabling branch protection for $BRANCH..."

    if [ ! -f "$RULES_FILE" ]; then
        print_error "Rules file not found: $RULES_FILE"
        exit 1
    fi

    if gh api -X PUT repos/$REPO/branches/$BRANCH/protection --input "$RULES_FILE"; then
        print_status "Branch protection ENABLED successfully"
        echo ""
        echo "Protection rules applied:"
        echo "• Required status checks: test, security, openapi-validation, codeql, dependency-check, ci-success"
        echo "• Required PR reviews: 1 approval"
        echo "• Dismiss stale reviews: Yes"
        echo "• Require conversation resolution: Yes"
        echo "• Force pushes: Disabled"
        echo "• Branch deletion: Disabled"
    else
        print_error "Failed to enable branch protection"
        exit 1
    fi
}

# Function to disable protection (EMERGENCY ONLY)
disable_protection() {
    print_warning "WARNING: Disabling branch protection should only be done in emergencies!"
    echo ""
    read -p "Please provide justification for disabling protection: " justification

    if [ -z "$justification" ]; then
        print_error "Justification required. Aborting."
        exit 1
    fi

    # Log the emergency override
    timestamp=$(date +%Y%m%d-%H%M%S)
    log_file="emergency-override-$timestamp.log"

    {
        echo "Emergency Override Log"
        echo "====================="
        echo "Timestamp: $(date)"
        echo "User: $(gh api user | jq -r .login)"
        echo "Branch: $BRANCH"
        echo "Justification: $justification"
        echo ""
    } > "$log_file"

    # Backup current rules
    echo "Backing up current rules..."
    gh api repos/$REPO/branches/$BRANCH/protection > "protection-backup-$timestamp.json" 2>/dev/null || true

    # Disable protection
    echo "Disabling branch protection..."
    if gh api -X DELETE repos/$REPO/branches/$BRANCH/protection; then
        print_warning "Branch protection DISABLED"
        echo "Backup saved to: protection-backup-$timestamp.json"
        echo "Log saved to: $log_file"
        echo ""
        print_warning "IMPORTANT: Re-enable protection as soon as possible!"
        echo "Run: $0 enable"
    else
        print_error "Failed to disable branch protection"
        exit 1
    fi
}

# Function to validate CI job names
validate_ci_jobs() {
    echo "Validating CI job names against workflows..."

    required_checks=(
        "test"
        "security"
        "openapi-validation"
        "codeql"
        "dependency-check"
        "ci-success"
    )

    echo "Looking for workflow definitions..."
    for check in "${required_checks[@]}"; do
        if grep -r "name: $check" .github/workflows/ 2>/dev/null; then
            print_status "Found job: $check"
        else
            print_warning "Job not found in workflows: $check (may be defined differently)"
        fi
    done
}

# Function to test protection (attempt push)
test_protection() {
    echo "Testing branch protection..."
    echo ""

    # Create a test branch
    test_branch="test-protection-$(date +%s)"

    echo "Creating test branch: $test_branch"
    git checkout -b "$test_branch" 2>/dev/null

    # Try to push directly to main (should fail)
    echo "Attempting direct push to main (should fail)..."
    if git push origin HEAD:main 2>&1 | grep -q "protected branch"; then
        print_status "Protection working: Direct push blocked"
    else
        print_warning "Direct push might be allowed (check manually)"
    fi

    # Clean up
    git checkout main 2>/dev/null
    git branch -D "$test_branch" 2>/dev/null

    echo ""
    echo "To fully test protection:"
    echo "1. Create a pull request"
    echo "2. Verify CI checks are required"
    echo "3. Verify review is required"
    echo "4. Try to merge without approval (should fail)"
}

# Main script logic
case "${1:-}" in
    check|status)
        check_protection
        ;;
    enable|on)
        enable_protection
        ;;
    disable|off)
        disable_protection
        ;;
    validate)
        validate_ci_jobs
        ;;
    test)
        test_protection
        ;;
    help|--help|-h)
        echo "Branch Protection Management for PazPaz"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  check, status  - Check current protection status"
        echo "  enable, on     - Enable branch protection"
        echo "  disable, off   - Disable protection (EMERGENCY ONLY)"
        echo "  validate       - Validate CI job names"
        echo "  test           - Test if protection is working"
        echo "  help           - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 check        # Check current status"
        echo "  $0 enable       # Enable protection"
        echo "  $0 validate     # Validate CI jobs exist"
        ;;
    *)
        echo "Branch Protection Manager"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac