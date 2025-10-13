# Backend Documentation

This directory contains backend-specific technical documentation for the PazPaz practice management system.

## 📁 Directory Structure

```
backend/docs/
├── README.md                    # This file
│
├── encryption/                  # PHI Encryption
│   ├── ENCRYPTION_ARCHITECTURE.md
│   ├── ENCRYPTION_IMPLEMENTATION_GUIDE.md
│   ├── ENCRYPTION_USAGE_GUIDE.md
│   ├── KEY_ROTATION_PROCEDURE.md
│   ├── DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md
│   ├── DAY3_AFTERNOON_ENCRYPTION_DESIGN_SUMMARY.md
│   ├── DAY4_DATABASE_ENCRYPTION_PERFORMANCE.md
│   ├── DATABASE_ARCHITECTURE_REVIEW_DAY4_ENCRYPTION.md
│   ├── WEEK1_DAY4_ENCRYPTION_IMPLEMENTATION_SUMMARY.md
│   └── ENCRYPTED_MODELS_EXAMPLE.py
│
├── testing/                     # Test Infrastructure
│   ├── PYTEST_CONFIGURATION_GUIDE.md
│   ├── TEST_FIXTURE_ANALYSIS.md
│   └── TEST_FIXTURE_QUICK_REFERENCE.md
│
├── api/                         # API Implementation
│   └── README.md (Coming in Week 2+)
│
├── database/                    # Database Schema & Migrations
│   └── README.md (Coming in Week 2+)
│
└── performance/                 # Performance Benchmarks
    └── README.md (Coming in Week 5)
```

## 📚 Documentation Categories

### Encryption (`encryption/`)

**PHI encryption implementation, key management, and security controls.**

#### Core Guides
- **ENCRYPTION_ARCHITECTURE.md** (41 KB) - Encryption system design and architecture
- **ENCRYPTION_IMPLEMENTATION_GUIDE.md** (33 KB) - Step-by-step implementation guide
- **ENCRYPTION_USAGE_GUIDE.md** (19 KB) - How to use encryption in your code
- **KEY_ROTATION_PROCEDURE.md** (31 KB) - Routine and emergency key rotation procedures

#### Database Integration
- **DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md** (29 KB) - Migration template for encrypted columns
- **ENCRYPTED_MODELS_EXAMPLE.py** (16 KB) - SQLAlchemy models with encryption examples

#### Implementation Reports
- **DAY3_AFTERNOON_ENCRYPTION_DESIGN_SUMMARY.md** (15 KB) - Day 3 design decisions
- **DAY4_DATABASE_ENCRYPTION_PERFORMANCE.md** (18 KB) - Performance benchmarks and analysis
- **DATABASE_ARCHITECTURE_REVIEW_DAY4_ENCRYPTION.md** (50 KB) - Architecture review and validation
- **WEEK1_DAY4_ENCRYPTION_IMPLEMENTATION_SUMMARY.md** (9 KB) - Week 1 Day 4 summary

### Testing (`testing/`)

**pytest configuration, test fixtures, and testing best practices.**

- **PYTEST_CONFIGURATION_GUIDE.md** (22 KB) - Comprehensive pytest configuration reference
- **TEST_FIXTURE_ANALYSIS.md** (15 KB) - Test fixture architecture and troubleshooting
- **TEST_FIXTURE_QUICK_REFERENCE.md** (6 KB) - Quick reference for common test patterns

### API (`api/`)

**FastAPI endpoint implementation guides (Coming in Week 2+).**

- Endpoint patterns and best practices
- Request/response schema design
- Authentication guards and workspace scoping
- Error handling and validation

### Database (`database/`)

**PostgreSQL schema and migration documentation (Coming in Week 2+).**

- Entity relationship diagrams
- Alembic migration patterns
- Index strategy and optimization
- Query performance analysis

### Performance (`performance/`)

**Performance benchmarks and optimization (Coming in Week 5).**

- API response time benchmarks
- Load testing results
- Profiling and optimization guides
- Monitoring and alerts

---

## 📖 Reading Guide

### For Implementing PHI Encryption

**Read in this order:**

1. **ENCRYPTION_ARCHITECTURE.md** - Understand the design decisions
   - AES-256-GCM encryption
   - Application-level vs database-level
   - Key management strategy (AWS Secrets Manager)

2. **ENCRYPTION_USAGE_GUIDE.md** - Quick start guide
   - How to encrypt/decrypt fields
   - Using `EncryptedString` SQLAlchemy type
   - Performance considerations

3. **ENCRYPTION_IMPLEMENTATION_GUIDE.md** - Detailed implementation
   - Step-by-step migration guide
   - Code examples
   - Testing encrypted models

