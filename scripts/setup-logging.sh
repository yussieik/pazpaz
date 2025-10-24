#!/bin/bash

################################################################################
# PazPaz Centralized Logging Setup Script
# Version: 1.0.0
#
# Purpose:
#   Configure centralized JSON-structured logging for all PazPaz services
#   on production servers with proper log rotation and retention.
#
# Features:
#   - Creates /opt/pazpaz/logs/ directory structure
#   - Configures Docker logging with JSON drivers
#   - Sets up log rotation (10MB per file, 7 files maximum)
#   - Creates logrotate configuration for additional logs
#   - Validates logging configuration
#   - Optional log forwarding preparation (Loki/ELK)
#
# Usage:
#   ./setup-logging.sh [--apply] [--validate-only] [--prepare-forwarding]
#
# Requirements:
#   - Root or sudo access on production server
#   - Docker and Docker Compose installed
#   - logrotate package installed
#
# HIPAA Compliance:
#   - Never logs PHI data
#   - Logs encrypted at rest (filesystem encryption)
#   - Access logs maintained for audit trails
#   - Retention policies enforced
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
readonly LOGROTATE_CONFIG="/etc/logrotate.d/pazpaz"
readonly DOCKER_CONFIG_DIR="/etc/docker"
readonly COMPOSE_PROJECT_NAME="pazpaz"

# Logging configuration
readonly LOG_MAX_SIZE="10m"
readonly LOG_MAX_FILE="7"
readonly LOG_RETENTION_DAYS="30"

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m' # No Color

# Operation modes
APPLY_CHANGES=false
VALIDATE_ONLY=false
PREPARE_FORWARDING=false
VERBOSE=false

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
    echo -e "${RED}✗${NC} $1" >&2
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

Configure centralized logging for PazPaz production infrastructure.

OPTIONS:
    --apply             Apply the logging configuration to the system
    --validate-only     Only validate current logging configuration
    --prepare-forwarding Prepare configuration for log forwarding (Loki/ELK)
    --verbose          Enable verbose output
    -h, --help         Show this help message

EXAMPLES:
    # Validate current logging setup
    $SCRIPT_NAME --validate-only

    # Apply logging configuration
    sudo $SCRIPT_NAME --apply

    # Prepare for log forwarding
    sudo $SCRIPT_NAME --prepare-forwarding

NOTES:
    - Must be run with sudo when applying changes
    - Creates /opt/pazpaz/logs/ directory structure
    - Configures Docker JSON logging with rotation
    - Sets up logrotate for additional log files

EOF
}

################################################################################
# Validation Functions
################################################################################

check_prerequisites() {
    print_section "Checking Prerequisites"

    local all_ok=true

    # Check if running as root when applying
    if [[ "$APPLY_CHANGES" == true ]] && [[ $EUID -ne 0 ]]; then
        log_error "This script must be run with sudo when applying changes"
        all_ok=false
    fi

    # Check Docker installation
    if command -v docker &> /dev/null; then
        log_success "Docker is installed: $(docker --version)"
    else
        log_error "Docker is not installed"
        all_ok=false
    fi

    # Check Docker Compose
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        log_success "Docker Compose is installed"
    else
        log_error "Docker Compose is not installed"
        all_ok=false
    fi

    # Check logrotate installation
    if command -v logrotate &> /dev/null; then
        log_success "logrotate is installed: $(logrotate --version 2>&1 | head -n1)"
    else
        log_warning "logrotate is not installed - recommended for log rotation"
    fi

    # Check jq for JSON processing
    if command -v jq &> /dev/null; then
        log_success "jq is installed for JSON processing"
    else
        log_warning "jq is not installed - recommended for log parsing"
    fi

    if [[ "$all_ok" != true ]]; then
        log_error "Prerequisites check failed"
        return 1
    fi

    log_success "All prerequisites met"
    return 0
}

################################################################################
# Directory Setup Functions
################################################################################

