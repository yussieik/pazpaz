#!/bin/bash
set -e

echo "=================================================="
echo "PazPaz: Local PostgreSQL Cleanup Script"
echo "=================================================="
echo ""
echo "This script will:"
echo "  1. Stop local PostgreSQL 16 service"
echo "  2. Prevent it from auto-starting"
echo "  3. Ensure Docker PostgreSQL runs on port 5432"
echo "  4. Run database migrations"
echo "  5. Verify setup with test connection"
echo ""
echo "⚠️  This requires sudo access for steps 1-2"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Step 1: Stop local PostgreSQL service
echo ""
echo "Step 1: Stopping local PostgreSQL service..."
if sudo launchctl list | grep -q postgresql-16; then
    sudo launchctl unload /Library/LaunchDaemons/postgresql-16.plist 2>/dev/null || true
    echo "✅ PostgreSQL LaunchDaemon unloaded"
else
    echo "ℹ️  PostgreSQL LaunchDaemon not running"
fi

# Kill any remaining postgres processes
echo ""
echo "Step 2: Killing any remaining PostgreSQL processes..."
sudo pkill -9 -f "/Library/PostgreSQL/16/bin/postgres" 2>/dev/null || true
sleep 2
if ps aux | grep -v grep | grep -q "/Library/PostgreSQL/16/bin/postgres"; then
    echo "⚠️  Warning: Some PostgreSQL processes may still be running"
else
    echo "✅ All local PostgreSQL processes stopped"
fi

# Step 3: Prevent auto-start
echo ""
echo "Step 3: Preventing PostgreSQL from auto-starting..."
if [ -f /Library/LaunchDaemons/postgresql-16.plist ]; then
    sudo rm /Library/LaunchDaemons/postgresql-16.plist
    echo "✅ LaunchDaemon plist removed"
else
    echo "ℹ️  LaunchDaemon plist already removed"
fi

# Step 4: Restart Docker database
echo ""
echo "Step 4: Restarting Docker PostgreSQL on port 5432..."
cd /Users/yussieik/Desktop/projects/pazpaz
docker compose down 2>/dev/null || true
sleep 2
docker compose up -d db
echo "⏳ Waiting for database to be healthy..."
sleep 10

# Check if database is healthy
if docker compose ps db | grep -q "healthy"; then
    echo "✅ Docker PostgreSQL is healthy"
else
    echo "⚠️  Warning: Docker PostgreSQL may not be healthy yet"
    echo "   Run: docker compose ps db"
fi

# Step 5: Run migrations
echo ""
echo "Step 5: Running database migrations..."
cd backend
uv run alembic upgrade head
echo "✅ Migrations completed"

# Step 6: Test connection
echo ""
echo "Step 6: Testing database connection..."
PYTHONPATH=src uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_connection():
    engine = create_async_engine('postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz')
    async with engine.begin() as conn:
        result = await conn.execute(__import__('sqlalchemy').text('SELECT version()'))
        version = result.scalar()
        print(f'✅ Connected to: {version}')
    await engine.dispose()

asyncio.run(test_connection())
"

echo ""
echo "=================================================="
echo "✅ Cleanup Complete!"
echo "=================================================="
echo ""
echo "Your setup is now using Docker PostgreSQL only."
echo ""
echo "Next steps:"
echo "  1. Run tests: cd backend && export PYTHONPATH=src && uv run pytest tests/ -v"
echo "  2. Start API: uv run uvicorn pazpaz.main:app --reload"
echo ""
echo "If you want to completely remove PostgreSQL 16:"
echo "  sudo rm -rf /Library/PostgreSQL/16"
echo ""
