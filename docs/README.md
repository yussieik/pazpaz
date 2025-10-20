# PazPaz Documentation

This directory contains all project-wide documentation for the PazPaz practice management system.

## 📁 Directory Structure

```
docs/
├── README.md                              # This file
├── SECURITY_FIRST_IMPLEMENTATION_PLAN.md  # Master implementation plan
├── PROJECT_OVERVIEW.md                    # Product overview and features
├── CONTEXT.md                             # Project context
├── AGENT_ROUTING_GUIDE.md                 # Agent delegation guide
│
├── security/                              # Security & Compliance
│   ├── encryption/                        # PHI encryption implementation
│   │   ├── ENCRYPTION_ARCHITECTURE.md
│   │   ├── ENCRYPTION_IMPLEMENTATION_GUIDE.md
│   │   ├── ENCRYPTION_USAGE_GUIDE.md
│   │   ├── KEY_ROTATION_PROCEDURE.md
│   │   ├── DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md
│   │   └── AWS_SECRETS_MANAGER_SETUP.md
│   ├── AUDIT_LOGGING_SCHEMA.md
│   ├── AUDIT_LOGGING_IMPLEMENTATION_REPORT.md
│   ├── REDIS_CONFIGURATION.md
│   ├── REDIS_MIGRATION_GUIDE.md
│   └── REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md
│
├── architecture/                          # System Architecture
│   ├── ARCHITECTURE_SUMMARY.md
│   └── BACKEND_ARCHITECTURE_DESIGN.md
│
├── backend/                               # Backend Implementation
│   ├── README.md
│   ├── api/                               # API Patterns
│   │   ├── README.md
│   │   ├── API.md
│   │   ├── RATE_LIMITING_IMPLEMENTATION.md
│   │   └── FLEXIBLE_RECORD_MANAGEMENT.md
│   ├── database/                          # Database Schema & Migrations
│   │   ├── README.md
│   │   ├── DATABASE_ARCHITECTURE_REVIEW.md
│   │   ├── SESSIONS_SCHEMA.md
│   │   └── WEEK2_DAY1_MORNING_SESSIONS_MIGRATION_REPORT.md
│   ├── encryption/                        # Encryption Operations (Supplemental)
│   │   ├── ENCRYPTION_KEY_ROTATION.md     # Key rotation procedures
│   │   └── KEY_BACKUP_RECOVERY.md         # Key backup and recovery
│   ├── storage/                           # S3/MinIO File Storage
│   │   ├── STORAGE_CONFIGURATION.md
│   │   ├── FILE_UPLOAD_SECURITY.md
│   │   ├── S3_CREDENTIAL_MANAGEMENT.md
│   │   └── WEEK3_DAY11_STORAGE_IMPLEMENTATION_SUMMARY.md
│   ├── SOFT_DELETE_PURGE_JOB.md
│   └── PDF_METADATA_SANITIZATION_IMPLEMENTATION.md
│
├── frontend/                              # Frontend (Vue 3)
│   ├── README.md
│   ├── API_CLIENT.md
│   ├── TESTING.md
│   ├── SESSION_EDITOR_IMPLEMENTATION_SUMMARY.md
│   ├── LOCALSTORAGE_ENCRYPTION_VERIFICATION.md
│   ├── AUTOSAVE_TEST_FIX_REPORT.md
│   ├── TIME_PICKER_UX_IMPROVEMENTS.md
│   ├── p0-keyboard-implementation.md
│   └── keyboard-shortcuts-manual-test.md
│
├── testing/                               # Testing Strategy
│   ├── ROUTING_TEST_SCENARIOS.md
│   ├── MANUAL_TEST_GUIDE.md
│   ├── backend/                           # Backend Test Infrastructure
│   │   ├── PYTEST_CONFIGURATION_GUIDE.md
│   │   ├── TEST_FIXTURE_ANALYSIS.md
│   │   ├── TEST_FIXTURE_BEST_PRACTICES.md
│   │   ├── TEST_FIXTURE_QUICK_REFERENCE.md
│   │   └── CSRF_TEST_GUIDE.md
│   └── frontend/                          # Frontend Testing (Coming soon)
│
├── reports/                               # QA & Security Reports
│   ├── qa/                                # Quality Assurance Reports
│   │   ├── QA_REPORT_WEEK1_COMPLETION.md
│   │   ├── QA_REPORT_WEEK2_DAY10_FINAL.md
│   │   ├── QA_REPORT_PDF_METADATA_STRIPPING.md
│   │   ├── WEEK_1_DAY_5_CORRECTED_STATUS.md
│   │   ├── TOAST_AUDIT_AND_FIXES.md
│   │   └── TOAST_FIX_TESTING.md
│   ├── security/                          # Security Audit Reports
│   │   ├── FILE_UPLOAD_SECURITY_AUDIT_WEEK3.md
│   │   ├── FILE_UPLOAD_SECURITY_REVERIFICATION_REPORT.md
│   │   ├── FILE_UPLOAD_SECURITY_SUMMARY.md
│   │   ├── SECURITY_AUDIT_WEEK2_DAY10.md
│   │   ├── LOCALSTORAGE_ENCRYPTION_VERIFICATION_REPORT.md
│   │   ├── S3_CREDENTIAL_SECURITY_REMEDIATION_REPORT.md
│   │   └── WEEK2_SECURITY_SUMMARY.md
│   └── implementation/                    # Implementation Summaries
│       ├── DAY9_IMPLEMENTATION_SUMMARY.md
│       ├── ENCRYPTED_OFFLINE_BACKUP_IMPLEMENTATION.md
│       └── PDF_METADATA_STRIPPING_SUMMARY.md
│
├── performance/                           # Performance Benchmarks
│   └── backend/                           # Backend Performance
│       └── README.md
│
├── deployment/                            # Infrastructure & Deployment
│   └── README.md
│
└── operations/                            # Day-to-day Operations
    └── README.md
```