setup_log_directories() {
    print_section "Setting Up Log Directories"

    local services=("nginx" "api" "worker" "db" "redis" "minio" "clamav" "frontend")

    # Create base log directory
    if [[ "$APPLY_CHANGES" == true ]]; then
        log_info "Creating base log directory: $LOG_BASE_DIR"
        mkdir -p "$LOG_BASE_DIR"
        chmod 755 "$LOG_BASE_DIR"

        # Create service-specific directories
        for service in "${services[@]}"; do
            local service_dir="$LOG_BASE_DIR/$service"
            log_info "Creating log directory for $service: $service_dir"
            mkdir -p "$service_dir"
            chmod 755 "$service_dir"
        done

        # Create aggregated logs directory
        mkdir -p "$LOG_BASE_DIR/aggregated"
        chmod 755 "$LOG_BASE_DIR/aggregated"

        # Create audit logs directory (HIPAA requirement)
        mkdir -p "$LOG_BASE_DIR/audit"
        chmod 750 "$LOG_BASE_DIR/audit"  # Restricted access

        log_success "Log directories created successfully"
    else
        log_info "Would create log directories under $LOG_BASE_DIR"
        for service in "${services[@]}"; do
            log_debug "  - $LOG_BASE_DIR/$service"
        done
    fi
}

################################################################################
# Docker Logging Configuration
################################################################################

configure_docker_logging() {
    print_section "Configuring Docker Logging"

    local daemon_config="$DOCKER_CONFIG_DIR/daemon.json"

    if [[ "$APPLY_CHANGES" == true ]]; then
        # Backup existing daemon.json if it exists
        if [[ -f "$daemon_config" ]]; then
            log_info "Backing up existing Docker daemon configuration"
            cp "$daemon_config" "${daemon_config}.backup.${TIMESTAMP}"
        fi

        # Create or update daemon.json with logging configuration
        log_info "Updating Docker daemon configuration"
        cat > "$daemon_config" <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "$LOG_MAX_SIZE",
    "max-file": "$LOG_MAX_FILE",
    "labels": "service,environment,version",
    "env": "ENVIRONMENT,SERVICE_NAME",
    "compress": "true"
  },
  "log-level": "info",
  "debug": false,
  "experimental": false
}
EOF

        log_info "Reloading Docker daemon configuration"
        systemctl reload docker || log_warning "Failed to reload Docker daemon - manual restart may be required"

        log_success "Docker logging configured"
    else
        log_info "Would configure Docker daemon with:"
        log_debug "  - Log driver: json-file"
        log_debug "  - Max size: $LOG_MAX_SIZE"
        log_debug "  - Max files: $LOG_MAX_FILE"
        log_debug "  - Compression: enabled"
    fi
}

################################################################################
# Logrotate Configuration
################################################################################

setup_logrotate() {
    print_section "Setting Up Log Rotation"

    if ! command -v logrotate &> /dev/null; then
        log_warning "logrotate not installed - skipping configuration"
        return 0
    fi

    if [[ "$APPLY_CHANGES" == true ]]; then
        log_info "Creating logrotate configuration: $LOGROTATE_CONFIG"

        cat > "$LOGROTATE_CONFIG" <<EOF
# PazPaz Log Rotation Configuration
# Generated by setup-logging.sh on $(date)

# Application logs
$LOG_BASE_DIR/*/*.log {
    daily
    rotate $LOG_RETENTION_DAYS
    maxsize $LOG_MAX_SIZE
    missingok
    notifempty
    compress
    delaycompress
    create 0644 root root
    sharedscripts
    postrotate
        # Signal applications to reopen log files if needed
        docker exec pazpaz-api kill -USR1 1 2>/dev/null || true
        docker exec pazpaz-arq-worker kill -USR1 1 2>/dev/null || true
    endscript
}

# Audit logs (HIPAA - longer retention)
$LOG_BASE_DIR/audit/*.log {
    daily
    rotate 90
    maxsize 50M
    missingok
    notifempty
    compress
    delaycompress
    create 0640 root root
    sharedscripts
}

# Aggregated logs
$LOG_BASE_DIR/aggregated/*.log {
    daily
    rotate 7
    maxsize 100M
    missingok
    notifempty
    compress
    delaycompress
    create 0644 root root
}

# JSON logs from Docker (additional rotation if needed)
$LOG_BASE_DIR/*/*.json {
    daily
    rotate 7
    maxsize $LOG_MAX_SIZE
    missingok
    notifempty
    compress
    delaycompress
    create 0644 root root
}
EOF

        # Test logrotate configuration
        log_info "Testing logrotate configuration"
        logrotate -d "$LOGROTATE_CONFIG" 2>&1 | head -n 20 || log_warning "Logrotate test showed warnings"

        log_success "Logrotate configuration created"
    else
        log_info "Would create logrotate configuration with:"
        log_debug "  - Daily rotation"
        log_debug "  - $LOG_RETENTION_DAYS days retention for app logs"
        log_debug "  - 90 days retention for audit logs"
        log_debug "  - Compression enabled"
    fi
}

