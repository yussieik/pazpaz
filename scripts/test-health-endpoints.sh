#!/bin/bash

################################################################################
# PazPaz Health Endpoints Test Script
# Version: 1.0.0
#
# Purpose:
#   Test and validate all health check endpoints to ensure they respond
#   correctly for uptime monitoring services.
#
# Features:
#   - Tests multiple health endpoints
#   - Measures response times
#   - Validates response content
#   - Checks SSL certificates
#   - Reports endpoint availability
#
# Usage:
#   ./test-health-endpoints.sh [--production] [--verbose]
#
################################################################################

set -euo pipefail

# Script configuration
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_NAME=$(basename "$0")
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default configuration
ENVIRONMENT="local"
BASE_URL="http://localhost:8000"
VERBOSE=false
TEST_SSL=false

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m' # No Color

# Test results
declare -A TEST_RESULTS
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

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

Test PazPaz health check endpoints for monitoring readiness.

OPTIONS:
    --production    Test production endpoints (https://api.pazpaz.com)
    --staging      Test staging endpoints
    --local        Test local endpoints (default)
    --verbose      Show detailed output
    --ssl          Test SSL certificate validity
    -h, --help     Show this help message

EXAMPLES:
    # Test local development
    $SCRIPT_NAME --local

    # Test production with SSL checks
    $SCRIPT_NAME --production --ssl

    # Verbose output for debugging
    $SCRIPT_NAME --production --verbose

EOF
}

################################################################################
# Test Functions
################################################################################

test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=$3
    local expected_content=$4
    local max_response_time=$5  # in milliseconds

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log_info "Testing $name: $url"

    # Create temporary files for response
    local response_file="/tmp/pazpaz-health-response-$$"
    local headers_file="/tmp/pazpaz-health-headers-$$"
    local timing_file="/tmp/pazpaz-health-timing-$$"

    # Timing format for curl
    cat > "$timing_file" <<EOF
{
  "time_namelookup": %{time_namelookup},
  "time_connect": %{time_connect},
  "time_appconnect": %{time_appconnect},
  "time_pretransfer": %{time_pretransfer},
  "time_redirect": %{time_redirect},
  "time_starttransfer": %{time_starttransfer},
  "time_total": %{time_total},
  "http_code": "%{http_code}",
  "size_download": %{size_download},
  "speed_download": %{speed_download}
}
EOF

    # Make the request
    local curl_exit_code=0
    curl -s \
         -o "$response_file" \
         -D "$headers_file" \
         -w "@$timing_file" \
         --max-time 30 \
         "$url" > "${timing_file}.result" 2>/dev/null || curl_exit_code=$?

    # Parse results
    local http_code=$(jq -r '.http_code' "${timing_file}.result" 2>/dev/null || echo "000")
    local total_time=$(jq -r '.time_total' "${timing_file}.result" 2>/dev/null || echo "0")
    local response_time_ms=$(echo "$total_time * 1000" | bc 2>/dev/null || echo "0")

    # Read response body
    local response_body=""
    if [[ -f "$response_file" ]]; then
        response_body=$(cat "$response_file")
    fi

    # Determine test result
    local test_passed=true
    local failure_reasons=()

    # Check curl exit code
    if [[ $curl_exit_code -ne 0 ]]; then
        test_passed=false
        failure_reasons+=("Connection failed (curl exit code: $curl_exit_code)")
    fi

    # Check HTTP status code
    if [[ "$http_code" != "$expected_status" ]]; then
        test_passed=false
        failure_reasons+=("Expected status $expected_status, got $http_code")
    fi

    # Check response content
    if [[ -n "$expected_content" ]] && [[ ! "$response_body" =~ $expected_content ]]; then
        test_passed=false
        failure_reasons+=("Expected content '$expected_content' not found")
    fi

    # Check response time
    if [[ $(echo "$response_time_ms > $max_response_time" | bc 2>/dev/null || echo 0) -eq 1 ]]; then
        test_passed=false
        failure_reasons+=("Response time ${response_time_ms}ms exceeds ${max_response_time}ms")
    fi

    # Report results
    if [[ "$test_passed" == true ]]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        TEST_RESULTS["$name"]="PASSED"
        log_success "$name: OK (${response_time_ms}ms)"

        if [[ "$VERBOSE" == true ]]; then
            log_debug "  Status: $http_code"
            log_debug "  Response time: ${response_time_ms}ms"
            log_debug "  Body: ${response_body:0:100}..."
        fi
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        TEST_RESULTS["$name"]="FAILED"
        log_error "$name: FAILED"

        for reason in "${failure_reasons[@]}"; do
            log_error "  - $reason"
        done

        if [[ "$VERBOSE" == true ]]; then
            log_debug "  Response: $response_body"
        fi
    fi

    # Cleanup
    rm -f "$response_file" "$headers_file" "$timing_file" "${timing_file}.result"

    return $([ "$test_passed" == true ] && echo 0 || echo 1)
}