4. **ENCRYPTED_MODELS_EXAMPLE.py** - Working code examples
   - Session model with encrypted SOAP notes
   - Treatment plan with encrypted goals
   - Best practices

### For Key Rotation

**Read in this order:**

1. **KEY_ROTATION_PROCEDURE.md** - Complete procedures
   - Routine rotation (every 90 days)
   - Emergency rotation (within 24 hours)
   - Zero-downtime migration

2. **DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md** - Migration template
   - Alembic migration for key rotation
   - Dual-write pattern
   - Cleanup procedures

### For Writing Tests

**Read in this order:**

1. **TEST_FIXTURE_QUICK_REFERENCE.md** - Quick patterns
   - Common fixtures (`test_user_ws1`, `workspace_1`)
   - JWT authentication patterns
   - CSRF token handling

2. **PYTEST_CONFIGURATION_GUIDE.md** - Comprehensive reference
   - pytest configuration (`pytest.ini`)
   - Fixture architecture
   - Database setup/teardown
   - Troubleshooting

3. **TEST_FIXTURE_ANALYSIS.md** - Deep dive
   - Architecture decisions
   - Why function-scoped fixtures
   - Transaction rollback strategy
   - Stability verification

---

## 🔐 Security Notes

### PHI Encryption Requirements

All PHI (Protected Health Information) fields **MUST** be encrypted at rest:

- ✅ **Session notes:** Subjective, Objective, Assessment, Plan (SOAP)
- ✅ **Treatment plans:** Goals, progress notes
- ✅ **Medical history:** Conditions, medications
- ✅ **Contact info:** Email, phone (if considered PHI)

**Implementation:**
```python
from pazpaz.db.types import EncryptedString

class Session(Base):
    subjective = Column(EncryptedString)  # Encrypted PHI
    objective = Column(EncryptedString)   # Encrypted PHI
    assessment = Column(EncryptedString)  # Encrypted PHI
    plan = Column(EncryptedString)        # Encrypted PHI
```

### Performance Targets

- **Encryption overhead:** <10ms per field (actual: 0.001-0.003ms ✅)
- **Decryption overhead:** <10ms per field (actual: 0.001-0.003ms ✅)
- **API response time:** p95 <150ms (including encryption) ✅
- **Storage overhead:** ~38% (acceptable for HIPAA compliance) ✅

---

## 📝 Quick Links

### Encryption

- [Architecture Overview](encryption/ENCRYPTION_ARCHITECTURE.md)
- [Quick Start Guide](encryption/ENCRYPTION_USAGE_GUIDE.md)
- [Implementation Guide](encryption/ENCRYPTION_IMPLEMENTATION_GUIDE.md)
- [Key Rotation Procedures](encryption/KEY_ROTATION_PROCEDURE.md)
- [Code Examples](encryption/ENCRYPTED_MODELS_EXAMPLE.py)

### Testing

- [Quick Reference](testing/TEST_FIXTURE_QUICK_REFERENCE.md)
- [pytest Configuration Guide](testing/PYTEST_CONFIGURATION_GUIDE.md)
- [Fixture Architecture](testing/TEST_FIXTURE_ANALYSIS.md)

### Performance Reports

- [Encryption Performance](encryption/DAY4_DATABASE_ENCRYPTION_PERFORMANCE.md)
- [Architecture Review](encryption/DATABASE_ARCHITECTURE_REVIEW_DAY4_ENCRYPTION.md)

---

## 🔄 Documentation Maintenance

### When to Update

- **After Encryption Changes:** Update guides and examples
- **After Test Fixture Changes:** Update pytest configuration guide
- **Performance Regressions:** Update performance reports
- **New Features:** Add examples to ENCRYPTED_MODELS_EXAMPLE.py

### Documentation Standards

- All code examples must be valid Python/SQLAlchemy
- Include performance benchmarks for encryption operations
- Document security rationale (HIPAA, OWASP)
- Keep migration templates up-to-date with current schema

---

## 🚀 Next Steps

### For Week 2 (SOAP Notes Implementation)

1. Review **ENCRYPTION_USAGE_GUIDE.md** for encrypting SOAP fields
2. Use **ENCRYPTED_MODELS_EXAMPLE.py** as reference for Session model
3. Follow **DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md** for Alembic migration
4. Run performance tests (target: <10ms encryption overhead)

### For Key Rotation (Quarterly)

1. Follow **KEY_ROTATION_PROCEDURE.md** routine procedure
2. Use **DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md** for migration
3. Verify dual-write pattern during transition
4. Monitor performance during rotation

---

For project-wide documentation, see [/docs/README.md](../../docs/README.md)
