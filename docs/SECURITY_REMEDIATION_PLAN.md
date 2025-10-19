# PazPaz Backend Security Remediation Plan

**Created:** 2025-10-19
**Status:** In Progress
**Overall Security Score:** 7.4/10 → Target: 9.0/10
**Estimated Effort:** 48 hours (1.5 engineer-weeks)
**Target Completion:** Week 5 from start

---

## Progress Overview

- [ ] **Week 1:** Critical Security Fixes (4 tasks)
- [ ] **Week 2:** Encryption & Key Management (4 tasks)
- [ ] **Week 3:** File Upload Hardening (3 tasks)
- [ ] **Week 4:** Production Hardening (3 tasks)
- [ ] **Week 5:** Testing & Documentation (3 tasks)

**Total Tasks:** 17
**Completed:** 1
**In Progress:** 0
**Blocked:** 0

---

## Week 1: Critical Security Fixes

### ✅ Task 1.1: Enable Database SSL/TLS Connections
**Priority:** 🔴 CRITICAL
**Severity Score:** 2/10
**Estimated Effort:** 2 hours
**Status:** ✅ Completed (2025-10-19)

**Problem:**
Database connections use plain TCP without SSL/TLS, exposing PHI data in transit. HIPAA violation.

**Files Modified:**
- `/backend/src/pazpaz/db/base.py` - Added SSL context creation and verification
- `/backend/src/pazpaz/core/config.py` - Added SSL configuration settings
- `/backend/.env.example` - Documented SSL configuration
- `/docker-compose.yml` - Configured PostgreSQL with SSL certificates
- `/backend/scripts/generate_ssl_certs.sh` - Created certificate generation script (NEW)

**Implementation Steps:**
1. [x] Generate/obtain PostgreSQL SSL certificates - Created self-signed certs for development
2. [x] Configure PostgreSQL to require SSL - Updated docker-compose.yml with SSL config
3. [x] Update `base.py` to enforce SSL connections - Added SSL context with TLS 1.2+ enforcement
4. [x] Add SSL verification in connection string - Implemented via SSL context in connect_args
5. [x] Test connection with SSL enabled - Verified with test script, SSL active
6. [x] Add startup check to verify SSL is active - Added to main.py lifespan startup

**Code Changes:**
```python
# base.py
import ssl

ssl_context = ssl.create_default_context(cafile="/path/to/ca-cert.pem")
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args={
        "ssl": ssl_context,
        "server_settings": {
            "application_name": "pazpaz_api",
        },
    },
)
```

**Acceptance Criteria:**
- [x] All database connections use SSL/TLS - Verified via pg_stat_ssl query
- [x] Certificate validation enabled - SSL context enforces TLS 1.2+ with configurable verification modes
- [x] Startup check verifies SSL is active - Added to main.py lifespan, fails closed in production
- [x] Connection fails if SSL not available - PostgreSQL configured with ssl=on, client requires SSL
- [x] Tests pass with SSL enabled - test_ssl_connection.py passes successfully

**Implementation Notes:**
- Development uses self-signed certificates (verify-ca or require mode)
- Production should use CA-signed certificates (verify-full mode recommended)
- SSL modes: verify-full (production), verify-ca (staging), require (dev)
- Certificates generated via `./backend/scripts/generate_ssl_certs.sh`
- PostgreSQL server configured with TLS 1.2+ minimum, HIGH cipher suites
- Startup verification logs SSL status and fails in production if SSL not active

**Reference:** Data Protection Audit Report, Section 3.1

---

### ✅ Task 1.2: Fix JWT Token Expiration Validation
**Priority:** 🔴 CRITICAL
**Severity Score:** 2/10
**Estimated Effort:** 1 hour
**Status:** ⬜ Not Started

**Problem:**
`is_token_blacklisted()` disables expiration checking with `verify_exp=False`, allowing expired tokens to be accepted.

**Files to Modify:**
- `/backend/src/pazpaz/core/security.py`
- `/backend/src/pazpaz/api/deps.py`

**Implementation Steps:**
1. [ ] Remove `verify_exp=False` from `is_token_blacklisted()`
2. [ ] Add explicit expiration validation in `decode_jwt()`
3. [ ] Ensure all JWT decode operations validate expiration
4. [ ] Add test case for expired token rejection
5. [ ] Verify token refresh flow still works

**Code Changes:**
```python
# security.py
def decode_jwt(token: str) -> dict:
    """Decode JWT with expiration validation."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True}  # ENFORCE expiration
        )

        # Additional expiration check (defense-in-depth)
        exp = payload.get("exp")
        if not exp or datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise JWTError("Token expired")

        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted (without disabling expiration)."""
    try:
        # Remove verify_exp=False - use default validation
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        jti = payload.get("jti")
        return redis_client.exists(f"blacklist:{jti}")
    except jwt.ExpiredSignatureError:
        # Expired tokens are implicitly invalid
        return True
    except JWTError:
        return True
```

**Acceptance Criteria:**
- [ ] Expired tokens are rejected with 401 status
- [ ] Expiration validation cannot be bypassed
- [ ] Token refresh flow works correctly
- [ ] Tests cover expired token scenarios
- [ ] Blacklist check still functions

**Reference:** Auth & Authorization Audit Report, Issue #1

---