## 📚 Documentation Categories

### Main Documentation (Root Level)

**High-level planning and overview documents that apply to the entire project.**

- **SECURITY_FIRST_IMPLEMENTATION_PLAN.md** - 5-week implementation plan with security-first approach
- **PROJECT_OVERVIEW.md** - Product vision, features, and success criteria
- **CONTEXT.md** - Project context and background
- **AGENT_ROUTING_GUIDE.md** - Guide for delegating tasks to specialized agents
- **QUICKSTART.md** - Quick start guide for local development

### Security & Compliance (`security/`)

**Authentication, authorization, audit logging, encryption, and HIPAA compliance documentation.**

#### Encryption (`security/encryption/`)
- **ENCRYPTION_ARCHITECTURE.md** (41 KB) - Encryption system design (AES-256-GCM)
- **ENCRYPTION_IMPLEMENTATION_GUIDE.md** (33 KB) - Step-by-step implementation guide
- **ENCRYPTION_USAGE_GUIDE.md** (19 KB) - How to use encryption in your code
- **KEY_ROTATION_PROCEDURE.md** (31 KB) - Routine and emergency key rotation procedures
- **DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md** (29 KB) - Migration template for encrypted columns
- **AWS_SECRETS_MANAGER_SETUP.md** - AWS Secrets Manager configuration for key management

**Note:** Additional operational encryption docs exist in `backend/encryption/` (ENCRYPTION_KEY_ROTATION.md, KEY_BACKUP_RECOVERY.md) for operational procedures.

#### Authentication & Authorization
- **DEV_AUTHENTICATION_GUIDE.md** - Development authentication setup and testing

#### Redis & Audit Logging
- **AUDIT_LOGGING_SCHEMA.md** - Database schema for audit events (immutable logs)
- **AUDIT_LOGGING_IMPLEMENTATION_REPORT.md** - Audit middleware implementation details
- **REDIS_CONFIGURATION.md** - Redis security configuration guide
- **REDIS_MIGRATION_GUIDE.md** - Migration guide for Redis authentication
- **REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md** - Redis security implementation summary

### Architecture (`architecture/`)

**System design, component architecture, and technical decisions.**

- **ARCHITECTURE_SUMMARY.md** - High-level architecture overview
- **BACKEND_ARCHITECTURE_DESIGN.md** - Detailed backend architecture (FastAPI, SQLAlchemy)

### Backend (`backend/`)

**Backend implementation documentation, API patterns, database schema, and storage.**

