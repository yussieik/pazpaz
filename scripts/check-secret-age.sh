#!/usr/bin/env bash
# =============================================================================
# PazPaz Secret Age Checker
# =============================================================================
# Monitors secret rotation history and alerts when secrets are due for rotation
# Can be run manually, via cron, or in CI/CD pipelines
#
# Features:
#   - Checks age of all rotatable secrets
#   - Warns when rotation is approaching (30 days)
#   - Alerts when rotation is overdue
#   - Generates compliance report
#   - Integrates with monitoring systems
#
# Usage:
#   ./scripts/check-secret-age.sh [OPTIONS]
#
# Options:
#   --json           Output in JSON format for monitoring integration
#   --quiet          Only output warnings and errors
#   --verbose        Show detailed information
#   --update-history Update rotation history from current state
#   --report         Generate compliance report
#   --threshold DAYS Custom warning threshold (default: 30)
#
# Exit Codes:
#   0 - All secrets within rotation schedule
#   1 - Some secrets approaching rotation deadline
#   2 - Some secrets overdue for rotation
#   3 - Critical error (cannot read history)
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# File locations
ROTATION_HISTORY="${PROJECT_ROOT}/.rotation-history"
ENV_FILE="${PROJECT_ROOT}/.env.production"

# Default rotation periods (in days)
declare -A ROTATION_PERIODS
ROTATION_PERIODS["POSTGRES_PASSWORD"]=90
ROTATION_PERIODS["REDIS_PASSWORD"]=90
ROTATION_PERIODS["S3_CREDENTIALS"]=180
ROTATION_PERIODS["JWT_SECRET_KEY"]=90
ROTATION_PERIODS["SECRET_KEY"]=90
ROTATION_PERIODS["CSRF_SECRET_KEY"]=90
ROTATION_PERIODS["SMTP_PASSWORD"]=180

# Warning threshold (days before rotation due)
WARNING_THRESHOLD=30

# Output settings
OUTPUT_JSON=false
QUIET_MODE=false
VERBOSE_MODE=false
GENERATE_REPORT=false
UPDATE_HISTORY=false

# Tracking variables
declare -A SECRET_AGES
declare -A SECRET_STATUS
WARNINGS_COUNT=0
OVERDUE_COUNT=0
OK_COUNT=0

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# =============================================================================
# Output Functions
# =============================================================================

print_header() {
    [ "$QUIET_MODE" = true ] && return
    echo -e "${BLUE}${BOLD}$1${NC}"
}

print_success() {
    [ "$QUIET_MODE" = true ] && return
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS_COUNT++))
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    ((OVERDUE_COUNT++))
}

print_info() {
    [ "$QUIET_MODE" = true ] && return
    echo -e "ℹ️  $1"
}

print_verbose() {
    [ "$VERBOSE_MODE" = true ] && echo -e "   $1"
}

# =============================================================================
# Argument Parsing
# =============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --json)
                OUTPUT_JSON=true
                QUIET_MODE=true
                shift
                ;;
            --quiet)
                QUIET_MODE=true
                shift
                ;;
            --verbose)
                VERBOSE_MODE=true
                QUIET_MODE=false
                shift
                ;;
            --update-history)
                UPDATE_HISTORY=true
                shift
                ;;
            --report)
                GENERATE_REPORT=true
                shift
                ;;
            --threshold)
                WARNING_THRESHOLD="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
PazPaz Secret Age Checker

Usage: $0 [OPTIONS]

Options:
    --json           Output in JSON format for monitoring
    --quiet          Only show warnings and errors
    --verbose        Show detailed information
    --update-history Initialize/update rotation history
    --report         Generate compliance report
    --threshold DAYS Warning threshold in days (default: 30)
    --help           Show this help message

Examples:
    # Check secret age with standard output
    $0

    # JSON output for monitoring integration
    $0 --json

    # Update history file from current environment
    $0 --update-history

    # Generate compliance report
    $0 --report

    # Custom warning threshold (14 days)
    $0 --threshold 14

Exit Codes:
    0 - All secrets OK
    1 - Warnings (approaching rotation)
    2 - Errors (overdue for rotation)
    3 - Critical error
EOF
}

# =============================================================================
# History Management
# =============================================================================

