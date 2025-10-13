# S3/MinIO Storage Configuration Guide

**Created:** 2025-10-12
**Status:** Production-Ready
**Feature:** Week 3 Day 11 - S3/MinIO Integration

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Development Setup](#development-setup)
4. [Production Setup](#production-setup)
5. [Bucket Structure](#bucket-structure)
6. [Security Configuration](#security-configuration)
7. [API Reference](#api-reference)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Overview

PazPaz uses S3-compatible object storage for session attachment files (photos, PDFs, etc.). The storage system supports:

- **MinIO** for local development (S3-compatible open source)
- **AWS S3** for production deployment
- **Server-side encryption (SSE-S3)** for all stored files (AES-256)
- **Workspace-scoped paths** for multi-tenant isolation
- **Presigned URLs** for temporary authenticated access

**SECURITY NOTE:** Before deployment, review the [S3 Credential Management Guide](S3_CREDENTIAL_MANAGEMENT.md) to ensure secure credential configuration. Never use default credentials in production.

### Key Features

✅ **HIPAA Compliant**
- All files encrypted at rest (AES-256)
- Private buckets by default (no public access)
- Workspace path isolation (`workspace_id/sessions/{session_id}/`)
- Audit logging for all file operations

✅ **Production Ready**
- Connection pooling (50 max connections)
- Automatic retries (3 attempts, adaptive mode)
- TLS/SSL enforced in production
- Presigned URL expiration (15 minutes default)

✅ **Developer Friendly**
- MinIO runs in Docker Compose
- Web UI console (localhost:9001)
- Auto-bucket creation on startup
- Clear error messages and logging

---

## Architecture

### Storage Flow

```
User Upload → FastAPI Endpoint → File Validation → S3 Upload (encrypted)
                                       ↓
                            Workspace Path Scoping
                                       ↓
                    {workspace_id}/sessions/{session_id}/filename.jpg
                                       ↓
                            MinIO/S3 Bucket (AES-256 encrypted)
```

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **MinIO Service** | S3-compatible storage for development | `docker-compose.yml` |
| **S3 Client** | Boto3 singleton with connection pooling | `src/pazpaz/core/storage.py` |
| **Settings** | S3 configuration from environment | `src/pazpaz/core/config.py` |
| **Bucket Init Script** | Auto-create bucket on startup | `scripts/create_storage_buckets.py` |

---

## Development Setup

### 1. Start MinIO Service

MinIO runs in Docker Compose alongside PostgreSQL and Redis.

```bash
# From project root
cd /path/to/pazpaz
docker-compose up -d minio

# Verify MinIO is running
docker-compose ps
# Should show pazpaz-minio with status "Up"
```

**MinIO Ports:**
- **9000** - S3 API endpoint (used by boto3 client)
- **9001** - Web Console UI (browser access)

### 2. Environment Configuration

Configuration is in `backend/.env`:

```bash
# S3/MinIO Storage (Development)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin123
S3_BUCKET_NAME=pazpaz-attachments
S3_REGION=us-east-1
```

**SECURITY WARNING:** The default credentials (`minioadmin` / `minioadmin123`) are for **local development only**. These credentials are INSECURE and must NEVER be used in production or any network-accessible environment.

**Before deployment:**
1. Generate strong credentials (20+ characters): `openssl rand -base64 32`
2. Review [S3 Credential Management Guide](S3_CREDENTIAL_MANAGEMENT.md)
3. Use AWS Secrets Manager or IAM roles in production
4. Run validation: `python scripts/validate_s3_credentials.py`

### 3. Create Storage Bucket

Run the bucket initialization script:

```bash
cd backend
python scripts/create_storage_buckets.py
```

**Expected Output:**
```
============================================================
PazPaz Storage Bucket Initialization
============================================================
Endpoint: http://localhost:9000
Bucket: pazpaz-attachments
Region: us-east-1
------------------------------------------------------------
INFO: Creating bucket: pazpaz-attachments
INFO: Bucket created successfully: pazpaz-attachments
INFO: Bucket encryption enabled (SSE-S3): pazpaz-attachments
INFO: Public access blocked: pazpaz-attachments
------------------------------------------------------------
Bucket Configuration Status:
  Exists: True
  Encryption: Enabled
  Public Access: Blocked
  Versioning: Suspended
============================================================
Storage initialization complete!
============================================================
```

### 4. Access MinIO Console

Open your browser to: **http://localhost:9001**

**Login Credentials:**
- Username: `minioadmin`
- Password: `minioadmin123`

You can browse buckets, view objects, and manage configuration through the web UI.

### 5. Verify Storage Integration

Test the S3 client from Python:

```python
from pazpaz.core.storage import get_s3_client, verify_bucket_exists

# Get S3 client
s3_client = get_s3_client()

# Verify bucket exists
verify_bucket_exists()  # Returns True if successful

# List buckets
response = s3_client.list_buckets()
print(response['Buckets'])
# [{'Name': 'pazpaz-attachments', 'CreationDate': datetime(...)}]
```

---

## Production Setup

### Using AWS S3

For production, replace MinIO with AWS S3.

#### 1. Create S3 Bucket

```bash
# Using AWS CLI
aws s3api create-bucket \
  --bucket pazpaz-attachments-prod \
  --region us-west-2 \
  --create-bucket-configuration LocationConstraint=us-west-2

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket pazpaz-attachments-prod \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket pazpaz-attachments-prod \
  --public-access-block-configuration \
    BlockPublicAcls=true,\
    IgnorePublicAcls=true,\
    BlockPublicPolicy=true,\
    RestrictPublicBuckets=true
```

#### 2. Create IAM User

Create an IAM user with S3 access (principle of least privilege):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::pazpaz-attachments-prod",
        "arn:aws:s3:::pazpaz-attachments-prod/*"
      ]
    }
  ]
}
```

#### 3. Production Environment Variables

```bash
# S3/MinIO Storage (Production)
S3_ENDPOINT_URL=  # Leave empty for AWS S3 (uses default endpoint)
S3_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE  # IAM access key
S3_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_BUCKET_NAME=pazpaz-attachments-prod
S3_REGION=us-west-2
```

**Security Best Practices:**
- Store credentials in AWS Secrets Manager or environment variables (never commit to Git)
- Use IAM roles (EC2/ECS/EKS) instead of access keys when possible (recommended)
- Enable CloudTrail for S3 audit logging
- Enable S3 versioning for compliance (optional)
- Configure S3 lifecycle policies to transition old files to Glacier
- Rotate credentials every 90 days (see [S3 Credential Management Guide](S3_CREDENTIAL_MANAGEMENT.md))
- Validate credentials before deployment: `python scripts/validate_s3_credentials.py`

---

## Bucket Structure

### Workspace-Scoped Paths

All files are stored with workspace-scoped paths to enforce multi-tenant isolation:

```
pazpaz-attachments/
├── 1/                           # Workspace ID 1
│   └── sessions/
│       ├── 101/                 # Session ID 101
│       │   ├── photo1.jpg
│       │   └── report.pdf
│       └── 102/                 # Session ID 102
│           └── xray.png
├── 2/                           # Workspace ID 2
│   └── sessions/
│       └── 201/                 # Session ID 201
│           └── intake-form.pdf
└── 3/                           # Workspace ID 3
    └── sessions/
        └── 301/
            └── assessment.jpg
```

### Path Structure

**Format:** `{workspace_id}/sessions/{session_id}/{filename}`

**Example:** `123/sessions/456/photo.jpg`

### Path Isolation Benefits

1. **Security:** Workspace ID is always in path (application-level enforcement)
2. **Audit Trail:** Easy to identify which workspace owns each file
3. **Deletion:** Can delete all files for a workspace by prefix
4. **Organization:** Logical grouping by workspace and session

### Path Building

Use the `build_object_key()` helper:

```python
from pazpaz.core.storage import build_object_key

object_key = build_object_key(
    workspace_id=123,
    session_id=456,
    filename="photo.jpg"  # Must be sanitized before calling
)
# Returns: "123/sessions/456/photo.jpg"
```

---

## Security Configuration

### Server-Side Encryption (SSE-S3)

All files are automatically encrypted at rest using AES-256.

**MinIO:**
- Set `MINIO_KMS_AUTO_ENCRYPTION=on` in docker-compose.yml
- Encryption happens automatically on upload

**AWS S3:**
- Bucket encryption configured via AWS CLI or boto3
- All `PutObject` requests include `ServerSideEncryption: AES256`

### Private Buckets

Buckets are **private by default** (no public access).

**Access Methods:**
1. **Presigned URLs:** Temporary authenticated URLs (15 minutes expiration)
2. **Authenticated API:** Backend API endpoints with JWT authentication

**Never:**
- ❌ Make buckets public
- ❌ Use static URLs without authentication
- ❌ Store PHI in object metadata (use database instead)

### Presigned URLs

Presigned URLs provide time-limited access without AWS credentials.

```python
from pazpaz.core.storage import generate_presigned_url

# Generate download URL (expires in 15 minutes)
url = generate_presigned_url(
    object_key="123/sessions/456/photo.jpg",
    expires_in=900,  # 15 minutes (default)
    http_method="get_object"
)

# URL valid for 15 minutes
# https://pazpaz-attachments.s3.amazonaws.com/123/sessions/456/photo.jpg?
#   AWSAccessKeyId=...&Signature=...&Expires=1697123456
```

**Security Notes:**
- URLs expire after 15 minutes (configurable)
- Keep expiration short to minimize risk
- URLs are single-use (can't be reused after expiration)
- Logged in audit trail (who accessed what file)

### TLS/SSL Configuration

**Development (MinIO):**
- TLS disabled (`use_ssl=False`) for localhost
- Traffic between FastAPI and MinIO is unencrypted (same host)

**Production (AWS S3):**
- TLS enforced (`use_ssl=True`) for all connections
- boto3 uses HTTPS by default
- Certificate validation enabled

**Production MinIO:**
- Configure TLS certificates in MinIO server
- Set `S3_ENDPOINT_URL=https://minio.example.com`
- Update `use_ssl` logic in `storage.py` to check endpoint URL

---

## API Reference

### S3 Client

#### `get_s3_client() -> boto3.client`

Get cached S3 client singleton.

```python
from pazpaz.core.storage import get_s3_client

s3_client = get_s3_client()
```

**Returns:** Configured boto3 S3 client

**Configuration:**
- Connection pooling (50 max connections)
- Automatic retries (3 attempts, adaptive mode)
- 60s connect timeout, 300s read timeout
- Signature version 4 (s3v4)

#### `build_object_key(workspace_id: int, session_id: int, filename: str) -> str`

Build workspace-scoped S3 object key.

```python
from pazpaz.core.storage import build_object_key

key = build_object_key(123, 456, "photo.jpg")
# Returns: "123/sessions/456/photo.jpg"
```

**Args:**
- `workspace_id`: Workspace ID for isolation
- `session_id`: Session ID for grouping
- `filename`: Sanitized filename (caller must sanitize)

**Returns:** S3 object key string

#### `generate_presigned_url(object_key: str, expires_in: int = 900, http_method: str = "get_object") -> str`

Generate presigned URL for temporary file access.

```python
from pazpaz.core.storage import generate_presigned_url

url = generate_presigned_url(
    object_key="123/sessions/456/photo.jpg",
    expires_in=900,  # 15 minutes
    http_method="get_object"
)
```

**Args:**
- `object_key`: S3 object key (from `build_object_key`)
- `expires_in`: URL expiration in seconds (default: 900)
- `http_method`: S3 method (`get_object` or `put_object`)

**Returns:** Presigned URL string

**Raises:** `S3ClientError` if URL generation fails

#### `async upload_file(file_obj, workspace_id: int, session_id: int, filename: str, content_type: str) -> str`

Upload file to S3 with encryption.

```python
from pazpaz.core.storage import upload_file

# From FastAPI endpoint
object_key = await upload_file(
    file_obj=upload_file.file,  # UploadFile.file
    workspace_id=123,
    session_id=456,
    filename="photo.jpg",  # Sanitized
    content_type="image/jpeg"  # Validated MIME type
)
# Returns: "123/sessions/456/photo.jpg"
```

**Args:**
- `file_obj`: File-like object (from FastAPI UploadFile)
- `workspace_id`: Workspace ID for isolation
- `session_id`: Session ID for grouping
- `filename`: Sanitized filename
- `content_type`: Validated MIME type

**Returns:** S3 object key

**Raises:** `S3UploadError` if upload fails

**Security:**
- File is encrypted at rest (AES-256)
- Content-Type header set (prevents MIME sniffing)
- Workspace path isolation enforced

#### `async delete_file(object_key: str) -> None`

Delete file from S3.

```python
from pazpaz.core.storage import delete_file

await delete_file("123/sessions/456/photo.jpg")
```

**Args:**
- `object_key`: S3 object key to delete

**Raises:** `S3DeleteError` if deletion fails

**Note:** This is a hard delete. Consider soft deletes in database instead.

#### `verify_bucket_exists() -> bool`

Verify bucket exists and is accessible.

```python
from pazpaz.core.storage import verify_bucket_exists

exists = verify_bucket_exists()  # Returns True or raises
```

**Returns:** `True` if bucket exists and is accessible

**Raises:** `S3ClientError` if bucket doesn't exist or is not accessible

**Use Case:** Called during application startup to validate configuration.

---

## Testing

### Manual Testing (MinIO Console)

1. Start MinIO: `docker-compose up -d minio`
2. Open console: http://localhost:9001
3. Login: `minioadmin` / `minioadmin123`
4. Navigate to **Buckets** → **pazpaz-attachments**
5. Upload a test file via UI
6. Verify encryption status (should show "AES256")

### Python Testing

Create a test script (`test_storage.py`):

```python
import asyncio
from io import BytesIO
from pazpaz.core.storage import (
    get_s3_client,
    build_object_key,
    upload_file,
    generate_presigned_url,
    delete_file,
    verify_bucket_exists,
)

async def test_storage():
    # Verify bucket exists
    print("1. Verifying bucket...")
    verify_bucket_exists()
    print("   ✅ Bucket exists")

    # Upload test file
    print("2. Uploading test file...")
    test_content = b"Hello, PazPaz! This is a test file."
    file_obj = BytesIO(test_content)
    object_key = await upload_file(
        file_obj=file_obj,
        workspace_id=999,
        session_id=888,
        filename="test.txt",
        content_type="text/plain"
    )
    print(f"   ✅ Uploaded: {object_key}")

    # Generate presigned URL
    print("3. Generating presigned URL...")
    url = generate_presigned_url(object_key, expires_in=60)
    print(f"   ✅ URL: {url[:80]}...")

    # Download file (verify content)
    print("4. Downloading file...")
    import requests
    response = requests.get(url)
    assert response.content == test_content
    print(f"   ✅ Downloaded: {len(response.content)} bytes")

    # Delete file
    print("5. Deleting test file...")
    await delete_file(object_key)
    print(f"   ✅ Deleted: {object_key}")

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_storage())
```

Run the test:

```bash
cd backend
python test_storage.py
```

**Expected Output:**
```
1. Verifying bucket...
   ✅ Bucket exists
2. Uploading test file...
   ✅ Uploaded: 999/sessions/888/test.txt
3. Generating presigned URL...
   ✅ URL: http://localhost:9000/pazpaz-attachments/999/sessions/888/test.txt?...
4. Downloading file...
   ✅ Downloaded: 35 bytes
5. Deleting test file...
   ✅ Deleted: 999/sessions/888/test.txt

✅ All tests passed!
```

### Unit Tests

Create pytest tests in `tests/test_storage.py`:

```python
import pytest
from pazpaz.core.storage import build_object_key, get_s3_client, verify_bucket_exists

def test_build_object_key():
    key = build_object_key(123, 456, "photo.jpg")
    assert key == "123/sessions/456/photo.jpg"

def test_get_s3_client():
    client = get_s3_client()
    assert client is not None
    # Client should be cached (same instance)
    client2 = get_s3_client()
    assert client is client2

@pytest.mark.integration
def test_verify_bucket_exists():
    # Requires MinIO running
    exists = verify_bucket_exists()
    assert exists is True
```

Run tests:

```bash
cd backend
pytest tests/test_storage.py -v
```

---

## Troubleshooting

### MinIO Service Not Starting

**Problem:** `docker-compose up -d minio` fails or MinIO container exits

**Solutions:**

1. Check logs:
   ```bash
   docker-compose logs minio
   ```

2. Port conflict (9000 or 9001 already in use):
   ```bash
   # Check what's using port 9000
   lsof -i :9000
   # Kill the process or change MinIO ports in docker-compose.yml
   ```

3. Permission issues (volume mount):
   ```bash
   # Remove volume and recreate
   docker-compose down -v
   docker-compose up -d minio
   ```

### Bucket Creation Fails

**Problem:** `create_storage_buckets.py` exits with error

**Solutions:**

1. MinIO not running:
   ```bash
   docker-compose ps | grep minio
   # Should show "Up" status
   ```

2. Connection refused:
   ```
   Check S3_ENDPOINT_URL in .env matches MinIO port (default: http://localhost:9000)
   ```

3. Authentication failure:
   ```
   Verify S3_ACCESS_KEY and S3_SECRET_KEY match MINIO_ROOT_USER and MINIO_ROOT_PASSWORD
   ```

### File Upload Fails

**Problem:** `S3UploadError` when uploading files

**Solutions:**

1. Check bucket exists:
   ```python
   from pazpaz.core.storage import verify_bucket_exists
   verify_bucket_exists()  # Should return True or raise clear error
   ```

2. Check credentials:
   ```
   Verify S3_ACCESS_KEY and S3_SECRET_KEY in .env are correct
   ```

3. Check file size limits:
   ```
   MinIO default max object size: 5TB (plenty for attachments)
   Check FastAPI upload limits if using large files
   ```

### Presigned URL Fails

**Problem:** Presigned URL returns 403 Forbidden or expires immediately

**Solutions:**

1. Check URL expiration:
   ```python
   # Generate URL with longer expiration for testing
   url = generate_presigned_url(object_key, expires_in=3600)  # 1 hour
   ```

2. Clock skew:
   ```
   Ensure system clock is synchronized (presigned URLs use timestamps)
   ```

3. Object doesn't exist:
   ```python
   # Verify object exists
   s3_client = get_s3_client()
   s3_client.head_object(Bucket=settings.s3_bucket_name, Key=object_key)
   ```

### Production AWS S3 Connection Fails

**Problem:** Cannot connect to AWS S3 in production

**Solutions:**

1. Check credentials:
   ```bash
   aws s3 ls s3://pazpaz-attachments-prod
   # Should list bucket contents (or empty bucket)
   ```

2. Check IAM permissions:
   ```
   Verify IAM user has s3:PutObject, s3:GetObject, s3:DeleteObject, s3:ListBucket
   ```

3. Check network:
   ```
   Ensure server has internet access and can reach *.s3.amazonaws.com
   ```

4. Check region:
   ```
   S3_REGION must match bucket region (e.g., us-west-2)
   ```

### Encryption Not Enabled

**Problem:** Files stored in S3 without encryption

**Solutions:**

1. MinIO: Check docker-compose.yml:
   ```yaml
   environment:
     MINIO_KMS_AUTO_ENCRYPTION: "on"  # Must be quoted
   ```

2. AWS S3: Check bucket encryption:
   ```bash
   aws s3api get-bucket-encryption --bucket pazpaz-attachments-prod
   ```

3. Verify upload includes encryption header:
   ```python
   # In storage.py upload_file() function
   ExtraArgs={"ServerSideEncryption": "AES256"}
   ```

---

## Additional Resources

### Documentation
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Boto3 S3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)

