#!/bin/bash

################################################################################
# PazPaz Performance Check Script
# Version: 1.0.0
#
# Purpose:
#   Measure and analyze API response times to ensure performance meets SLA
#   targets (p95 <150ms for schedule endpoints).
#
# Features:
#   - Measures response time percentiles (p50, p95, p99)
#   - Tests critical endpoints
#   - Concurrent request testing
#   - Performance trend analysis
#   - SLA compliance reporting
#   - Database query performance checks
#
# Usage:
#   ./check-performance.sh [OPTIONS]
#
# Examples:
#   ./check-performance.sh --production --full
#   ./check-performance.sh --endpoint /api/v1/appointments --requests 1000
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
NUM_REQUESTS=100
CONCURRENCY=10
TEST_MODE="quick"
SPECIFIC_ENDPOINT=""
OUTPUT_FORMAT="human"
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

# Performance thresholds (in milliseconds)
readonly P50_TARGET=50
readonly P95_TARGET=150
readonly P99_TARGET=500

# Critical endpoints to test
declare -a CRITICAL_ENDPOINTS=(
    "/api/v1/health"
    "/api/v1/appointments"
    "/api/v1/schedule"
    "/api/v1/clients"
)

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

Measure PazPaz API performance and verify SLA compliance.

OPTIONS:
    --production       Test production environment
    --staging         Test staging environment
    --local           Test local environment (default)
    --quick           Quick test (100 requests)
    --standard        Standard test (500 requests)
    --full            Full test (1000 requests)
    --stress          Stress test (5000 requests)
    -e, --endpoint    Test specific endpoint
    -n, --requests    Number of requests (default: 100)
    -c, --concurrent  Concurrent requests (default: 10)
    --json            Output results as JSON
    --csv             Output results as CSV
    --verbose         Verbose output
    -h, --help        Show this help message

EXAMPLES:
    # Quick performance check
    $SCRIPT_NAME --quick

    # Production performance test
    $SCRIPT_NAME --production --standard

    # Test specific endpoint
    $SCRIPT_NAME --endpoint /api/v1/appointments --requests 1000

    # Stress test with high concurrency
    $SCRIPT_NAME --stress --concurrent 50

    # Export results as JSON
    $SCRIPT_NAME --full --json > results.json

EOF
}

################################################################################
# Performance Measurement Functions
################################################################################

measure_endpoint_performance() {
    local endpoint=$1
    local num_requests=$2
    local concurrency=$3
    local results_file="/tmp/pazpaz-perf-${TIMESTAMP}-$$"

    log_info "Testing $endpoint with $num_requests requests (concurrency: $concurrency)"

    # Create curl format file for timing
    cat > "${results_file}.format" <<EOF
%{time_total}
EOF

    # Run requests in parallel batches
    local batch_size=$concurrency
    local completed=0

    > "$results_file"  # Clear results file

    while [[ $completed -lt $num_requests ]]; do
        local remaining=$((num_requests - completed))
        local current_batch=$((remaining < batch_size ? remaining : batch_size))

        log_debug "Running batch: $completed-$((completed + current_batch))"

        # Launch batch of concurrent requests
        for ((i=0; i<current_batch; i++)); do
            {
                curl -s -o /dev/null \
                     -w "@${results_file}.format" \
                     --max-time 30 \
                     "${BASE_URL}${endpoint}" >> "$results_file" 2>/dev/null
            } &
        done

        # Wait for batch to complete
        wait

        completed=$((completed + current_batch))

        # Show progress
        if [[ $((completed % 100)) -eq 0 ]] || [[ $completed -eq $num_requests ]]; then
            echo -ne "\r  Progress: $completed/$num_requests requests completed"
        fi
    done
    echo ""  # New line after progress

    # Calculate statistics
    if [[ -f "$results_file" ]] && [[ -s "$results_file" ]]; then
        calculate_percentiles "$results_file" "$endpoint"
    else
        log_error "No results collected for $endpoint"
        return 1
    fi

    # Cleanup
    rm -f "$results_file" "${results_file}.format"
}

