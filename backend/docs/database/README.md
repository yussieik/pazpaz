# Database Documentation

PostgreSQL schema, migrations, and query optimization guides.

## 📋 Contents

This directory will contain:

- **Schema Design** - Entity relationship diagrams, normalization
- **Migration Patterns** - Alembic migration best practices
- **Index Strategy** - Performance indexes, partial indexes
- **Query Optimization** - pg_stat_statements analysis, query plans
- **Constraints** - Foreign keys, check constraints, unique indexes
- **Triggers & Functions** - PostgreSQL triggers (e.g., audit immutability)
- **Partitioning** - Table partitioning strategies (if needed)

## 🚀 Coming in Week 2+

Database documentation will be added as we implement:
- Sessions table (Week 2 Day 6)
- Session attachments (Week 2 Day 6)
- Plans of care (Week 3 Day 13)
- Email reminders (Week 4 Day 16)

## 📝 Current Schema

See existing migrations:
- `alembic/versions/` - All schema migrations
- `/docs/security/AUDIT_LOGGING_SCHEMA.md` - Audit events table design
- `/backend/docs/encryption/DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md` - Encryption migration pattern

## 🔍 Performance Targets

- **p95 latency:** <150ms for CRUD operations
- **p95 latency:** <500ms for complex queries (timeline)
- **Index coverage:** All foreign keys and frequently queried columns
- **Query plans:** Always use indexes (no sequential scans on large tables)
