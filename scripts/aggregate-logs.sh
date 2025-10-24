#!/bin/bash

################################################################################
# PazPaz Log Aggregation and Viewing Script
# Version: 1.0.0
#
# Purpose:
#   Collect, aggregate, and view logs from all PazPaz services with filtering
#   and search capabilities for troubleshooting and monitoring.
#
# Features:
#   - Collects logs from all Docker containers
#   - Aggregates logs from multiple sources
#   - Filters by service, time range, and log level
#   - Searches for specific patterns
#   - Formats JSON logs for readability
#   - Exports logs for analysis
#   - HIPAA-compliant log handling
#
# Usage:
#   ./aggregate-logs.sh [OPTIONS]
#
# Examples:
#   ./aggregate-logs.sh --service api --level ERROR --since 1h
#   ./aggregate-logs.sh --search "authentication failed" --last 100
#   ./aggregate-logs.sh --export /tmp/pazpaz-logs.tar.gz
#
################################################################################

set -euo pipefail

# Script configuration
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_NAME=$(basename "$0")
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Default configuration
readonly LOG_BASE_DIR="/opt/pazpaz/logs"
readonly COMPOSE_PROJECT_NAME="pazpaz"
readonly TEMP_DIR="/tmp/pazpaz-logs-$$"

# Default filters
SERVICE="all"
LOG_LEVEL="all"
TIME_RANGE="1h"
LAST_LINES=0
SEARCH_PATTERN=""
FOLLOW_LOGS=false
EXPORT_PATH=""
FORMAT_OUTPUT=true
SHOW_STATS=false

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m' # No Color

# Log level colors
declare -A LEVEL_COLORS=(
    ["ERROR"]="${RED}"
    ["WARN"]="${YELLOW}"
    ["WARNING"]="${YELLOW}"
    ["INFO"]="${BLUE}"
    ["DEBUG"]="${GRAY}"
    ["TRACE"]="${GRAY}"
    ["FATAL"]="${RED}"
    ["CRITICAL"]="${RED}"
)

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}ℹ${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}✓${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_header() {
    echo "" >&2
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}" >&2
    echo -e "${CYAN}$1${NC}" >&2
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}" >&2
}

print_section() {
    echo "" >&2
    echo -e "${MAGENTA}▶ $1${NC}" >&2
    echo -e "${GRAY}$(printf '%.0s─' {1..60})${NC}" >&2
}

show_usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Aggregate and view logs from PazPaz services.

OPTIONS:
    -s, --service SERVICE    Filter by service (api|worker|nginx|db|redis|all)
    -l, --level LEVEL       Filter by log level (ERROR|WARN|INFO|DEBUG|all)
    -t, --since TIME        Show logs since TIME (e.g., 5m, 1h, 24h)
    -n, --last N           Show last N lines
    -g, --grep PATTERN     Search for pattern in logs
    -f, --follow           Follow log output (tail -f mode)
    -e, --export PATH      Export logs to tar.gz file
    --raw                  Don't format JSON logs
    --stats                Show log statistics
    -h, --help            Show this help message

SERVICES:
    api       - FastAPI backend service
    worker    - ARQ background worker
    nginx     - Reverse proxy
    db        - PostgreSQL database
    redis     - Cache and queue
    minio     - Object storage
    clamav    - Antivirus scanner
    frontend  - Vue.js application
    all       - All services (default)

LOG LEVELS:
    ERROR     - Error messages only
    WARN      - Warning and error messages
    INFO      - Informational messages and above
    DEBUG     - Debug messages and above
    all       - All log levels (default)

TIME FORMATS:
    5m        - Last 5 minutes
    1h        - Last 1 hour
    24h       - Last 24 hours
    2d        - Last 2 days
    7d        - Last 7 days

