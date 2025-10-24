# Database Migration Scripts

This directory contains production-ready database migration scripts for PazPaz.

## Scripts

### migrate.sh
**Purpose:** Production-safe database migration with comprehensive safety checks

**Features:**
- ✅ Automatic pre-migration backups (pg_dump -Fc format)
- ✅ Migration SQL preview with --dry-run
- ✅ Test migration on copy database before production
- ✅ Automatic rollback on failure (Alembic downgrade or backup restore)
- ✅ Post-migration validation and integrity checks
- ✅ Comprehensive logging and audit trail
- ✅ 300-second timeout with configurable override
- ✅ Support for both upgrade and downgrade operations

**Usage:**
```bash
# Standard migration
./migrate.sh upgrade

# Preview changes (dry-run)
./migrate.sh --dry-run upgrade

# Rollback to previous version
./migrate.sh downgrade -1

# Check current revision
./migrate.sh current

# Validate database state
./migrate.sh validate
```

### deploy-with-migrations.sh
**Purpose:** Example integration showing how to combine migrations with deployment

**Usage:**
```bash
# Deploy with migrations
./deploy-with-migrations.sh

# Skip migrations
./deploy-with-migrations.sh --skip-migration

# Force migration despite warnings
./deploy-with-migrations.sh --force
```

## Safety Features

| Feature | Description | Implementation |
|---------|-------------|----------------|
| **Pre-migration Backup** | Automatic database snapshot | `pg_dump -Fc` to `/opt/pazpaz/backups/migrations/` |
| **Test Migration** | Run on copy before production | Creates `pazpaz_test_migration` database |
| **Rollback Capability** | Automatic on failure | Alembic downgrade → Backup restore |
| **Validation** | Post-migration checks | Schema, foreign keys, query tests |
| **Timeout Protection** | Prevent stuck migrations | 300 seconds default, configurable |
| **Audit Logging** | Complete trail | Timestamped logs in `/opt/pazpaz/logs/` |

## Integration with CI/CD

The migration script is designed to integrate with the deployment pipeline:

1. **Pre-deployment:** Backup and validate current state
2. **Migration:** Apply with safety checks
3. **Deployment:** Only proceed if migration succeeds
4. **Post-deployment:** Validate complete system

## Environment Requirements

```bash
# Required environment variables (.env.production)
POSTGRES_PASSWORD=your-secure-password

# Database configuration (defaults)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pazpaz
DB_USER=pazpaz
```

## Docker Support

The scripts automatically detect Docker environments:
- Uses `docker exec` for containerized PostgreSQL
- Falls back to direct `psql` commands for local environments
- Compatible with docker-compose.prod.yml setup

## File Locations

| Type | Location |
|------|----------|
| **Backups** | `/opt/pazpaz/backups/migrations/` |
| **Logs** | `/opt/pazpaz/logs/migration-*.log` |
| **Reports** | `/opt/pazpaz/logs/migration-report-*.txt` |
| **Migrations** | `backend/alembic/versions/` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Pre-migration checks failed |
| 2 | Backup failed |
| 3 | Test migration failed |
| 4 | Production migration failed |
| 5 | Rollback failed |
| 6 | Validation failed |

## Documentation

For detailed documentation, see:
- [Database Migration Guide](../docs/deployment/database-migrations.md)
- [Deployment Script Guide](../docs/deployment/deploy-script.md)

## Testing

```bash
# Test script syntax
bash -n migrate.sh

# Test help command
./migrate.sh --help

# Test in development environment
./migrate.sh --env development --skip-backup upgrade
```

## Support

For issues or questions about database migrations:
1. Check logs in `/opt/pazpaz/logs/`
2. Review migration reports
3. Consult the [troubleshooting guide](../docs/deployment/database-migrations.md#troubleshooting)