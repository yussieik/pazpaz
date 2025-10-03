# 🛡️ Security-First Implementation Plan
## PazPaz Features 1-3: SOAP Notes, Plan of Care, Email Reminders

**Created:** 2025-10-03
**Status:** Week 1 Day 1 - COMPLETED ✅
**Approach:** Security-First with Parallel Agent Execution
**Total Duration:** 5 weeks (25 days)
**Last Updated:** 2025-10-03 (Day 1 completed)

---

## 📋 Executive Summary

This plan implements three critical features (SOAP Notes, Plan of Care, Email Reminders) with **security and HIPAA compliance as the foundation**. We address all CRITICAL vulnerabilities BEFORE implementing PHI-handling features.

### Key Principles
1. **No PHI storage without encryption at rest**
2. **No API endpoints without authentication + CSRF protection**
3. **No data operations without audit logging**
4. **Parallel agent execution where possible**
5. **Each week ends with working, tested, secure code**

### Success Criteria
- ✅ All CRITICAL security vulnerabilities fixed
- ✅ HIPAA compliance requirements met
- ✅ Performance targets achieved (p95 < 150ms)
- ✅ Workspace isolation verified
- ✅ Comprehensive test coverage

---

## 🗓️ Week-by-Week Breakdown

### **WEEK 1: Security Foundation (Days 1-5)** - IN PROGRESS 🔄
**Goal:** Fix all CRITICAL security vulnerabilities
**Progress:** Day 1 Complete ✅ | Day 2 Complete ✅ | Days 3-5 Pending

### **WEEK 2: SOAP Notes Core (Days 6-10)**
**Goal:** Implement session documentation with encryption

### **WEEK 3: SOAP Notes Complete + Plan of Care (Days 11-15)**
**Goal:** File attachments + treatment planning

### **WEEK 4: Email Reminders (Days 16-20)**
**Goal:** Notification system with security controls

### **WEEK 5: Integration + QA (Days 21-25)**
**Goal:** End-to-end testing, security audit, production prep

---

## 📅 WEEK 1: Security Foundation (Days 1-5)

### Objective
Fix all 5 CRITICAL security vulnerabilities before implementing any PHI-handling features.

### Day 1: Authentication & Redis Security ✅ COMPLETED

#### Morning Session (4 hours) ✅ COMPLETED
**Agent: `fullstack-backend-specialist`**
**Status:** ✅ Complete (including bug fix for SlowAPI limiter)

**Task:** Implement JWT-based Magic Link Authentication
- ✅ Replace temporary X-Workspace-ID header with JWT tokens
- ✅ Implement magic link generation endpoint
- ✅ Create token validation middleware
- ✅ Add JWT to all protected endpoints
- ✅ Update OpenAPI spec with security scheme

**Deliverables:** ✅ ALL DELIVERED
- ✅ `/api/v1/auth/magic-link` (POST) - Request magic link
- ✅ `/api/v1/auth/verify` (GET) - Verify token and issue JWT
- ✅ `/api/v1/auth/logout` (POST) - Invalidate JWT
- ✅ `JWTAuthMiddleware` - Token validation
- ✅ Updated `get_current_user()` dependency
- ✅ **BONUS:** Fixed SlowAPI limiter initialization bug

**Acceptance Criteria:** ✅ ALL MET
- ✅ Magic link expires after 10 minutes
- ✅ JWT expires after 7 days
- ✅ Rate limiting: 3 magic link requests per hour per IP
- ✅ All endpoints require valid JWT (except auth endpoints)
- ✅ Application starts without errors
- ✅ 15 comprehensive tests written

#### Afternoon Session (4 hours) ✅ COMPLETED
**Agent: `database-architect`**
**Status:** ✅ Complete

**Task:** Secure Redis Configuration
- ✅ Enable Redis authentication
- ✅ Bind Redis to localhost only
- ✅ Update connection strings with password
- ✅ Document configuration in docker-compose.yml

**Deliverables:** ✅ ALL DELIVERED
- ✅ Updated `docker-compose.yml` with Redis password
- ✅ Updated `.env.example` with `REDIS_PASSWORD`
- ✅ Updated Redis client initialization in all modules
- ✅ Migration guide for existing deployments
- ✅ **BONUS:** Created comprehensive Redis security documentation

**Acceptance Criteria:** ✅ ALL MET
- ✅ Redis requires password authentication (tested)
- ✅ Redis only accessible from localhost (verified)
- ✅ All application code uses authenticated connection (tested)
- ✅ Documentation updated (2 comprehensive guides created)

**Documentation Created:**
- ✅ `/docs/REDIS_CONFIGURATION.md` (6.5 KB)
- ✅ `/docs/REDIS_MIGRATION_GUIDE.md` (10.8 KB)
- ✅ `/docs/REDIS_SECURITY_IMPLEMENTATION_SUMMARY.md` (8.3 KB)

---

### Day 2: CSRF Protection & Audit Logging Schema ✅ COMPLETED

#### Morning Session (4 hours) ✅ COMPLETED
**Agent: `fullstack-backend-specialist`**
**Status:** ✅ Complete

**Task:** Implement CSRF Protection
- ✅ Implement double-submit cookie pattern
- ✅ Add CSRF middleware
- ✅ Generate CSRF tokens on authentication
- ✅ Protect all POST/PUT/DELETE endpoints

**Deliverables:** ✅ ALL DELIVERED
- ✅ `CSRFProtectionMiddleware` implemented
- ✅ CSRF token generation and validation functions
- ✅ CSRF validation on all state-changing endpoints
- ✅ Frontend integration guide in implementation report
- ✅ 17 comprehensive tests (100% passing)

