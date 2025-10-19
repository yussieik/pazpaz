# PazPaz Security Checklists

**Last Updated:** 2025-10-19
**Version:** 1.0
**Status:** Production Ready
**Classification:** Internal

---

## Table of Contents

1. [Pre-Deployment Security Checklist](#pre-deployment-security-checklist)
2. [Security Review Process](#security-review-process)
3. [Dependency Audit Procedure](#dependency-audit-procedure)
4. [Weekly Security Tasks](#weekly-security-tasks)
5. [Monthly Security Tasks](#monthly-security-tasks)
6. [Quarterly Security Tasks](#quarterly-security-tasks)
7. [Annual Security Tasks](#annual-security-tasks)

---

## Pre-Deployment Security Checklist

### Infrastructure Security

**Database**:
- [ ] SSL/TLS enabled (verify-full mode in production)
- [ ] Strong database password (32+ characters)
- [ ] Database user has minimum required privileges (no SUPERUSER, no CREATE DATABASE)
- [ ] Database accessible only from application servers (security group rules)
- [ ] Database backups automated (daily, 30-day retention)
- [ ] Point-in-time recovery (PITR) enabled
- [ ] Database audit logging enabled (pgaudit)

**API Server**:
- [ ] All secrets in AWS Secrets Manager (no hardcoded credentials)
- [ ] Environment variables validated at startup (no missing required vars)
- [ ] SSL startup check passes (database connection encrypted)
- [ ] Health check endpoint responding (`/health`)
- [ ] Security headers configured (HSTS, CSP, X-Frame-Options)
- [ ] CORS restricted (same-origin only in production)
- [ ] Rate limiting enabled (authentication endpoints: 5/min, general: 100/min)
- [ ] Request size limits enforced (20 MB max)

**File Storage (S3/MinIO)**:
- [ ] Bucket encryption enabled (SSE-S3 or SSE-KMS)
- [ ] Bucket versioning enabled (ransomware protection)
- [ ] Public access blocked (no public ACLs)
- [ ] Pre-signed URLs used (no permanent public URLs)
- [ ] File upload limits configured (10 MB per file, 50 MB per session)
- [ ] ClamAV antivirus running and monitored
- [ ] S3 access logs enabled

**Redis**:
- [ ] Redis password set (32+ characters)
- [ ] Redis accessible only from application servers
- [ ] Persistence enabled (AOF or RDB)
- [ ] Maxmemory policy configured (allkeys-lru)

**Network**:
- [ ] TLS 1.2+ enforced (no TLS 1.0/1.1)
- [ ] Strong cipher suites only (no RC4, DES, MD5)
- [ ] Firewall rules restrict traffic (least privilege)
- [ ] No public SSH access (use AWS SSM or bastion host)
- [ ] VPC security groups properly configured

### Application Security

**Authentication**:
- [ ] Magic link token entropy sufficient (256 bits, `secrets.token_urlsafe(32)`)
- [ ] Magic link expiration configured (10 minutes)
- [ ] JWT expiration validation enabled (`verify_exp=True`)
- [ ] JWT signature algorithm pinned (HS256 only)
- [ ] Token blacklisting functional (Redis integration)
- [ ] CSRF protection enabled (all state-changing requests)
- [ ] Rate limiting on `/auth/magic-link` (3/hour per IP, 5/hour per email)
- [ ] HttpOnly cookies (`access_token`, `csrf_token`)
- [ ] SameSite=Lax cookie attribute set

**Encryption**:
- [ ] Encryption master key 256 bits (32 bytes)
- [ ] Key stored in AWS Secrets Manager (not in environment variables)
- [ ] All PHI fields use `EncryptedString` type
- [ ] Encryption algorithm AES-256-GCM (not CBC or ECB)
- [ ] Non-deterministic encryption (random nonce per encryption)
- [ ] Key versioning implemented (v1, v2, v3 support)
- [ ] Key rotation schedule defined (90 days)

**Workspace Isolation**:
- [ ] All database queries filter by `workspace_id`
- [ ] `workspace_id` derived from JWT (never from client input)
- [ ] Generic 404 errors (no information leakage)
- [ ] Foreign key constraints enforce workspace boundaries
- [ ] Cross-workspace access tests passing

**Input Validation**:
- [ ] Pydantic schemas validate all request bodies
- [ ] SQLAlchemy ORM used (no raw SQL queries)
- [ ] File upload validation (extension, MIME, content, malware, size, dimensions)
- [ ] Request size limits enforced (middleware)
- [ ] No eval() or exec() with user input

**Audit Logging**:
- [ ] All PHI access logged (GET requests to `/clients`, `/sessions`)
- [ ] All PHI modifications logged (POST/PUT/DELETE)
- [ ] Authentication events logged (login, logout, failed attempts)
- [ ] Audit logs immutable (no UPDATE/DELETE)
- [ ] Audit logs include: user_id, workspace_id, action, resource_type, resource_id, IP, timestamp
- [ ] No PII in application logs (only in audit_events table)

**Error Handling**:
- [ ] Generic error messages (no sensitive data exposure)
- [ ] Debug mode disabled in production (`DEBUG=false`)
- [ ] Stack traces disabled in production
- [ ] Error logging excludes PII/secrets

### Code Security

**Dependencies**:
- [ ] All dependencies up-to-date (no critical vulnerabilities)
- [ ] Dependency lock file committed (`uv.lock`, `package-lock.json`)
- [ ] No deprecated dependencies
- [ ] License compliance verified (no GPL/AGPL unless approved)

**Code Review**:
- [ ] Security review completed (by security-auditor or security officer)
- [ ] No TODO/FIXME comments related to security
- [ ] No commented-out authentication/authorization code
- [ ] No test credentials in code (hardcoded passwords, API keys)
- [ ] No console.log() or print() statements with sensitive data

**Testing**:
- [ ] Penetration tests passing (43 tests, 0 critical vulnerabilities)
- [ ] Workspace isolation tests passing (6/7 passing)
- [ ] Authentication tests passing (JWT expiration, blacklisting, CSRF)
- [ ] Encryption tests passing (key versioning, non-deterministic)
- [ ] File upload security tests passing (malware, polyglot, MIME confusion)

### Deployment

**CI/CD**:
- [ ] Secrets not in CI/CD logs
- [ ] Docker images scanned for vulnerabilities (Trivy/Snyk)
- [ ] Code scanning enabled (CodeQL/Semgrep)
- [ ] Dependency scanning enabled (npm audit, uv)
- [ ] SBOM (Software Bill of Materials) generated

**Infrastructure as Code**:
- [ ] Terraform/CloudFormation templates reviewed
- [ ] IAM policies follow least privilege
- [ ] S3 buckets not public (unless explicitly required)
- [ ] Security groups restrict traffic to minimum required

**Monitoring**:
- [ ] CloudWatch alarms configured (encryption key access, decryption failures, auth failures)
- [ ] PagerDuty integration tested (critical alerts)
- [ ] Log aggregation configured (CloudWatch, Datadog, Splunk)
- [ ] Security event monitoring enabled

---

## Security Review Process

### When to Perform Security Review

**Required**:
- New authentication/authorization code
- Changes to encryption logic
- Database query modifications (workspace isolation risk)
- File upload functionality
- New API endpoints handling PHI
- Dependency upgrades (major versions)

**Optional** (but recommended):
- New frontend components handling sensitive data
- Infrastructure changes
- Configuration updates

### Security Review Checklist

#### 1. Authentication & Authorization Review

```
[ ] Authentication required for endpoint?
  └─ If YES:
      [ ] JWT validation present? (get_current_user dependency)
      [ ] Workspace scoping enforced? (filter by current_user.workspace_id)
      [ ] CSRF token required? (POST/PUT/DELETE endpoints)

[ ] New authentication flow?
  └─ If YES:
      [ ] Rate limiting configured?
      [ ] Token entropy sufficient? (256 bits minimum)
      [ ] Token expiration set? (short-lived preferred)
      [ ] Audit logging enabled?

[ ] Authorization logic changes?
  └─ If YES:
      [ ] Least privilege enforced? (users see only their data)
      [ ] No client-provided IDs trusted? (workspace_id, user_id from JWT only)
      [ ] Generic errors on unauthorized access? (404, not 403)
```

#### 2. Data Protection Review

```
[ ] PHI fields encrypted?
  └─ Client: full_name, phone, email, address, medical_history
  └─ Session: subjective, objective, assessment, plan

[ ] Encryption algorithm correct?
  [ ] AES-256-GCM (not CBC, not ECB)
  [ ] Random nonce per encryption
  [ ] Key versioning support

[ ] Data in transit encrypted?
  [ ] HTTPS for API (TLS 1.2+)
  [ ] Database SSL (verify-full mode)
  [ ] Redis TLS (production)

[ ] Sensitive data in logs?
  [ ] No PII in application logs
  [ ] No secrets in logs
  [ ] No encryption keys in error messages
```

#### 3. Input Validation Review

```
[ ] Pydantic schema validates input?
  [ ] Required fields enforced
  [ ] Type validation (str, int, UUID, email, etc.)
  [ ] Length constraints (min_length, max_length)
  [ ] Pattern matching (regex for emails, phones)

[ ] SQL injection prevention?
  [ ] SQLAlchemy ORM used (no raw SQL)
  [ ] Parameterized queries (no string concatenation)
  [ ] Input sanitization (if raw SQL unavoidable)

[ ] File upload validation?
  [ ] Extension whitelist (jpg, jpeg, png, webp, pdf only)
  [ ] MIME type detection (libmagic)
  [ ] Content validation (PIL for images, pypdf for PDFs)
  [ ] Malware scanning (ClamAV in production)
  [ ] Size limits (10 MB per file, 50 MB per session)
  [ ] Dimension limits (50 megapixels for images)
```

#### 4. Workspace Isolation Review

```
[ ] All queries filter by workspace_id?
  └─ SELECT * FROM clients WHERE workspace_id = ? AND ...
  └─ SELECT * FROM sessions WHERE workspace_id = ? AND ...

[ ] workspace_id source verified?
  [ ] From JWT (current_user.workspace_id)
  [ ] NEVER from query params (?workspace_id=...)
  [ ] NEVER from request body ({"workspace_id": "..."})

[ ] Cross-workspace references prevented?
  [ ] Foreign keys validated (client_id belongs to workspace)
  [ ] Generic 404 on cross-workspace access
```

#### 5. Audit Logging Review

```
[ ] PHI access logged?
  [ ] GET requests to /clients, /sessions
  [ ] Includes: user_id, workspace_id, resource_type, resource_id, IP

[ ] PHI modifications logged?
  [ ] POST/PUT/DELETE to /clients, /sessions
  [ ] Includes metadata (before/after values? No - too verbose)

[ ] Authentication events logged?
  [ ] Login (magic link verification)
  [ ] Logout (token blacklisted)
  [ ] Failed login attempts
```

### Security Review Sign-Off

```
SECURITY REVIEW SIGN-OFF

Pull Request: #XXX
Reviewer: [SECURITY_OFFICER or security-auditor]
Date: [DATE]

Code Changes Reviewed:
- [File 1: /api/clients.py]
- [File 2: /models/client.py]
- [File 3: /schemas/client.py]

Security Checklist:
[ ] Authentication/authorization reviewed
[ ] Data protection reviewed
[ ] Input validation reviewed
[ ] Workspace isolation reviewed
[ ] Audit logging reviewed

Findings:
- [FINDING 1: Description, Severity, Remediation]
- [FINDING 2: ...]

Approval:
[ ] Approved (no security concerns)
[ ] Approved with minor fixes (non-blocking)
[ ] Rejected (blocking security issues found)

Signature: _____________ Date: _______
```

---

## Dependency Audit Procedure

### Frontend Dependencies (npm)

**Weekly Audit**:

```bash
cd frontend

# 1. Check for known vulnerabilities
npm audit

# 2. Review audit report
npm audit --json > /tmp/npm-audit.json
cat /tmp/npm-audit.json | jq '.vulnerabilities | to_entries | map({package: .key, severity: .value.severity, via: .value.via})'

# 3. Fix auto-fixable vulnerabilities
npm audit fix

# 4. Review breaking changes (if audit fix --force needed)
npm audit fix --dry-run --force

# 5. Update package-lock.json
npm install

# 6. Verify no regressions
npm run test
npm run build
```

**Severity Thresholds**:
- Critical: Fix immediately (within 24 hours)
- High: Fix within 1 week
- Medium: Fix within 30 days
- Low: Review, fix if low-effort

**SBOM Generation**:

```bash
# Generate Software Bill of Materials
npx @cyclonedx/cyclonedx-npm --output-file /tmp/frontend-sbom.json
```

### Backend Dependencies (uv)

**Weekly Audit**:

```bash
cd backend

# 1. Check for known vulnerabilities
pip-audit

# Or use safety (alternative)
uv run safety check

# 2. Review outdated dependencies
uv run pip list --outdated

# 3. Update dependencies (cautiously)
uv add <package>@latest

# 4. Run tests after updates
uv run pytest

# 5. Update lock file
uv sync
```

**Critical Dependencies**:
- FastAPI: Authentication, validation, API framework
- SQLAlchemy: Database ORM (SQL injection prevention)
- cryptography: Encryption library (AES-256-GCM)
- python-jose: JWT library (signature validation)
- pydantic: Input validation
- aiohttp: HTTP client (API calls)

**SBOM Generation**:

```bash
# Generate SBOM with CycloneDX
pip install cyclonedx-bom
cyclonedx-py -o /tmp/backend-sbom.json
```

### Docker Image Scanning

```bash
# Scan API image for vulnerabilities
trivy image pazpaz-api:latest --severity CRITICAL,HIGH

# Or use Snyk
snyk container test pazpaz-api:latest

# Generate vulnerability report
trivy image pazpaz-api:latest --format json --output /tmp/image-scan.json
```

---

## Weekly Security Tasks

**Every Monday** (30 minutes):

- [ ] Review CloudWatch alarms (security-related)
- [ ] Check authentication failure rate (>100/hour? Investigate)
- [ ] Audit database SSL connections (ensure all encrypted)
- [ ] Review recent audit events (spot-check for anomalies)
- [ ] Run `npm audit` (frontend dependencies)
- [ ] Run `pip-audit` (backend dependencies)
- [ ] Verify ClamAV antivirus running (production)
- [ ] Check SSL certificate expiration (>30 days remaining?)

---

## Monthly Security Tasks

**First Monday of Month** (2 hours):

- [ ] Review AWS Secrets Manager access logs (unauthorized access?)
- [ ] Audit encryption key access (CloudWatch logs)
- [ ] Review user access logs (inactive users? Revoke access)
- [ ] Scan Docker images for vulnerabilities (Trivy/Snyk)
- [ ] Review firewall rules (security group changes justified?)
- [ ] Update dependency SBOM (frontend + backend)
- [ ] Review rate limiting violations (brute force attempts?)
- [ ] Spot-check audit log completeness (PHI access logged?)
- [ ] Test backup restoration (1 random backup)
- [ ] Review incident response plan (any updates needed?)

---

## Quarterly Security Tasks

**First Week of Quarter** (1 day):

- [ ] **Encryption Key Rotation** (90-day schedule)
  - Generate new key (v_next)
  - Deploy dual-key application
  - Re-encrypt all data (background job)
  - Retire old key
  - Document rotation in audit log

- [ ] **Key Recovery Drill** (verify backups functional)
  - Download random backup from S3
  - Decrypt with GPG
  - Verify key length (32 bytes)
  - Test decryption in staging
  - Document drill results

- [ ] **Penetration Testing** (manual or automated)
  - Run security test suite (43 tests)
  - Review findings (0 critical vulnerabilities expected)
  - Fix any new vulnerabilities discovered
  - Update penetration test report

- [ ] **Security Review** (quarterly audit)
  - Review access control changes
  - Audit workspace isolation implementation
  - Verify authentication flows secure
  - Check error handling (no PII leakage)
  - Review audit logging completeness

- [ ] **Dependency Major Updates**
  - Review breaking changes (FastAPI, SQLAlchemy, Vue)
  - Test in staging
  - Deploy to production (if safe)

---

## Annual Security Tasks

**January** (1 week):

- [ ] **HIPAA Security Risk Assessment**
  - Review administrative safeguards
  - Review physical safeguards
  - Review technical safeguards
  - Document findings
  - Update security policies

- [ ] **Annual Security Training** (all staff)
  - HIPAA privacy and security rules
  - Phishing awareness
  - Password hygiene
  - Incident reporting procedures
  - Data handling best practices

- [ ] **Disaster Recovery Drill**
  - Simulate complete infrastructure failure
  - Restore from backups (database + keys + files)
  - Verify RTO/RPO met (RTO: 4 hours, RPO: 24 hours)
  - Document lessons learned

- [ ] **Security Policy Review**
  - Update security architecture documentation
  - Review incident response plan
  - Update key management procedures
  - Review security checklist (this document)

- [ ] **Third-Party Security Audit** (if required)
  - Engage external auditor (penetration testing firm)
  - SOC 2 Type II audit (if customer requirement)
  - HIPAA compliance audit
  - Remediate findings

- [ ] **Encryption Algorithm Review**
  - Verify AES-256-GCM still NIST-approved
  - Review JWT algorithm (HS256 still secure?)
  - Check for quantum-resistant alternatives (future-proofing)

---

**Document Owner**: Security Officer
**Review Schedule**: Quarterly
**Next Review**: 2026-01-19
**Approved By**: Security Officer, DevOps Lead, HIPAA Compliance Officer