EXAMPLES:
    # Show all ERROR logs from the API in the last hour
    $SCRIPT_NAME --service api --level ERROR --since 1h

    # Follow all logs in real-time
    $SCRIPT_NAME --follow

    # Search for authentication failures
    $SCRIPT_NAME --grep "authentication failed"

    # Show last 100 lines from all services
    $SCRIPT_NAME --last 100

    # Export logs for the last 24 hours
    $SCRIPT_NAME --since 24h --export /tmp/logs.tar.gz

    # Show log statistics
    $SCRIPT_NAME --stats

EOF
}

################################################################################
# Log Collection Functions
################################################################################

get_container_name() {
    local service=$1
    case $service in
        api)      echo "pazpaz-api" ;;
        worker)   echo "pazpaz-arq-worker" ;;
        nginx)    echo "pazpaz-nginx" ;;
        db)       echo "pazpaz-db" ;;
        redis)    echo "pazpaz-redis" ;;
        minio)    echo "pazpaz-minio" ;;
        clamav)   echo "pazpaz-clamav" ;;
        frontend) echo "pazpaz-frontend" ;;
        *)        echo "" ;;
    esac
}

collect_docker_logs() {
    local service=$1
    local since=$2
    local last=$3
    local follow=$4

    local container=$(get_container_name "$service")

    if [[ -z "$container" ]]; then
        log_error "Unknown service: $service"
        return 1
    fi

    # Build docker logs command
    local cmd="docker logs"

    if [[ "$since" != "all" ]]; then
        cmd="$cmd --since $(date -d "-$since" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || date -v "-$since" '+%Y-%m-%dT%H:%M:%S')"
    fi

    if [[ $last -gt 0 ]]; then
        cmd="$cmd --tail $last"
    fi

    if [[ "$follow" == true ]]; then
        cmd="$cmd --follow"
    fi

    cmd="$cmd $container 2>&1"

    # Execute and capture logs
    eval "$cmd" 2>/dev/null || log_warning "Could not get logs for $container"
}

collect_all_logs() {
    local since=$1
    local last=$2
    local follow=$3

    local services=("api" "worker" "nginx" "db" "redis" "minio" "clamav" "frontend")

    for service in "${services[@]}"; do
        local container=$(get_container_name "$service")

        # Check if container is running
        if docker ps --format "{{.Names}}" | grep -q "^$container$"; then
            log_info "Collecting logs from $service..."
            collect_docker_logs "$service" "$since" "$last" "$follow"
        else
            log_warning "Container $container is not running"
        fi
    done
}

################################################################################
# Log Filtering Functions
################################################################################

filter_by_level() {
    local level=$1

    if [[ "$level" == "all" ]]; then
        cat
        return
    fi

    # Create regex pattern for log levels
    local pattern=""
    case $level in
        ERROR)
            pattern="ERROR|FATAL|CRITICAL|SEVERE"
            ;;
        WARN)
            pattern="WARN|WARNING|ERROR|FATAL|CRITICAL|SEVERE"
            ;;
        INFO)
            pattern="INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|SEVERE"
            ;;
        DEBUG)
            pattern="DEBUG|TRACE|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|SEVERE"
            ;;
    esac

    grep -E "$pattern" || true
}

filter_by_pattern() {
    local pattern=$1

    if [[ -z "$pattern" ]]; then
        cat
        return
    fi

    grep -i "$pattern" || true
}

################################################################################
# Log Formatting Functions
################################################################################

format_json_log() {
    while IFS= read -r line; do
        # Try to parse as JSON
        if echo "$line" | jq -e . >/dev/null 2>&1; then
            # It's valid JSON - format it nicely
            local timestamp=$(echo "$line" | jq -r '.time // .timestamp // .["@timestamp"] // ""' 2>/dev/null)
            local level=$(echo "$line" | jq -r '.level // .severity // .log_level // "INFO"' 2>/dev/null | tr '[:lower:]' '[:upper:]')
            local message=$(echo "$line" | jq -r '.message // .msg // .log // ""' 2>/dev/null)
            local service=$(echo "$line" | jq -r '.service // .container_name // .attrs.service // ""' 2>/dev/null)

            # Get color for log level
            local color="${LEVEL_COLORS[$level]:-$NC}"

            # Format output
            if [[ -n "$timestamp" ]]; then
                echo -e "${GRAY}[$timestamp]${NC} ${color}[$level]${NC} ${CYAN}[$service]${NC} $message"
            else
                echo -e "${color}[$level]${NC} $message"
            fi
        else
            # Not JSON - output as-is
            echo "$line"
        fi
    done
}