**Acceptance Criteria:** ✅ ALL MET
- ✅ All POST/PUT/DELETE require CSRF token (double-submit pattern)
- ✅ CSRF tokens expire after 7 days (match JWT)
- ✅ SameSite=Strict cookie configuration for CSRF token
- ✅ Secure flag configurable for production (HTTPS)
- ✅ Workspace scoping in Redis storage
- ✅ Constant-time comparison prevents timing attacks

**Files Created:**
- ✅ `src/pazpaz/middleware/csrf.py` (187 lines)
- ✅ `tests/test_csrf_protection.py` (398 lines)

**Files Modified:**
- ✅ `src/pazpaz/core/config.py` (added csrf_token_expire_minutes)
- ✅ `src/pazpaz/api/auth.py` (CSRF token generation on login/logout)
- ✅ `src/pazpaz/main.py` (middleware integration)
- ✅ `.env.example` (CSRF configuration)

#### Afternoon Session (4 hours) ✅ COMPLETED
**Agent: `database-architect`**
**Status:** ✅ Complete

**Task:** Design and Create Audit Events Table
- ✅ Design `audit_events` schema with immutability
- ✅ Create Alembic migration
- ✅ Add 5 performance-optimized indexes
- ✅ Implement immutability constraints (database triggers)

**Deliverables:** ✅ ALL DELIVERED
- ✅ Migration: `alembic/versions/de72ee2cfb00_add_audit_events_table.py` (230 lines)
- ✅ SQLAlchemy model: `models/audit_event.py` (228 lines)
- ✅ Database triggers preventing UPDATE/DELETE (immutable)
- ✅ 5 indexes including partial index for PHI access
- ✅ Comprehensive documentation (1,800+ lines)

**Acceptance Criteria:** ✅ ALL MET
- ✅ Table created with workspace_id scoping
- ✅ Immutability enforced at database level (triggers)
- ✅ 5 indexes: workspace_created, workspace_user, event_type, resource, phi_access (partial)
- ✅ Migration tested with rollback (upgrade + downgrade successful)
- ✅ 60+ event types defined across 8 categories
- ✅ HIPAA compliance requirements met
- ✅ Performance targets: <50ms p95 for PHI queries

**Documentation Created:**
- ✅ `/docs/AUDIT_LOGGING_SCHEMA.md` (1,800+ lines)
- ✅ `/docs/AUDIT_LOGGING_IMPLEMENTATION_REPORT.md`

---

### Day 3: Audit Logging Implementation & Encryption Design

#### Morning Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Audit Logging Middleware
- Create audit logging middleware
- Log all CRUD operations (CREATE, READ, UPDATE, DELETE)
- Capture IP address, user agent, timestamps
- Integrate with existing endpoints

**Deliverables:**
- `AuditMiddleware` for FastAPI
- `create_audit_event()` helper function
- Audit logging on Users, Clients, Appointments
- Audit log viewer API endpoint

**Acceptance Criteria:**
- [ ] All PHI access logged to audit_events
- [ ] Logs include: user_id, workspace_id, action, entity_type, entity_id, IP, timestamp
- [ ] NO PII/PHI in log metadata (only IDs)
- [ ] Audit logs are append-only

#### Afternoon Session (4 hours)
**Agent: `database-architect`**

**Task:** Design PHI Encryption Strategy
- Choose encryption approach (pgcrypto vs application-level)
- Design key management strategy
- Document encryption/decryption flow
- Create encryption implementation guide

**Deliverables:**
- Encryption architecture document
- Key rotation strategy
- Performance impact analysis
- Implementation guide for developers

**Acceptance Criteria:**
- [ ] AES-256-GCM encryption recommended
- [ ] Key storage strategy defined (env vars + rotation)
- [ ] Decryption performance < 10ms per field
- [ ] HIPAA compliance verified

---

### Day 4: Database Encryption Implementation

#### Full Day Session (8 hours)
**Agents: `database-architect` + `fullstack-backend-specialist` (parallel)**

**`database-architect` Tasks:**
- Install pgcrypto extension in PostgreSQL
- Create encrypted column types for future use
- Write encryption/decryption functions
- Test encryption performance

**Deliverables:**
- pgcrypto extension enabled
- SQL functions: `encrypt_phi()`, `decrypt_phi()`
- Performance benchmarks
- Migration template for encrypted columns

**`fullstack-backend-specialist` Tasks:**
- Implement application-level encryption helpers
- Create `EncryptedString` SQLAlchemy type
- Update models to use encrypted fields (prepared for Week 2)
- Write encryption unit tests

**Deliverables:**
- `utils/encryption.py` - Encryption helpers
- `EncryptedString` custom SQLAlchemy type
- Unit tests for encryption/decryption
- Documentation on using encrypted fields

**Combined Acceptance Criteria:**
- [ ] Encryption/decryption working end-to-end
- [ ] Performance: <10ms overhead per encrypted field
- [ ] Key rotation procedure documented
- [ ] Tests verify data integrity after encryption

---

### Day 5: Security Review & Week 1 QA

#### Morning Session (4 hours)
**Agent: `security-auditor`**

**Task:** Week 1 Security Audit
- Review authentication implementation
- Verify CSRF protection
- Audit Redis security configuration
- Review audit logging completeness
- Validate encryption implementation

**Deliverables:**
- Security audit report
- Vulnerability assessment
- Remediation recommendations
- Sign-off on security foundation

**Acceptance Criteria:**
- [ ] No CRITICAL vulnerabilities remaining
- [ ] Authentication properly implemented
- [ ] CSRF protection on all endpoints
- [ ] Audit logging functional
- [ ] Encryption ready for use

#### Afternoon Session (4 hours)
**Agent: `backend-qa-specialist`**

**Task:** Week 1 Quality Assurance
- Run all existing tests + new security tests
- Verify workspace isolation still intact
- Performance testing (auth overhead)
- Integration testing (auth + audit flow)