### ✅ Task 1.3: Fix CSRF Middleware Ordering
**Priority:** 🔴 CRITICAL
**Severity Score:** 3/10
**Estimated Effort:** 30 minutes
**Status:** ⬜ Not Started

**Problem:**
AuditMiddleware runs BEFORE CSRFProtectionMiddleware, allowing state-changing operations to bypass CSRF. `/verify` endpoint uses GET method (should be POST).

**Files to Modify:**
- `/backend/src/pazpaz/main.py`
- `/backend/src/pazpaz/api/auth.py`

**Implementation Steps:**
1. [ ] Reorder middleware: CSRF before Audit
2. [ ] Change `/verify` endpoint from GET to POST
3. [ ] Update frontend to use POST for `/verify`
4. [ ] Test CSRF protection on all endpoints
5. [ ] Verify audit logging still works

**Code Changes:**
```python
# main.py - CORRECT ORDER
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFProtectionMiddleware)  # BEFORE Audit
app.add_middleware(AuditMiddleware)           # AFTER CSRF
app.add_middleware(RequestIDMiddleware)

# auth.py - Change to POST
@router.post("/verify")  # Changed from GET
async def verify_magic_link(
    token: str = Body(...),  # In request body, not query param
    ...
```

**Acceptance Criteria:**
- [ ] CSRFProtectionMiddleware runs before AuditMiddleware
- [ ] `/verify` endpoint changed to POST
- [ ] Frontend updated to POST to `/verify`
- [ ] All tests pass
- [ ] CSRF tokens validated on state-changing operations

**Reference:** Auth & Authorization Audit Report, Issue #2

---

### ✅ Task 1.4: Implement Request Size Limits
**Priority:** 🔴 CRITICAL
**Severity Score:** 4/10
**Estimated Effort:** 1 hour
**Status:** ⬜ Not Started

**Problem:**
No global request body size limit. Attackers can send extremely large JSON payloads to cause memory exhaustion (DoS).

**Files to Modify:**
- `/backend/src/pazpaz/main.py`
- `/backend/src/pazpaz/middleware/request_size.py` (new file)

**Implementation Steps:**
1. [ ] Create RequestSizeLimitMiddleware
2. [ ] Set max request size to 20 MB (covers 10 MB file + metadata)
3. [ ] Add middleware to application
4. [ ] Test with large JSON payload (should reject)
5. [ ] Ensure file uploads still work

**Code Changes:**
```python
# middleware/request_size.py (NEW FILE)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce maximum request body size to prevent DoS."""

    MAX_REQUEST_SIZE = 20 * 1024 * 1024  # 20 MB

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > self.MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large (max {self.MAX_REQUEST_SIZE // (1024*1024)} MB)"
                }
            )

        return await call_next(request)

# main.py
from pazpaz.middleware.request_size import RequestSizeLimitMiddleware
app.add_middleware(RequestSizeLimitMiddleware)
```

**Acceptance Criteria:**
- [ ] Requests >20 MB rejected with 413 status
- [ ] File uploads up to 10 MB still work
- [ ] Error message is clear and actionable
- [ ] Test with 100 MB payload (should reject)
- [ ] Performance impact is negligible

**Reference:** API Security Audit Report, Issue #7

---

## Week 2: Encryption & Key Management

### ✅ Task 2.1: Move Database Credentials to AWS Secrets Manager
**Priority:** 🔴 CRITICAL
**Severity Score:** 5/10
**Estimated Effort:** 3 hours
**Status:** ⬜ Not Started

**Problem:**
Database password stored in `.env` file (not encrypted). Default password in `.env.example`.

**Files to Modify:**
- `/backend/src/pazpaz/core/config.py`
- `/backend/src/pazpaz/utils/secrets_manager.py`
- `/backend/.env.example`

**Implementation Steps:**
1. [ ] Create AWS Secrets Manager secret for DB credentials
2. [ ] Update `secrets_manager.py` to fetch DB credentials
3. [ ] Modify `config.py` to use Secrets Manager in production
4. [ ] Test connection with Secrets Manager credentials
5. [ ] Document secret format in README
6. [ ] Remove default password from `.env.example`

**Code Changes:**
```python
# secrets_manager.py
def get_database_credentials() -> str:
    """Fetch database credentials from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name=settings.aws_region)

    try:
        response = client.get_secret_value(SecretId='pazpaz/database-credentials')
        creds = json.loads(response['SecretString'])

        return (
            f"postgresql+asyncpg://{creds['username']}:{creds['password']}"
            f"@{creds['host']}:{creds['port']}/{creds['database']}"
            f"?ssl=verify-full&sslrootcert={creds.get('ssl_cert_path', '/etc/ssl/certs/ca-certificates.crt')}"
        )
    except ClientError as e:
        logger.error("failed_to_fetch_db_credentials", error=str(e))
        raise

# config.py
@property
def database_url(self) -> str:
    """Get database URL from Secrets Manager (prod) or env var (dev)."""
    if self.environment in ("production", "staging"):
        return get_database_credentials()
    return os.getenv("DATABASE_URL", "postgresql+asyncpg://pazpaz:pazpaz@localhost:5432/pazpaz")
```

**AWS Secret Format:**
```json
{
  "username": "pazpaz",
  "password": "GENERATED_STRONG_PASSWORD",
  "host": "prod-db.internal",
  "port": 5432,
  "database": "pazpaz",
  "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem"
}
```