test_ssl_certificate() {
    local domain=$1

    if [[ "$TEST_SSL" != true ]]; then
        return 0
    fi

    print_section "SSL Certificate Check"

    log_info "Checking SSL certificate for $domain"

    # Check certificate validity
    local cert_info=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)

    if [[ -z "$cert_info" ]]; then
        log_error "Could not retrieve SSL certificate"
        return 1
    fi

    # Parse dates
    local not_before=$(echo "$cert_info" | grep "notBefore" | cut -d= -f2)
    local not_after=$(echo "$cert_info" | grep "notAfter" | cut -d= -f2)

    log_info "Certificate valid from: $not_before"
    log_info "Certificate valid until: $not_after"

    # Check if certificate will expire soon (within 30 days)
    local expire_timestamp=$(date -d "$not_after" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$not_after" +%s)
    local current_timestamp=$(date +%s)
    local days_until_expiry=$(( (expire_timestamp - current_timestamp) / 86400 ))

    if [[ $days_until_expiry -lt 0 ]]; then
        log_error "Certificate has EXPIRED!"
        return 1
    elif [[ $days_until_expiry -lt 30 ]]; then
        log_warning "Certificate expires in $days_until_expiry days - renewal needed soon"
    else
        log_success "Certificate is valid for $days_until_expiry more days"
    fi

    # Check certificate chain
    log_info "Verifying certificate chain..."
    echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl verify 2>/dev/null && \
        log_success "Certificate chain is valid" || \
        log_warning "Certificate chain verification failed"

    return 0
}

################################################################################
# Main Test Suite
################################################################################

run_health_tests() {
    print_header "PazPaz Health Endpoint Tests v$SCRIPT_VERSION"

    log_info "Testing environment: $ENVIRONMENT"
    log_info "Base URL: $BASE_URL"
    echo ""

    # Basic Health Check
    print_section "Basic Health Checks"

    test_endpoint \
        "API Health" \
        "$BASE_URL/api/v1/health" \
        "200" \
        "healthy" \
        "3000"

    test_endpoint \
        "API Root" \
        "$BASE_URL/api/v1/" \
        "200" \
        "" \
        "3000"

    # Readiness Checks
    print_section "Readiness Checks"

    test_endpoint \
        "API Readiness" \
        "$BASE_URL/api/v1/health/ready" \
        "200" \
        "ready\|degraded" \
        "5000"

    # Component Health Checks
    print_section "Component Health Checks"

    test_endpoint \
        "Database Health" \
        "$BASE_URL/api/v1/health/db" \
        "200" \
        "database_connected" \
        "5000"

    test_endpoint \
        "Cache Health" \
        "$BASE_URL/api/v1/health/cache" \
        "200" \
        "redis_connected" \
        "3000"

    test_endpoint \
        "Storage Health" \
        "$BASE_URL/api/v1/health/storage" \
        "200" \
        "storage_available" \
        "5000"

    # Application Endpoints
    print_section "Application Endpoints"

    test_endpoint \
        "Web Application" \
        "${BASE_URL/api./}" \
        "200" \
        "PazPaz\|<!DOCTYPE html>" \
        "5000"

    test_endpoint \
        "API Documentation" \
        "$BASE_URL/docs" \
        "200" \
        "FastAPI\|Swagger" \
        "3000"

    # Authentication Endpoints
    print_section "Authentication Status"

    test_endpoint \
        "Auth Status" \
        "$BASE_URL/api/v1/auth/status" \
        "200\|401" \
        "" \
        "3000"

    # SSL Certificate Check (if enabled)
    if [[ "$TEST_SSL" == true ]] && [[ "$BASE_URL" =~ ^https ]]; then
        local domain=$(echo "$BASE_URL" | sed -E 's|https://([^/]+).*|\1|')
        test_ssl_certificate "$domain"
    fi
}

