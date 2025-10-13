# Backend Documentation

This directory contains backend-specific technical documentation for the PazPaz practice management system. This serves as the central navigation hub for all backend-related documentation.

## 🚀 Getting Started

### Quick Start for Backend Development

1. **Setup Development Environment**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env with your configuration

   # Install dependencies (Python 3.13.5)
   uv python install 3.13.5
   uv python pin 3.13.5
   uv sync
   ```

2. **Start Services**
   ```bash
   # From project root
   docker-compose up -d db redis minio

   # From backend directory
   uv run alembic upgrade head
   uv run python -m pazpaz.main
   ```

3. **Run Tests**
   ```bash
   uv run pytest tests/
   ```

4. **Key Resources**
   - [API Patterns & Conventions](api/README.md)
   - [Database Schema](database/README.md)
   - [Storage Configuration](storage/STORAGE_CONFIGURATION.md)
   - [Testing Guide](/docs/testing/backend/PYTEST_CONFIGURATION_GUIDE.md)

## 📁 Directory Structure

```
docs/backend/                    # Backend documentation root
├── README.md                    # This file - navigation hub
│
├── api/                         # API Implementation
│   ├── README.md               # API patterns and conventions
│   ├── API.md                  # Detailed API implementation guide
│   ├── RATE_LIMITING_IMPLEMENTATION.md
│   └── FLEXIBLE_RECORD_MANAGEMENT.md
│
├── database/                    # Database Schema & Migrations
│   ├── README.md               # Database overview
│   ├── DATABASE_ARCHITECTURE_REVIEW.md
│   ├── SESSIONS_SCHEMA.md
│   └── WEEK2_DAY1_MORNING_SESSIONS_MIGRATION_REPORT.md
│
├── storage/                     # S3/MinIO File Storage
│   ├── STORAGE_CONFIGURATION.md
│   ├── FILE_UPLOAD_SECURITY.md
│   ├── S3_CREDENTIAL_MANAGEMENT.md
│   └── WEEK3_DAY11_STORAGE_IMPLEMENTATION_SUMMARY.md
│
├── PDF_METADATA_SANITIZATION_IMPLEMENTATION.md  # PDF PHI protection
└── SOFT_DELETE_PURGE_JOB.md                    # Soft delete implementation
```

## 📚 Documentation Categories

### API (`api/`)

**FastAPI endpoint implementation, patterns, and conventions.**

- [**README.md**](api/README.md) - API design patterns and best practices
- [**API.md**](api/API.md) - Comprehensive API implementation guide
- [**RATE_LIMITING_IMPLEMENTATION.md**](api/RATE_LIMITING_IMPLEMENTATION.md) - Redis-based sliding window rate limiting
- [**FLEXIBLE_RECORD_MANAGEMENT.md**](api/FLEXIBLE_RECORD_MANAGEMENT.md) - Soft delete and record lifecycle management

### Database (`database/`)

**PostgreSQL schema, migrations, and database architecture.**

- [**README.md**](database/README.md) - Database schema overview
- [**DATABASE_ARCHITECTURE_REVIEW.md**](database/DATABASE_ARCHITECTURE_REVIEW.md) - Comprehensive architecture review
- [**SESSIONS_SCHEMA.md**](database/SESSIONS_SCHEMA.md) - SOAP session notes schema with encryption
- [**Migration Report**](database/WEEK2_DAY1_MORNING_SESSIONS_MIGRATION_REPORT.md) - Sessions table migration implementation

### Storage (`storage/`)

**S3/MinIO file storage, security, and credential management.**

- [**STORAGE_CONFIGURATION.md**](storage/STORAGE_CONFIGURATION.md) - Complete S3/MinIO configuration guide
- [**FILE_UPLOAD_SECURITY.md**](storage/FILE_UPLOAD_SECURITY.md) - Triple validation, EXIF stripping, security
- [**S3_CREDENTIAL_MANAGEMENT.md**](storage/S3_CREDENTIAL_MANAGEMENT.md) - 840+ line credential management guide
- [**Implementation Summary**](storage/WEEK3_DAY11_STORAGE_IMPLEMENTATION_SUMMARY.md) - Week 3 Day 11 storage implementation

### Security & Compliance

**PHI protection, data sanitization, and compliance features.**

- [**PDF_METADATA_SANITIZATION_IMPLEMENTATION.md**](PDF_METADATA_SANITIZATION_IMPLEMENTATION.md) - PDF metadata stripping for PHI protection
- [**SOFT_DELETE_PURGE_JOB.md**](SOFT_DELETE_PURGE_JOB.md) - 30-day soft delete and automated purge implementation

### Testing

**Backend testing infrastructure and patterns.**

- [**pytest Configuration Guide**](/docs/testing/backend/PYTEST_CONFIGURATION_GUIDE.md) - Comprehensive pytest setup
- [**Test Fixture Analysis**](/docs/testing/backend/TEST_FIXTURE_ANALYSIS.md) - Fixture architecture deep dive
- [**Quick Reference**](/docs/testing/backend/TEST_FIXTURE_QUICK_REFERENCE.md) - Common test patterns
- [**CSRF Testing**](/docs/testing/backend/CSRF_TEST_GUIDE.md) - CSRF protection testing guide

## 📖 Reading Guide

### For Implementing New API Endpoints

**Read in this order:**

1. [**API Patterns**](api/README.md) - Understand FastAPI patterns
   - Request/response models with Pydantic
   - Workspace scoping requirements
   - Error handling patterns

2. [**Database Schema**](database/README.md) - Review relevant database models
   - SQLAlchemy model definitions
   - Relationship patterns
   - Query optimization

3. [**Testing Guide**](/docs/testing/backend/TEST_FIXTURE_QUICK_REFERENCE.md) - Write comprehensive tests
   - Common fixtures and patterns
   - Authentication testing
   - CSRF token handling

### For File Upload Implementation

**Read in this order:**

1. [**Storage Configuration**](storage/STORAGE_CONFIGURATION.md) - S3/MinIO setup
   - Environment configuration
   - Bucket management
   - Access policies

2. [**File Upload Security**](storage/FILE_UPLOAD_SECURITY.md) - Security implementation
   - Triple validation (magic bytes, extension, MIME)
   - EXIF metadata stripping
   - Virus scanning integration

3. [**PDF Metadata Sanitization**](PDF_METADATA_SANITIZATION_IMPLEMENTATION.md) - PHI protection
   - Automatic metadata stripping
   - HIPAA compliance

### For Implementing Soft Delete

**Read in this order:**

1. [**Soft Delete Implementation**](SOFT_DELETE_PURGE_JOB.md) - Complete guide
   - Database schema with soft delete columns
   - 30-day grace period logic
   - Restore functionality

2. [**Flexible Record Management**](api/FLEXIBLE_RECORD_MANAGEMENT.md) - API patterns
   - Soft delete endpoints
   - Query filtering
   - Audit logging

### For Writing Tests

**Read in this order:**

1. [**Quick Reference**](/docs/testing/backend/TEST_FIXTURE_QUICK_REFERENCE.md) - Common patterns
   - Fixture usage (`test_user_ws1`, `workspace_1`)
   - JWT authentication
   - CSRF tokens

2. [**pytest Configuration**](/docs/testing/backend/PYTEST_CONFIGURATION_GUIDE.md) - Deep dive
   - Configuration options
   - Database transactions
   - Troubleshooting

---

## 🔐 Security Notes

### PHI Encryption Requirements

All PHI (Protected Health Information) fields **MUST** be encrypted at rest. See [Encryption Architecture](/docs/security/encryption/ENCRYPTION_ARCHITECTURE.md) for implementation details.

- ✅ **Session notes:** Subjective, Objective, Assessment, Plan (SOAP)
- ✅ **Treatment plans:** Goals, progress notes
- ✅ **Medical history:** Conditions, medications
- ✅ **Contact info:** Email, phone (if considered PHI)

**Implementation:**
```python
from pazpaz.db.types import EncryptedString