**Acceptance Criteria:**
- [ ] Production uses Secrets Manager for DB credentials
- [ ] Development still uses `.env` file
- [ ] Connection succeeds with fetched credentials
- [ ] Error handling for Secrets Manager failures
- [ ] Documentation updated

**Reference:** Data Protection Audit Report, Section 3.2

---

### ✅ Task 2.2: Implement Encryption Key Rotation (90-Day Policy)
**Priority:** 🔴 CRITICAL
**Severity Score:** 3/10
**Estimated Effort:** 8 hours
**Status:** ⬜ Not Started

**Problem:**
No key rotation policy. Keys never rotated. HIPAA requires 90-day rotation.

**Files to Modify:**
- `/backend/src/pazpaz/utils/encryption.py`
- `/backend/src/pazpaz/utils/secrets_manager.py`
- `/backend/src/pazpaz/db/types.py`
- `/backend/src/pazpaz/models/session.py`

**Implementation Steps:**
1. [ ] Design key versioning schema
2. [ ] Create key registry to track multiple versions
3. [ ] Enable `EncryptedStringVersioned` for all PHI fields
4. [ ] Implement key rotation function
5. [ ] Create background job to re-encrypt old data
6. [ ] Document key rotation procedure
7. [ ] Test encryption/decryption with versioned keys
8. [ ] Set up AWS Lambda for automatic rotation

**Code Changes:**
```python
# encryption.py
@dataclass
class EncryptionKeyMetadata:
    key: bytes
    version: str
    created_at: datetime
    expires_at: datetime

    @property
    def needs_rotation(self) -> bool:
        """HIPAA: Rotate keys every 90 days."""
        return datetime.now(UTC) > (self.created_at + timedelta(days=90))

KEY_REGISTRY = {}  # Populated from Secrets Manager

def get_key_for_version(version: str) -> bytes:
    """Get encryption key for specific version."""
    if version not in KEY_REGISTRY:
        # Fetch from Secrets Manager
        key = fetch_key_from_secrets_manager(f"pazpaz/encryption-key-{version}")
        KEY_REGISTRY[version] = key
    return KEY_REGISTRY[version]

def encrypt_with_version(plaintext: str, version: str = "v2") -> bytes:
    """Encrypt with versioned key."""
    key = get_key_for_version(version)
    # ... AES-256-GCM encryption
    # Prepend version to ciphertext: b"v2:" + nonce + ciphertext
    return f"{version}:".encode() + nonce + ciphertext_with_tag

def decrypt_versioned(ciphertext: bytes) -> str:
    """Decrypt with version detection."""
    # Extract version from prefix
    version_end = ciphertext.index(b":")
    version = ciphertext[:version_end].decode()
    encrypted_data = ciphertext[version_end+1:]

    key = get_key_for_version(version)
    # ... AES-256-GCM decryption
```

**Key Rotation Procedure:**
```python
# scripts/rotate_encryption_keys.py
async def rotate_encryption_keys():
    """
    1. Generate new key (v3)
    2. Store in Secrets Manager
    3. Update KEY_REGISTRY
    4. All NEW encryptions use v3
    5. OLD data still decrypts with v1/v2
    6. Background job re-encrypts old data
    """
    new_version = generate_next_version()
    new_key = generate_encryption_key()

    # Store in Secrets Manager
    store_key_in_secrets_manager(new_version, new_key)

    # Mark as current
    update_current_key_version(new_version)

    # Schedule re-encryption job
    schedule_data_re_encryption(from_version="v2", to_version=new_version)
```

**Acceptance Criteria:**
- [ ] Multiple key versions supported
- [ ] Old data decrypts with old keys
- [ ] New data encrypts with current key
- [ ] 90-day rotation schedule documented
- [ ] Re-encryption script tested
- [ ] AWS Lambda rotation configured

**Reference:** Data Protection Audit Report, Section 1.2

---

### ✅ Task 2.3: Add Encryption Key Backup (Multi-Region)
**Priority:** 🔴 CRITICAL
**Severity Score:** 1/10
**Estimated Effort:** 4 hours
**Status:** ⬜ Not Started

**Problem:**
No key backup strategy. Lost AWS key = permanent data loss.

**Files to Modify:**
- AWS Secrets Manager configuration (infrastructure)
- `/backend/docs/security/KEY_BACKUP_RECOVERY.md` (new file)

**Implementation Steps:**
1. [ ] Enable multi-region replication in AWS Secrets Manager
2. [ ] Create offline GPG-encrypted backup procedure
3. [ ] Store backup in secure offline location
4. [ ] Document recovery procedure
5. [ ] Test key recovery from backup
6. [ ] Schedule quarterly recovery drills

**AWS Configuration:**
```bash
# Enable multi-region replication
aws secretsmanager replicate-secret-to-regions \
    --secret-id pazpaz/encryption-key-v1 \
    --add-replica-regions Region=us-west-2 \
    --add-replica-regions Region=eu-west-1

# Verify replication
aws secretsmanager describe-secret --secret-id pazpaz/encryption-key-v1
```