calculate_percentiles() {
    local results_file=$1
    local endpoint=$2

    # Convert to milliseconds and sort
    local sorted_file="${results_file}.sorted"
    awk '{print $1 * 1000}' "$results_file" | sort -n > "$sorted_file"

    local count=$(wc -l < "$sorted_file")

    if [[ $count -eq 0 ]]; then
        log_error "No valid measurements for $endpoint"
        return 1
    fi

    # Calculate percentiles
    local p50_index=$((count * 50 / 100))
    local p95_index=$((count * 95 / 100))
    local p99_index=$((count * 99 / 100))

    # Ensure indices are at least 1
    p50_index=$((p50_index < 1 ? 1 : p50_index))
    p95_index=$((p95_index < 1 ? 1 : p95_index))
    p99_index=$((p99_index < 1 ? 1 : p99_index))

    local p50=$(sed -n "${p50_index}p" "$sorted_file")
    local p95=$(sed -n "${p95_index}p" "$sorted_file")
    local p99=$(sed -n "${p99_index}p" "$sorted_file")
    local min=$(head -n1 "$sorted_file")
    local max=$(tail -n1 "$sorted_file")
    local avg=$(awk '{sum+=$1} END {print sum/NR}' "$sorted_file")

    # Format results
    printf "\n"
    printf "  %-15s: %s\n" "Endpoint" "$endpoint"
    printf "  %-15s: %d\n" "Requests" "$count"
    printf "  %-15s: %.2f ms\n" "Min" "$min"
    printf "  %-15s: %.2f ms\n" "Max" "$max"
    printf "  %-15s: %.2f ms\n" "Average" "$avg"
    printf "  %-15s: %.2f ms" "P50 (median)" "$p50"

    # Check P50 against target
    if (( $(echo "$p50 <= $P50_TARGET" | bc -l) )); then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${YELLOW}⚠${NC} (target: <${P50_TARGET}ms)"
    fi

    printf "  %-15s: %.2f ms" "P95" "$p95"

    # Check P95 against target
    if (( $(echo "$p95 <= $P95_TARGET" | bc -l) )); then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${RED}✗${NC} (target: <${P95_TARGET}ms)"
    fi

    printf "  %-15s: %.2f ms" "P99" "$p99"

    # Check P99 against target
    if (( $(echo "$p99 <= $P99_TARGET" | bc -l) )); then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${YELLOW}⚠${NC} (target: <${P99_TARGET}ms)"
    fi

    # Store results for summary
    echo "$endpoint,$count,$min,$max,$avg,$p50,$p95,$p99" >> "/tmp/pazpaz-perf-summary-$$"

    # Cleanup
    rm -f "$sorted_file"

    # Return status based on P95 target
    if (( $(echo "$p95 <= $P95_TARGET" | bc -l) )); then
        return 0
    else
        return 1
    fi
}

################################################################################
# Load Testing Functions
################################################################################

run_load_test() {
    local endpoint=$1
    local duration=${2:-30}  # seconds

    print_section "Load Test: $endpoint"

    log_info "Running ${duration}s load test..."

    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    local results_file="/tmp/pazpaz-load-${TIMESTAMP}-$$"
    local request_count=0
    local error_count=0

    > "$results_file"

    # Run continuous load for duration
    while [[ $(date +%s) -lt $end_time ]]; do
        # Launch concurrent requests
        for ((i=0; i<CONCURRENCY; i++)); do
            {
                local response_time=$(curl -s -o /dev/null -w "%{time_total}" \
                                          --max-time 5 \
                                          "${BASE_URL}${endpoint}" 2>/dev/null)

                if [[ $? -eq 0 ]]; then
                    echo "$response_time" >> "$results_file"
                else
                    ((error_count++))
                fi
            } &
        done

        wait
        request_count=$((request_count + CONCURRENCY))

        # Show progress
        local elapsed=$(($(date +%s) - start_time))
        echo -ne "\r  Time: ${elapsed}s, Requests: $request_count, Errors: $error_count"
    done
    echo ""

    # Calculate throughput
    local actual_duration=$(($(date +%s) - start_time))
    local throughput=$(echo "scale=2; $request_count / $actual_duration" | bc)

    echo ""
    echo "  Load Test Results:"
    echo "  Duration: ${actual_duration}s"
    echo "  Total Requests: $request_count"
    echo "  Errors: $error_count"
    echo "  Throughput: ${throughput} req/s"

    if [[ -s "$results_file" ]]; then
        calculate_percentiles "$results_file" "$endpoint (load)"
    fi

    # Cleanup
    rm -f "$results_file"
}

################################################################################
# Database Performance Check
################################################################################

