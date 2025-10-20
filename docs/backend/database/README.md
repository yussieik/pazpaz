# Database Documentation

Comprehensive documentation for PazPaz database architecture, schema design, migrations, and performance optimization.

## 📋 Table of Contents

### Core Documentation
- [DATABASE_ARCHITECTURE_REVIEW.md](./DATABASE_ARCHITECTURE_REVIEW.md) - Complete schema analysis and recommendations
- [SESSIONS_SCHEMA.md](./SESSIONS_SCHEMA.md) - Sessions and attachments tables (PHI encryption)
- [WEEK2_DAY1_MORNING_SESSIONS_MIGRATION_REPORT.md](./WEEK2_DAY1_MORNING_SESSIONS_MIGRATION_REPORT.md) - Session table migration details

### Related Documentation
- [/docs/security/AUDIT_LOGGING_SCHEMA.md](/docs/security/AUDIT_LOGGING_SCHEMA.md) - Audit events table design
- [/docs/security/KEY_MANAGEMENT.md](/docs/security/KEY_MANAGEMENT.md) - Encryption key management and rotation procedures
- [/docs/security/encryption/](/docs/security/encryption/) - PHI encryption implementation guides
- [/backend/alembic/versions/](/backend/alembic/versions/) - All database migrations

## 🗄️ Current Database Schema

### Core Tables (13 total)
1. **workspaces** - Multi-tenant workspace isolation
2. **users** - User accounts with role-based access
3. **clients** - Client records (PII/PHI) with healthcare fields
4. **appointments** - Scheduling with conflict detection
5. **sessions** - SOAP notes with encrypted PHI (AES-256-GCM)
6. **session_attachments** - File references for S3/MinIO storage
7. **session_versions** - Amendment history tracking (immutable)
8. **services** - Service types and pricing
9. **locations** - Practice locations
10. **audit_events** - HIPAA-compliant audit trail (append-only)
11. **alembic_version** - Migration tracking

### Key Features
- **100% PHI Encryption**: All sensitive fields use AES-256-GCM via `EncryptedString` type with versioned keys
- **Workspace Isolation**: Every table includes workspace_id with CASCADE delete
- **Soft Delete**: All patient data uses soft delete (deleted_at) for audit trails
- **Performance Optimized**: Composite and partial indexes for <150ms p95 queries
- **Audit Logging**: Immutable audit_events table tracks all PHI access
- **Client PII/PHI Fully Encrypted**: All client PII fields (name, email, phone, address, emergency contacts) and PHI fields (medical_history, date_of_birth) now encrypted ✅

## 🚀 Migration History

### Applied Migrations (Current HEAD: 92df859932f2)
1. `65ac34a08850` - Initial schema (workspaces, users, clients, appointments)
2. `f6092aa0856d` - Add service and location entities
3. `83680210d7d2` - Add client healthcare fields (address, medical_history, emergency contacts)
4. `de72ee2cfb00` - Add audit_events table (HIPAA compliance)
5. `6be7adba063b` - Add pgcrypto extension
6. `8283b279aeac` - Fix pgcrypto functions
7. `430584776d5b` - Create sessions tables (SOAP notes)
8. `0131df2d459b` - Add appointment edit tracking fields
9. `9262695391b3` - Create session_versions table (amendment tracking)
10. `03742492d865` - Add session amendment tracking fields
11. `2de77d93d190` - Add soft delete fields to sessions
12. `11a114ee018b` - Add check constraint for finalized sessions
13. `ea67a34acb9c` - Add client-level attachments table
14. `d1f764670a60` - Add workspace storage quota fields
15. `a2341bb8aa45` - **Encrypt client PII fields (first_name, last_name, email, phone, address, medical_history, emergency contacts)**
16. `92df859932f2` - **Encrypt client date_of_birth field** (current HEAD)

### Running Migrations
```bash
# Apply all migrations
uv run alembic upgrade head

# Check current version
uv run alembic current

# Create new migration
uv run alembic revision -m "description"

# Rollback last migration
uv run alembic downgrade -1
```