**Offline Backup Procedure:**
```bash
#!/bin/bash
# scripts/backup_encryption_keys.sh

DATE=$(date +%Y%m%d)

# Fetch all key versions
for version in v1 v2 v3; do
    aws secretsmanager get-secret-value \
        --secret-id pazpaz/encryption-key-$version \
        --query SecretString \
        --output text | \
    gpg --encrypt --recipient security@pazpaz.com > \
    encryption-key-$version-backup-$DATE.gpg
done

# Store on offline USB drive
# Document storage location in KEY_BACKUP_RECOVERY.md
echo "Backup complete: encryption-key-*-backup-$DATE.gpg"
echo "Store in: Secure location A (fireproof safe)"
```

**Recovery Test Script:**
```python
# tests/test_key_recovery.py
async def test_quarterly_key_recovery():
    """Test key recovery from backup (run quarterly)."""
    # 1. Fetch backup key from cold storage
    backup_key = fetch_backup_key_from_glacier("v1")

    # 2. Decrypt test PHI with backup key
    test_ciphertext = load_test_ciphertext()
    recovered_data = decrypt_with_key(test_ciphertext, backup_key)

    # 3. Verify decryption succeeded
    assert recovered_data == EXPECTED_PLAINTEXT

    logger.info("key_recovery_test_passed", key_version="v1")
```

**Acceptance Criteria:**
- [ ] Multi-region replication enabled (2+ regions)
- [ ] Offline backup created and stored securely
- [ ] Recovery procedure documented
- [ ] Recovery test passes
- [ ] Quarterly drill scheduled

**Reference:** Data Protection Audit Report, Section 5.1

---

### ✅ Task 2.4: Fix MinIO Encryption (Enable KMS)
**Priority:** 🔴 CRITICAL
**Severity Score:** 2/10
**Estimated Effort:** 2 hours
**Status:** ⬜ Not Started

**Problem:**
MinIO in development mode bypasses server-side encryption. Files stored unencrypted.

**Files to Modify:**
- `/backend/docker-compose.yml`
- `/backend/src/pazpaz/core/storage.py`
- `/backend/.env.example`

**Implementation Steps:**
1. [ ] Configure MinIO with KMS in docker-compose
2. [ ] Always enable encryption (MinIO and AWS)
3. [ ] Use HTTPS even in development
4. [ ] Validate encryption after upload
5. [ ] Test file upload with encryption

**Code Changes:**
```yaml
# docker-compose.yml
minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: ${S3_ACCESS_KEY}
    MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY}
    # Enable server-side encryption with KMS
    MINIO_KMS_SECRET_KEY: "my-minio-key:${MINIO_ENCRYPTION_KEY}"
  volumes:
    - minio_data:/data
  ports:
    - "9000:9000"
    - "9001:9001"
  networks:
    - pazpaz
```

```python
# storage.py - FIX: Always use encryption
async def upload_file(
    file: UploadFile,
    s3_key: str,
    content_type: str,
) -> dict:
    extra_args = {"ContentType": content_type}

    # ALWAYS enable encryption (MinIO or AWS)
    if is_minio_endpoint(settings.s3_endpoint_url):
        # MinIO with KMS
        extra_args["ServerSideEncryption"] = "aws:kms"
        extra_args["SSEKMSKeyId"] = settings.minio_kms_key_id
    else:
        # AWS S3
        extra_args["ServerSideEncryption"] = "AES256"

    # Upload
    await s3_client.upload_fileobj(file.file, settings.s3_bucket_name, s3_key, ExtraArgs=extra_args)

    # VERIFY encryption
    verify_file_encrypted(s3_key)

    return {"bucket": settings.s3_bucket_name, "key": s3_key}

def verify_file_encrypted(s3_key: str):
    """Verify file is encrypted at rest."""
    response = s3_client.head_object(Bucket=settings.s3_bucket_name, Key=s3_key)
    encryption = response.get("ServerSideEncryption")

    if not encryption:
        raise SecurityError(f"File {s3_key} not encrypted at rest!")

    logger.info("file_encryption_verified", key=s3_key, encryption=encryption)
```

**.env.example:**
```bash
# MinIO Encryption
MINIO_ENCRYPTION_KEY=CHANGE_ME_32_BYTE_BASE64_KEY
```

**Acceptance Criteria:**
- [ ] MinIO KMS encryption enabled
- [ ] All uploads encrypted (dev and prod)
- [ ] Encryption validated after upload
- [ ] HTTPS used for MinIO
- [ ] Tests pass with encryption

**Reference:** Data Protection Audit Report, Section 2.1

---

## Week 3: File Upload Hardening

### ✅ Task 3.1: Integrate ClamAV Malware Scanning
**Priority:** 🟠 HIGH
**Severity Score:** 5/10
**Estimated Effort:** 4 hours
**Status:** ⬜ Not Started

**Problem:**
No malware scanning on file uploads. Valid PDFs/images could contain malware.

**Files to Modify:**
- `/backend/src/pazpaz/utils/malware_scanner.py` (new file)
- `/backend/src/pazpaz/utils/file_validation.py`
- `/backend/docker-compose.yml`
- `/backend/requirements.txt`

**Implementation Steps:**
1. [ ] Add ClamAV container to docker-compose
2. [ ] Install `pyclamd` library
3. [ ] Create malware scanner utility
4. [ ] Integrate into file validation pipeline
5. [ ] Test with EICAR test virus
6. [ ] Configure fail-closed behavior in production