**Deliverables:**
- Test report
- Performance benchmarks
- Regression test results
- Week 1 completion sign-off

**Acceptance Criteria:**
- [ ] All tests passing
- [ ] No performance degradation (< 10ms auth overhead)
- [ ] Workspace isolation verified
- [ ] Security foundation ready for Week 2

---

## 📅 WEEK 2: SOAP Notes Core (Days 6-10)

### Objective
Implement session documentation (SOAP Notes) with encryption, autosave, and offline sync.

### Day 6: Database Schema & Models

#### Morning Session (4 hours)
**Agent: `database-architect`**

**Task:** Create Sessions Tables
- Design `sessions` table with encrypted PHI columns
- Design `session_attachments` table (S3/MinIO references)
- Create Alembic migration
- Add performance indexes

**Deliverables:**
- Migration: `[timestamp]_create_sessions_tables.py`
- Indexes: (workspace_id, client_id, session_date), (workspace_id, is_draft)
- Foreign key relationships to clients, appointments, users
- Comments on all PHI columns

**Acceptance Criteria:**
- [ ] Tables created with workspace_id scoping
- [ ] PHI columns use encryption (subjective, objective, assessment, plan)
- [ ] Indexes support <150ms p95 queries
- [ ] Migration tested with rollback

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Create SQLAlchemy Models
- Implement `Session` model with encrypted fields
- Implement `SessionAttachment` model
- Add relationships to Client, Appointment, User
- Create Pydantic schemas

**Deliverables:**
- `models/session.py` - Session model with EncryptedString fields
- `models/session_attachment.py` - Attachment model
- `schemas/session.py` - Pydantic request/response schemas
- Unit tests for model validation

**Acceptance Criteria:**
- [ ] Models use encrypted PHI fields
- [ ] Relationships properly defined
- [ ] Pydantic schemas validate input
- [ ] Tests verify encryption/decryption

---

### Day 7: SOAP Notes CRUD API

#### Full Day Session (8 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement SOAP Notes CRUD Endpoints
- Create session (POST /sessions)
- Get session by ID (GET /sessions/{id})
- List sessions for client (GET /clients/{id}/sessions)
- Update session (PUT /sessions/{id})
- Delete session (DELETE /sessions/{id}) - soft delete only

**Deliverables:**
- 5 CRUD endpoints in `routers/sessions.py`
- Workspace scoping on all queries
- Audit logging integration
- CSRF protection on POST/PUT/DELETE
- OpenAPI documentation

**Acceptance Criteria:**
- [ ] All endpoints require JWT authentication
- [ ] Workspace isolation enforced
- [ ] PHI encrypted at rest
- [ ] All operations logged to audit_events
- [ ] Response time p95 < 150ms

---

### Day 8: Autosave & Draft Mode

#### Morning Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Autosave Functionality
- Add `is_draft` boolean to Session model
- Create draft save endpoint (PATCH /sessions/{id}/draft)
- Implement partial updates (only changed fields)
- Add `draft_last_saved_at` timestamp

**Deliverables:**
- `PATCH /sessions/{id}/draft` - Save draft
- `POST /sessions/{id}/finalize` - Mark as complete
- Partial update logic (only update non-null fields)
- Frontend integration guide

**Acceptance Criteria:**
- [ ] Drafts save without full validation
- [ ] Finalized sessions become immutable (24h grace period)
- [ ] Autosave rate limited to 60/minute per user
- [ ] Last saved timestamp updated

#### Afternoon Session (4 hours)
**Agent: `fullstack-frontend-specialist`**

**Task:** Build SOAP Notes Editor UI
- Create SessionEditor.vue component
- Implement autosave with 5-second debounce
- Build SOAP note form (4 text areas)
- Add draft/finalized status indicator

**Deliverables:**
- `components/SessionEditor.vue`
- Autosave composable: `useAutosave()`
- API client integration
- Draft status UI

**Acceptance Criteria:**
- [ ] Autosave triggers every 5 seconds after typing
- [ ] Draft status visible to user
- [ ] "Finalize" button to lock note
- [ ] Loading states and error handling

---

### Day 9: Offline Sync & Conflict Resolution

#### Morning Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Offline Draft Sync
- Create sync endpoint (POST /sessions/sync-draft)
- Implement idempotency keys (prevent replay)
- Add conflict detection (version field)
- Handle offline drafts (local_draft_id)

**Deliverables:**
- `POST /sessions/sync-draft` - Sync offline draft
- Idempotency key validation (Redis cache)
- Conflict resolution logic (last-write-wins or manual merge)
- Sync status responses

**Acceptance Criteria:**
- [ ] Idempotency prevents duplicate drafts
- [ ] Conflicts detected via version field
- [ ] 409 Conflict response with merge options
- [ ] Sync idempotent (same draft_id = same result)

#### Afternoon Session (4 hours)
**Agent: `fullstack-frontend-specialist`**

**Task:** Implement Offline Draft Storage
- Use IndexedDB for offline drafts
- Sync queue for pending drafts
- Conflict resolution UI
- Network status detection

**Deliverables:**
- `composables/useOfflineDrafts.ts`
- IndexedDB schema and helpers
- Sync queue with retry logic
- Conflict resolution modal

**Acceptance Criteria:**
- [ ] Drafts stored in IndexedDB when offline
- [ ] Auto-sync when online
- [ ] Conflict modal shows both versions
- [ ] User can choose version or merge manually

---

### Day 10: Week 2 Testing & Review

#### Morning Session (4 hours)
**Agent: `backend-qa-specialist`**

**Task:** SOAP Notes QA
- Test all CRUD operations
- Verify workspace isolation
- Test autosave and offline sync
- Performance testing (query response times)