## 🔍 Performance Targets & Metrics

### Query Performance Goals
- **p95 latency:** <150ms for CRUD operations ✅
- **p95 latency:** <500ms for complex queries (timeline) ✅
- **Index coverage:** 100% on foreign keys and frequent queries ✅
- **Query plans:** No sequential scans on tables >1000 rows ✅

### Current Index Strategy
- **Composite indexes** start with workspace_id (multi-tenant optimization)
- **Partial indexes** for common filters (is_draft=true, deleted_at IS NULL)
- **Covering indexes** for read-heavy queries (client timeline, appointment conflicts)
- **Expression indexes** planned for encrypted field searches (future)

### Storage Estimates
- Sessions: ~20.3 KB per record (with encryption overhead)
- Clients: ~2 KB per record (without attachments)
- Appointments: ~500 bytes per record
- Audit Events: ~1 KB per record
- Index overhead: ~2-3% of data size (excellent ratio)

## 🔒 Security & Compliance

### PHI Protection
- **Application-level encryption**: AES-256-GCM for all PHI fields
- **Key management**: AWS Secrets Manager integration (production)
- **Audit trail**: All PHI access logged to audit_events table
- **Soft delete only**: Patient data never hard-deleted (7-year retention)

### Workspace Isolation
- Foreign key CASCADE ensures complete data removal
- All queries filtered by workspace_id
- Composite indexes prevent cross-workspace scans
- Future: PostgreSQL Row-Level Security (RLS) for defense in depth

## 📊 Entity Relationships

```
┌─────────────┐
│  Workspace  │ (root tenant)
└──────┬──────┘
       │ CASCADE
       ├─────────────┬──────────────┬─────────────┬──────────┬──────────┐
       ▼             ▼              ▼             ▼          ▼          ▼
  ┌────────┐   ┌─────────┐   ┌──────────┐  ┌─────────┐ ┌────────┐ ┌─────────────┐
  │ Users  │   │ Clients │   │ Services │  │Locations│ │Sessions│ │ AuditEvents │
  └────┬───┘   └────┬────┘   └──────────┘  └─────────┘ └───┬────┘ └─────────────┘
       │            │                                        │
       │            ├────────────────────────────────────────┤
       │            ▼                                        │
       │      ┌──────────────┐                              │
       └─────►│ Appointments │◄─────────────────────────────┘
              └──────────────┘         (SET NULL)
```

### Cascade Behavior
- **CASCADE**: Workspace → All entities (complete tenant cleanup)
- **CASCADE**: Client → Appointments, Sessions (remove patient history)
- **CASCADE**: Session → Attachments, Versions (cleanup related data)
- **SET NULL**: User deletion preserves audit trail
- **SET NULL**: Service/Location deletion preserves appointments

## 🛠️ Development Tools

### Useful Database Commands
```bash
# Connect to database
docker exec -it pazpaz-db psql -U pazpaz -d pazpaz

# List all tables
\dt

# Describe table structure
\d+ sessions

# Show indexes
\di+ ix_sessions*

# Check table size
\dt+ sessions

# Analyze query performance
EXPLAIN ANALYZE SELECT ...
```

### Performance Monitoring
```sql
-- Check slow queries
SELECT * FROM pg_stat_statements
WHERE mean_exec_time > 150
ORDER BY mean_exec_time DESC;

-- Index usage statistics
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan;

-- Table bloat check
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## 📝 Documentation Standards

All database documentation must include:
- Table purpose and security considerations
- Column specifications with nullable/default values
- Index design with target query patterns
- Foreign key relationships and cascade behavior
- Performance benchmarks and storage estimates
- Migration testing results

## 🚧 Future Enhancements

### Week 3+ Planned Features
- **Plan of Care**: Treatment plans with goals and interventions
- **Email Reminders**: Appointment reminder queue tables
- **Reporting Views**: Materialized views for analytics
- **Full-text Search**: PostgreSQL FTS for client/note search
- **Row-Level Security**: Database-enforced workspace isolation