format_logs() {
    if [[ "$FORMAT_OUTPUT" == true ]]; then
        format_json_log
    else
        cat
    fi
}

################################################################################
# Log Statistics Functions
################################################################################

show_log_statistics() {
    print_section "Log Statistics"

    local temp_file="/tmp/pazpaz-log-stats-$$"

    # Collect logs for statistics
    log_info "Collecting logs for analysis..."

    if [[ "$SERVICE" == "all" ]]; then
        collect_all_logs "$TIME_RANGE" 0 false > "$temp_file" 2>/dev/null
    else
        collect_docker_logs "$SERVICE" "$TIME_RANGE" 0 false > "$temp_file" 2>/dev/null
    fi

    # Total lines
    local total_lines=$(wc -l < "$temp_file")
    echo "Total log entries: $total_lines"
    echo ""

    # Log levels distribution
    echo "Log Level Distribution:"
    echo "  ERROR:   $(grep -c -E "ERROR|FATAL|CRITICAL" "$temp_file" || echo 0)"
    echo "  WARNING: $(grep -c -E "WARN|WARNING" "$temp_file" || echo 0)"
    echo "  INFO:    $(grep -c -E "INFO" "$temp_file" || echo 0)"
    echo "  DEBUG:   $(grep -c -E "DEBUG|TRACE" "$temp_file" || echo 0)"
    echo ""

    # Top error messages
    echo "Top Error Messages:"
    grep -E "ERROR|FATAL|CRITICAL" "$temp_file" 2>/dev/null | \
        sed 's/.*ERROR[[:space:]]*//; s/.*FATAL[[:space:]]*//; s/.*CRITICAL[[:space:]]*//' | \
        sort | uniq -c | sort -rn | head -5 | \
        while read count msg; do
            echo "  $count: ${msg:0:60}..."
        done
    echo ""

    # Service distribution (if all services)
    if [[ "$SERVICE" == "all" ]]; then
        echo "Log Distribution by Service:"
        for svc in api worker nginx db redis minio clamav frontend; do
            local container=$(get_container_name "$svc")
            local count=$(grep -c "$container" "$temp_file" 2>/dev/null || echo 0)
            if [[ $count -gt 0 ]]; then
                printf "  %-12s: %d\n" "$svc" "$count"
            fi
        done
        echo ""
    fi

    # Time distribution (last 24h by hour)
    if command -v awk &>/dev/null; then
        echo "Hourly Distribution (last 24h):"
        awk '{
            match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}/, arr)
            if (arr[0]) {
                hour = substr(arr[0], 12, 2)
                hours[hour]++
            }
        }
        END {
            for (h=0; h<24; h++) {
                hh = sprintf("%02d", h)
                count = hours[hh] ? hours[hh] : 0
                printf "  %s:00 : %d\n", hh, count
            }
        }' "$temp_file" | tail -12
    fi

    # Cleanup
    rm -f "$temp_file"
}

################################################################################
# Log Export Functions
################################################################################