**Code Changes:**
```yaml
# docker-compose.yml
clamav:
  image: clamav/clamav:latest
  container_name: pazpaz-clamav
  ports:
    - "3310:3310"
  volumes:
    - clamav_data:/var/lib/clamav
  networks:
    - pazpaz
  healthcheck:
    test: ["CMD", "clamdscan", "--ping", "3"]
    interval: 30s
    timeout: 10s
    retries: 3
```

```python
# utils/malware_scanner.py (NEW FILE)
import clamd
from pazpaz.core.config import settings

class MalwareDetectedError(Exception):
    """Raised when malware is detected in file."""
    pass

class ScannerUnavailableError(Exception):
    """Raised when ClamAV service is unavailable."""
    pass

def scan_file_for_malware(file_content: bytes, filename: str) -> None:
    """
    Scan file for malware using ClamAV.

    Args:
        file_content: File bytes to scan
        filename: Original filename (for logging)

    Raises:
        MalwareDetectedError: If file contains malware
        ScannerUnavailableError: If ClamAV service is down
    """
    try:
        # Connect to ClamAV daemon
        clam = clamd.ClamdNetworkSocket(host='clamav', port=3310)

        # Scan file content
        result = clam.instream(io.BytesIO(file_content))

        if result['stream'][0] == 'FOUND':
            virus_name = result['stream'][1]
            logger.warning(
                "malware_detected",
                filename=filename,
                virus=virus_name,
                action="rejected",
            )
            raise MalwareDetectedError(f"Malware detected: {virus_name}")

        logger.info("malware_scan_passed", filename=filename)

    except clamd.ConnectionError as e:
        logger.error("clamav_connection_failed", error=str(e))

        # FAIL CLOSED: Reject file if scanner unavailable in production
        if settings.environment in ("production", "staging"):
            raise ScannerUnavailableError("Malware scanner unavailable. Upload rejected for security.")

        # FAIL OPEN: Allow in development (warn only)
        logger.warning("malware_scan_skipped_dev", filename=filename)

# file_validation.py
from pazpaz.utils.malware_scanner import scan_file_for_malware

def validate_file(filename: str, file_content: bytes) -> FileType:
    """Validate file with malware scanning."""
    # Existing validations...
    validate_file_size(len(file_content))
    extension = validate_extension(filename)
    detected_mime = detect_mime_type(file_content)
    validate_mime_extension_match(detected_mime, extension)

    if detected_mime in (FileType.JPEG, FileType.PNG, FileType.WEBP):
        validate_image_content(file_content, detected_mime)
    elif detected_mime == FileType.PDF:
        validate_pdf_content(file_content)

    # NEW: Malware scan
    scan_file_for_malware(file_content, filename)

    return detected_mime
```

**Testing:**
```python
# tests/test_malware_scanner.py
def test_eicar_virus_detected():
    """Test malware detection with EICAR test file."""
    # EICAR test virus (harmless test string)
    eicar = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'

    with pytest.raises(MalwareDetectedError, match="EICAR"):
        scan_file_for_malware(eicar, "test.txt")
```

**Acceptance Criteria:**
- [ ] ClamAV container running in docker-compose
- [ ] Malware scanning integrated into upload pipeline
- [ ] EICAR test virus detected and rejected
- [ ] Production fails closed if scanner unavailable
- [ ] Development logs warning if scanner down
- [ ] Performance impact <500ms per file

**Reference:** API Security Audit Report, Issue #8

---

### ✅ Task 3.2: Add Content-Type Validation
**Priority:** 🟠 HIGH
**Severity Score:** 6/10
**Estimated Effort:** 2 hours
**Status:** ⬜ Not Started

**Problem:**
API endpoints don't validate Content-Type header. Parser confusion attacks possible.

**Files to Modify:**
- `/backend/src/pazpaz/middleware/content_type.py` (new file)
- `/backend/src/pazpaz/main.py`

**Implementation Steps:**
1. [ ] Create ContentTypeValidationMiddleware
2. [ ] Require `application/json` for non-file endpoints
3. [ ] Require `multipart/form-data` for file uploads
4. [ ] Add middleware to application
5. [ ] Test with incorrect Content-Type (should reject)

**Code Changes:**
```python
# middleware/content_type.py (NEW FILE)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """Validate Content-Type header on POST/PUT/PATCH requests."""

    async def dispatch(self, request: Request, call_next):
        # Only validate on mutation requests with body
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        content_type = request.headers.get("content-type", "").split(";")[0].strip()

        # File upload endpoints require multipart
        if "/attachments" in request.url.path:
            if not content_type.startswith("multipart/form-data"):
                return JSONResponse(
                    status_code=415,
                    content={
                        "detail": "Content-Type must be multipart/form-data for file uploads"
                    }
                )
        # All other mutation endpoints require JSON
        elif content_type != "application/json":
            return JSONResponse(
                status_code=415,
                content={
                    "detail": "Content-Type must be application/json"
                }
            )

        return await call_next(request)

# main.py
from pazpaz.middleware.content_type import ContentTypeValidationMiddleware
app.add_middleware(ContentTypeValidationMiddleware)
```

**Acceptance Criteria:**
- [ ] POST/PUT/PATCH require correct Content-Type
- [ ] File uploads require multipart/form-data
- [ ] JSON endpoints require application/json
- [ ] 415 status code for wrong Content-Type
- [ ] GET/HEAD/OPTIONS not affected

**Reference:** API Security Audit Report, Issue #3

---