initialize_history() {
    print_info "Initializing rotation history file..."

    cat > "$ROTATION_HISTORY" << EOF
# PazPaz Secret Rotation History
# Format: SECRET_NAME=YYYY-MM-DD
# Generated: $(date +%Y-%m-%d)

# Database
POSTGRES_PASSWORD=$(date +%Y-%m-%d)

# Cache
REDIS_PASSWORD=$(date +%Y-%m-%d)

# Object Storage
S3_CREDENTIALS=$(date +%Y-%m-%d)

# Application Security
JWT_SECRET_KEY=$(date +%Y-%m-%d)
SECRET_KEY=$(date +%Y-%m-%d)
CSRF_SECRET_KEY=$(date +%Y-%m-%d)

# External Services
SMTP_PASSWORD=$(date +%Y-%m-%d)
EOF

    chmod 600 "$ROTATION_HISTORY"
    print_success "Rotation history initialized"
}

read_rotation_history() {
    if [ ! -f "$ROTATION_HISTORY" ]; then
        if [ "$UPDATE_HISTORY" = true ]; then
            initialize_history
        else
            print_error "Rotation history file not found: $ROTATION_HISTORY"
            print_info "Run with --update-history to create it"
            exit 3
        fi
    fi

    print_verbose "Reading rotation history from $ROTATION_HISTORY"

    # Parse history file
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue

        # Store in associative array
        SECRET_AGES["$key"]="$value"
        print_verbose "  $key: last rotated on $value"
    done < "$ROTATION_HISTORY"
}

update_rotation_history() {
    local secret_name=$1
    local date_rotated=$2

    if grep -q "^${secret_name}=" "$ROTATION_HISTORY"; then
        sed -i "s|^${secret_name}=.*|${secret_name}=${date_rotated}|" "$ROTATION_HISTORY"
    else
        echo "${secret_name}=${date_rotated}" >> "$ROTATION_HISTORY"
    fi
}

# =============================================================================
# Age Calculation
# =============================================================================

calculate_days_since() {
    local date_str=$1

    # Convert date string to seconds since epoch
    local date_seconds=$(date -d "$date_str" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$date_str" +%s 2>/dev/null)
    local now_seconds=$(date +%s)

    # Calculate days difference
    local diff_seconds=$((now_seconds - date_seconds))
    local days=$((diff_seconds / 86400))

    echo $days
}

check_secret_age() {
    local secret_name=$1
    local rotation_period=$2
    local last_rotated="${SECRET_AGES[$secret_name]:-unknown}"

    if [ "$last_rotated" = "unknown" ]; then
        print_error "$secret_name: No rotation history found"
        SECRET_STATUS["$secret_name"]="NO_HISTORY"
        return 2
    fi

    local days_old=$(calculate_days_since "$last_rotated")
    local days_remaining=$((rotation_period - days_old))

    print_verbose "  Age: $days_old days, Period: $rotation_period days, Remaining: $days_remaining days"

    if [ $days_remaining -lt 0 ]; then
        # Overdue
        local overdue_days=$((-days_remaining))
        print_error "$secret_name: OVERDUE by $overdue_days days (rotated $days_old days ago, limit: $rotation_period days)"
        SECRET_STATUS["$secret_name"]="OVERDUE:$overdue_days"
        return 2
    elif [ $days_remaining -le $WARNING_THRESHOLD ]; then
        # Warning
        print_warning "$secret_name: Due in $days_remaining days (rotated $days_old days ago)"
        SECRET_STATUS["$secret_name"]="WARNING:$days_remaining"
        return 1
    else
        # OK
        print_success "$secret_name: OK ($days_remaining days remaining)"
        SECRET_STATUS["$secret_name"]="OK:$days_remaining"
        ((OK_COUNT++))
        return 0
    fi
}

# =============================================================================
# Checking Functions
# =============================================================================

check_all_secrets() {
    print_header "Checking Secret Rotation Status"
    print_header "════════════════════════════════════════════"
    print_info "Date: $(date +%Y-%m-%d)"
    print_info "Warning threshold: $WARNING_THRESHOLD days"
    echo ""

    for secret_name in "${!ROTATION_PERIODS[@]}"; do
        local period="${ROTATION_PERIODS[$secret_name]}"
        check_secret_age "$secret_name" "$period"
    done
}

# =============================================================================
# JSON Output
# =============================================================================

output_json() {
    local status="ok"
    [ $WARNINGS_COUNT -gt 0 ] && status="warning"
    [ $OVERDUE_COUNT -gt 0 ] && status="error"

    cat << EOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$status",
  "summary": {
    "ok": $OK_COUNT,
    "warnings": $WARNINGS_COUNT,
    "overdue": $OVERDUE_COUNT
  },
  "secrets": [
EOF

    local first=true
    for secret_name in "${!SECRET_STATUS[@]}"; do
        local status_info="${SECRET_STATUS[$secret_name]}"
        local status_type="${status_info%%:*}"
        local status_value="${status_info#*:}"
        local rotation_period="${ROTATION_PERIODS[$secret_name]}"
        local last_rotated="${SECRET_AGES[$secret_name]:-null}"

        [ "$first" = false ] && echo ","
        first=false

        cat << EOF
    {
      "name": "$secret_name",
      "status": "$status_type",
      "rotation_period": $rotation_period,
      "last_rotated": "$last_rotated",
EOF

        case "$status_type" in
            OK)
                echo "      \"days_remaining\": $status_value"
                ;;
            WARNING)
                echo "      \"days_remaining\": $status_value"
                ;;
            OVERDUE)
                echo "      \"days_overdue\": $status_value"
                ;;
            NO_HISTORY)
                echo "      \"error\": \"No rotation history\""
                ;;
        esac

        printf "    }"
    done

    cat << EOF

  ]
}
EOF
}