export_logs() {
    local export_path=$1

    print_section "Exporting Logs"

    # Create temporary directory
    mkdir -p "$TEMP_DIR"

    log_info "Collecting logs for export..."

    # Collect logs from each service
    local services=("api" "worker" "nginx" "db" "redis" "minio" "clamav" "frontend")

    for service in "${services[@]}"; do
        local container=$(get_container_name "$service")

        if docker ps -a --format "{{.Names}}" | grep -q "^$container$"; then
            log_info "Exporting logs from $service..."
            docker logs "$container" --since "$(date -d "-$TIME_RANGE" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || date -v "-$TIME_RANGE" '+%Y-%m-%dT%H:%M:%S')" \
                > "$TEMP_DIR/${service}.log" 2>&1 || true
        fi
    done

    # Collect file-based logs if they exist
    if [[ -d "$LOG_BASE_DIR" ]]; then
        log_info "Collecting file-based logs..."
        find "$LOG_BASE_DIR" -type f -name "*.log" -mtime -7 -exec cp {} "$TEMP_DIR/" \; 2>/dev/null || true
    fi

    # Create metadata file
    cat > "$TEMP_DIR/metadata.txt" <<EOF
PazPaz Log Export
=================
Export Date: $(date -Iseconds)
Time Range: $TIME_RANGE
Services: ${services[*]}
Host: $(hostname)
Export Tool: $SCRIPT_NAME v$SCRIPT_VERSION
EOF

    # Create tarball
    log_info "Creating archive: $export_path"
    tar -czf "$export_path" -C "$TEMP_DIR" . 2>/dev/null

    # Cleanup
    rm -rf "$TEMP_DIR"

    log_success "Logs exported to: $export_path"
    log_info "Archive size: $(du -h "$export_path" | cut -f1)"
}

################################################################################
# Main Viewing Function
################################################################################

view_logs() {
    # Collect logs based on service selection
    if [[ "$SERVICE" == "all" ]]; then
        collect_all_logs "$TIME_RANGE" "$LAST_LINES" "$FOLLOW_LOGS"
    else
        collect_docker_logs "$SERVICE" "$TIME_RANGE" "$LAST_LINES" "$FOLLOW_LOGS"
    fi
}

################################################################################
# Main Function
################################################################################

main() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--service)
                SERVICE="$2"
                shift 2
                ;;
            -l|--level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            -t|--since)
                TIME_RANGE="$2"
                shift 2
                ;;
            -n|--last)
                LAST_LINES="$2"
                shift 2
                ;;
            -g|--grep)
                SEARCH_PATTERN="$2"
                shift 2
                ;;
            -f|--follow)
                FOLLOW_LOGS=true
                shift
                ;;
            -e|--export)
                EXPORT_PATH="$2"
                shift 2
                ;;
            --raw)
                FORMAT_OUTPUT=false
                shift
                ;;
            --stats)
                SHOW_STATS=true
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

    # Validate service
    if [[ "$SERVICE" != "all" ]]; then
        local valid_services=("api" "worker" "nginx" "db" "redis" "minio" "clamav" "frontend")
        if [[ ! " ${valid_services[@]} " =~ " ${SERVICE} " ]]; then
            log_error "Invalid service: $SERVICE"
            echo "Valid services: ${valid_services[*]}" >&2
            exit 1
        fi
    fi

    # Handle different modes
    if [[ -n "$EXPORT_PATH" ]]; then
        # Export mode
        export_logs "$EXPORT_PATH"
    elif [[ "$SHOW_STATS" == true ]]; then
        # Statistics mode
        show_log_statistics
    else
        # Viewing mode
        print_header "PazPaz Log Aggregator v$SCRIPT_VERSION"

        # Show current filters
        echo "" >&2
        echo "Filters:" >&2
        echo "  Service: $SERVICE" >&2
        echo "  Level: $LOG_LEVEL" >&2
        echo "  Time: $TIME_RANGE" >&2
        if [[ -n "$SEARCH_PATTERN" ]]; then
            echo "  Search: $SEARCH_PATTERN" >&2
        fi
        if [[ $LAST_LINES -gt 0 ]]; then
            echo "  Lines: Last $LAST_LINES" >&2
        fi
        if [[ "$FOLLOW_LOGS" == true ]]; then
            echo "  Mode: Following (Ctrl+C to stop)" >&2
        fi
        echo "" >&2

        # View and filter logs
        view_logs | filter_by_level "$LOG_LEVEL" | filter_by_pattern "$SEARCH_PATTERN" | format_logs
    fi
}

# Cleanup on exit
trap 'rm -rf "$TEMP_DIR"' EXIT

# Execute main function
main "$@"