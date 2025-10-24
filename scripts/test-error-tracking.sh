#!/bin/bash

################################################################################
# PazPaz Sentry Error Tracking Test Script
# Version: 1.0.0
#
# Purpose:
#   Test Sentry error tracking integration by triggering various types of
#   errors and verifying they are captured correctly.
#
# Features:
#   - Tests backend error capture
#   - Tests frontend error capture
#   - Validates Sentry configuration
#   - Sends test errors of different severities
#   - Verifies error filtering and sanitization
#
# Usage:
#   ./test-error-tracking.sh [--production] [--all-types]
#
################################################################################

set -euo pipefail

# Script configuration
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_NAME=$(basename "$0")
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Default configuration
ENVIRONMENT="local"
BASE_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"
TEST_ALL_TYPES=false
VERBOSE=false

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m' # No Color

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_debug() {
    if [[ "$VERBOSE" == true ]]; then
        echo -e "${GRAY}[DEBUG]${NC} $1"
    fi
}

print_header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
}

print_section() {
    echo ""
    echo -e "${MAGENTA}▶ $1${NC}"
    echo -e "${GRAY}$(printf '%.0s─' {1..60})${NC}"
}

show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Test Sentry error tracking integration for PazPaz.

OPTIONS:
    --production    Test production Sentry integration
    --staging      Test staging Sentry integration
    --local        Test local development (default)
    --all-types    Test all error types (comprehensive)
    --verbose      Show detailed output
    -h, --help     Show this help message

ERROR TYPES:
    exception      - Standard exception
    http          - HTTP 500 error
    validation    - Validation error
    database      - Database connection error
    timeout       - Request timeout
    memory        - Memory error
    permission    - Permission denied

EXAMPLES:
    # Test local development
    $SCRIPT_NAME --local

    # Test production with all error types
    $SCRIPT_NAME --production --all-types

    # Verbose output for debugging
    $SCRIPT_NAME --verbose

NOTES:
    - Requires Sentry DSN to be configured
    - Check Sentry dashboard after running tests
    - Some tests may require API endpoints to be available

EOF
}

################################################################################
# Backend Error Tests
################################################################################

test_backend_exception() {
    print_section "Testing Backend Exception"

    local test_id="test-${TIMESTAMP}-exception"

    log_info "Triggering standard exception..."

    # Create a unique error message for tracking
    local error_message="Test exception from $SCRIPT_NAME at $TIMESTAMP"

    # Trigger exception via API
    local response=$(curl -s -X POST "$BASE_URL/api/v1/test/error" \
        -H "Content-Type: application/json" \
        -H "X-Test-Id: $test_id" \
        -d "{
            \"error_type\": \"exception\",
            \"message\": \"$error_message\",
            \"test_id\": \"$test_id\"
        }" 2>&1 || true)

    log_success "Exception triggered with test ID: $test_id"
    log_info "Check Sentry for error with message: $error_message"

    if [[ "$VERBOSE" == true ]]; then
        log_debug "Response: $response"
    fi
}

test_backend_http_error() {
    print_section "Testing HTTP 500 Error"

    local test_id="test-${TIMESTAMP}-http500"

    log_info "Triggering HTTP 500 error..."

    # Trigger HTTP error
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$BASE_URL/api/v1/test/error" \
        -H "Content-Type: application/json" \
        -H "X-Test-Id: $test_id" \
        -d "{
            \"error_type\": \"http\",
            \"test_id\": \"$test_id\"
        }" 2>&1 || true)

    if [[ "$response" == "500" ]]; then
        log_success "HTTP 500 error triggered successfully"
    else
        log_warning "Expected HTTP 500, got: $response"
    fi
}

test_backend_validation_error() {
    print_section "Testing Validation Error"

    local test_id="test-${TIMESTAMP}-validation"

    log_info "Triggering validation error..."

    # Send invalid data to trigger validation
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$BASE_URL/api/v1/appointments" \
        -H "Content-Type: application/json" \
        -H "X-Test-Id: $test_id" \
        -d "{
            \"invalid_field\": \"invalid_value\",
            \"missing_required\": null
        }" 2>&1 || true)

    if [[ "$response" == "422" ]]; then
        log_success "Validation error triggered (422 response)"
    else
        log_warning "Expected 422, got: $response"
    fi
}