#### API (`backend/api/`)
- **README.md** - API design patterns and best practices
- **API.md** - API implementation guide and conventions
- **RATE_LIMITING_IMPLEMENTATION.md** - Redis-based rate limiting (sliding window)
- **FLEXIBLE_RECORD_MANAGEMENT.md** - Soft delete and record management patterns

#### Database (`backend/database/`)
- **README.md** - Database schema overview
- **DATABASE_ARCHITECTURE_REVIEW.md** - Comprehensive database architecture review
- **SESSIONS_SCHEMA.md** - SOAP session notes schema with encryption
- **WEEK2_DAY1_MORNING_SESSIONS_MIGRATION_REPORT.md** - Sessions table migration report

#### Storage (`backend/storage/`)
- **STORAGE_CONFIGURATION.md** - S3/MinIO storage configuration
- **FILE_UPLOAD_SECURITY.md** - File upload security implementation (triple validation, EXIF stripping)
- **S3_CREDENTIAL_MANAGEMENT.md** (840+ lines) - Credential management, rotation, and security
- **WEEK3_DAY11_STORAGE_IMPLEMENTATION_SUMMARY.md** - Storage implementation summary

#### Miscellaneous
- **SOFT_DELETE_PURGE_JOB.md** - Soft delete and purge job implementation
- **PDF_METADATA_SANITIZATION_IMPLEMENTATION.md** - PDF metadata stripping for PHI protection

### Frontend (`frontend/`)

**Vue 3 application documentation, component architecture, and UI patterns.**

- **README.md** - Frontend architecture overview
- **API_CLIENT.md** - API client integration and usage
- **TESTING.md** - Frontend testing strategy and patterns
- **SESSION_EDITOR_IMPLEMENTATION_SUMMARY.md** - SOAP notes editor implementation
- **LOCALSTORAGE_ENCRYPTION_VERIFICATION.md** - Client-side encryption verification
- **AUTOSAVE_TEST_FIX_REPORT.md** - Autosave functionality test fixes
- **TIME_PICKER_UX_IMPROVEMENTS.md** - Time picker UX enhancements
- **p0-keyboard-implementation.md** - Keyboard shortcuts implementation (P0)
- **keyboard-shortcuts-manual-test.md** - Manual testing guide for keyboard shortcuts

### Testing (`testing/`)

**Testing strategy, test patterns, and quality assurance.**

- **ROUTING_TEST_SCENARIOS.md** - API routing test scenarios
- **MANUAL_TEST_GUIDE.md** - Manual testing procedures and checklists

#### Backend Testing (`testing/backend/`)
- **PYTEST_CONFIGURATION_GUIDE.md** (22 KB) - Comprehensive pytest configuration reference
- **TEST_FIXTURE_ANALYSIS.md** (15 KB) - Test fixture architecture and troubleshooting
- **TEST_FIXTURE_BEST_PRACTICES.md** - Best practices for writing maintainable tests
- **TEST_FIXTURE_QUICK_REFERENCE.md** (6 KB) - Quick reference for common test patterns
- **CSRF_TEST_GUIDE.md** - CSRF protection testing guide

### Reports (`reports/`)

**Quality assurance, security audit reports, and implementation summaries.**

#### QA Reports (`reports/qa/`)
- **QA_REPORT_WEEK1_COMPLETION.md** - Week 1 completion QA report
- **QA_REPORT_WEEK2_DAY10_FINAL.md** - Week 2 Day 10 final QA report
- **QA_REPORT_PDF_METADATA_STRIPPING.md** - PDF metadata stripping QA report (9.7/10 quality)
- **WEEK_1_DAY_5_CORRECTED_STATUS.md** - Week 1 Day 5 corrected status
- **TOAST_AUDIT_AND_FIXES.md** - Toast notification system audit and fixes
- **TOAST_FIX_TESTING.md** - Toast fix testing results

#### Security Reports (`reports/security/`)
- **FILE_UPLOAD_SECURITY_AUDIT_WEEK3.md** - Week 3 file upload security audit
- **FILE_UPLOAD_SECURITY_REVERIFICATION_REPORT.md** - Security re-verification (9.5/10 score)
- **FILE_UPLOAD_SECURITY_SUMMARY.md** - File upload security summary
- **SECURITY_AUDIT_WEEK2_DAY10.md** - Week 2 Day 10 security audit
- **LOCALSTORAGE_ENCRYPTION_VERIFICATION_REPORT.md** - localStorage encryption verification
- **S3_CREDENTIAL_SECURITY_REMEDIATION_REPORT.md** - S3 credential security remediation
- **WEEK2_SECURITY_SUMMARY.md** - Week 2 security summary