**Deliverables:**
- Test report with coverage metrics
- Performance benchmarks (target: p95 < 150ms)
- Workspace isolation test results
- Bug reports (if any)

**Acceptance Criteria:**
- [ ] All CRUD tests passing
- [ ] Workspace isolation verified
- [ ] Autosave working correctly
- [ ] Offline sync functional

#### Afternoon Session (4 hours)
**Agent: `security-auditor`**

**Task:** SOAP Notes Security Review
- Verify PHI encryption at rest
- Test authentication on all endpoints
- Audit logging completeness
- Input validation and XSS prevention

**Deliverables:**
- Security audit report
- Vulnerability scan results
- Encryption verification
- Week 2 sign-off

**Acceptance Criteria:**
- [ ] PHI encrypted in database
- [ ] All endpoints authenticated
- [ ] All operations audited
- [ ] No HIGH/CRITICAL vulnerabilities

---

## 📅 WEEK 3: File Attachments + Plan of Care (Days 11-15)

### Objective
Complete SOAP Notes with file attachments, then implement Plan of Care feature.

### Day 11: S3/MinIO Integration

#### Morning Session (4 hours)
**Agent: `database-architect`**

**Task:** Configure S3/MinIO Storage
- Set up MinIO in docker-compose.yml
- Configure S3 bucket with encryption (SSE-S3)
- Design bucket structure (workspace_id/sessions/{id}/)
- Create S3 client configuration

**Deliverables:**
- Updated `docker-compose.yml` with MinIO service
- Bucket creation script
- S3 client singleton
- Storage configuration documentation

**Acceptance Criteria:**
- [ ] MinIO running with encryption enabled
- [ ] Bucket structure enforces workspace scoping
- [ ] S3 client authenticated
- [ ] TLS enabled for all connections

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** File Upload Security Implementation
- Implement file type validation (MIME + extension + content)
- Add file size limits (10 MB per file)
- Integrate virus scanning (ClamAV optional for V1)
- Strip EXIF metadata from images

**Deliverables:**
- `utils/file_validation.py` - Triple validation
- `utils/file_sanitization.py` - EXIF stripping
- File upload helpers
- Security test suite

**Acceptance Criteria:**
- [ ] Only allowed types: JPEG, PNG, WebP, PDF
- [ ] File size limited to 10 MB
- [ ] MIME type verified via python-magic
- [ ] EXIF metadata stripped from images

---

### Day 12: File Upload API

#### Full Day Session (8 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement File Attachment Endpoints
- Upload file (POST /sessions/{id}/attachments)
- List attachments (GET /sessions/{id}/attachments)
- Download file (GET /attachments/{id}/download) - presigned URL
- Delete attachment (DELETE /attachments/{id})

**Deliverables:**
- 4 file attachment endpoints
- Presigned URL generation (15-minute expiry)
- S3 upload/download logic
- Audit logging for file operations

**Acceptance Criteria:**
- [ ] Files stored in workspace-scoped S3 paths
- [ ] Presigned URLs expire after 15 minutes
- [ ] All uploads/downloads logged
- [ ] Rate limit: 10 uploads/minute per user

---

### Day 13: Plan of Care Database & API

#### Morning Session (4 hours)
**Agent: `database-architect`**

**Task:** Create Plan of Care Tables
- Design `plans_of_care` table with encrypted fields
- Design `plan_of_care_progress_notes` table
- Create Alembic migration
- Add performance indexes

**Deliverables:**
- Migration: `[timestamp]_create_plan_of_care_tables.py`
- Indexes: (workspace_id, client_id, start_date), (workspace_id, status)
- Encrypted fields: treatment_goals, progress_notes
- JSONB column for flexible goal tracking

**Acceptance Criteria:**
- [ ] Tables created with workspace scoping
- [ ] PHI columns encrypted
- [ ] Indexes support timeline queries
- [ ] Migration tested

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Plan of Care API
- Create plan (POST /plans-of-care)
- Get plan (GET /plans-of-care/{id})
- Update plan (PUT /plans-of-care/{id})
- Add progress note (POST /plans-of-care/{id}/progress-notes)
- Get client timeline (GET /clients/{id}/timeline)

**Deliverables:**
- 5 Plan of Care endpoints
- SQLAlchemy models with encrypted fields
- Timeline aggregation query (sessions + plans)
- Pydantic schemas

**Acceptance Criteria:**
- [ ] All endpoints authenticated and CSRF protected
- [ ] PHI encrypted at rest
- [ ] Timeline query < 500ms p95
- [ ] Audit logging integrated

---

### Day 14: Frontend for Attachments & Plan of Care

#### Morning Session (4 hours)
**Agent: `fullstack-frontend-specialist`**

**Task:** Build File Upload UI
- Create FileUpload.vue component
- Implement drag-and-drop
- Show upload progress
- Display attachment list with download links

**Deliverables:**
- `components/FileUpload.vue`
- `components/AttachmentList.vue`
- File upload composable
- Progress indicators

**Acceptance Criteria:**
- [ ] Drag-and-drop file upload
- [ ] Progress bar during upload
- [ ] Preview for images
- [ ] Download via presigned URLs

#### Afternoon Session (4 hours)
**Agent: `fullstack-frontend-specialist`**

**Task:** Build Plan of Care UI
- Create PlanOfCareEditor.vue
- Build timeline view (sessions + plans)
- Progress note form
- Goal tracking UI

**Deliverables:**
- `components/PlanOfCareEditor.vue`
- `components/ClientTimeline.vue`
- Timeline rendering with chronological events
- Goal status indicators

**Acceptance Criteria:**
- [ ] Plan creation/editing functional
- [ ] Timeline shows sessions + plans chronologically
- [ ] Progress notes can be added
- [ ] Goals can be marked as achieved

---

### Day 15: Week 3 Testing & Security Review

