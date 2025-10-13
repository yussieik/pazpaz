# Storage Documentation Hub

**Last Updated:** 2025-10-13
**Module:** S3/MinIO Object Storage for Session Attachments
**Status:** Production-Ready ✅

## Overview

This directory contains comprehensive documentation for PazPaz's object storage system, which handles secure file uploads, storage, and retrieval for session attachments (photos, PDFs) in a HIPAA-compliant manner.

## Quick Navigation

### 🔐 Security & Credentials
- **[S3 Credential Management Guide](S3_CREDENTIAL_MANAGEMENT.md)** (1406 lines)
  Complete guide for secure credential management across all environments. **MUST READ before deployment**.
  - Password strength requirements
  - Environment-specific configurations (dev/staging/prod)
  - Zero-downtime rotation procedures
  - Emergency response procedures
  - AWS Secrets Manager & IAM integration

- **[File Upload Security Documentation](FILE_UPLOAD_SECURITY.md)** (783 lines)
  Defense-in-depth security architecture for file uploads with PHI protection.
  - Triple validation (extension + MIME + content)
  - EXIF metadata stripping for privacy
  - Path traversal prevention
  - Workspace isolation enforcement
  - Security test cases

### ⚙️ Configuration & Setup
- **[Storage Configuration Guide](STORAGE_CONFIGURATION.md)** (851 lines)
  Step-by-step setup for MinIO (development) and AWS S3 (production).
  - Docker Compose MinIO service
  - Bucket structure with workspace scoping
  - Server-side encryption (SSE-S3)
  - Presigned URLs for secure access
  - API reference with examples

### 📊 Implementation Summary
- **[Week 3 Day 11 Implementation Summary](WEEK3_DAY11_STORAGE_IMPLEMENTATION_SUMMARY.md)** (668 lines)
  Technical implementation details and deliverables from the storage system build.
  - Architecture decisions
  - Code quality metrics
  - Performance benchmarks
  - Known limitations (MinIO vs AWS S3)

## Architecture Overview

```
┌──────────────────┐
│   Vue Frontend   │
│  (File Upload)   │
└────────┬─────────┘
         │ HTTP POST
         ↓ multipart/form-data
┌──────────────────┐
│  FastAPI Backend │
│   (Validation)   │
├──────────────────┤
│ • Size limits    │
│ • MIME detection │
│ • Content parse  │
│ • EXIF stripping │
└────────┬─────────┘
         │ boto3
         ↓
┌──────────────────┐
│   S3/MinIO       │
│  Object Storage  │
├──────────────────┤
│ • AES-256 (SSE)  │
│ • Workspace paths│
│ • Private bucket │
└──────────────────┘
```

## Storage Structure

All files are organized with workspace-scoped paths for multi-tenant isolation:

```
pazpaz-attachments/
├── workspaces/
│   ├── {workspace_uuid}/
│   │   └── sessions/
│   │       └── {session_uuid}/
│   │           └── attachments/
│   │               ├── {uuid}.jpg   # Photo attachment
│   │               ├── {uuid}.pdf   # PDF document
│   │               └── {uuid}.png   # Image file
│   └── {another_workspace}/
│       └── sessions/...
```

## Key Features

### 🛡️ Security Features
- **Triple Validation**: Extension → MIME type → Content parsing
- **Privacy Protection**: EXIF metadata stripped from images
- **PDF Sanitization**: Metadata removal from PDF documents ([details](../../PDF_METADATA_SANITIZATION_IMPLEMENTATION.md))
- **Encryption**: AES-256 server-side encryption (AWS S3)
- **Access Control**: Time-limited presigned URLs (15 minutes)
- **Workspace Isolation**: Path-based multi-tenant separation
- **UUID Filenames**: Prevents path traversal attacks

### 🚀 Performance Features
- **Connection Pooling**: 50 max connections
- **Automatic Retries**: 3 attempts with exponential backoff
- **Caching**: S3 client singleton pattern
- **Async Operations**: Non-blocking file uploads/downloads
- **Optimized Timeouts**: 60s connect, 300s read

### 🏥 HIPAA Compliance
- **PHI Protection**: All files encrypted at rest
- **Audit Logging**: Every operation tracked ([AuditEvent](/docs/security/AUDIT_LOGGING_SCHEMA.md))
- **Access Control**: JWT-based workspace validation
- **Data Retention**: Soft deletes with configurable retention
- **Breach Response**: Documented incident procedures

## Related Documentation