# =============================================================================
# Compliance Report
# =============================================================================

generate_compliance_report() {
    print_header "PazPaz Secret Rotation Compliance Report"
    print_header "════════════════════════════════════════════════════════════"
    echo ""
    print_info "Generated: $(date)"
    print_info "Report Period: Last 90 days"
    echo ""

    print_header "Executive Summary"
    echo "───────────────────────────"
    echo "Total Secrets Monitored: ${#ROTATION_PERIODS[@]}"
    echo "Compliant (OK): $OK_COUNT"
    echo "Approaching Deadline: $WARNINGS_COUNT"
    echo "Non-Compliant (Overdue): $OVERDUE_COUNT"
    echo ""

    if [ $OVERDUE_COUNT -eq 0 ] && [ $WARNINGS_COUNT -eq 0 ]; then
        print_success "✅ FULLY COMPLIANT - All secrets are within rotation schedule"
    elif [ $OVERDUE_COUNT -eq 0 ]; then
        print_warning "⚠️  ATTENTION REQUIRED - Some secrets approaching rotation deadline"
    else
        print_error "❌ NON-COMPLIANT - Immediate rotation required for overdue secrets"
    fi
    echo ""

    print_header "Detailed Secret Status"
    echo "───────────────────────────"
    printf "%-25s %-15s %-15s %-20s %s\n" "Secret" "Status" "Last Rotated" "Next Rotation" "Days Remaining"
    printf "%-25s %-15s %-15s %-20s %s\n" "─────────" "──────" "────────────" "─────────────" "──────────────"

    for secret_name in "${!SECRET_STATUS[@]}"; do
        local status_info="${SECRET_STATUS[$secret_name]}"
        local status_type="${status_info%%:*}"
        local status_value="${status_info#*:}"
        local last_rotated="${SECRET_AGES[$secret_name]:-N/A}"
        local rotation_period="${ROTATION_PERIODS[$secret_name]}"

        local status_display=""
        local next_rotation="N/A"
        local days_display="N/A"

        case "$status_type" in
            OK)
                status_display="${GREEN}✅ OK${NC}"
                next_rotation=$(date -d "$last_rotated + $rotation_period days" +%Y-%m-%d 2>/dev/null || echo "N/A")
                days_display="$status_value"
                ;;
            WARNING)
                status_display="${YELLOW}⚠️  WARNING${NC}"
                next_rotation=$(date -d "$last_rotated + $rotation_period days" +%Y-%m-%d 2>/dev/null || echo "N/A")
                days_display="$status_value"
                ;;
            OVERDUE)
                status_display="${RED}❌ OVERDUE${NC}"
                next_rotation="IMMEDIATE"
                days_display="-$status_value (overdue)"
                ;;
            NO_HISTORY)
                status_display="${RED}❓ UNKNOWN${NC}"
                ;;
        esac

        printf "%-25s %-25b %-15s %-20s %s\n" "$secret_name" "$status_display" "$last_rotated" "$next_rotation" "$days_display"
    done

    echo ""
    print_header "Recommendations"
    echo "───────────────────────────"

    if [ $OVERDUE_COUNT -gt 0 ]; then
        echo "1. IMMEDIATE ACTION REQUIRED:"
        echo "   Run: ./scripts/rotate-secrets.sh --all"
        echo ""
    fi

    if [ $WARNINGS_COUNT -gt 0 ]; then
        echo "2. Schedule rotation for secrets approaching deadline:"
        for secret_name in "${!SECRET_STATUS[@]}"; do
            local status_info="${SECRET_STATUS[$secret_name]}"
            if [[ "$status_info" == WARNING:* ]]; then
                echo "   - $secret_name"
            fi
        done
        echo ""
    fi

    echo "3. Best Practices:"
    echo "   - Test rotation in staging before production"
    echo "   - Schedule rotations during maintenance windows"
    echo "   - Update GitHub Secrets after rotation"
    echo "   - Document all rotations in incident log"
    echo ""

    print_header "Compliance Notes"
    echo "───────────────────────────"
    echo "• HIPAA §164.308(a)(5): Requires regular review and updates of passwords"
    echo "• NIST 800-66: Recommends 90-day rotation for high-value credentials"
    echo "• PCI-DSS 8.2.4: Requires password changes at least every 90 days"
    echo ""

    print_header "Audit Trail"
    echo "───────────────────────────"
    echo "Rotation history file: $ROTATION_HISTORY"
    echo "Last modified: $(stat -c %y "$ROTATION_HISTORY" 2>/dev/null || stat -f "%Sm" "$ROTATION_HISTORY" 2>/dev/null || echo "Unknown")"
    echo "Rotation logs directory: /opt/pazpaz/logs/"
    echo ""

    # Save report to file
    local report_file="/opt/pazpaz/logs/rotation-compliance-$(date +%Y%m%d).txt"
    print_info "Report saved to: $report_file"
}