### ✅ Task 3.3: Implement Workspace Storage Quotas
**Priority:** 🟠 HIGH
**Severity Score:** 6/10
**Estimated Effort:** 2 hours
**Status:** ⬜ Not Started

**Problem:**
No global workspace storage quota. Could lead to storage abuse.

**Files to Modify:**
- `/backend/src/pazpaz/utils/file_validation.py`
- `/backend/src/pazpaz/models/workspace.py`

**Implementation Steps:**
1. [ ] Add storage tracking to Workspace model
2. [ ] Create quota validation function
3. [ ] Check quota before file upload
4. [ ] Update storage usage after upload/delete
5. [ ] Add endpoint to view storage usage

**Code Changes:**
```python
# models/workspace.py
class Workspace(Base):
    # Existing fields...
    storage_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_quota_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=10 * 1024 * 1024 * 1024,  # 10 GB default
        nullable=False,
    )

# file_validation.py
async def validate_workspace_storage_quota(
    workspace_id: uuid.UUID,
    new_file_size: int,
    db: AsyncSession,
) -> None:
    """Check if adding new file would exceed workspace quota."""
    workspace = await db.get(Workspace, workspace_id)

    if not workspace:
        raise ValueError("Workspace not found")

    if workspace.storage_used_bytes + new_file_size > workspace.storage_quota_bytes:
        usage_mb = workspace.storage_used_bytes / (1024 * 1024)
        quota_mb = workspace.storage_quota_bytes / (1024 * 1024)
        raise StorageQuotaExceededError(
            f"Workspace storage quota exceeded. "
            f"Using {usage_mb:.1f} MB of {quota_mb:.1f} MB."
        )

async def update_workspace_storage(
    workspace_id: uuid.UUID,
    bytes_delta: int,
    db: AsyncSession,
) -> None:
    """Update workspace storage usage."""
    workspace = await db.get(Workspace, workspace_id)
    workspace.storage_used_bytes += bytes_delta
    await db.commit()

# In upload endpoint
await validate_workspace_storage_quota(workspace_id, file_size, db)
# ... upload file
await update_workspace_storage(workspace_id, file_size, db)
```

**Acceptance Criteria:**
- [ ] Workspace model tracks storage usage
- [ ] Upload rejected if quota exceeded
- [ ] Storage usage updated on upload/delete
- [ ] Admin endpoint to view/adjust quotas
- [ ] Migration adds storage fields

**Reference:** API Security Audit Report, Section 2.3

---

## Week 4: Production Hardening

### ✅ Task 4.1: Tighten CSP (Nonce-Based) for Production
**Priority:** 🟠 HIGH
**Severity Score:** 6/10
**Estimated Effort:** 3 hours
**Status:** ⬜ Not Started

**Problem:**
CSP allows `unsafe-inline` and `unsafe-eval` in production, weakening XSS protection.

**Files to Modify:**
- `/backend/src/pazpaz/main.py`
- `/frontend/index.html`
- `/frontend/vite.config.ts`

**Implementation Steps:**
1. [ ] Generate CSP nonce per request
2. [ ] Pass nonce to frontend via meta tag
3. [ ] Configure Vue to use nonce for inline scripts
4. [ ] Remove `unsafe-inline` and `unsafe-eval` from production CSP
5. [ ] Test in production mode

**Code Changes:**
```python
# main.py
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Production: Nonce-based CSP
        if not settings.debug:
            nonce = secrets.token_urlsafe(16)
            request.state.csp_nonce = nonce

            response.headers["Content-Security-Policy"] = (
                f"default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                f"style-src 'self' 'nonce-{nonce}'; "
                f"img-src 'self' data: https:; "
                f"font-src 'self' data:; "
                f"connect-src 'self'; "
                f"frame-ancestors 'none'; "
                f"base-uri 'self'; "
                f"form-action 'self'"
            )
        else:
            # Development: Allow unsafe-inline for HMR
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                ...
            )
```

```html
<!-- frontend/index.html -->
<head>
  <meta name="csp-nonce" content="__CSP_NONCE__">
  <script nonce="__CSP_NONCE__">
    // Inline scripts use nonce
  </script>
</head>
```

**Acceptance Criteria:**
- [ ] Production CSP uses nonces
- [ ] No `unsafe-inline` or `unsafe-eval` in production
- [ ] Frontend scripts execute with nonce
- [ ] Development mode unchanged
- [ ] Tests pass in production mode

**Reference:** API Security Audit Report, Section 6

---

### ✅ Task 4.2: Add Missing HTTP Security Headers
**Priority:** 🟡 MEDIUM
**Severity Score:** 7/10
**Estimated Effort:** 1 hour
**Status:** ⬜ Not Started

**Problem:**
Missing `Referrer-Policy` and `Permissions-Policy` headers.

**Files to Modify:**
- `/backend/src/pazpaz/main.py`

**Implementation Steps:**
1. [ ] Add `Referrer-Policy` header
2. [ ] Add `Permissions-Policy` header
3. [ ] Test headers are present in responses
4. [ ] Verify no sensitive data in referrer

**Code Changes:**
```python
# main.py - SecurityHeadersMiddleware
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
```

**Acceptance Criteria:**
- [ ] `Referrer-Policy` set to `strict-origin-when-cross-origin`
- [ ] `Permissions-Policy` disables geolocation, microphone, camera
- [ ] Headers present in all responses
- [ ] Security scanner passes