check_database_performance() {
    print_section "Database Performance Check"

    if [[ "$ENVIRONMENT" == "local" ]]; then
        log_info "Checking database query performance..."

        # Test database connectivity
        local db_test=$(docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "SELECT 1" 2>/dev/null || echo "FAILED")

        if [[ "$db_test" != "FAILED" ]]; then
            log_success "Database connection successful"

            # Get slow queries
            log_info "Checking for slow queries (>100ms)..."

            docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
                SELECT
                    substring(query, 1, 50) as query_preview,
                    calls,
                    mean_exec_time::numeric(10,2) as avg_ms,
                    max_exec_time::numeric(10,2) as max_ms
                FROM pg_stat_statements
                WHERE mean_exec_time > 100
                ORDER BY mean_exec_time DESC
                LIMIT 5
            " 2>/dev/null || log_warning "pg_stat_statements not available"

            # Check connection pool
            log_info "Checking connection pool status..."

            docker exec pazpaz-db psql -U pazpaz -d pazpaz -c "
                SELECT
                    count(*) as connections,
                    state
                FROM pg_stat_activity
                WHERE datname = 'pazpaz'
                GROUP BY state
            " 2>/dev/null
        else
            log_warning "Could not connect to database"
        fi
    else
        log_info "Database checks only available in local environment"
    fi
}

################################################################################
# Cache Performance Check
################################################################################