#### Morning Session (4 hours)
**Agent: `backend-qa-specialist`**

**Task:** Week 3 QA
- Test file upload with malicious files
- Test file size limits
- Verify presigned URL expiration
- Test Plan of Care CRUD
- Timeline query performance

**Deliverables:**
- File upload security test results
- Plan of Care test coverage
- Performance benchmarks
- Bug reports

**Acceptance Criteria:**
- [ ] Malicious files rejected
- [ ] File size limits enforced
- [ ] Presigned URLs expire correctly
- [ ] Plan of Care functional
- [ ] Timeline query < 500ms

#### Afternoon Session (4 hours)
**Agent: `security-auditor`**

**Task:** File Upload & Plan of Care Security Audit
- Verify file validation (MIME, extension, content)
- Test path traversal prevention
- Verify S3 bucket permissions (private only)
- Review Plan of Care encryption
- Audit log completeness

**Deliverables:**
- Security audit report
- File upload vulnerability scan
- S3 security configuration review
- Week 3 sign-off

**Acceptance Criteria:**
- [ ] No file upload vulnerabilities
- [ ] S3 buckets are private
- [ ] Plan of Care PHI encrypted
- [ ] All operations audited

---

## 📅 WEEK 4: Email Reminders (Days 16-20)

### Objective
Implement email notification system with template security and delivery tracking.

### Day 16: Email Reminder Database & Templates

#### Morning Session (4 hours)
**Agent: `database-architect`**

**Task:** Create Email Reminder Tables
- Design `reminder_templates` table
- Design `reminder_schedules` table
- Design `reminder_queue` table
- Design `user_notification_preferences` table
- Create Alembic migration

**Deliverables:**
- Migration: `[timestamp]_create_reminder_system_tables.py`
- Indexes for queue processing (scheduled_send_at, status)
- Template variable constraints
- Queue status enum

**Acceptance Criteria:**
- [ ] Tables created with workspace scoping
- [ ] Indexes support queue processing <50ms
- [ ] Template types defined (appointment_reminder, etc.)
- [ ] Migration tested

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Template System with Security
- Create template CRUD endpoints
- Implement Jinja2 sandboxed rendering
- Variable whitelist (client_first_name, appointment_date, etc.)
- Auto-escape all variables

**Deliverables:**
- Template CRUD endpoints (POST/GET/PUT/DELETE /templates)
- `utils/email_templates.py` - Sandboxed renderer
- Variable whitelist enforcement
- Template validation

**Acceptance Criteria:**
- [ ] Only whitelisted variables allowed
- [ ] All variables auto-escaped (XSS prevention)
- [ ] No PHI in templates (validated)
- [ ] Templates tested with injection attempts

---

### Day 17: Reminder Configuration & Background Jobs

#### Morning Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Reminder Schedules
- Create schedule CRUD endpoints
- Configure trigger types (appointment_scheduled, etc.)
- Set offset timing (e.g., -1440 minutes = 24h before)
- Recipient configuration (client, therapist, both)

**Deliverables:**
- Schedule CRUD endpoints (POST/GET/PUT/DELETE /reminder-schedules)
- `services/reminder_service.py` - Schedule logic
- Trigger event handlers
- Schedule validation

**Acceptance Criteria:**
- [ ] Schedules configurable per workspace
- [ ] Offset timing supports before/after events
- [ ] Active/inactive toggle
- [ ] Template selection per schedule

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Set Up Background Job Queue
- Configure Redis job queue (ARQ or RQ)
- Encrypt job payloads (contains PII)
- Implement retry logic (max 3 retries)
- Create dead letter queue

**Deliverables:**
- `workers/email_worker.py` - Background worker
- Job payload encryption
- Retry configuration (exponential backoff)
- DLQ with 7-day cleanup

**Acceptance Criteria:**
- [ ] Jobs encrypted in Redis
- [ ] Max 3 retry attempts
- [ ] Failed jobs moved to DLQ
- [ ] Worker monitoring/logging

---

### Day 18: Email Sending & Delivery Tracking

#### Morning Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Email Sending
- Integrate email provider (SendGrid or AWS SES)
- Send appointment reminders
- Track delivery status (sent, bounced, failed)
- Update reminder_queue table

**Deliverables:**
- `services/email_service.py` - Email sender
- Delivery status tracking
- Webhook handler for bounce/complaint events
- Email logging

**Acceptance Criteria:**
- [ ] Emails sent via authenticated SMTP
- [ ] Delivery status tracked
- [ ] Bounces/complaints logged
- [ ] Unsubscribe link in all emails

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Reminder Scheduler (Cron Job)
- Create scheduler that runs every 5 minutes
- Query reminder_queue for pending reminders
- Enqueue email jobs
- Update queue status

**Deliverables:**
- `workers/reminder_scheduler.py` - Cron job
- Queue processing logic (find pending reminders)
- Job enqueueing
- Scheduler monitoring

**Acceptance Criteria:**
- [ ] Scheduler runs every 5 minutes
- [ ] Query performance <50ms (indexed)
- [ ] Jobs enqueued correctly
- [ ] Status updates tracked

---

### Day 19: Email Security & Rate Limiting

#### Morning Session (4 hours)
**Agent: `security-auditor`**

**Task:** Email Security Audit
- Review template injection prevention
- Verify email validation (format + DNS MX check)
- Test rate limiting
- Review PHI leakage prevention
- SPF/DKIM/DMARC configuration check

**Deliverables:**
- Email security audit report
- Template injection test results
- Rate limiting verification
- PHI leakage check
- DNS configuration guide