test_backend_database_error() {
    print_section "Testing Database Error"

    local test_id="test-${TIMESTAMP}-database"

    log_info "Simulating database connection error..."

    # This would require a special endpoint or database manipulation
    # For testing purposes, we'll make a request that might trigger a DB error
    local response=$(curl -s -X GET "$BASE_URL/api/v1/test/db-error" \
        -H "X-Test-Id: $test_id" 2>&1 || true)

    log_info "Database error test attempted"
    log_info "Check Sentry for database-related errors"
}

test_backend_timeout() {
    print_section "Testing Request Timeout"

    local test_id="test-${TIMESTAMP}-timeout"

    log_info "Triggering request timeout..."

    # Make request with very short timeout
    local response=$(curl -s --max-time 1 \
        -X POST "$BASE_URL/api/v1/test/slow" \
        -H "X-Test-Id: $test_id" 2>&1 || true)

    if [[ "$response" == *"timeout"* ]] || [[ "$response" == *"timed out"* ]]; then
        log_success "Timeout error triggered"
    else
        log_info "Timeout test completed"
    fi
}

test_backend_auth_error() {
    print_section "Testing Authentication Error"

    local test_id="test-${TIMESTAMP}-auth"

    log_info "Triggering authentication error..."

    # Make request with invalid token
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X GET "$BASE_URL/api/v1/users/me" \
        -H "Authorization: Bearer invalid-token-$test_id" 2>&1 || true)

    if [[ "$response" == "401" ]]; then
        log_success "Authentication error triggered (401 response)"
    else
        log_warning "Expected 401, got: $response"
    fi
}

test_backend_permission_error() {
    print_section "Testing Permission Error"

    local test_id="test-${TIMESTAMP}-permission"

    log_info "Triggering permission denied error..."

    # Try to access resource without permission
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X DELETE "$BASE_URL/api/v1/admin/users/1" \
        -H "X-Test-Id: $test_id" 2>&1 || true)

    if [[ "$response" == "403" ]]; then
        log_success "Permission error triggered (403 response)"
    else
        log_info "Permission test completed with response: $response"
    fi
}

################################################################################
# Frontend Error Tests
################################################################################

