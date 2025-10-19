#!/usr/bin/env bash
# Verification script for Docker resource limits
# SECURITY: Verifies DoS protection via resource constraints

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Resource Limits Verification ===${NC}\n"

# Function to get expected CPU limit
get_expected_cpu() {
    case "$1" in
        pazpaz-db|pazpaz-clamav) echo "2.000" ;;
        pazpaz-redis|pazpaz-minio) echo "1.000" ;;
        *) echo "0" ;;
    esac
}

# Function to get expected memory limit
get_expected_mem() {
    case "$1" in
        pazpaz-db|pazpaz-clamav) echo "2GiB" ;;
        pazpaz-minio) echo "1GiB" ;;
        pazpaz-redis) echo "512MiB" ;;
        *) echo "0" ;;
    esac
}

FAILED=0

echo -e "${YELLOW}Checking running containers...${NC}"
RUNNING_CONTAINERS=$(docker ps --filter "name=pazpaz-" --format "{{.Names}}" 2>/dev/null || true)

if [ -z "$RUNNING_CONTAINERS" ]; then
    echo -e "${RED}✗ No PazPaz containers running${NC}"
    echo -e "${YELLOW}  Start with: docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found running containers${NC}\n"

# Check each container's resource limits
for CONTAINER in pazpaz-db pazpaz-redis pazpaz-minio pazpaz-clamav; do
    if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
        echo -e "${YELLOW}⚠ $CONTAINER not running (skipped)${NC}"
        continue
    fi

    echo -e "${BLUE}Checking $CONTAINER...${NC}"

    # Get CPU limit
    CPU_LIMIT=$(docker inspect "$CONTAINER" --format '{{.HostConfig.NanoCpus}}' 2>/dev/null)
    if [ "$CPU_LIMIT" = "0" ] || [ -z "$CPU_LIMIT" ]; then
        echo -e "${RED}  ✗ No CPU limit set${NC}"
        FAILED=1
    else
        # Convert nanocpus to CPUs (divide by 1 billion)
        CPU_CORES=$(echo "scale=3; $CPU_LIMIT / 1000000000" | bc)
        EXPECTED_CPU=$(get_expected_cpu "$CONTAINER")
        if [ "$CPU_CORES" = "$EXPECTED_CPU" ]; then
            echo -e "${GREEN}  ✓ CPU limit: $CPU_CORES cores${NC}"
        else
            echo -e "${YELLOW}  ⚠ CPU limit: $CPU_CORES cores (expected: $EXPECTED_CPU)${NC}"
        fi
    fi

    # Get memory limit
    MEM_LIMIT=$(docker inspect "$CONTAINER" --format '{{.HostConfig.Memory}}' 2>/dev/null)
    if [ "$MEM_LIMIT" = "0" ] || [ -z "$MEM_LIMIT" ]; then
        echo -e "${RED}  ✗ No memory limit set${NC}"
        FAILED=1
    else
        # Convert bytes to human-readable format
        if [ "$MEM_LIMIT" -ge 1073741824 ]; then
            MEM_HUMAN="$(( MEM_LIMIT / 1073741824 ))GiB"
        else
            MEM_HUMAN="$(( MEM_LIMIT / 1048576 ))MiB"
        fi
        EXPECTED_MEM=$(get_expected_mem "$CONTAINER")
        if [ "$MEM_HUMAN" = "$EXPECTED_MEM" ]; then
            echo -e "${GREEN}  ✓ Memory limit: $MEM_HUMAN${NC}"
        else
            echo -e "${YELLOW}  ⚠ Memory limit: $MEM_HUMAN (expected: $EXPECTED_MEM)${NC}"
        fi
    fi

    echo ""
done

# Show live resource usage
echo -e "${BLUE}=== Current Resource Usage ===${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
    $(docker ps --filter "name=pazpaz-" --format "{{.Names}}" | tr '\n' ' ')

echo ""

if [ $FAILED -eq 1 ]; then
    echo -e "${RED}[VERIFICATION FAILED] Some containers missing resource limits${NC}"
    echo -e "${YELLOW}Apply limits with: docker-compose up -d --force-recreate${NC}"
    exit 1
fi

echo -e "${GREEN}[VERIFICATION PASSED] All containers have proper resource limits${NC}"
echo -e "${YELLOW}HIPAA Compliance: §164.308(a)(7)(ii)(B) - Resource Management${NC}"
exit 0