**Acceptance Criteria:**
- [ ] No template injection vulnerabilities
- [ ] Email addresses validated
- [ ] Rate limits enforced (50 emails/hour per workspace)
- [ ] No PHI in email bodies
- [ ] SPF/DKIM/DMARC configured

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Implement Rate Limiting & Email Verification
- Add rate limiting (100 emails/hour per workspace)
- Implement email verification flow
- Create unsubscribe mechanism
- Add user notification preferences

**Deliverables:**
- Rate limiting middleware (slowapi)
- Email verification endpoint
- Unsubscribe token generation
- Preference management API

**Acceptance Criteria:**
- [ ] Rate limits enforced (workspace + global)
- [ ] Email verification before first reminder
- [ ] Unsubscribe link in all emails
- [ ] Preferences stored in database

---

### Day 20: Email UI & Week 4 Testing

#### Morning Session (4 hours)
**Agent: `fullstack-frontend-specialist`**

**Task:** Build Email Reminder UI
- Template editor with variable picker
- Schedule configuration UI
- Reminder log viewer
- Notification preferences

**Deliverables:**
- `components/TemplateEditor.vue`
- `components/ReminderScheduleConfig.vue`
- `components/ReminderLogs.vue`
- `views/NotificationSettings.vue`

**Acceptance Criteria:**
- [ ] Template editor with live preview
- [ ] Schedule creation/editing
- [ ] Delivery status visible
- [ ] User can enable/disable reminders

#### Afternoon Session (4 hours)
**Agent: `backend-qa-specialist`**

**Task:** Week 4 QA
- Test email template rendering
- Verify rate limiting
- Test background job execution
- Verify delivery tracking
- Performance testing

**Deliverables:**
- Email system test report
- Background job test results
- Rate limiting verification
- Performance benchmarks
- Week 4 sign-off

**Acceptance Criteria:**
- [ ] Templates render correctly
- [ ] Rate limits working
- [ ] Jobs execute successfully
- [ ] Delivery tracked accurately

---

## 📅 WEEK 5: Integration, QA & Production Prep (Days 21-25)

### Objective
End-to-end testing, comprehensive security audit, performance optimization, production deployment preparation.

### Day 21: End-to-End Integration Testing

#### Full Day Session (8 hours)
**Agent: `backend-qa-specialist`**

**Task:** Comprehensive Integration Testing
- Test complete SOAP Notes workflow (create → autosave → attach files → finalize)
- Test Plan of Care workflow (create plan → add progress notes → view timeline)
- Test Email Reminder workflow (create template → configure schedule → verify delivery)
- Test cross-feature interactions (SOAP note triggers reminder)

**Deliverables:**
- Integration test suite
- End-to-end test scenarios
- User journey testing
- Cross-feature interaction tests

**Acceptance Criteria:**
- [ ] All workflows functional end-to-end
- [ ] No regressions in existing features
- [ ] Cross-feature triggers working
- [ ] All tests passing

---

### Day 22: Comprehensive Security Audit

#### Full Day Session (8 hours)
**Agent: `security-auditor`**

**Task:** Final Security Audit & Penetration Testing
- Penetration testing (file upload, email templates)
- Authentication/authorization review
- PHI encryption verification (database + S3)
- Audit log completeness check
- Workspace isolation verification
- HIPAA compliance checklist

**Deliverables:**
- Final security audit report
- Penetration test results
- HIPAA compliance certification
- Risk assessment summary
- Production readiness checklist

**Acceptance Criteria:**
- [ ] No CRITICAL or HIGH vulnerabilities
- [ ] PHI encrypted at rest (verified in DB)
- [ ] All operations audited (100% coverage)
- [ ] Workspace isolation verified
- [ ] HIPAA compliance requirements met

---

### Day 23: Performance Optimization

#### Morning Session (4 hours)
**Agent: `database-architect`**

**Task:** Database Performance Tuning
- Analyze slow queries (pg_stat_statements)
- Optimize indexes if needed
- Add missing indexes
- Query plan analysis
- Consider materialized views for timeline

**Deliverables:**
- Query performance report
- Index optimization recommendations
- Materialized view for timeline (if needed)
- Performance tuning guide

**Acceptance Criteria:**
- [ ] All queries meet p95 targets (<150ms sessions, <500ms timeline)
- [ ] Indexes optimized
- [ ] No N+1 query issues
- [ ] Database performance documented

#### Afternoon Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** API Performance Optimization
- Add response caching (Redis) for read-heavy endpoints
- Optimize serialization (Pydantic)
- Add pagination to list endpoints
- Implement query result caching

**Deliverables:**
- Cache strategy implementation
- Pagination on all list endpoints
- Cache invalidation logic
- Performance benchmarks

**Acceptance Criteria:**
- [ ] Read-heavy endpoints cached (5-minute TTL)
- [ ] All list endpoints paginated
- [ ] Cache invalidation on updates
- [ ] API response times improved

---

### Day 24: Frontend Polish & UX Review

#### Morning Session (4 hours)
**Agent: `fullstack-frontend-specialist`**

**Task:** Frontend Polish & Error Handling
- Improve loading states
- Add error boundaries
- Enhance offline mode UX
- Add success/error notifications
- Accessibility improvements (ARIA labels, keyboard navigation)

**Deliverables:**
- Loading skeletons for all views
- Error boundary components
- Offline mode indicators
- Toast notifications
- Accessibility audit report

**Acceptance Criteria:**
- [ ] All loading states implemented
- [ ] Errors handled gracefully
- [ ] Offline mode clear to user
- [ ] Keyboard navigation functional
- [ ] WCAG 2.1 Level AA compliance

#### Afternoon Session (4 hours)
**Agent: `ux-design-consultant`**

**Task:** UX Review & Design QA
- Review SOAP Notes editor UX
- Evaluate Plan of Care timeline visualization
- Assess email template editor usability
- Check visual consistency
- Provide design feedback

