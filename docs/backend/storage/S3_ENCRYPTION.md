# S3/MinIO Server-Side Encryption (SSE) Verification

**Status**: ✅ Implemented
**Priority**: P0 (CRITICAL - HIPAA Compliance)
**HIPAA Requirement**: §164.312(a)(2)(iv) - Encryption at rest for PHI

## Overview

All PHI file attachments (SOAP note photos, client documents, consent forms) **MUST** be encrypted at rest in S3/MinIO storage. This document describes how the application enforces and verifies server-side encryption (SSE) to ensure HIPAA compliance.

### Why This Matters

**Security Issue**: Without encryption verification, PHI file attachments could be stored unencrypted at rest if S3/MinIO is misconfigured or encryption fails silently.

**Impact**:
- **HIGH severity** - PHI data exposure if encryption fails
- Violates HIPAA §164.312(a)(2)(iv) encryption requirement
- No detection mechanism if encryption fails
- Potential data breach with significant legal and financial consequences

## Implementation

### Architecture

```
File Upload Flow with Encryption Verification:

1. File Validation (MIME type, size, content)
   ↓
2. File Sanitization (EXIF stripping, filename sanitization)
   ↓
3. S3 Upload with SSE-S3 Forced
   ├─> ServerSideEncryption='AES256' parameter
   └─> Content uploaded with encryption enabled
   ↓
4. Encryption Verification (CRITICAL)
   ├─> HEAD request to verify ServerSideEncryption header
   ├─> If missing → DELETE file + RAISE error (fail-closed)
   └─> If present → Continue
   ↓
5. Store Encryption Metadata in Database
   ├─> algorithm: "AES256"
   ├─> verified_at: ISO timestamp
   ├─> s3_sse: ServerSideEncryption value from S3
   └─> etag: S3 ETag for integrity verification
   ↓
6. Return Success to Client
```

### Key Components

#### 1. Forced Server-Side Encryption

**File**: `backend/src/pazpaz/utils/file_upload.py`

```python
# Force SSE-S3 encryption on all uploads (AWS S3 only)
if not is_minio_endpoint(settings.s3_endpoint_url):
    extra_args["ServerSideEncryption"] = "AES256"
    logger.info(
        "s3_sse_enabled",
        s3_key=s3_key,
        encryption="AES256",
    )
```

**Behavior**:
- **AWS S3**: `ServerSideEncryption='AES256'` is set on all uploads
- **MinIO**: SSE-S3 not supported without KMS setup, encryption skipped in development
- **Production**: AWS S3 MUST have bucket-level default encryption enabled

#### 2. Encryption Verification

**File**: `backend/src/pazpaz/core/storage.py`

```python
def verify_file_encrypted(object_key: str) -> None:
    """
    Verify that file is encrypted at rest in S3/MinIO.

    HIPAA Compliance: §164.312(a)(2)(iv)

    Fail-Closed Behavior:
    - If ServerSideEncryption header is missing → raise error (AWS S3 only)
    - If S3 request fails → raise error
    - Production MUST have encryption enabled (no exceptions)
    - MinIO: Skip verification (SSE-S3 not supported without KMS)
    """
    s3_client = get_s3_client()

    # MinIO doesn't return ServerSideEncryption header
    if is_minio_endpoint(settings.s3_endpoint_url):
        logger.info("minio_encryption_check_skipped", object_key=object_key)
        return  # Skip verification for MinIO

    # Retrieve object metadata (no download, just headers)
    response = s3_client.head_object(
        Bucket=settings.s3_bucket_name,
        Key=object_key,
    )

    # Check ServerSideEncryption header
    encryption = response.get("ServerSideEncryption")

    if not encryption:
        # FAIL CLOSED: Reject upload if encryption cannot be verified
        logger.error(
            "encryption_verification_failed",
            object_key=object_key,
            reason="ServerSideEncryption header missing",
        )
        raise EncryptionVerificationError(
            f"File {object_key} not encrypted at rest! "
            "This is a HIPAA violation for PHI data."
        )

    logger.info(
        "encryption_verified",
        object_key=object_key,
        encryption_method=encryption,
    )
```

**Verification Logic**:
1. After S3 upload completes, make `HEAD` request for object metadata
2. Check if `ServerSideEncryption` header is present
3. If missing → **DELETE** file immediately + **RAISE** `EncryptionVerificationError`
4. If present → Log encryption method and continue
5. Store verification metadata in database