################################################################################
# Performance Test
################################################################################

run_performance_test() {
    print_section "Performance Test"

    log_info "Running performance test (100 requests)..."

    local endpoint="$BASE_URL/api/v1/health"
    local temp_file="/tmp/pazpaz-perf-$$"

    # Run 100 requests and collect times
    for i in {1..100}; do
        curl -s -o /dev/null -w "%{time_total}\n" "$endpoint" >> "$temp_file" 2>/dev/null &
        if [[ $((i % 10)) -eq 0 ]]; then
            wait  # Wait every 10 requests to avoid overwhelming
        fi
    done
    wait  # Wait for all remaining requests

    # Calculate statistics
    if [[ -f "$temp_file" ]]; then
        local count=$(wc -l < "$temp_file")
        local avg=$(awk '{sum+=$1} END {print sum/NR*1000}' "$temp_file")
        local p50=$(sort -n "$temp_file" | awk 'NR==50 {print $1*1000}')
        local p95=$(sort -n "$temp_file" | awk 'NR==95 {print $1*1000}')
        local p99=$(sort -n "$temp_file" | awk 'NR==99 {print $1*1000}')

        echo ""
        echo "Performance Results ($count requests):"
        printf "  Average: %.2fms\n" "$avg"
        printf "  P50: %.2fms\n" "$p50"
        printf "  P95: %.2fms\n" "$p95"
        printf "  P99: %.2fms\n" "$p99"

        # Check against SLA
        if [[ $(echo "$p95 < 150" | bc) -eq 1 ]]; then
            log_success "P95 response time meets SLA (<150ms)"
        else
            log_warning "P95 response time exceeds SLA target of 150ms"
        fi

        rm -f "$temp_file"
    fi
}

################################################################################
# Summary Report
################################################################################

print_summary() {
    print_header "Test Summary"

    echo ""
    echo "Total Tests: $TOTAL_TESTS"
    echo "Passed: $PASSED_TESTS"
    echo "Failed: $FAILED_TESTS"
    echo ""

    if [[ $FAILED_TESTS -eq 0 ]]; then
        log_success "All health endpoints are operational!"
        echo ""
        echo "✅ Ready for uptime monitoring configuration"
    else
        log_error "Some health endpoints are failing!"
        echo ""
        echo "Failed endpoints:"
        for endpoint in "${!TEST_RESULTS[@]}"; do
            if [[ "${TEST_RESULTS[$endpoint]}" == "FAILED" ]]; then
                echo "  ❌ $endpoint"
            fi
        done
        echo ""
        echo "Please fix these issues before configuring uptime monitoring."
    fi

    # Return appropriate exit code
    [[ $FAILED_TESTS -eq 0 ]] && exit 0 || exit 1
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
                TEST_SSL=true
                shift
                ;;
            --staging)
                ENVIRONMENT="staging"
                BASE_URL="https://staging.api.pazpaz.com"
                TEST_SSL=true
                shift
                ;;
            --local)
                ENVIRONMENT="local"
                BASE_URL="http://localhost:8000"
                TEST_SSL=false
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --ssl)
                TEST_SSL=true
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

    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi

    # Check if jq is available for JSON parsing
    if ! command -v jq &> /dev/null; then
        log_warning "jq is not installed - some features may be limited"
    fi

    # Check if bc is available for calculations
    if ! command -v bc &> /dev/null; then
        log_warning "bc is not installed - some calculations may be limited"
    fi

    # Run tests
    run_health_tests

    # Run performance test (only if basic tests pass)
    if [[ $FAILED_TESTS -eq 0 ]]; then
        run_performance_test
    fi

    # Print summary
    print_summary
}

# Execute main function
main "$@"