### Related PazPaz Docs
- **[S3 Credential Management Guide](S3_CREDENTIAL_MANAGEMENT.md)** - MUST READ before deployment
- [File Upload Security](FILE_UPLOAD_SECURITY.md)
- [Encryption Architecture](/docs/security/encryption/ENCRYPTION_ARCHITECTURE.md)
- [Security Audit Week 2](/docs/SECURITY_AUDIT_WEEK2_DAY10.md)
- [API Implementation Guide](/backend/docs/api/)

### Security Best Practices
- [HIPAA S3 Configuration Guide](https://aws.amazon.com/compliance/hipaa-compliance/)
- [S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)

---

## Changelog

### 2025-10-12 - Initial Release
- MinIO service added to docker-compose.yml
- S3 client singleton with connection pooling
- Workspace-scoped bucket paths
- Automatic bucket creation script
- Server-side encryption (SSE-S3) enabled
- Presigned URL generation
- Production AWS S3 support
- Comprehensive documentation

---

## Support

For issues or questions about S3/MinIO storage:

1. Check this documentation
2. Review troubleshooting section
3. Check application logs: `docker-compose logs api`
4. Check MinIO logs: `docker-compose logs minio`
5. Open an issue with logs and configuration details

---

**Status:** ✅ Production-Ready
**Last Updated:** 2025-10-12
**Maintained By:** database-architect
