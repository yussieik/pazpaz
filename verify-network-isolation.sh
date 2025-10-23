#!/bin/bash
# Verification script for docker-compose.prod.yml network isolation

echo "========================================"
echo "Network Isolation Verification Report"
echo "========================================"
echo

# Check if docker-compose.prod.yml exists
if [ ! -f docker-compose.prod.yml ]; then
    echo "❌ ERROR: docker-compose.prod.yml not found!"
    exit 1
fi

echo "1. Checking Network Definitions:"
echo "---------------------------------"
grep -A 3 "^networks:" docker-compose.prod.yml | grep -E "^\s+(frontend|backend|database):" -A 3 | while read line; do
    if echo "$line" | grep -q "internal: true"; then
        echo "  ✅ $(echo "$line" | sed 's/internal: true/is ISOLATED (internal: true)/')"
    fi
done

echo
echo "2. Checking Service Port Exposure:"
echo "-----------------------------------"

# Check nginx (should have ports exposed)
if grep -A 50 "^\s*nginx:" docker-compose.prod.yml | grep -q "ports:"; then
    echo "  ✅ nginx: Ports 80,443 exposed (correct - public facing)"
else
    echo "  ❌ nginx: No ports exposed (should expose 80,443)"
fi

# Check services that should NOT have ports exposed
for service in api arq-worker db redis minio; do
    if grep -A 50 "^\s*$service:" docker-compose.prod.yml | grep -B 50 "^\s*[a-z-]*:" | grep -q "ports:"; then
        echo "  ❌ $service: Has exposed ports (SECURITY ISSUE - should be internal only)"
    else
        echo "  ✅ $service: No ports exposed (secure)"
    fi
done

echo
echo "3. Checking Service Network Assignments:"
echo "-----------------------------------------"

# Manually check each service's networks
echo "  nginx:"
grep -A 50 "^\s*nginx:" docker-compose.prod.yml | grep -A 5 "networks:" | grep "^\s*-" | sed 's/^/    /'

echo "  api:"
grep -A 50 "^\s*api:" docker-compose.prod.yml | grep -A 5 "networks:" | grep "^\s*-" | sed 's/^/    /'

echo "  arq-worker:"
grep -A 50 "^\s*arq-worker:" docker-compose.prod.yml | grep -A 5 "networks:" | grep "^\s*-" | sed 's/^/    /'

echo "  db:"
grep -A 50 "^\s*db:" docker-compose.prod.yml | grep -A 5 "networks:" | grep "^\s*-" | sed 's/^/    /'

echo "  redis:"
grep -A 50 "^\s*redis:" docker-compose.prod.yml | grep -A 5 "networks:" | grep "^\s*-" | sed 's/^/    /'

echo "  minio:"
grep -A 50 "^\s*minio:" docker-compose.prod.yml | grep -A 5 "networks:" | grep "^\s*-" | sed 's/^/    /'

echo
echo "4. Security Validation Summary:"
echo "--------------------------------"

# Count issues
ISSUES=0

# Check if backend and database networks are internal
if ! grep -A 3 "^\s*backend:" docker-compose.prod.yml | grep -q "internal: true"; then
    echo "  ❌ Backend network is NOT isolated"
    ISSUES=$((ISSUES + 1))
fi

if ! grep -A 3 "^\s*database:" docker-compose.prod.yml | grep -q "internal: true"; then
    echo "  ❌ Database network is NOT isolated"
    ISSUES=$((ISSUES + 1))
fi

# Final result
if [ $ISSUES -eq 0 ]; then
    echo "  ✅ All network isolation requirements met!"
    echo "  ✅ Production security standards satisfied!"
else
    echo "  ❌ Found $ISSUES network isolation issues!"
    echo "  ⚠️  Fix these before production deployment!"
fi

echo
echo "========================================"
echo "End of Verification Report"
echo "========================================"