**Fail-Closed Design**: If encryption cannot be verified, the file is **deleted** and the upload **fails**. This ensures no unencrypted PHI is stored.

#### 3. Encryption Metadata Storage

**File**: `backend/src/pazpaz/models/session_attachment.py`

```python
class SessionAttachment(Base):
    """File attachment with encryption metadata for HIPAA compliance."""

    encryption_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="S3 server-side encryption metadata for HIPAA compliance verification",
    )
```

**Metadata Structure**:
```json
{
  "algorithm": "AES256",
  "verified_at": "2025-10-20T13:45:00.123456+00:00",
  "s3_sse": "AES256",
  "etag": "abc123def456"
}
```

**Fields**:
- `algorithm`: Always "AES256" (SSE-S3 encryption algorithm)
- `verified_at`: ISO 8601 timestamp when encryption was verified
- `s3_sse`: ServerSideEncryption value from S3 response
- `etag`: S3 ETag for object integrity verification

**Purpose**:
- Audit trail: Prove encryption was verified at upload time
- Compliance: Demonstrate HIPAA §164.312(a)(2)(iv) compliance
- Troubleshooting: Debug encryption issues in production

#### 4. Upload API Integration

**Files**:
- `backend/src/pazpaz/api/session_attachments.py`
- `backend/src/pazpaz/api/client_attachments.py`

```python
# Upload to S3/MinIO with encryption verification
try:
    upload_result = upload_file_to_s3(
        file_content=sanitized_content,
        s3_key=s3_key,
        content_type=file_type.value,
    )
    encryption_metadata = upload_result.get("encryption_metadata")
except EncryptionVerificationError as e:
    # Encryption verification failed - file already deleted
    logger.error("s3_encryption_verification_failed", error=str(e))
    await db.rollback()  # Rollback transaction (quota released)
    raise HTTPException(
        status_code=500,
        detail="Failed to encrypt file. Upload aborted for security.",
    )

# Create database record with encryption metadata
attachment = SessionAttachment(
    session_id=session_id,
    client_id=session.client_id,
    workspace_id=workspace_id,
    file_name=safe_filename,
    file_type=file_type.value,
    file_size_bytes=len(sanitized_content),
    s3_key=s3_key,
    uploaded_by_user_id=current_user.id,
    encryption_metadata=encryption_metadata,  # Store verification metadata
)
```

**Behavior**:
- If encryption verification fails, upload is rejected with HTTP 500
- Transaction is rolled back (storage quota reservation released)
- File is deleted from S3 (fail-closed)
- User receives clear error message

## Production Configuration

### AWS S3 Bucket Configuration

**Required**:
1. **Bucket Default Encryption**: Enable SSE-S3 (AES-256) at bucket level
2. **Bucket Policy**: Deny unencrypted uploads

**Bucket Policy Example**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnencryptedObjectUploads",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::pazpaz-production/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

**How to Enable Default Encryption**:

AWS Console:
1. Navigate to S3 → Buckets → `pazpaz-production`
2. Properties tab → Default encryption
3. Select "Server-side encryption with Amazon S3 managed keys (SSE-S3)"
4. Select "AES-256"
5. Save changes

AWS CLI:
```bash
aws s3api put-bucket-encryption \
  --bucket pazpaz-production \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": false
    }]
  }'
```

**Verification**:
```bash
# Verify bucket encryption is enabled
aws s3api get-bucket-encryption --bucket pazpaz-production

# Expected output:
# {
#   "ServerSideEncryptionConfiguration": {
#     "Rules": [{
#       "ApplyServerSideEncryptionByDefault": {
#         "SSEAlgorithm": "AES256"
#       }
#     }]
#   }
# }
```

### MinIO Configuration (Development Only)

**Development Environment**:
- MinIO does NOT support SSE-S3 without KMS setup
- Encryption verification is **skipped** for MinIO endpoints
- This is acceptable for **local development only**

**Production Requirement**:
- **NEVER** use MinIO in production without proper KMS configuration
- **ALWAYS** use AWS S3 with SSE-S3 in production/staging

**MinIO KMS Setup** (Optional for development):
See: https://min.io/docs/minio/linux/operations/server-side-encryption.html

## Testing

### Test Coverage

**File**: `backend/tests/security/test_s3_encryption_verification.py`

**Test Cases**:
1. ✅ Upload with SSE-S3 succeeds and metadata stored
2. ✅ Upload verification checks response encryption headers
3. ✅ Upload fails gracefully if encryption cannot be verified
4. ✅ Unencrypted file is deleted automatically (fail-closed)
5. ✅ Encryption metadata is stored in database
6. ✅ MinIO skips verification (development only)