**Reference:** API Security Audit Report, Section 6

---

### ✅ Task 4.3: Rate Limiting Improvements
**Priority:** 🟡 MEDIUM
**Severity Score:** 7/10
**Estimated Effort:** 2 hours
**Status:** ⬜ Not Started

**Problem:**
Rate limiting fails open when Redis is down. No IP-based global rate limiting.

**Files to Modify:**
- `/backend/src/pazpaz/api/deps.py`
- `/backend/src/pazpaz/main.py`

**Implementation Steps:**
1. [ ] Make rate limiting fail closed in production
2. [ ] Add IP-based global rate limiting
3. [ ] Add rate limit headers to responses
4. [ ] Test with Redis down (should fail closed)

**Code Changes:**
```python
# deps.py
async def check_rate_limit_redis(
    redis_client: Redis,
    key: str,
    max_requests: int,
    window_seconds: int,
) -> bool:
    """Check rate limit with fail-closed behavior."""
    try:
        # Existing rate limit logic...
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds)
        return current <= max_requests
    except Exception as e:
        logger.error("rate_limit_check_failed", error=str(e))

        # FAIL CLOSED in production
        if settings.environment in ("production", "staging"):
            raise HTTPException(
                status_code=503,
                detail="Rate limiting service unavailable"
            )

        # FAIL OPEN in development (warn only)
        logger.warning("rate_limit_bypassed_dev")
        return True

# main.py - Add IP-based rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute", "1000/hour"],
)
app.state.limiter = limiter
```

**Acceptance Criteria:**
- [ ] Production fails closed if Redis down
- [ ] IP-based rate limiting active
- [ ] Rate limit headers in responses
- [ ] Tests cover Redis failure scenario

**Reference:** Auth & Authorization Audit Report, Issue #3

---

## Week 5: Testing & Documentation

### ✅ Task 5.1: Security Penetration Testing
**Priority:** 🟡 MEDIUM
**Severity Score:** N/A
**Estimated Effort:** 8 hours
**Status:** ⬜ Not Started

**Problem:**
Need to validate all security fixes with penetration testing.

**Testing Checklist:**

**File Upload Security:**
- [ ] Upload polyglot file (valid image + PHP script)
- [ ] Upload ZIP bomb (42.zip)
- [ ] Upload EICAR test virus
- [ ] Test Unicode normalization attacks
- [ ] Test null byte injection in filenames
- [ ] Upload 100 MB file (should reject)
- [ ] Upload file with path traversal in name

**Workspace Isolation:**
- [ ] Attempt to access resources from different workspace
- [ ] Test UUID enumeration for resource discovery
- [ ] Verify generic 404 errors (no information leakage)
- [ ] Test concurrent user sessions in different workspaces
- [ ] Try to modify `workspace_id` in request body

**Input Validation:**
- [ ] Send 1 GB JSON payload (should reject)
- [ ] Send malformed JSON with deeply nested objects
- [ ] Test integer overflow in page/page_size
- [ ] Test negative values in numeric fields
- [ ] Test SQL injection in search queries

**Authentication:**
- [ ] Test JWT token replay after logout
- [ ] Test expired token handling
- [ ] Test CSRF bypass attempts
- [ ] Test rate limit enforcement
- [ ] Brute force magic link codes

**Encryption:**
- [ ] Verify database SSL connection
- [ ] Verify S3 files encrypted at rest
- [ ] Test key rotation scenario
- [ ] Test multi-version decryption

**Acceptance Criteria:**
- [ ] All tests documented in `/docs/security/PENETRATION_TEST_RESULTS.md`
- [ ] No critical vulnerabilities found
- [ ] High/Medium issues documented with remediation plan

**Reference:** All audit reports

---

### ✅ Task 5.2: Security Documentation
**Priority:** 🟡 MEDIUM
**Severity Score:** N/A
**Estimated Effort:** 4 hours
**Status:** ⬜ Not Started

**Problem:**
Security procedures not documented.

**Documentation to Create:**

1. [ ] `/docs/security/SECURITY_ARCHITECTURE.md`
   - Encryption architecture
   - Authentication flow diagrams
   - Workspace isolation design
   - Network security

2. [ ] `/docs/security/KEY_MANAGEMENT.md`
   - Key generation procedure
   - Key rotation schedule (90 days)
   - Key backup procedure
   - Key recovery procedure

3. [ ] `/docs/security/INCIDENT_RESPONSE.md`
   - Security incident classification
   - Escalation procedures
   - Breach notification requirements (HIPAA)
   - Post-incident review template

4. [ ] `/docs/security/SECURITY_CHECKLIST.md`
   - Pre-deployment security checklist
   - Security review process
   - Dependency audit procedure

5. [ ] Update `/README.md`
   - Security features overview
   - Responsible disclosure policy
   - Security contact information

**Acceptance Criteria:**
- [ ] All documentation complete and reviewed
- [ ] Procedures tested and validated
- [ ] Documentation accessible to team

**Reference:** All audit reports

---

### ✅ Task 5.3: Quarterly Key Recovery Drill
**Priority:** 🟡 MEDIUM
**Severity Score:** N/A
**Estimated Effort:** 2 hours
**Status:** ⬜ Not Started

**Problem:**
Need to ensure key backup/recovery procedures work.