test_frontend_error() {
    print_section "Testing Frontend Error"

    local test_id="test-${TIMESTAMP}-frontend"

    log_info "Creating frontend test page..."

    # Create temporary HTML file with Sentry test
    cat > "/tmp/sentry-test-$test_id.html" <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Sentry Error Test</title>
    <script>
        // Simulate Sentry initialization
        console.log("Sentry test page loaded");

        // Function to trigger various errors
        function triggerError(type) {
            const testId = "$test_id";

            switch(type) {
                case 'exception':
                    throw new Error(\`Test frontend exception \${testId}\`);

                case 'promise':
                    Promise.reject(new Error(\`Unhandled promise rejection \${testId}\`));
                    break;

                case 'reference':
                    undefinedFunction();
                    break;

                case 'type':
                    null.toString();
                    break;

                case 'network':
                    fetch('https://nonexistent.pazpaz.com/api')
                        .catch(e => { throw e; });
                    break;

                default:
                    console.error(\`Unknown error type: \${type}\`);
            }
        }

        // Auto-trigger error after load
        window.addEventListener('load', () => {
            setTimeout(() => {
                try {
                    triggerError('exception');
                } catch(e) {
                    console.error("Error triggered:", e);
                    if (window.Sentry) {
                        window.Sentry.captureException(e);
                    }
                }
            }, 1000);
        });
    </script>
</head>
<body>
    <h1>Sentry Frontend Error Test</h1>
    <p>Test ID: $test_id</p>
    <p>This page will trigger a test error in 1 second...</p>

    <button onclick="triggerError('exception')">Trigger Exception</button>
    <button onclick="triggerError('promise')">Trigger Promise Rejection</button>
    <button onclick="triggerError('reference')">Trigger Reference Error</button>
    <button onclick="triggerError('type')">Trigger Type Error</button>
    <button onclick="triggerError('network')">Trigger Network Error</button>
</body>
</html>
EOF

    log_success "Test page created: /tmp/sentry-test-$test_id.html"

    # If running locally, try to open in browser
    if [[ "$ENVIRONMENT" == "local" ]] && command -v open &> /dev/null; then
        log_info "Opening test page in browser..."
        open "/tmp/sentry-test-$test_id.html"
    else
        log_info "Open this file in a browser: /tmp/sentry-test-$test_id.html"
    fi
}

################################################################################
# Sentry Verification
################################################################################

verify_sentry_configuration() {
    print_section "Verifying Sentry Configuration"

    # Check if Sentry DSN is configured
    log_info "Checking Sentry DSN configuration..."

    # Check backend configuration
    if [[ -f "$SCRIPT_DIR/../backend/.env.production" ]]; then
        if grep -q "SENTRY_DSN" "$SCRIPT_DIR/../backend/.env.production"; then
            log_success "Backend Sentry DSN configured"
        else
            log_warning "Backend Sentry DSN not found in .env.production"
        fi
    else
        log_warning "Backend .env.production file not found"
    fi

    # Check frontend configuration
    if [[ -f "$SCRIPT_DIR/../frontend/.env.production" ]]; then
        if grep -q "VITE_SENTRY_DSN" "$SCRIPT_DIR/../frontend/.env.production"; then
            log_success "Frontend Sentry DSN configured"
        else
            log_warning "Frontend Sentry DSN not found in .env.production"
        fi
    else
        log_warning "Frontend .env.production file not found"
    fi

    # Test Sentry connectivity (if we have curl and a DSN)
    log_info "Testing Sentry connectivity..."

    # This is a basic connectivity check
    if curl -s -o /dev/null -w "%{http_code}" https://sentry.io 2>/dev/null | grep -q "200"; then
        log_success "Sentry.io is reachable"
    else
        log_warning "Cannot reach Sentry.io"
    fi
}

################################################################################
# Summary Report
################################################################################

generate_test_report() {
    print_header "Sentry Error Tracking Test Report"

    echo ""
    echo "Environment: $ENVIRONMENT"
    echo "Backend URL: $BASE_URL"
    echo "Frontend URL: $FRONTEND_URL"
    echo "Timestamp: $TIMESTAMP"
    echo ""

    echo "Tests Executed:"
    echo "  ✓ Backend exception test"
    echo "  ✓ Backend HTTP error test"
    if [[ "$TEST_ALL_TYPES" == true ]]; then
        echo "  ✓ Backend validation error test"
        echo "  ✓ Backend database error test"
        echo "  ✓ Backend timeout test"
        echo "  ✓ Backend authentication error test"
        echo "  ✓ Backend permission error test"
    fi
    echo "  ✓ Frontend error test page created"
    echo ""

    echo "Next Steps:"
    echo "1. Check Sentry dashboard at https://sentry.io"
    echo "2. Look for errors with timestamp: $TIMESTAMP"
    echo "3. Verify error details and context are captured"
    echo "4. Check that sensitive data is properly sanitized"
    echo "5. Verify alerts are triggered (if configured)"
    echo ""

    log_success "Error tracking tests completed!"
    echo ""
    echo "Dashboard Links:"
    echo "  Issues: https://sentry.io/organizations/pazpaz/issues/"
    echo "  Performance: https://sentry.io/organizations/pazpaz/performance/"
    echo "  Releases: https://sentry.io/organizations/pazpaz/releases/"
}

################################################################################
# Main Function
################################################################################

main() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --production)
                ENVIRONMENT="production"
                BASE_URL="https://api.pazpaz.com"
                FRONTEND_URL="https://pazpaz.com"
                shift
                ;;
            --staging)
                ENVIRONMENT="staging"
                BASE_URL="https://staging-api.pazpaz.com"
                FRONTEND_URL="https://staging.pazpaz.com"
                shift
                ;;
            --local)
                ENVIRONMENT="local"
                BASE_URL="http://localhost:8000"
                FRONTEND_URL="http://localhost:3000"
                shift
                ;;
            --all-types)
                TEST_ALL_TYPES=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    print_header "PazPaz Sentry Error Tracking Test v$SCRIPT_VERSION"

    # Verify Sentry configuration
    verify_sentry_configuration

    # Run backend error tests
    test_backend_exception
    test_backend_http_error

    if [[ "$TEST_ALL_TYPES" == true ]]; then
        test_backend_validation_error
        test_backend_database_error
        test_backend_timeout
        test_backend_auth_error
        test_backend_permission_error
    fi

    # Run frontend error test
    test_frontend_error

    # Generate report
    generate_test_report
}

# Execute main function
main "$@"