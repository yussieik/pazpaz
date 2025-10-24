# Database Migration Guide

## Overview

The PazPaz database migration system provides production-safe schema migrations with comprehensive safety checks, automatic backups, test migrations, and rollback capability. This guide covers all aspects of database migrations for the PazPaz application.

## Table of Contents

- [Migration Script](#migration-script)
- [Safety Features](#safety-features)
- [Usage Examples](#usage-examples)
- [Migration Workflow](#migration-workflow)
- [Rollback Procedures](#rollback-procedures)
- [Testing Migrations](#testing-migrations)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Migration Script

The migration script (`scripts/migrate.sh`) is the primary tool for managing database schema changes in production.

### Location
```bash
/opt/pazpaz/scripts/migrate.sh  # Production
./scripts/migrate.sh             # Development
```

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `upgrade [revision]` | Upgrade database to revision (default: head) | `./migrate.sh upgrade` |
| `downgrade [revision]` | Downgrade database to revision | `./migrate.sh downgrade -1` |
| `current` | Show current database revision | `./migrate.sh current` |
| `history` | Show migration history | `./migrate.sh history` |
| `validate` | Validate database integrity | `./migrate.sh validate` |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Generate and show migration SQL without applying | false |
| `--skip-backup` | Skip database backup (NOT recommended) | false |
| `--skip-test` | Skip test migration (dangerous) | false |
| `--force` | Force migration even with warnings | false |
| `--timeout <seconds>` | Migration timeout | 300 |
| `--env <environment>` | Environment (production/staging/development) | production |

## Safety Features

The migration system implements multiple layers of safety to prevent data loss and ensure successful migrations:

### 1. Pre-Migration Backup
- **Automatic backup** before any migration
- **Compressed format** using `pg_dump -Fc`
- **Timestamped backups** stored in `/opt/pazpaz/backups/migrations/`
- **30-day retention** with automatic cleanup

### 2. Test Migration
- **Copy database** created from backup
- **Migration tested** on copy before production
- **Validation** of test migration results
- **Automatic cleanup** of test database

### 3. Rollback Capability
- **Alembic downgrade** as primary rollback method
- **Backup restore** as fallback if downgrade fails
- **Current revision tracking** for precise rollback
- **Automatic rollback** on migration failure

### 4. Post-Migration Validation
- **Schema validation** checking critical tables
- **Foreign key integrity** verification
- **Query tests** ensuring database accessibility
- **Migration report** generation for audit trail

### 5. Comprehensive Logging
- **Timestamped logs** in `/opt/pazpaz/logs/`
- **Detailed progress** tracking
- **Error reporting** with context
- **Migration reports** for auditing

## Usage Examples

### Standard Production Migration

```bash
# 1. Review pending migrations
./migrate.sh history

# 2. Dry run to preview changes
./migrate.sh --dry-run upgrade

# 3. Apply migration with all safety checks
./migrate.sh upgrade

# 4. Validate migration
./migrate.sh validate
```

### Emergency Rollback

```bash
# Rollback to previous revision
./migrate.sh downgrade -1

# Or rollback to specific revision
./migrate.sh downgrade abc123def456
```

### Development Testing

```bash
# Test migration without backup (development only)
./migrate.sh --skip-backup --env development upgrade

# Force migration despite test failures (use with caution)
./migrate.sh --force upgrade
```

## Migration Workflow

### Creating a New Migration

1. **Create migration with Alembic:**
```bash
cd backend
PYTHONPATH=src uv run alembic revision --autogenerate -m "Add feature X"
```

2. **Review generated migration:**
```bash
# Check the new file in backend/alembic/versions/
ls -la backend/alembic/versions/
```

3. **Test locally:**
```bash
# Apply to local development database
cd backend
PYTHONPATH=src uv run alembic upgrade head
```

4. **Test with migration script:**
```bash
# Use migration script for full safety checks
./scripts/migrate.sh --env development upgrade
```

### Production Deployment

1. **Pre-deployment checks:**
```bash
# Check current revision
./migrate.sh current

# Review pending migrations
./migrate.sh history

# Validate current database state
./migrate.sh validate
```

2. **Dry run:**
```bash
# Generate SQL and review changes
./migrate.sh --dry-run upgrade > /tmp/migration-preview.sql
cat /tmp/migration-preview.sql
```

3. **Apply migration:**
```bash
# Run with full safety checks
./migrate.sh upgrade
```

4. **Post-deployment validation:**
```bash
# Verify migration success
./migrate.sh validate

# Check application health
curl https://your-domain.com/health
```

## Rollback Procedures

### Automatic Rollback

The migration script automatically rolls back if:
- Test migration fails (unless `--force` is used)
- Production migration times out
- Post-migration validation fails
- Migration application fails

### Manual Rollback

#### Method 1: Using Alembic Downgrade
```bash
# Rollback one revision
./migrate.sh downgrade -1

# Rollback to specific revision
./migrate.sh downgrade abc123def456
```

#### Method 2: Restore from Backup
```bash
# If Alembic downgrade fails, restore backup manually
# 1. Find latest backup
ls -la /opt/pazpaz/backups/migrations/

# 2. Restore using pg_restore
pg_restore -U pazpaz -d pazpaz -c /opt/pazpaz/backups/migrations/pre-migration-TIMESTAMP.dump
```

### Rollback Decision Tree

```
Migration Failed?
├─ Yes → Automatic Rollback
│   ├─ Try Alembic Downgrade
│   │   ├─ Success → Done
│   │   └─ Failed → Restore from Backup
│   └─ Validate Rollback
└─ No → Validation Failed?
    ├─ Yes → Manual Decision
    │   ├─ Critical Issue → Rollback
    │   └─ Minor Issue → Keep & Fix
    └─ No → Success
```

## Testing Migrations

### Local Testing

1. **Create test database:**
```bash
createdb pazpaz_test
pg_restore -d pazpaz_test production-backup.dump
```

2. **Test migration:**
```bash
DATABASE_URL=postgresql://user:pass@localhost/pazpaz_test \
  ./migrate.sh upgrade
```

3. **Verify results:**
```bash
psql -d pazpaz_test -c "SELECT * FROM alembic_version;"
```

### Staging Testing

1. **Deploy to staging environment:**
```bash
./migrate.sh --env staging upgrade
```

2. **Run integration tests:**
```bash
pytest tests/integration/ --env staging
```

3. **Performance testing:**
```bash
# Verify p95 < 150ms requirement
./scripts/performance-test.sh --env staging
```

## Troubleshooting

### Common Issues and Solutions

#### Migration Timeout
**Problem:** Migration exceeds default 300-second timeout
```bash
ERROR: Migration timed out after 300 seconds
```

**Solution:** Increase timeout for large migrations
```bash
./migrate.sh --timeout 600 upgrade
```

#### Test Migration Fails
**Problem:** Test migration fails but you need to proceed
```bash
ERROR: Test migration failed
```

**Solution:** Review failure, then force if safe
```bash
# First, understand why it failed
./migrate.sh --dry-run upgrade

# If safe to proceed
./migrate.sh --force upgrade
```

#### Database Connection Failed
**Problem:** Cannot connect to database
```bash
ERROR: Cannot connect to database
```

**Solution:** Check credentials and connectivity
```bash
# Verify environment file
cat .env.production | grep POSTGRES

# Test connection
psql -h localhost -U pazpaz -d pazpaz -c "SELECT 1;"
```

#### Alembic Version Mismatch
**Problem:** Alembic version table out of sync
```bash
ERROR: Can't locate revision identified by 'abc123'
```

**Solution:** Manually fix alembic_version table
```bash
# Check current version
psql -d pazpaz -c "SELECT * FROM alembic_version;"

# Update to correct version
psql -d pazpaz -c "UPDATE alembic_version SET version_num = 'correct_revision';"
```

### Recovery Procedures

#### Corrupted Migration State
1. Backup current state
2. Drop alembic_version table
3. Manually set to known good revision
4. Run migrations from that point

```bash
# Backup current state
pg_dump -Fc pazpaz > emergency-backup.dump

# Fix alembic_version
psql -d pazpaz << EOF
DROP TABLE IF EXISTS alembic_version;
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
INSERT INTO alembic_version VALUES ('known_good_revision');
EOF

# Continue migrations
./migrate.sh upgrade
```

## Best Practices

### Before Migration

1. **Always backup first** - Never skip backup in production
2. **Review migration SQL** - Use `--dry-run` to preview changes
3. **Test in staging** - Validate in staging environment first
4. **Check disk space** - Ensure sufficient space for backup
5. **Schedule maintenance window** - Plan for potential downtime

### During Migration

1. **Monitor closely** - Watch logs in real-time
2. **Have rollback plan ready** - Know your rollback procedure
3. **Keep backup accessible** - Ensure backup file is valid
4. **Document any issues** - Record problems for postmortem

### After Migration

1. **Validate thoroughly** - Run `./migrate.sh validate`
2. **Test application** - Verify all features work
3. **Monitor performance** - Check for degradation
4. **Keep backup** - Don't delete backup immediately
5. **Document completion** - Update deployment log

### Migration Development

1. **Make migrations reversible** - Always include downgrade()
2. **Keep migrations small** - One logical change per migration
3. **Test both directions** - Test upgrade and downgrade
4. **Add comments** - Document complex changes
5. **Consider data migrations** - Handle existing data properly

### Example: Safe Migration Pattern

```python
"""Add index for performance

Revision ID: abc123def456
Revises: previous_revision
Create Date: 2024-10-24 10:00:00

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add index with IF NOT EXISTS for safety
    op.create_index(
        'idx_appointments_workspace_date',
        'appointments',
        ['workspace_id', 'date'],
        if_not_exists=True
    )

def downgrade():
    # Remove index with IF EXISTS for safety
    op.drop_index(
        'idx_appointments_workspace_date',
        'appointments',
        if_exists=True
    )
```

## Integration with Deployment

The migration script integrates with the main deployment script (`deploy.sh`):

```bash
# In deploy.sh, migrations are run before deployment
if ./scripts/migrate.sh upgrade; then
    # Continue with deployment
    docker-compose up -d
else
    # Abort deployment
    exit 1
fi
```

### Deployment Order

1. Pull latest code
2. **Run database migrations**
3. Build and deploy application
4. Run health checks
5. Switch traffic to new version

## Monitoring and Alerts

### Key Metrics

- Migration duration
- Backup size and duration
- Test migration success rate
- Production migration success rate
- Rollback frequency

### Alert Conditions

- Migration failure
- Rollback initiated
- Migration duration > threshold
- Backup failure
- Validation failure

### Example Monitoring Setup

```bash
# Add to monitoring system
curl -X POST https://monitoring.example.com/alert \
  -d "service=database-migration" \
  -d "status=$MIGRATION_STATUS" \
  -d "duration=$MIGRATION_DURATION" \
  -d "revision=$TARGET_REVISION"
```

## Appendix: Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_PASSWORD` | Database password | Yes |
| `DATABASE_URL` | Full connection string (optional) | No |
| `DEPLOYMENT_DIR` | Override deployment directory | No |
| `BACKUP_DIR` | Override backup directory | No |

## Appendix: File Locations

| File/Directory | Purpose |
|---------------|---------|
| `/opt/pazpaz/backups/migrations/` | Migration backups |
| `/opt/pazpaz/logs/migration-*.log` | Migration logs |
| `/opt/pazpaz/logs/migration-report-*.txt` | Migration reports |
| `backend/alembic/versions/` | Migration files |
| `backend/alembic.ini` | Alembic configuration |

## Related Documentation

- [Deployment Guide](./deploy-script.md)
- [Database Architecture](../architecture/database.md)
- [Backup and Recovery](./backup-recovery.md)
- [Disaster Recovery](../operations/disaster-recovery.md)