**Drill Procedure:**

1. [ ] Schedule drill with team (non-production hours)
2. [ ] Simulate key loss scenario
3. [ ] Recover keys from backup (multi-region)
4. [ ] Recover keys from offline backup (GPG)
5. [ ] Decrypt test PHI data with recovered keys
6. [ ] Verify all data accessible
7. [ ] Document drill results
8. [ ] Update procedures if issues found

**Test Script:**
```python
# tests/security/test_key_recovery_drill.py
async def test_key_recovery_drill():
    """
    Quarterly drill to ensure key recovery works.
    Run this test every 90 days.
    """
    # 1. Fetch backup key from AWS Secrets Manager replica
    logger.info("Fetching key from us-west-2 replica...")
    backup_key_aws = fetch_key_from_replica("us-west-2", "v1")

    # 2. Fetch key from offline GPG backup
    logger.info("Decrypting GPG backup...")
    backup_key_offline = decrypt_gpg_backup("encryption-key-v1-backup.gpg")

    # 3. Verify both backups match
    assert backup_key_aws == backup_key_offline

    # 4. Decrypt test PHI with recovered key
    logger.info("Decrypting test PHI...")
    test_ciphertext = load_test_ciphertext()
    recovered_data = decrypt_with_key(test_ciphertext, backup_key_aws)

    # 5. Verify decryption succeeded
    assert recovered_data == EXPECTED_PLAINTEXT

    # 6. Log success
    logger.info(
        "key_recovery_drill_passed",
        key_version="v1",
        drill_date=datetime.now().isoformat(),
    )

    # 7. Generate drill report
    generate_drill_report()
```

**Acceptance Criteria:**
- [ ] Drill procedure documented
- [ ] Test script passes
- [ ] Drill report generated
- [ ] Next drill scheduled (3 months)

**Reference:** Data Protection Audit Report, Section 5.1

---

## Tracking & Reporting

### Weekly Progress Reports

**Week 1 Status:**
- Completed: 1/4 tasks
- In Progress: 0/4 tasks
- Blocked: 0/4 tasks
- Notes: Task 1.1 (Database SSL/TLS) completed on 2025-10-19. All database connections now encrypted with TLS 1.2+.

**Week 2 Status:**
- Completed: 0/4 tasks
- In Progress: 0/4 tasks
- Blocked: 0/4 tasks
- Notes: [Add weekly notes here]

**Week 3 Status:**
- Completed: 0/3 tasks
- In Progress: 0/3 tasks
- Blocked: 0/3 tasks
- Notes: [Add weekly notes here]

**Week 4 Status:**
- Completed: 0/3 tasks
- In Progress: 0/3 tasks
- Blocked: 0/3 tasks
- Notes: [Add weekly notes here]

**Week 5 Status:**
- Completed: 0/3 tasks
- In Progress: 0/3 tasks
- Blocked: 0/3 tasks
- Notes: [Add weekly notes here]

---

## Risk Register

| Risk ID | Description | Impact | Mitigation | Owner | Status |
|---------|-------------|--------|------------|-------|--------|
| R-001 | Database SSL certificates expire | High | Set up auto-renewal with Let's Encrypt | DevOps | ⬜ Open |
| R-002 | AWS Secrets Manager service disruption | Critical | Multi-region replication + offline backup | Security | ⬜ Open |
| R-003 | ClamAV signatures out of date | Medium | Auto-update in docker-compose | DevOps | ⬜ Open |
| R-004 | Key rotation breaks existing data | High | Thorough testing + rollback plan | Engineering | ⬜ Open |

---

## Success Criteria

### Security Score Targets

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Overall Security Score | 7.4/10 | 9.0/10 | ⬜ Not Met |
| Authentication Score | 7.5/10 | 9.5/10 | ⬜ Not Met |
| Data Protection Score | 6.5/10 | 9.0/10 | ⬜ Not Met |
| API Security Score | 8.2/10 | 9.0/10 | ⬜ Not Met |
| HIPAA Compliance | ❌ Non-Compliant | ✅ Compliant | ⬜ Not Met |

### Production Readiness Checklist

- [ ] All CRITICAL issues resolved
- [ ] All HIGH priority issues resolved
- [ ] Penetration testing passed
- [ ] Security documentation complete
- [ ] Key backup/recovery tested
- [ ] Team trained on security procedures
- [ ] Incident response plan in place
- [ ] HIPAA compliance validated
- [ ] Security audit sign-off

---

## Resources

### Audit Reports
- [Authentication & Authorization Audit](/docs/reports/security/2025-01-19-auth-authorization-audit.md)
- [Data Protection & Encryption Audit](/docs/reports/security/2025-01-19-data-encryption-audit.md) (to be created)
- [API Security & Input Validation Audit](/docs/reports/security/2025-01-19-api-input-validation-audit.md) (to be created)

### References
- [OWASP Top 10 (2021)](https://owasp.org/Top10/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [NIST Cryptographic Standards](https://csrc.nist.gov/projects/cryptographic-standards-and-guidelines)

### Contacts
- **Security Lead:** [Name]
- **Engineering Lead:** [Name]
- **DevOps Lead:** [Name]
- **Security Incident Email:** security@pazpaz.com

---

**Last Updated:** 2025-10-19
**Next Review:** After Week 5 completion
**Document Owner:** Security Team