**Deliverables:**
- UX review report
- Design feedback document
- Usability improvements list
- Visual consistency check
- Final design sign-off

**Acceptance Criteria:**
- [ ] UX patterns consistent with app design
- [ ] Visual hierarchy clear
- [ ] Interactions intuitive
- [ ] Design system followed
- [ ] Calm, professional aesthetic maintained

---

### Day 25: Production Deployment Preparation

#### Morning Session (4 hours)
**Agent: `fullstack-backend-specialist`**

**Task:** Production Configuration & Deployment Prep
- Environment configuration (.env production template)
- Docker production build optimization
- Database migration runbook
- Monitoring setup (logging, alerts)
- Deployment checklist

**Deliverables:**
- `.env.production.example` with all required variables
- Production `docker-compose.yml`
- Migration deployment guide
- Monitoring configuration (Datadog/New Relic)
- Deployment runbook

**Acceptance Criteria:**
- [ ] All secrets configured securely
- [ ] Production builds optimized
- [ ] Migration tested on staging
- [ ] Monitoring/alerting configured
- [ ] Rollback plan documented

#### Afternoon Session (4 hours)
**Agent: `backend-qa-specialist`**

**Task:** Final QA Sign-Off
- Run full test suite
- Verify all acceptance criteria met
- Smoke testing on staging environment
- Load testing (simulate 100 concurrent users)
- Create final QA report

**Deliverables:**
- Final test report (all features)
- Staging environment verification
- Load test results
- Production readiness sign-off
- Known issues log (if any)

**Acceptance Criteria:**
- [ ] All tests passing (unit, integration, e2e)
- [ ] Staging environment functional
- [ ] Load test successful (100 users, <500ms p95)
- [ ] No blocking bugs
- [ ] Production deployment approved

---

## 🔄 Agent Parallelization Strategy

### When to Run Agents in Parallel

#### Week 1, Day 4 (Database Encryption)
**Parallel Execution:**
- `database-architect`: PostgreSQL pgcrypto setup
- `fullstack-backend-specialist`: Application-level encryption helpers

**Reason:** Independent tasks, both needed for Week 2

#### Week 2, Day 8 (Autosave UI)
**Parallel Execution:**
- `fullstack-backend-specialist`: Backend autosave API
- `fullstack-frontend-specialist`: Frontend autosave UI

**Reason:** API and UI can be built simultaneously

#### Week 2, Day 9 (Offline Sync)
**Parallel Execution:**
- `fullstack-backend-specialist`: Sync API with idempotency
- `fullstack-frontend-specialist`: IndexedDB offline storage

**Reason:** Backend and frontend sync logic independent

#### Week 3, Day 14 (Frontend Implementation)
**Parallel Execution:**
- `fullstack-frontend-specialist`: File upload UI (morning)
- `fullstack-frontend-specialist`: Plan of Care UI (afternoon)

**Reason:** Two separate features, can be built in sequence but optimized

#### Week 5, Day 23 (Performance Optimization)
**Parallel Execution:**
- `database-architect`: Database performance tuning
- `fullstack-backend-specialist`: API caching and optimization

**Reason:** Database and API optimizations are complementary

---

## 📊 Success Metrics & KPIs

### Security Metrics
- **Encryption Coverage:** 100% of PHI fields encrypted at rest
- **Audit Log Coverage:** 100% of PHI operations logged
- **Vulnerability Count:** 0 CRITICAL, 0 HIGH vulnerabilities
- **Authentication:** 100% of endpoints require JWT (except auth endpoints)

### Performance Metrics
- **API Response Time:** p95 < 150ms for SOAP Notes, < 500ms for timeline
- **File Upload:** < 3 seconds for 5 MB file
- **Email Delivery:** 95% delivered within 5 minutes of scheduled time
- **Background Jobs:** 99% success rate on first attempt

### Quality Metrics
- **Test Coverage:** > 80% code coverage
- **Uptime:** 99.9% availability
- **Error Rate:** < 1% of requests fail
- **User Satisfaction:** SOAP Notes workflow < 2 minutes from start to save

---

## 🚨 Risk Management

### High-Risk Areas & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Encryption performance degrades queries | Medium | High | Day 4 performance testing, caching strategy |
| File upload vulnerabilities | Medium | Critical | Triple validation, ClamAV scanning |
| Email PHI leakage | Low | Critical | Template whitelist, security audit |
| Background job failures | Medium | Medium | Retry logic, DLQ, monitoring |
| Timeline query too slow | Medium | Medium | Indexes, materialized views if needed |

### Contingency Plans

**If Encryption Slows Queries:**
- Add aggressive caching (Redis)
- Use materialized views for timeline
- Decrypt only displayed fields (lazy loading)

**If File Upload Vulnerable:**
- Disable feature until hardened
- Add ClamAV virus scanning (required before production)
- Stricter MIME type validation

**If Background Jobs Unstable:**
- Increase retry limits
- Add manual retry UI for failed jobs
- Implement job monitoring dashboard

---

## 📋 Daily Standup Format

### Morning Standup (9:00 AM)
**Each agent reports:**
1. Yesterday's accomplishments
2. Today's plan
3. Blockers/dependencies

### End-of-Day Sync (5:00 PM)
**Each agent reports:**
1. Completed tasks
2. In-progress tasks (handoff to next agent if needed)
3. Tomorrow's preparation

---

## ✅ Weekly Sign-Off Checklist

### Week 1 Sign-Off
- [ ] Authentication implemented (magic link + JWT)
- [ ] Redis secured with password
- [ ] CSRF protection on all endpoints
- [ ] Audit logging functional
- [ ] Encryption ready for use
- [ ] Security audit passed
- [ ] No CRITICAL vulnerabilities