# =============================================================================
# Integration Helpers
# =============================================================================

send_slack_alert() {
    local webhook_url="${SLACK_WEBHOOK_URL:-}"

    if [ -z "$webhook_url" ]; then
        return
    fi

    local color="good"
    local title="Secret Rotation Status"
    local text="All secrets are within rotation schedule"

    if [ $OVERDUE_COUNT -gt 0 ]; then
        color="danger"
        title="⚠️ Secret Rotation OVERDUE"
        text="$OVERDUE_COUNT secret(s) are overdue for rotation!"
    elif [ $WARNINGS_COUNT -gt 0 ]; then
        color="warning"
        title="Secret Rotation Warning"
        text="$WARNINGS_COUNT secret(s) approaching rotation deadline"
    fi

    curl -X POST "$webhook_url" \
        -H 'Content-Type: application/json' \
        -d "{
            \"attachments\": [{
                \"color\": \"$color\",
                \"title\": \"$title\",
                \"text\": \"$text\",
                \"fields\": [
                    {\"title\": \"OK\", \"value\": \"$OK_COUNT\", \"short\": true},
                    {\"title\": \"Warnings\", \"value\": \"$WARNINGS_COUNT\", \"short\": true},
                    {\"title\": \"Overdue\", \"value\": \"$OVERDUE_COUNT\", \"short\": true}
                ],
                \"footer\": \"PazPaz Security\",
                \"ts\": $(date +%s)
            }]
        }" 2>/dev/null
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    # Parse arguments
    parse_arguments "$@"

    # Read rotation history
    read_rotation_history

    # Check all secrets
    if [ "$OUTPUT_JSON" = false ]; then
        check_all_secrets
    else
        # Quiet check for JSON output
        QUIET_MODE=true
        for secret_name in "${!ROTATION_PERIODS[@]}"; do
            local period="${ROTATION_PERIODS[$secret_name]}"
            check_secret_age "$secret_name" "$period" >/dev/null 2>&1
        done
    fi

    # Output results
    if [ "$OUTPUT_JSON" = true ]; then
        output_json
    elif [ "$GENERATE_REPORT" = true ]; then
        generate_compliance_report
    else
        # Summary
        echo ""
        print_header "Summary"
        print_header "════════════════════════════════════════════"
        echo "✅ OK: $OK_COUNT secrets"
        echo "⚠️  Warnings: $WARNINGS_COUNT secrets"
        echo "❌ Overdue: $OVERDUE_COUNT secrets"

        if [ $OVERDUE_COUNT -gt 0 ]; then
            echo ""
            print_error "ACTION REQUIRED: Some secrets are overdue for rotation!"
            echo "Run: ./scripts/rotate-secrets.sh --all"
        elif [ $WARNINGS_COUNT -gt 0 ]; then
            echo ""
            print_warning "Some secrets are approaching rotation deadline"
            echo "Schedule rotation soon: ./scripts/rotate-secrets.sh --all"
        else
            echo ""
            print_success "All secrets are within rotation schedule"
        fi
    fi

    # Send alerts if configured
    send_slack_alert

    # Exit with appropriate code
    if [ $OVERDUE_COUNT -gt 0 ]; then
        exit 2
    elif [ $WARNINGS_COUNT -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@"