**Run Tests**:
```bash
cd backend
uv run pytest tests/security/test_s3_encryption_verification.py -v
```

**Expected Output**:
```
tests/security/test_s3_encryption_verification.py::TestS3EncryptionVerification::test_upload_verifies_encryption_success PASSED
tests/security/test_s3_encryption_verification.py::TestS3EncryptionVerification::test_upload_fails_if_encryption_verification_fails PASSED
...
12 passed in 1.92s
```

### Manual Testing

**Upload a file and verify encryption**:

1. Upload file via API:
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/{session_id}/attachments" \
  -H "Authorization: Bearer {token}" \
  -F "file=@test_photo.jpg"
```

2. Check database for encryption metadata:
```sql
SELECT
  id,
  file_name,
  encryption_metadata
FROM session_attachments
ORDER BY created_at DESC
LIMIT 1;
```

**Expected Result**:
```json
{
  "algorithm": "AES256",
  "verified_at": "2025-10-20T13:45:00.123456+00:00",
  "s3_sse": "AES256",
  "etag": "abc123def456"
}
```

3. Verify S3 object is encrypted (AWS CLI):
```bash
aws s3api head-object \
  --bucket pazpaz-production \
  --key {s3_key}

# Look for:
# "ServerSideEncryption": "AES256"
```

## Troubleshooting

### Issue: Upload fails with "Failed to encrypt file"

**Cause**: S3 bucket encryption is not enabled or misconfigured

**Solution**:
1. Verify bucket default encryption is enabled (see "Production Configuration" above)
2. Check bucket policy allows `s3:PutObject` with `ServerSideEncryption`
3. Verify IAM user/role has `s3:PutObject` permission
4. Check application logs for detailed error:
```bash
docker-compose logs api | grep encryption_verification_failed
```

### Issue: MinIO uploads fail with encryption errors

**Cause**: MinIO doesn't support SSE-S3 headers without KMS

**Solution**:
- Ensure `is_minio_endpoint()` correctly detects MinIO (checks for "localhost", "127.0.0.1", or "minio" in URL)
- Verify environment is "local" or "development" (not "production")
- For production, **ALWAYS** use AWS S3, never MinIO

### Issue: Encryption metadata is `null` in database

**Cause**: Existing attachments uploaded before encryption verification was implemented

**Solution**:
- Old attachments will have `encryption_metadata = null`
- **NEW uploads** will always have encryption metadata populated
- To backfill existing attachments, create a migration script to fetch S3 metadata and update DB

**Backfill Script Example**:
```python
# backend/scripts/backfill_encryption_metadata.py
async def backfill_encryption_metadata():
    """Backfill encryption metadata for existing attachments."""
    from pazpaz.models.session_attachment import SessionAttachment
    from pazpaz.core.storage import get_s3_client

    s3_client = get_s3_client()

    # Fetch all attachments without encryption metadata
    query = select(SessionAttachment).where(
        SessionAttachment.encryption_metadata.is_(None),
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachments = result.scalars().all()

    for attachment in attachments:
        try:
            # Fetch S3 object metadata
            response = s3_client.head_object(
                Bucket=settings.s3_bucket_name,
                Key=attachment.s3_key,
            )

            # Build encryption metadata
            encryption_metadata = {
                "algorithm": "AES256",
                "verified_at": datetime.now(UTC).isoformat(),
                "s3_sse": response.get("ServerSideEncryption", "UNKNOWN"),
                "etag": response.get("ETag", "").strip('"'),
            }

            # Update attachment
            attachment.encryption_metadata = encryption_metadata

        except Exception as e:
            logger.error(
                "backfill_failed",
                attachment_id=str(attachment.id),
                s3_key=attachment.s3_key,
                error=str(e),
            )

    await db.commit()
```

## Security Considerations

### Fail-Closed Design

**Philosophy**: If encryption cannot be verified, **reject the upload**.

**Implementation**:
1. Upload succeeds to S3
2. Verification fails (no `ServerSideEncryption` header)
3. **DELETE** file from S3 immediately
4. **ROLLBACK** database transaction
5. **RAISE** `EncryptionVerificationError`
6. Return HTTP 500 to client

**Why Fail-Closed**:
- Prevents accidental storage of unencrypted PHI
- Ensures HIPAA compliance by default
- Better to fail upload than risk data breach

### Defense in Depth

**Multiple Layers of Encryption Enforcement**:

1. **Bucket-Level Default Encryption**: S3 bucket configured with SSE-S3 by default
2. **Upload-Level Encryption**: `ServerSideEncryption='AES256'` parameter on every upload
3. **Bucket Policy**: Deny unencrypted uploads at policy level
4. **Verification After Upload**: Check `ServerSideEncryption` header via `HEAD` request
5. **Database Audit Trail**: Store encryption metadata for every file
6. **Fail-Closed Cleanup**: Delete unencrypted files automatically

**Result**: Even if one layer fails, others catch the issue.

### HTTPS Requirement

**Production Requirement**: S3 endpoint MUST use HTTPS.

**Enforcement**:
```python
# backend/src/pazpaz/core/storage.py
if settings.environment in ("production", "staging"):
    if settings.s3_endpoint_url and not settings.s3_endpoint_url.startswith("https://"):
        raise ValueError(
            f"S3_ENDPOINT_URL must use HTTPS in {settings.environment} environment. "
            f"HTTP transmission exposes PHI in cleartext, violating HIPAA §164.312(e)(1)."
        )
```

**Why**: HIPAA §164.312(e)(1) - Transmission Security requires encryption in transit.

## Compliance

### HIPAA Requirements Met

✅ **§164.312(a)(2)(iv) - Encryption at Rest**:
- All PHI file attachments encrypted with AES-256
- Encryption verified after every upload
- Encryption metadata stored in database for audit trail

✅ **§164.312(e)(1) - Transmission Security**:
- HTTPS enforced for all S3 connections in production
- TLS 1.2+ required for data in transit

✅ **§164.308(a)(1)(ii)(D) - Information System Activity Review**:
- Encryption verification logged with structured logging
- Encryption metadata stored in database
- Failed verifications logged and alerted

### Audit Trail

**What is logged**:
- Every file upload with encryption status
- Encryption verification success/failure
- Encryption metadata (algorithm, timestamp, S3 headers)
- Failed uploads due to encryption issues

**Log Example**:
```json
{
  "event": "attachment_uploaded",
  "attachment_id": "uuid",
  "s3_key": "workspaces/{uuid}/sessions/{uuid}/attachments/{uuid}.jpg",
  "encryption_verified": true,
  "encryption_algorithm": "AES256",
  "timestamp": "2025-10-20T13:45:00.123456+00:00"
}
```

**Database Audit Trail**:
```sql
SELECT
  id,
  s3_key,
  encryption_metadata->>'algorithm' as algorithm,
  encryption_metadata->>'verified_at' as verified_at,
  created_at
FROM session_attachments
WHERE workspace_id = '{workspace_uuid}'
ORDER BY created_at DESC;
```

## Migration Guide

### Alembic Migration

**Migration File**: `backend/alembic/versions/01a5a73e9841_add_encryption_metadata_to_attachments.py`

**Apply Migration**:
```bash
cd backend
uv run alembic upgrade head
```

**Rollback Migration** (if needed):
```bash
uv run alembic downgrade -1
```

### Backward Compatibility

**Existing Attachments**:
- `encryption_metadata` column is **nullable**
- Old attachments uploaded before this feature will have `encryption_metadata = null`
- **NEW uploads** will always populate this field
- Application code handles `null` values gracefully

**Code Compatibility**:
```python
# Safe to check encryption metadata
if attachment.encryption_metadata:
    algorithm = attachment.encryption_metadata.get("algorithm")
    verified_at = attachment.encryption_metadata.get("verified_at")
else:
    # Old attachment, no metadata available
    algorithm = "UNKNOWN"
    verified_at = None
```

## Related Documentation

- [File Upload Security](FILE_UPLOAD_SECURITY.md) - Triple validation, EXIF stripping, malware scanning
- [S3 Credential Management](S3_CREDENTIAL_MANAGEMENT.md) - IAM roles, secret rotation
- [Storage Configuration](STORAGE_CONFIGURATION.md) - S3/MinIO setup, bucket policies

## References

- [HIPAA Security Rule §164.312(a)(2)(iv)](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html) - Encryption at rest
- [HIPAA Security Rule §164.312(e)(1)](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html) - Transmission security
- [AWS S3 Server-Side Encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/serv-side-encryption.html)
- [MinIO Server-Side Encryption](https://min.io/docs/minio/linux/operations/server-side-encryption.html)

---

**Last Updated**: 2025-10-20
**Implemented By**: backend-fullstack-specialist
**Reviewed By**: security-auditor