### Week 2 Sign-Off
- [ ] SOAP Notes CRUD functional
- [ ] PHI encrypted at rest
- [ ] Autosave working
- [ ] Offline sync implemented
- [ ] Workspace isolation verified
- [ ] Performance targets met (p95 < 150ms)
- [ ] Security audit passed

### Week 3 Sign-Off
- [ ] File attachments functional
- [ ] S3/MinIO encrypted
- [ ] Plan of Care CRUD functional
- [ ] Timeline query optimized
- [ ] File upload security verified
- [ ] No file upload vulnerabilities

### Week 4 Sign-Off
- [ ] Email templates secure (no injection)
- [ ] Reminder schedules functional
- [ ] Background jobs executing
- [ ] Delivery tracking working
- [ ] Rate limiting enforced
- [ ] No PHI in emails verified

### Week 5 Sign-Off
- [ ] All integration tests passing
- [ ] Security audit passed (final)
- [ ] Performance optimized
- [ ] Production configuration ready
- [ ] Deployment runbook complete
- [ ] **PRODUCTION READY** ✅

---

## 📞 Escalation Protocol

### When to Escalate
1. **CRITICAL vulnerability found** → Immediate halt, security team review
2. **Performance target missed by >50%** → Architecture review needed
3. **Agent blocked for >4 hours** → Resource allocation issue
4. **Acceptance criteria cannot be met** → Requirements clarification needed

### Escalation Contacts
- **Security Issues:** security-auditor agent → User review
- **Performance Issues:** database-architect + fullstack-backend-specialist
- **UX Issues:** ux-design-consultant → User feedback
- **Blocking Issues:** User decision required

---

## 📚 Documentation Deliverables

### Technical Documentation
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Database schema documentation
- [ ] Encryption key rotation guide
- [ ] Deployment runbook
- [ ] Monitoring/alerting setup guide

### User Documentation
- [ ] SOAP Notes user guide
- [ ] Plan of Care user guide
- [ ] Email reminder configuration guide
- [ ] Offline mode usage guide

### Security Documentation
- [ ] Security architecture document
- [ ] HIPAA compliance certification
- [ ] Incident response playbook
- [ ] Breach notification procedures

---

## 🎯 Definition of Done

A feature is considered **DONE** when:

1. ✅ **Functionality:** All acceptance criteria met, tests passing
2. ✅ **Security:** No CRITICAL/HIGH vulnerabilities, PHI encrypted, audit logged
3. ✅ **Performance:** Meets p95 targets (<150ms for CRUD, <500ms for complex queries)
4. ✅ **Quality:** >80% test coverage, code reviewed, QA approved
5. ✅ **Documentation:** API docs updated, user guide written, runbook complete
6. ✅ **UX:** Design review passed, accessibility verified (WCAG 2.1 AA)
7. ✅ **Production Ready:** Environment configured, monitoring set up, deployment tested

---

## 🚀 Go-Live Checklist

### Pre-Deployment (Day 24-25)
- [ ] All tests passing (unit, integration, e2e)
- [ ] Security audit passed (no CRITICAL/HIGH issues)
- [ ] Performance verified on staging (load test successful)
- [ ] Database migrations tested on staging
- [ ] Monitoring/alerting configured
- [ ] Rollback plan documented and tested
- [ ] Team trained on new features

### Deployment Day
- [ ] Backup production database
- [ ] Run database migrations
- [ ] Deploy backend services
- [ ] Deploy frontend assets
- [ ] Verify monitoring dashboards
- [ ] Smoke test critical paths
- [ ] Enable feature flags (if used)
- [ ] Notify users of new features

### Post-Deployment (Week 6)
- [ ] Monitor error rates (< 1%)
- [ ] Monitor performance (meet p95 targets)
- [ ] Monitor security alerts (audit logs)
- [ ] Collect user feedback
- [ ] Address P0/P1 bugs within 24 hours
- [ ] Plan incremental improvements

---

## 📈 Reporting & Visibility

### Daily Progress Report
**Format:** Markdown table in Slack/Email

| Agent | Tasks Completed | Tasks In Progress | Blockers | ETA |
|-------|----------------|-------------------|----------|-----|
| database-architect | Migration X created | Testing encryption | None | On track |
| fullstack-backend-specialist | Auth API done | CRUD endpoints | Waiting for schema | +1 day |
| security-auditor | Week 1 audit complete | - | None | Complete |

### Weekly Executive Summary
**Sent every Friday:**
- Accomplishments this week
- Next week's objectives
- Risks/blockers
- Overall progress (% complete)
- Schedule status (on track / at risk / delayed)

---

## 🏁 Final Notes

### Critical Success Factors
1. **Security First:** No shortcuts on encryption, auth, or audit logging
2. **Parallel Execution:** Maximize agent efficiency with parallel tasks
3. **Daily Sync:** Morning standup + EOD handoffs prevent blocking
4. **Testing Rigor:** QA and security review EVERY week
5. **User Focus:** UX review ensures features are actually usable

### What Could Go Wrong?
- **Encryption performance issues** → Mitigate with caching and lazy loading
- **File upload vulnerabilities** → Triple validation + ClamAV required
- **Background job instability** → Comprehensive monitoring and DLQ
- **Timeline query too slow** → Materialized views or denormalization

### Success Indicators
- ✅ Zero CRITICAL vulnerabilities in production
- ✅ 100% PHI encrypted at rest
- ✅ All operations audited (HIPAA compliant)
- ✅ Performance targets met (p95 < 150ms)
- ✅ Users can document sessions, track plans, and receive reminders securely

---

**READY TO BEGIN? 🚀**

This plan provides a clear, executable roadmap for implementing three critical features with security and compliance as the foundation. Each week builds on the previous, with multiple checkpoints to ensure quality and security.

**Next Step:** Review this plan, approve, and we'll begin **Week 1, Day 1** with authentication implementation!