class Session(Base):
    subjective = Column(EncryptedString(5000))  # Encrypted PHI
    objective = Column(EncryptedString(5000))   # Encrypted PHI
    assessment = Column(EncryptedString(5000))  # Encrypted PHI
    plan = Column(EncryptedString(5000))        # Encrypted PHI
```

### Performance Targets

- **API response time:** p95 <150ms (including encryption) ✅
- **Encryption overhead:** <10ms per field (actual: 0.001-0.003ms ✅)
- **Decryption overhead:** <10ms per field (actual: 0.001-0.003ms ✅)
- **Storage overhead:** ~38% (acceptable for HIPAA compliance) ✅

### Security Checklist

- [ ] All endpoints validate workspace access
- [ ] PHI fields use `EncryptedString` type
- [ ] File uploads sanitize metadata (EXIF, PDF)
- [ ] Audit logging captures all data modifications
- [ ] CSRF protection on state-changing requests
- [ ] Input validation on all user-supplied data

---

## 🔗 Related Documentation

### Security & Encryption

- [**Encryption Architecture**](/docs/security/encryption/ENCRYPTION_ARCHITECTURE.md) - AES-256-GCM design
- [**Encryption Usage Guide**](/docs/security/encryption/ENCRYPTION_USAGE_GUIDE.md) - How to encrypt PHI
- [**Key Rotation Procedures**](/docs/security/encryption/KEY_ROTATION_PROCEDURE.md) - 90-day rotation
- [**Audit Logging Schema**](/docs/security/AUDIT_LOGGING_SCHEMA.md) - Immutable audit trail

### Architecture

- [**Backend Architecture**](/docs/architecture/BACKEND_ARCHITECTURE_DESIGN.md) - FastAPI + SQLAlchemy design
- [**System Architecture**](/docs/architecture/ARCHITECTURE_SUMMARY.md) - High-level overview
- [**Project Overview**](/docs/PROJECT_OVERVIEW.md) - Product requirements

### Frontend Integration

- [**Frontend Documentation**](/docs/frontend/README.md) - Vue 3 application
- [**API Client**](/docs/frontend/API_CLIENT.md) - OpenAPI client usage

### Reports & Audits

- [**QA Reports**](/docs/reports/qa/) - Quality assurance reports
- [**Security Audits**](/docs/reports/security/) - Security audit findings
- [**Implementation Summaries**](/docs/reports/implementation/) - Feature implementations

---

## 🔄 Documentation Maintenance

### When to Update

- **After API Changes:** Update API documentation and OpenAPI spec
- **After Database Schema Changes:** Update database documentation and migration guides
- **After Security Implementation:** Update security guides and audit reports
- **After Performance Testing:** Update benchmarks and optimization guides
- **After Bug Fixes:** Document lessons learned and update relevant guides

### Documentation Standards

- All code examples must be valid Python/SQLAlchemy/FastAPI
- Include performance benchmarks for critical operations
- Document security rationale (HIPAA, OWASP)
- Keep migration templates up-to-date with current schema
- Link to related documentation
- Include "Last Updated" dates where relevant

---

## 🚀 Next Steps

### Current Implementation Status

- ✅ **Week 1:** Security foundation (encryption, audit logging, Redis)
- ✅ **Week 2:** SOAP notes and sessions
- ✅ **Week 3:** File uploads with security
- ⏳ **Week 4:** Plan of Care (in progress)
- ⏳ **Week 5:** Background jobs and deployment

### For New Features

1. Review relevant API patterns in [api/](api/)
2. Check database schema in [database/](database/)
3. Implement with security requirements (encryption, audit logging)
4. Write comprehensive tests using [testing guides](/docs/testing/backend/)
5. Update documentation

---

**Last Updated:** 2025-10-13

For project-wide documentation, see [/docs/README.md](/docs/README.md)