#### Implementation Reports (`reports/implementation/`)
- **DAY9_IMPLEMENTATION_SUMMARY.md** - Day 9 implementation summary
- **ENCRYPTED_OFFLINE_BACKUP_IMPLEMENTATION.md** - Encrypted offline backup implementation
- **PDF_METADATA_STRIPPING_SUMMARY.md** - PDF metadata stripping implementation summary

### Performance (`performance/`)

**Performance benchmarks and optimization.**

#### Backend Performance (`performance/backend/`)
- **PERFORMANCE_TESTING.md** - Performance testing strategy and benchmarks
- **README.md** - Performance monitoring and optimization guide

Future additions (Week 5):
- API response time benchmarks
- Load testing results
- Profiling and optimization guides
- Monitoring and alerts

### Deployment (`deployment/`)

**Infrastructure and deployment documentation (Coming in Week 5).**

- AWS/cloud infrastructure
- CI/CD pipelines
- Environment configuration
- Database migration procedures
- Monitoring and alerting

### Operations (`operations/`)

**Day-to-day operations and maintenance (Coming in Week 5).**

- Runbooks and procedures
- Troubleshooting guides
- Incident response
- Performance tuning
- Security incident procedures

---

## 📖 Reading Guide

### For New Developers

1. Start with **PROJECT_OVERVIEW.md** to understand the product
2. Read **SECURITY_FIRST_IMPLEMENTATION_PLAN.md** to understand the development approach
3. Review **architecture/ARCHITECTURE_SUMMARY.md** for system design
4. Check **AGENT_ROUTING_GUIDE.md** to understand how to delegate tasks

### For Implementing PHI Encryption

**Read in this order:**

1. **security/encryption/ENCRYPTION_ARCHITECTURE.md** - Understand the design decisions
   - AES-256-GCM encryption
   - Application-level vs database-level
   - Key management strategy (AWS Secrets Manager)

2. **security/encryption/ENCRYPTION_USAGE_GUIDE.md** - Quick start guide
   - How to encrypt/decrypt fields
   - Using `EncryptedString` SQLAlchemy type
   - Performance considerations

3. **security/encryption/ENCRYPTION_IMPLEMENTATION_GUIDE.md** - Detailed implementation
   - Step-by-step migration guide
   - Code examples
   - Testing encrypted models

4. **security/encryption/ENCRYPTED_MODELS_EXAMPLE.py** - Working code examples
   - Session model with encrypted SOAP notes
   - Treatment plan with encrypted goals
   - Best practices

### For Security Review

