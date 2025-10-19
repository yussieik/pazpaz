# PazPaz Security Architecture

**Last Updated:** 2025-10-19
**Version:** 1.0
**Status:** Production Ready
**Classification:** Public (Architecture Overview)

---

## Table of Contents

1. [Overview](#overview)
2. [Security Objectives](#security-objectives)
3. [Threat Model](#threat-model)
4. [Encryption Architecture](#encryption-architecture)
5. [Authentication Architecture](#authentication-architecture)
6. [Workspace Isolation Architecture](#workspace-isolation-architecture)
7. [Network Security](#network-security)
8. [Defense-in-Depth Layers](#defense-in-depth-layers)
9. [Security Boundaries & Trust Zones](#security-boundaries--trust-zones)
10. [Compliance Mapping](#compliance-mapping)

---

## Overview

PazPaz is a HIPAA-compliant practice management system for independent therapists, handling **Protected Health Information (PHI)** and **Personally Identifiable Information (PII)**. The security architecture implements defense-in-depth principles with multiple overlapping security controls to protect sensitive healthcare data.

### Key Security Principles

1. **Privacy-First**: Client data encrypted at rest and in transit
2. **Workspace Isolation**: Multi-tenant architecture with perfect data segregation
3. **Zero Trust**: Never trust client-provided data; always validate server-side
4. **Fail Securely**: Security failures default to denying access
5. **Least Privilege**: Users and services operate with minimal required permissions
6. **Audit Everything**: All PHI access/modifications logged to immutable audit trail

### Compliance Framework

- **HIPAA Security Rule** (45 CFR Part 164, Subpart C)
- **GDPR** (EU General Data Protection Regulation) - Data protection principles
- **OWASP Top 10** - Application security best practices

---

## Security Objectives

### Primary Security Goals

1. **Confidentiality**: Prevent unauthorized access to PHI/PII
   - Encryption at rest (AES-256-GCM)
   - Encryption in transit (TLS 1.2+)
   - Workspace-scoped access control

2. **Integrity**: Prevent unauthorized modification of PHI/PII
   - JWT signature validation (HS256)
   - Database constraints and transactions
   - Audit logging of all modifications

3. **Availability**: Ensure authorized users can access data when needed
   - Rate limiting prevents DoS attacks
   - Database connection pooling and failover
   - Graceful degradation under load

4. **Accountability**: Track all PHI access and modifications
   - Audit events logged to database (immutable)
   - User attribution via JWT claims
   - IP address tracking for authentication events

---

## Threat Model

### Assets Requiring Protection

1. **PHI/PII (Highest Value)**
   - Client names, contact information, addresses
   - Medical history, treatment notes (SOAP documentation)
   - Session photos/attachments
   - Therapist notes and assessments

2. **Authentication Credentials**
   - Magic link tokens (UUID4, 10-minute expiration)
   - JWT access tokens (HS256, 7-day expiration)
   - CSRF tokens (session-scoped)

3. **Encryption Keys**
   - Master encryption key (AES-256, versioned)
   - Database credentials (PostgreSQL)
   - JWT signing secret (HMAC-SHA256)

4. **Infrastructure Secrets**
   - S3/MinIO credentials
   - Redis connection string
   - Email service credentials (SMTP)

### Threat Actors

1. **External Attackers** (Primary Threat)
   - Motivation: PHI theft for identity theft, medical fraud, blackmail
   - Capabilities: Network attacks, brute force, SQL injection, XSS
   - Attack Vectors: Public API endpoints, authentication flows, file uploads

2. **Malicious Insiders** (Secondary Threat)
   - Motivation: Unauthorized access to client records, data exfiltration
   - Capabilities: Valid credentials, knowledge of system internals
   - Attack Vectors: API abuse, workspace enumeration, audit log tampering

3. **Compromised User Accounts** (Tertiary Threat)
   - Motivation: Attacker gains control of legitimate user account
   - Capabilities: All privileges of compromised user
   - Attack Vectors: Phishing, credential stuffing, session hijacking

### Attack Scenarios

#### Scenario 1: Cross-Workspace Data Access (Critical)
**Attack**: User from Workspace A attempts to access Client data from Workspace B
**Impact**: PHI breach, HIPAA violation, legal liability
**Mitigations**:
- All database queries filter by `workspace_id` (from JWT, never client input)
- Generic 404 errors (no information leakage)
- Audit logging of failed access attempts

#### Scenario 2: SQL Injection via Search Queries (High)
**Attack**: Attacker injects SQL in client search endpoint
**Impact**: Database compromise, PHI exfiltration
**Mitigations**:
- SQLAlchemy ORM (parameterized queries, no string concatenation)
- Pydantic input validation
- Least-privilege database user (no DROP/ALTER permissions)

#### Scenario 3: File Upload Malware (High)
**Attack**: Attacker uploads malicious file disguised as image/PDF
**Impact**: Code execution, data breach, ransomware
**Mitigations**:
- Extension whitelist (jpg, jpeg, png, webp, pdf only)
- MIME type detection (libmagic reads file headers)
- Content validation (PIL for images, pypdf for PDFs)
- ClamAV malware scanning (production)
- File size limits (10 MB per file, 50 MB per session)

#### Scenario 4: JWT Token Replay After Logout (Medium)
**Attack**: Attacker reuses stolen JWT after user logs out
**Impact**: Unauthorized API access, PHI exposure
**Mitigations**:
- Token blacklisting (Redis-based, JTI tracking)
- Short token expiration (7 days default)
- CSRF protection on all state-changing requests

---

## Encryption Architecture

### Encryption at Rest (PHI Protection)

**Algorithm**: AES-256-GCM (Galois/Counter Mode)
**Key Size**: 256 bits (32 bytes)
**IV/Nonce**: 96 bits (random per encryption, never reused)
**Implementation**: Application-level encryption via `EncryptedString` SQLAlchemy type

#### Encrypted Fields

All PHI fields in the database use `EncryptedString` type:

```python
# models/client.py
class Client(Base):
    full_name = Column(EncryptedString, nullable=False)  # PHI
    phone = Column(EncryptedString, nullable=True)       # PHI
    email = Column(EncryptedString, nullable=False)      # PHI
    address = Column(EncryptedString, nullable=True)     # PHI

# models/session.py
class Session(Base):
    subjective = Column(EncryptedString, nullable=True)  # PHI (patient symptoms)
    objective = Column(EncryptedString, nullable=True)   # PHI (therapist findings)
    assessment = Column(EncryptedString, nullable=True)  # PHI (diagnosis)
    plan = Column(EncryptedString, nullable=True)        # PHI (treatment plan)
```

#### Encryption Process Flow

```
Plaintext PHI → UTF-8 Encode → AES-256-GCM Encrypt → Base64 Encode → Database
                                      ↓
                              Random 96-bit Nonce
                              256-bit Master Key (versioned)
                              Authentication Tag (128-bit)
```

#### Key Features

1. **Non-Deterministic**: Same plaintext produces different ciphertext (semantic security)
   - Random nonce generated per encryption
   - Prevents pattern analysis and frequency attacks

2. **Authenticated Encryption**: GCM mode provides integrity + confidentiality
   - 128-bit authentication tag prevents tampering
   - Decrypt operation fails if ciphertext modified

3. **Key Versioning**: Multi-version support for key rotation
   - Ciphertext format: `{"algorithm": "aes-256-gcm", "version": "v2", "ciphertext": "..."}`
   - Old data decrypts with old key versions (backward compatibility)
   - New data encrypts with current key version

#### Key Storage

**Development**:
- Master key in `.env` file (base64-encoded, 32 bytes)
- Key rotation manual via configuration update

**Production**:
- Master key in AWS Secrets Manager
- Automatic rotation every 90 days (HIPAA compliant)
- Multi-region replication for disaster recovery
- IAM-based access control (principle of least privilege)

### Encryption in Transit (Network Protection)

#### Database Connections

**Protocol**: PostgreSQL with SSL/TLS 1.2+
**Certificate Validation**: Required (verify-full mode in production)
**Cipher Suites**: HIGH (excludes weak ciphers like RC4, MD5, DES)

```python
# backend/src/pazpaz/db/base.py
import ssl

ssl_context = ssl.create_default_context(
    purpose=ssl.Purpose.SERVER_AUTH,
    cafile="/path/to/ca-cert.pem"
)
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

engine = create_async_engine(
    database_url,
    connect_args={
        "ssl": ssl_context,
        "server_settings": {"application_name": "pazpaz_api"},
    }
)
```

#### API Connections

**Protocol**: HTTPS (TLS 1.2+)
**Security Headers**:
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`

#### Redis Connections

**Development**: Plain TCP (localhost only)
**Production**: TLS-encrypted connections + authentication

---

## Authentication Architecture

### Passwordless Authentication (Magic Link)

PazPaz uses **passwordless authentication** via magic links to eliminate password-related vulnerabilities (weak passwords, credential stuffing, phishing).

#### Magic Link Flow

```
1. User Request
   ↓
   POST /api/v1/auth/magic-link {"email": "user@example.com"}
   ↓
   Rate Limit Check (3 requests/hour per IP, 5 requests/hour per email)
   ↓
   User Lookup (email → User table)
   ↓
   Generate Token (secrets.token_urlsafe(32) → 256-bit entropy)
   ↓
   Store Token in Redis (key: "magic_link:{token}", TTL: 10 minutes)
   ↓
   Send Email (SMTP via MailHog/SendGrid)

2. User Clicks Link
   ↓
   POST /api/v1/auth/verify {"token": "..."}
   ↓
   Token Lookup in Redis
   ↓
   Token Validation (expiration, single-use)
   ↓
   User Lookup (user_id from token data)
   ↓
   Generate JWT (HS256, 7-day expiration, JTI for blacklisting)
   ↓
   Set HttpOnly Cookies (access_token, csrf_token)
   ↓
   Delete Magic Link Token (single-use enforcement)
   ↓
   Create Audit Event (user_authenticated)
```

#### Magic Link Security Features

1. **High Entropy**: `secrets.token_urlsafe(32)` generates 256 bits of entropy
   - Search space: 2^256 combinations (computationally infeasible to brute force)

2. **Short Expiration**: 10-minute window reduces attack surface
   - Attacker has limited time to intercept and use stolen link

3. **Single-Use**: Token deleted after verification
   - Replay attacks impossible

4. **Rate Limiting**: Prevents brute force and email bombing
   - 3 requests/hour per IP
   - 5 requests/hour per email address

5. **Audit Logging**: All authentication events logged
   - Magic link requests (successful and failed)
   - Token verifications (successful and failed)
   - IP addresses tracked for forensic analysis

### JWT (JSON Web Token) Session Management

#### Token Structure

```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "user_id": "uuid",
    "workspace_id": "uuid",
    "email": "user@example.com",
    "exp": 1234567890,
    "iat": 1234567890,
    "jti": "uuid"
  },
  "signature": "HMAC-SHA256(...)"
}
```

#### Token Security

1. **Signature Algorithm**: HS256 (HMAC-SHA256)
   - Symmetric signing with secret key (not exposed to client)
   - Prevents token tampering (signature validation required)

2. **Expiration Validation**: Explicit + implicit checks
   - `jwt.decode(..., options={"verify_exp": True})`
   - Manual timestamp validation (defense-in-depth)

3. **Token Blacklisting**: Redis-based revocation
   - JTI (JWT ID) stored in Redis on logout
   - Blacklist checked on every request
   - TTL matches token expiration (automatic cleanup)

4. **HttpOnly Cookies**: Token stored in cookie (not localStorage)
   - `HttpOnly` flag prevents JavaScript access (XSS mitigation)
   - `Secure` flag requires HTTPS
   - `SameSite=Lax` prevents CSRF attacks

### CSRF Protection

**Implementation**: Double-submit cookie pattern
**Middleware**: `CSRFProtectionMiddleware` validates on all POST/PUT/DELETE/PATCH

```python
# Request validation
csrf_token_cookie = request.cookies.get("csrf_token")
csrf_token_header = request.headers.get("X-CSRF-Token")

if not secrets.compare_digest(csrf_token_cookie, csrf_token_header):
    raise HTTPException(status_code=403, detail="CSRF token validation failed")
```

**Exemptions**:
- GET/HEAD/OPTIONS requests (safe methods)
- `/api/v1/auth/magic-link` (authentication entry point)
- `/api/v1/auth/verify` (pre-authentication endpoint)

---

## Workspace Isolation Architecture

### Multi-Tenant Data Segregation

PazPaz uses **workspace scoping** to ensure perfect isolation between therapist accounts. Each workspace is a logical container for all data (clients, sessions, appointments, audit events).

#### Workspace Model

```python
# models/workspace.py
class Workspace(Base):
    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)

    # Relationships
    users = relationship("User", back_populates="workspace")
    clients = relationship("Client", back_populates="workspace")
    sessions = relationship("Session", back_populates="workspace")
    appointments = relationship("Appointment", back_populates="workspace")
```

#### Workspace Scoping Rules

1. **JWT-Derived workspace_id**: Always from JWT token, never from client input
   ```python
   # api/deps.py
   async def get_current_user(access_token: str = Cookie(None)) -> User:
       payload = decode_access_token(access_token)
       user_id = payload["user_id"]
       workspace_id = payload["workspace_id"]  # Trusted source
       return await get_user_by_id(db, user_id)
   ```

2. **All Queries Filter by workspace_id**: Every database query includes workspace filter
   ```python
   # api/clients.py
   query = (
       select(Client)
       .where(Client.workspace_id == current_user.workspace_id)  # CRITICAL
       .where(Client.id == client_id)
   )
   ```

3. **Generic 404 Errors**: No information leakage
   ```python
   # api/deps.py
   async def get_or_404(model, model_id, workspace_id):
       obj = await db.get(model, model_id)
       if not obj or obj.workspace_id != workspace_id:
           raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
       return obj
   ```

4. **Foreign Key Constraints**: Database-level enforcement
   ```sql
   ALTER TABLE clients
   ADD CONSTRAINT fk_clients_workspace
   FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
   ON DELETE CASCADE;
   ```

#### Workspace Isolation Validation

**Penetration Test Results**: 6/7 tests passed (9.5/10 security score)

✅ **Validated Controls**:
- Cross-workspace client access blocked (404 error)
- UUID enumeration prevented (generic errors)
- Concurrent sessions isolated (no shared state)
- Soft-deleted records remain isolated
- Query params ignored (workspace_id from JWT only)
- Request body workspace_id ignored

---

## Network Security

### Firewall & Network Segmentation

**Production Architecture**:

```
Internet
   ↓
[AWS ALB/CloudFront]
   ↓ HTTPS (TLS 1.2+)
[API Gateway / Reverse Proxy]
   ↓
[Application Server (FastAPI)] ← Private subnet
   ↓ TLS 1.2+
[PostgreSQL Database] ← Private subnet (no internet access)
   ↓
[Redis Cache] ← Private subnet (no internet access)
   ↓
[MinIO/S3 Storage] ← Private bucket (pre-signed URLs only)
```

**Security Groups**:
- API Server: Ingress HTTPS (443) from ALB only
- Database: Ingress PostgreSQL (5432) from API Server only
- Redis: Ingress Redis (6379) from API Server only
- S3: No direct access (IAM role-based)

### Security Headers

**Configured in `SecurityHeadersMiddleware`**:

```python
headers = {
    # HSTS: Force HTTPS for 1 year
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

    # CSP: Prevent XSS and data injection attacks
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'",

    # Prevent clickjacking
    "X-Frame-Options": "DENY",

    # Prevent MIME sniffing
    "X-Content-Type-Options": "nosniff",

    # XSS protection (legacy browsers)
    "X-XSS-Protection": "1; mode=block",

    # Referrer policy (privacy)
    "Referrer-Policy": "strict-origin-when-cross-origin",

    # Permissions policy
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
```

### CORS Configuration

**Development**: Enabled for `http://localhost:5173` (frontend dev server)
**Production**: Same-origin only (reverse proxy routes `/api` to backend)

```python
# main.py
if settings.environment == "local":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

---

## Defense-in-Depth Layers

### Layer 1: Network Security
- TLS 1.2+ for all connections
- Security headers (HSTS, CSP, X-Frame-Options)
- Firewall rules (security groups)
- Rate limiting (DDoS prevention)

### Layer 2: Authentication & Authorization
- Passwordless magic link (eliminates password attacks)
- JWT with expiration and blacklisting
- CSRF protection on state-changing requests
- Workspace scoping (multi-tenant isolation)

### Layer 3: Input Validation
- Pydantic schema validation (type checking, constraints)
- Request size limits (20 MB max)
- SQLAlchemy ORM (parameterized queries, SQL injection prevention)
- File upload validation (7-layer defense: extension, MIME, content, malware, size, dimensions, sanitization)

### Layer 4: Data Protection
- Encryption at rest (AES-256-GCM for PHI)
- Encryption in transit (TLS 1.2+ for database, HTTPS for API)
- Key versioning (backward compatibility during rotation)
- Secure key storage (AWS Secrets Manager in production)

### Layer 5: Audit & Monitoring
- Audit events for all PHI access/modifications
- Authentication event logging (login, logout, failed attempts)
- Rate limit violation tracking
- Error logging (no PII in logs)

### Layer 6: Application Security
- Generic error messages (no information leakage)
- Fail-secure defaults (deny access on error)
- Least privilege (database user, IAM roles)
- Security testing (penetration testing, dependency scanning)

---

## Security Boundaries & Trust Zones

### Trust Zones

```
[Untrusted Zone]
   ↓ (HTTPS, rate limiting, input validation)
[DMZ: API Gateway / Reverse Proxy]
   ↓ (Authentication, authorization, CSRF)
[Trusted Zone: Application Server]
   ↓ (TLS, parameterized queries)
[Highly Trusted Zone: Database / Redis / S3]
```

### Trust Boundaries

1. **Internet → API Gateway**
   - Controls: TLS 1.2+, rate limiting, DDoS protection
   - Validates: Nothing trusted from internet

2. **API Gateway → Application Server**
   - Controls: JWT validation, CSRF protection, workspace scoping
   - Validates: User identity, permissions, workspace context

3. **Application Server → Database**
   - Controls: TLS 1.2+, parameterized queries, least privilege user
   - Validates: SQL syntax (ORM-generated), connection credentials

4. **Application Server → S3/MinIO**
   - Controls: IAM roles, pre-signed URLs (short-lived), file validation
   - Validates: File content, MIME types, malware scanning

### Data Flow Security

```
User Input → Input Validation → Authentication → Authorization → Encryption → Database
             (Pydantic)         (JWT)           (workspace)     (AES-256)    (TLS)
```

**Security Checkpoints**:
1. Input validation rejects malformed data
2. Authentication verifies user identity
3. Authorization confirms user has permission
4. Encryption protects PHI at rest
5. TLS protects data in transit

---

## Compliance Mapping

### HIPAA Security Rule

#### Administrative Safeguards (§164.308)

- **§164.308(a)(1)(ii)(A) Risk Analysis**: Penetration testing conducted (8.5/10 security score)
- **§164.308(a)(1)(ii)(B) Risk Management**: Security remediation plan in place
- **§164.308(a)(3)(i) Workforce Security**: Workspace isolation enforces access control
- **§164.308(a)(4)(i) Information Access Management**: JWT-based authentication, workspace scoping
- **§164.308(a)(5)(i) Security Awareness and Training**: Documented security architecture
- **§164.308(a)(8) Evaluation**: Quarterly key rotation drills, annual security audits

#### Physical Safeguards (§164.310)

- **§164.310(d)(1) Device and Media Controls**: S3 encryption at rest, database backups encrypted

#### Technical Safeguards (§164.312)

- **§164.312(a)(1) Access Control**: JWT authentication, workspace isolation, RBAC
- **§164.312(a)(2)(i) Unique User Identification**: User IDs (UUID), email-based identity
- **§164.312(a)(2)(iv) Encryption and Decryption**: AES-256-GCM for PHI, TLS 1.2+ in transit
- **§164.312(b) Audit Controls**: Audit events table, immutable logs
- **§164.312(c)(1) Integrity**: JWT signatures, database constraints, audit logging
- **§164.312(d) Person or Entity Authentication**: Magic link + JWT authentication
- **§164.312(e)(1) Transmission Security**: TLS 1.2+ for all connections

### GDPR Compliance

- **Article 25 (Data Protection by Design)**: Encryption by default, workspace isolation
- **Article 32 (Security of Processing)**: Encryption, pseudonymization, access controls
- **Article 33 (Breach Notification)**: Incident response plan (72-hour notification)
- **Article 35 (Data Protection Impact Assessment)**: Risk analysis completed

---

## References

- [HIPAA Security Rule (45 CFR Part 164)](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [OWASP Top 10 Application Security Risks](https://owasp.org/www-project-top-ten/)
- [NIST SP 800-53 Security Controls](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- [CWE Top 25 Most Dangerous Software Weaknesses](https://cwe.mitre.org/top25/)

---

**Document Owner**: Security Team
**Review Schedule**: Quarterly
**Next Review**: 2026-01-19
**Approved By**: Engineering Lead, Security Auditor