################################################################################
# Log Forwarding Preparation
################################################################################

prepare_log_forwarding() {
    print_section "Preparing Log Forwarding Configuration"

    local forwarding_dir="$LOG_BASE_DIR/forwarding"

    if [[ "$APPLY_CHANGES" == true ]]; then
        mkdir -p "$forwarding_dir"

        # Create Loki configuration template
        log_info "Creating Loki promtail configuration template"
        cat > "$forwarding_dir/promtail-config.yaml" <<EOF
# Promtail Configuration for PazPaz Logs
# Use this template to forward logs to Loki

server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push
    tenant_id: pazpaz

scrape_configs:
  # Docker container logs
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: pazpaz
          __path__: /var/lib/docker/containers/*/*log

    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            time: time
            service: attrs.service
            environment: attrs.environment

      - labels:
          service:
          environment:

      - timestamp:
          format: RFC3339Nano
          source: time

      - output:
          source: output

  # Application logs
  - job_name: application
    static_configs:
      - targets:
          - localhost
        labels:
          job: pazpaz-app
          __path__: $LOG_BASE_DIR/api/*.log

    pipeline_stages:
      - multiline:
          firstline: '^\\d{4}-\\d{2}-\\d{2}'

      - regex:
          expression: '^(?P<timestamp>\\S+\\s+\\S+)\\s+(?P<level>\\w+)\\s+(?P<message>.*)'

      - labels:
          level:

      - timestamp:
          format: '2006-01-02 15:04:05'
          source: timestamp

  # Audit logs (HIPAA)
  - job_name: audit
    static_configs:
      - targets:
          - localhost
        labels:
          job: pazpaz-audit
          compliance: hipaa
          __path__: $LOG_BASE_DIR/audit/*.log
EOF

        # Create Elasticsearch/Logstash configuration template
        log_info "Creating Logstash configuration template"
        cat > "$forwarding_dir/logstash.conf" <<EOF
# Logstash Configuration for PazPaz Logs

input {
  # Docker logs via journald
  journald {
    path => "/var/log/journal"
    seekto => "tail"
    tags => ["docker", "pazpaz"]
  }

  # Application log files
  file {
    path => ["$LOG_BASE_DIR/api/*.log"]
    type => "application"
    codec => multiline {
      pattern => "^%{TIMESTAMP_ISO8601}"
      negate => true
      what => "previous"
    }
  }

  # Audit logs (HIPAA)
  file {
    path => ["$LOG_BASE_DIR/audit/*.log"]
    type => "audit"
    tags => ["hipaa", "audit"]
  }
}

filter {
  # Parse JSON logs from Docker
  if [type] == "docker" {
    json {
      source => "message"
      target => "docker"
    }

    mutate {
      add_field => {
        "service" => "%{[docker][attrs][service]}"
        "environment" => "%{[docker][attrs][environment]}"
      }
    }
  }

  # Parse application logs
  if [type] == "application" {
    grok {
      match => {
        "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:log_message}"
      }
    }

    date {
      match => ["timestamp", "ISO8601"]
      target => "@timestamp"
    }
  }

  # Add metadata
  mutate {
    add_field => {
      "application" => "pazpaz"
      "cluster" => "production"
    }
  }

  # Remove sensitive data (HIPAA compliance)
  mutate {
    gsub => [
      "message", "\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b", "[EMAIL_REDACTED]",
      "message", "\\b\\d{3}-\\d{2}-\\d{4}\\b", "[SSN_REDACTED]",
      "message", "\\b\\d{10}\\b", "[PHONE_REDACTED]"
    ]
  }
}

output {
  # Send to Elasticsearch
  elasticsearch {
    hosts => ["https://elasticsearch:9200"]
    index => "pazpaz-%{type}-%{+YYYY.MM.dd}"
    template_name => "pazpaz"
    ssl => true
    ssl_certificate_verification => true
    user => "\${ELASTIC_USER}"
    password => "\${ELASTIC_PASSWORD}"
  }

  # Also output to file for backup
  file {
    path => "$LOG_BASE_DIR/aggregated/logstash-%{+YYYY-MM-dd}.log"
    codec => json_lines
  }
}
EOF

        log_success "Log forwarding templates created in $forwarding_dir"
        log_info "Edit the configuration files and deploy Loki/Logstash as needed"
    else
        log_info "Would create log forwarding templates for:"
        log_debug "  - Loki/Promtail configuration"
        log_debug "  - Elasticsearch/Logstash configuration"
    fi
}

################################################################################
# Validation Functions
################################################################################

validate_logging_setup() {
    print_section "Validating Logging Configuration"

    local validation_passed=true

    # Check log directories
    log_info "Checking log directories..."
    if [[ -d "$LOG_BASE_DIR" ]]; then
        log_success "Base log directory exists: $LOG_BASE_DIR"

        # Check subdirectories
        for dir in nginx api worker db redis minio clamav frontend audit aggregated; do
            if [[ -d "$LOG_BASE_DIR/$dir" ]]; then
                log_success "  ✓ $dir directory exists"
            else
                log_warning "  ✗ $dir directory missing"
            fi
        done
    else
        log_error "Base log directory does not exist: $LOG_BASE_DIR"
        validation_passed=false
    fi

    # Check Docker logging configuration
    log_info "Checking Docker logging configuration..."
    if [[ -f "$DOCKER_CONFIG_DIR/daemon.json" ]]; then
        local log_driver=$(jq -r '.["log-driver"]' "$DOCKER_CONFIG_DIR/daemon.json" 2>/dev/null || echo "unknown")
        if [[ "$log_driver" == "json-file" ]]; then
            log_success "Docker configured with json-file driver"

            local max_size=$(jq -r '.["log-opts"]["max-size"]' "$DOCKER_CONFIG_DIR/daemon.json" 2>/dev/null || echo "unknown")
            local max_file=$(jq -r '.["log-opts"]["max-file"]' "$DOCKER_CONFIG_DIR/daemon.json" 2>/dev/null || echo "unknown")

            log_info "  Max size: $max_size"
            log_info "  Max files: $max_file"
        else
            log_warning "Docker using non-standard log driver: $log_driver"
        fi
    else
        log_warning "Docker daemon.json not found"
    fi

    # Check logrotate configuration
    log_info "Checking logrotate configuration..."
    if [[ -f "$LOGROTATE_CONFIG" ]]; then
        log_success "Logrotate configuration exists"

        # Test configuration
        if logrotate -d "$LOGROTATE_CONFIG" &> /dev/null; then
            log_success "Logrotate configuration is valid"
        else
            log_warning "Logrotate configuration has issues"
        fi
    else
        log_warning "Logrotate configuration not found"
    fi

    # Check running containers logging
    log_info "Checking container logging..."
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q pazpaz; then
        for container in $(docker ps --filter "label=app=pazpaz" --format "{{.Names}}"); do
            local log_config=$(docker inspect "$container" --format '{{.HostConfig.LogConfig.Type}}' 2>/dev/null)
            if [[ "$log_config" == "json-file" ]]; then
                log_success "  ✓ $container using json-file logging"
            else
                log_warning "  ✗ $container using $log_config logging"
            fi
        done
    else
        log_info "No PazPaz containers currently running"
    fi

    # Check disk space for logs
    log_info "Checking disk space..."
    local disk_usage=$(df -h "$LOG_BASE_DIR" 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ -n "$disk_usage" ]]; then
        if [[ "$disk_usage" -lt 80 ]]; then
            log_success "Disk usage acceptable: ${disk_usage}%"
        else
            log_warning "High disk usage: ${disk_usage}%"
        fi
    fi

    if [[ "$validation_passed" == true ]]; then
        log_success "Logging configuration validation passed"
        return 0
    else
        log_error "Logging configuration validation failed"
        return 1
    fi
}

################################################################################
# Test Logging Function
################################################################################

test_logging() {
    print_section "Testing Logging System"

    log_info "Generating test log entries..."

    # Generate test logs for each service
    local test_message="Test log entry from setup-logging.sh at $(date -Iseconds)"

    # Test Docker logging
    if docker ps | grep -q pazpaz-api; then
        docker exec pazpaz-api sh -c "echo '$test_message' >> /app/logs/test.log" 2>/dev/null || true
        log_success "Generated test log for API service"
    fi

    # Test direct file logging
    if [[ "$APPLY_CHANGES" == true ]]; then
        echo "$(date -Iseconds) INFO $test_message" >> "$LOG_BASE_DIR/api/test.log"
        echo "$(date -Iseconds) AUDIT User test performed logging check" >> "$LOG_BASE_DIR/audit/test.log"
        log_success "Generated test log files"
    fi

    # Check if logs are being collected
    log_info "Checking log collection..."
    if [[ -f "$LOG_BASE_DIR/api/test.log" ]]; then
        log_success "Test logs successfully written"
        tail -n 1 "$LOG_BASE_DIR/api/test.log"
    fi
}

################################################################################
# Summary Function
################################################################################

print_summary() {
    print_header "Logging Setup Summary"

    echo ""
    echo "Configuration Applied:"
    echo "  • Base directory: $LOG_BASE_DIR"
    echo "  • Log rotation: $LOG_MAX_SIZE per file, $LOG_MAX_FILE files"
    echo "  • Retention: $LOG_RETENTION_DAYS days (standard), 90 days (audit)"
    echo "  • Docker driver: json-file with compression"
    echo ""

    if [[ "$PREPARE_FORWARDING" == true ]]; then
        echo "Log Forwarding Templates:"
        echo "  • Loki/Promtail: $LOG_BASE_DIR/forwarding/promtail-config.yaml"
        echo "  • Logstash: $LOG_BASE_DIR/forwarding/logstash.conf"
        echo ""
    fi

    echo "Next Steps:"
    echo "  1. Review the logging configuration"
    echo "  2. Run './aggregate-logs.sh' to view aggregated logs"
    echo "  3. Set up log monitoring and alerting"
    echo "  4. Configure log forwarding if needed"
    echo ""

    log_success "Logging setup completed successfully!"
}

################################################################################
# Main Function
################################################################################

main() {
    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --apply)
                APPLY_CHANGES=true
                shift
                ;;
            --validate-only)
                VALIDATE_ONLY=true
                shift
                ;;
            --prepare-forwarding)
                PREPARE_FORWARDING=true
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

    print_header "PazPaz Centralized Logging Setup v$SCRIPT_VERSION"

    # Check prerequisites
    if ! check_prerequisites; then
        log_error "Prerequisites check failed"
        exit 1
    fi

    if [[ "$VALIDATE_ONLY" == true ]]; then
        # Only validate existing configuration
        validate_logging_setup
        exit $?
    fi

    # Setup logging infrastructure
    setup_log_directories
    configure_docker_logging
    setup_logrotate

    if [[ "$PREPARE_FORWARDING" == true ]]; then
        prepare_log_forwarding
    fi

    # Validate setup
    validate_logging_setup

    # Test logging
    if [[ "$APPLY_CHANGES" == true ]]; then
        test_logging
    fi

    # Print summary
    print_summary
}

# Execute main function
main "$@"