1. **SECURITY_FIRST_IMPLEMENTATION_PLAN.md** - Week 1 security foundation
2. **security/AUDIT_LOGGING_SCHEMA.md** - Audit trail design
3. **security/REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md** - Redis hardening
4. **security/encryption/ENCRYPTION_ARCHITECTURE.md** - PHI encryption implementation
5. **backend/storage/FILE_UPLOAD_SECURITY.md** - File upload security
6. **reports/security/** - Security audit reports

### For Architecture Review

1. **architecture/BACKEND_ARCHITECTURE_DESIGN.md** - Detailed backend design
2. **architecture/ARCHITECTURE_SUMMARY.md** - High-level overview
3. **PROJECT_OVERVIEW.md** - Product requirements driving architecture

### For Writing Tests

**Read in this order:**

1. **testing/backend/TEST_FIXTURE_QUICK_REFERENCE.md** - Quick patterns
   - Common fixtures (`test_user_ws1`, `workspace_1`)
   - JWT authentication patterns
   - CSRF token handling

2. **testing/backend/PYTEST_CONFIGURATION_GUIDE.md** - Comprehensive reference
   - pytest configuration (`pytest.ini`)
   - Fixture architecture
   - Database setup/teardown
   - Troubleshooting

3. **testing/backend/TEST_FIXTURE_ANALYSIS.md** - Deep dive
   - Architecture decisions
   - Why function-scoped fixtures
   - Transaction rollback strategy
   - Stability verification

### For File Upload Implementation

1. **backend/storage/STORAGE_CONFIGURATION.md** - S3/MinIO setup
2. **backend/storage/FILE_UPLOAD_SECURITY.md** - Security implementation
3. **backend/storage/S3_CREDENTIAL_MANAGEMENT.md** - Credential management
4. **backend/PDF_METADATA_SANITIZATION_IMPLEMENTATION.md** - PDF metadata stripping

---

## 🔒 Security Requirements

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
    subjective = Column(EncryptedString(5000))  # Encrypted PHI
    objective = Column(EncryptedString(5000))   # Encrypted PHI
    assessment = Column(EncryptedString(5000))  # Encrypted PHI
    plan = Column(EncryptedString(5000))        # Encrypted PHI
```

### Performance Targets

- **Encryption overhead:** <10ms per field (actual: 0.001-0.003ms ✅)
- **Decryption overhead:** <10ms per field (actual: 0.001-0.003ms ✅)
- **API response time:** p95 <150ms (including encryption) ✅
- **Storage overhead:** ~38% (acceptable for HIPAA compliance) ✅

---

## 🔄 Documentation Maintenance

### When to Update

- **Weekly:** Update SECURITY_FIRST_IMPLEMENTATION_PLAN.md with progress
- **After Major Changes:** Update architecture docs when system design changes
- **New Features:** Document security controls, audit logging, and encryption
- **Bug Fixes:** Update relevant guides with lessons learned
- **Security Audits:** Add reports to `reports/security/`
- **QA Reviews:** Add reports to `reports/qa/`

### Documentation Standards

- Use clear, descriptive headers
- Include code examples where relevant
- Document security rationale (HIPAA compliance, OWASP best practices)
- Keep diagrams and examples up-to-date
- Link to related documentation
- All code examples must be valid Python/SQLAlchemy/TypeScript

---

## 📝 Quick Links

### Implementation

- [Security-First Implementation Plan](SECURITY_FIRST_IMPLEMENTATION_PLAN.md)
- [Agent Routing Guide](AGENT_ROUTING_GUIDE.md)

### Architecture

- [Backend Architecture](architecture/BACKEND_ARCHITECTURE_DESIGN.md)
- [Architecture Summary](architecture/ARCHITECTURE_SUMMARY.md)

### Security

- [Encryption Architecture](security/encryption/ENCRYPTION_ARCHITECTURE.md)
- [Encryption Usage Guide](security/encryption/ENCRYPTION_USAGE_GUIDE.md)
- [Audit Logging Schema](security/AUDIT_LOGGING_SCHEMA.md)
- [Redis Security](security/REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md)
- [File Upload Security](backend/storage/FILE_UPLOAD_SECURITY.md)

### Backend

- [API Patterns](backend/api/)
- [Database Schema](backend/database/)
- [Storage Configuration](backend/storage/)
- [Testing Guide](testing/backend/PYTEST_CONFIGURATION_GUIDE.md)

### Frontend

- [Frontend Overview](frontend/README.md)
- [Session Editor](frontend/SESSION_EDITOR_IMPLEMENTATION_SUMMARY.md)
- [Keyboard Shortcuts](frontend/p0-keyboard-implementation.md)

### Reports

- [QA Reports](reports/qa/)
- [Security Reports](reports/security/)

---

## 🚀 Next Steps

### For Week 3 (File Upload & Plan of Care)

1. Review **backend/storage/STORAGE_CONFIGURATION.md** for S3/MinIO setup
2. Review **backend/storage/FILE_UPLOAD_SECURITY.md** for security implementation
3. Use **security/encryption/ENCRYPTION_USAGE_GUIDE.md** for encrypting Plan of Care fields
4. Run performance tests (target: <150ms p95 response time)

### For Key Rotation (Quarterly)

1. Follow **security/encryption/KEY_ROTATION_PROCEDURE.md** routine procedure
2. Use **security/encryption/DATABASE_ENCRYPTION_MIGRATION_TEMPLATE.md** for migration
3. Verify dual-write pattern during transition
4. Monitor performance during rotation

---

**Note:** All documentation is consolidated under this main `docs/` directory. Legacy folders (`/backend/docs/`, `/frontend/docs/`) exist but are deprecated and contain minimal content. All new documentation should be added to `/docs/`.