### Security & Compliance
- [HIPAA Compliance Overview](/docs/security/HIPAA_COMPLIANCE.md)
- [Security Audit Reports](/docs/reports/security/)
- [PDF Metadata Sanitization](/docs/backend/PDF_METADATA_SANITIZATION_IMPLEMENTATION.md)
- [Encryption Architecture](/docs/security/encryption/ENCRYPTION_ARCHITECTURE.md)

### Implementation Details
- [Storage Client Code](/backend/src/pazpaz/core/storage.py)
- [File Validation Utils](/backend/src/pazpaz/utils/file_validation.py)
- [File Sanitization Utils](/backend/src/pazpaz/utils/file_sanitization.py)
- [Storage Tests](/backend/tests/test_file_upload.py)

### API Documentation
- [Session Attachments API](/backend/docs/api/SESSIONS.md#attachments)
- [OpenAPI Specification](/backend/docs/api/openapi.json)

## Quick Start

### Local Development (MinIO)

1. **Start MinIO Service**:
   ```bash
   docker-compose up -d minio
   ```

2. **Configure Environment** (`backend/.env`):
   ```bash
   S3_ENDPOINT_URL=http://localhost:9000
   S3_ACCESS_KEY=minioadmin        # Change these!
   S3_SECRET_KEY=minioadmin123     # Change these!
   S3_BUCKET_NAME=pazpaz-attachments
   S3_REGION=us-east-1
   ```

3. **Create Bucket**:
   ```bash
   cd backend
   python scripts/create_storage_buckets.py
   ```

4. **Access MinIO Console**:
   - URL: http://localhost:9001
   - Login with configured credentials

### Production (AWS S3)

See [Storage Configuration Guide](STORAGE_CONFIGURATION.md#production-setup) for detailed AWS S3 setup.

## Common Tasks

### Generate Secure Credentials
```bash
# Username (16 chars)
openssl rand -base64 16 | tr -d '/+=' | cut -c1-16

# Password (32 chars)
openssl rand -base64 32 | tr -d '/+=' | cut -c1-32
```

### Test Storage Connection
```python
from pazpaz.core.storage import verify_bucket_exists
verify_bucket_exists()  # Should return True
```

### Upload File (Python)
```python
from pazpaz.core.storage import generate_secure_filename, upload_file
from pazpaz.utils.file_validation import FileType

# Generate secure S3 key
s3_key = generate_secure_filename(
    workspace_id=workspace.id,
    session_id=session.id,
    file_type=FileType.JPEG
)

# Upload with encryption
await upload_file(
    file_obj=file.file,
    workspace_id=workspace.id,
    session_id=session.id,
    filename="sanitized_name.jpg",
    content_type="image/jpeg"
)
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| MinIO not starting | Check ports 9000/9001 availability: `lsof -i :9000` |
| Authentication failed | Verify S3_ACCESS_KEY matches MINIO_ROOT_USER in docker-compose |
| Bucket not found | Run `python scripts/create_storage_buckets.py` |
| Upload fails | Check file size limits (10MB) and allowed types |
| Presigned URL 403 | Check URL expiration and system clock sync |

For detailed troubleshooting, see [Storage Configuration Guide](STORAGE_CONFIGURATION.md#troubleshooting).

## Security Checklist

Before deploying to production:

- [ ] Changed default MinIO credentials
- [ ] Credentials stored in AWS Secrets Manager (not .env)
- [ ] IAM roles configured (not access keys) if possible
- [ ] Bucket encryption enabled (SSE-S3 or SSE-KMS)
- [ ] Public access blocked on bucket
- [ ] CloudTrail logging enabled
- [ ] Presigned URL expiration ≤ 15 minutes
- [ ] File validation and sanitization enabled
- [ ] Audit logging configured

## Support

For storage-related issues:

1. Check this documentation
2. Review [troubleshooting guide](STORAGE_CONFIGURATION.md#troubleshooting)
3. Check logs: `docker-compose logs minio` (dev) or CloudWatch (prod)
4. Consult security team for credential/access issues

## Changelog

### 2025-10-13
- Created comprehensive README with navigation
- Added cross-references to related documentation
- Included architecture overview and quick start guides

### 2025-10-12
- Initial storage implementation (Week 3 Day 11)
- Created core documentation files
- Implemented MinIO/S3 integration

---

**Maintained By:** Documentation Curator & database-architect
**Security Priority:** HIGH (PHI handling)
**Review Schedule:** Quarterly with credential rotation