check_cache_performance() {
    print_section "Cache Performance Check"

    if [[ "$ENVIRONMENT" == "local" ]]; then
        log_info "Checking Redis cache performance..."

        # Test Redis connectivity
        local redis_ping=$(docker exec pazpaz-redis redis-cli ping 2>/dev/null || echo "FAILED")

        if [[ "$redis_ping" == "PONG" ]]; then
            log_success "Redis connection successful"

            # Get cache stats
            local stats=$(docker exec pazpaz-redis redis-cli INFO stats 2>/dev/null)

            if [[ -n "$stats" ]]; then
                local hits=$(echo "$stats" | grep "keyspace_hits:" | cut -d: -f2 | tr -d '\r')
                local misses=$(echo "$stats" | grep "keyspace_misses:" | cut -d: -f2 | tr -d '\r')

                if [[ -n "$hits" ]] && [[ -n "$misses" ]] && [[ $((hits + misses)) -gt 0 ]]; then
                    local hit_rate=$(echo "scale=2; $hits * 100 / ($hits + $misses)" | bc)
                    echo "  Cache Hit Rate: ${hit_rate}%"

                    if (( $(echo "$hit_rate >= 80" | bc -l) )); then
                        log_success "Cache hit rate is good"
                    elif (( $(echo "$hit_rate >= 50" | bc -l) )); then
                        log_warning "Cache hit rate could be improved"
                    else
                        log_error "Cache hit rate is poor"
                    fi
                else
                    log_info "No cache statistics available yet"
                fi
            fi

            # Check memory usage
            local memory=$(docker exec pazpaz-redis redis-cli INFO memory | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
            echo "  Memory Usage: $memory"
        else
            log_warning "Could not connect to Redis"
        fi
    else
        log_info "Cache checks only available in local environment"
    fi
}

################################################################################
# Summary Report
################################################################################

generate_summary_report() {
    print_header "Performance Test Summary"

    local summary_file="/tmp/pazpaz-perf-summary-$$"

    if [[ ! -f "$summary_file" ]]; then
        log_error "No performance data collected"
        return 1
    fi

    echo ""
    echo "Environment: $ENVIRONMENT"
    echo "Base URL: $BASE_URL"
    echo "Test Type: $TEST_MODE"
    echo "Total Requests: $NUM_REQUESTS per endpoint"
    echo "Concurrency: $CONCURRENCY"
    echo ""

    # Parse summary data
    local all_pass=true
    echo "Results by Endpoint:"
    echo "────────────────────────────────────────────────────────────"
    printf "%-30s %8s %8s %8s %s\n" "Endpoint" "P50 (ms)" "P95 (ms)" "P99 (ms)" "Status"
    echo "────────────────────────────────────────────────────────────"

    while IFS=',' read -r endpoint count min max avg p50 p95 p99; do
        local status="✓ PASS"
        local status_color="${GREEN}"

        if (( $(echo "$p95 > $P95_TARGET" | bc -l) )); then
            status="✗ FAIL"
            status_color="${RED}"
            all_pass=false
        elif (( $(echo "$p95 > $P95_TARGET * 0.8" | bc -l) )); then
            status="⚠ WARN"
            status_color="${YELLOW}"
        fi

        printf "%-30s %8.2f %8.2f %8.2f " "$endpoint" "$p50" "$p95" "$p99"
        echo -e "${status_color}${status}${NC}"
    done < "$summary_file"

    echo "────────────────────────────────────────────────────────────"
    echo ""

    # Overall verdict
    if [[ "$all_pass" == true ]]; then
        log_success "All endpoints meet performance SLA targets! ✓"
        echo ""
        echo "✅ System is performing within acceptable limits"
    else
        log_error "Some endpoints exceed performance SLA targets"
        echo ""
        echo "❌ Performance optimization needed"
        echo ""
        echo "Recommendations:"
        echo "  1. Review slow queries with EXPLAIN ANALYZE"
        echo "  2. Check for missing database indexes"
        echo "  3. Implement caching for frequently accessed data"
        echo "  4. Consider query optimization or denormalization"
        echo "  5. Profile application code for bottlenecks"
    fi

    # Export options
    if [[ "$OUTPUT_FORMAT" == "json" ]]; then
        export_json_results "$summary_file"
    elif [[ "$OUTPUT_FORMAT" == "csv" ]]; then
        export_csv_results "$summary_file"
    fi

    # Cleanup
    rm -f "$summary_file"
}

export_json_results() {
    local summary_file=$1

    echo ""
    echo "JSON Output:"
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"environment\": \"$ENVIRONMENT\","
    echo "  \"base_url\": \"$BASE_URL\","
    echo "  \"results\": ["

    local first=true
    while IFS=',' read -r endpoint count min max avg p50 p95 p99; do
        if [[ "$first" != true ]]; then
            echo ","
        fi
        echo -n "    {\"endpoint\": \"$endpoint\", \"p50\": $p50, \"p95\": $p95, \"p99\": $p99}"
        first=false
    done < "$summary_file"

    echo ""
    echo "  ]"
    echo "}"
}

export_csv_results() {
    local summary_file=$1

    echo ""
    echo "CSV Output:"
    echo "endpoint,requests,min_ms,max_ms,avg_ms,p50_ms,p95_ms,p99_ms"
    cat "$summary_file"
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
                shift
                ;;
            --staging)
                ENVIRONMENT="staging"
                BASE_URL="https://staging-api.pazpaz.com"
                shift
                ;;
            --local)
                ENVIRONMENT="local"
                BASE_URL="http://localhost:8000"
                shift
                ;;
            --quick)
                TEST_MODE="quick"
                NUM_REQUESTS=100
                shift
                ;;
            --standard)
                TEST_MODE="standard"
                NUM_REQUESTS=500
                shift
                ;;
            --full)
                TEST_MODE="full"
                NUM_REQUESTS=1000
                shift
                ;;
            --stress)
                TEST_MODE="stress"
                NUM_REQUESTS=5000
                CONCURRENCY=50
                shift
                ;;
            -e|--endpoint)
                SPECIFIC_ENDPOINT="$2"
                shift 2
                ;;
            -n|--requests)
                NUM_REQUESTS="$2"
                shift 2
                ;;
            -c|--concurrent)
                CONCURRENCY="$2"
                shift 2
                ;;
            --json)
                OUTPUT_FORMAT="json"
                shift
                ;;
            --csv)
                OUTPUT_FORMAT="csv"
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

    # Check dependencies
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi

    if ! command -v bc &> /dev/null; then
        log_error "bc is required but not installed"
        exit 1
    fi

    print_header "PazPaz Performance Check v$SCRIPT_VERSION"

    # Test endpoints
    if [[ -n "$SPECIFIC_ENDPOINT" ]]; then
        # Test specific endpoint
        print_section "Testing Specific Endpoint"
        measure_endpoint_performance "$SPECIFIC_ENDPOINT" "$NUM_REQUESTS" "$CONCURRENCY"
    else
        # Test all critical endpoints
        print_section "Testing Critical Endpoints"

        for endpoint in "${CRITICAL_ENDPOINTS[@]}"; do
            measure_endpoint_performance "$endpoint" "$NUM_REQUESTS" "$CONCURRENCY" || true
        done
    fi

    # Additional checks for local environment
    if [[ "$ENVIRONMENT" == "local" ]]; then
        check_database_performance
        check_cache_performance
    fi

    # Run load test for stress mode
    if [[ "$TEST_MODE" == "stress" ]]; then
        run_load_test "/api/v1/health" 30
    fi

    # Generate summary report
    generate_summary_report
}

# Cleanup on exit
trap 'rm -f /tmp/pazpaz-perf-*-$$' EXIT

# Execute main function
main "$@"