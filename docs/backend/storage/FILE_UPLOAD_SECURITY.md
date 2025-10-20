# File Upload Security Documentation

**PazPaz Practice Management System**
**Module**: Session Attachments File Upload
**Security Level**: HIPAA-compliant PHI handling
**Last Updated**: 2025-10-20

## Overview

This document describes the defense-in-depth security architecture for file uploads in the PazPaz application. Session attachments (photos, PDFs) are validated, sanitized, and stored securely to prevent common file upload vulnerabilities while protecting patient privacy.

## Security Architecture

### Defense Layers

The file upload system implements multiple overlapping security layers (defense-in-depth):

1. **Size validation** - Prevent resource exhaustion attacks
2. **Extension validation** - Whitelist-based file type filtering
3. **MIME type detection** - Read file headers with libmagic
4. **MIME/extension matching** - Prevent type confusion attacks
5. **Content validation** - Parse files with format-specific libraries
6. **Metadata stripping** - Remove EXIF GPS/camera data for privacy
7. **Filename sanitization** - Prevent path traversal attacks
8. **Secure storage keys** - UUID-based, no user-controlled paths
9. **Workspace isolation** - Enforce multi-tenant data separation
10. **Audit logging** - Track all upload/download/delete operations

### Triple Validation Approach

Every uploaded file undergoes three independent validation checks:

```
User Upload → Size Check → Extension Check → MIME Detection → MIME/Extension Match → Content Parse → Sanitize → Store
```

## Supported File Types

**Images (for clinical documentation)**:
- JPEG (.jpg, .jpeg) - Wound photos, treatment areas
- PNG (.png) - Screenshots, diagrams
- WebP (.webp) - Modern image format with better compression

**Documents (for records)**:
- PDF (.pdf) - Lab reports, referrals, consent forms

### Why These Types?

- **Clinical relevance**: Common formats for medical documentation
- **Safe parsing**: Well-supported libraries (Pillow, pypdf)
- **No executable content**: Cannot contain scripts or macros
- **PHI protection**: Suitable for encrypted storage

## File Size Limits

### Per-File Limits

- **Maximum file size**: 10 MB
- **Reason**: Balance between usability and resource protection
- **Enforcement**: Validated before MIME detection

### Per-Session Limits

- **Maximum total attachments**: 50 MB per session
- **Reason**: Prevent unbounded storage growth
- **Enforcement**: Checked against existing attachments before upload

### Rationale

- 10 MB is sufficient for high-resolution clinical photos (4K)
- 50 MB allows 5-10 photos or several PDF documents per session
- Protects against DoS attacks via excessive uploads
- Keeps S3/MinIO storage costs predictable

## Validation Implementation

### 1. Extension Validation (`file_validation.py`)

**Purpose**: First line of defense - reject obviously wrong file types

**Implementation**:
```python
ALLOWED_EXTENSIONS = {
    '.jpg': FileType.JPEG,
    '.jpeg': FileType.JPEG,
    '.png': FileType.PNG,
    '.webp': FileType.WEBP,
    '.pdf': FileType.PDF,
}
```

**Security features**:
- Case-insensitive matching (`.JPG` == `.jpg`)
- Only last extension matters (`file.jpg.php` rejected as `.php`)
- Fail closed: Unknown extensions rejected

**Blocked threats**:
- Executable files (`.exe`, `.sh`, `.bat`)
- Server-side scripts (`.php`, `.jsp`, `.asp`)
- Archive files (`.zip`, `.tar`, `.rar`)

### 2. MIME Type Detection (`file_validation.py`)

**Purpose**: Detect actual file type from content, not just extension

**Implementation**:
```python
import magic

mime_type = magic.from_buffer(file_content, mime=True)
```

**How it works**:
- Reads first 2048 bytes of file (file header)
- Uses libmagic database to identify file type
- Independent of filename or extension
- Cannot be spoofed by renaming file

**Example**:
```
PHP file renamed to photo.jpg:
- Extension validation: PASS (sees .jpg)
- MIME detection: FAIL (detects text/x-php)
→ File rejected
```

**Blocked threats**:
- Type confusion attacks (wrong extension)
- Polyglot files (multiple format headers)
- Malicious files disguised as images

### 3. MIME/Extension Matching (`file_validation.py`)

**Purpose**: Ensure MIME type and extension agree

**Implementation**:
```python
def validate_mime_extension_match(detected_mime: FileType, extension: str):
    allowed_extensions = ALLOWED_MIME_TYPES[detected_mime]
    if extension not in allowed_extensions:
        raise MimeTypeMismatchError(...)
```

**Example rejections**:
- `document.jpg` (PDF content with JPEG extension)
- `photo.pdf` (JPEG content with PDF extension)
- `image.png` (JPEG content with PNG extension)

**Blocked threats**:
- Type confusion attacks
- Mismatched file types
- Intentional or accidental wrong extensions

### 4. Content Validation (`file_validation.py`)

**Purpose**: Verify file can be safely parsed

**Image validation (Pillow)**:
```python
img = Image.open(io.BytesIO(file_content))
img.verify()  # Triggers decompression, detects corruption

# Check format matches MIME
assert img.format == expected_format

# Prevent decompression bombs
max_pixels = 50_000_000  # 50 megapixels
assert img.size[0] * img.size[1] <= max_pixels
```

**PDF validation (pypdf)**:
```python
pdf_reader = PdfReader(io.BytesIO(file_content))

# Check not empty
assert len(pdf_reader.pages) > 0

# Prevent resource exhaustion
max_pages = 1000
assert len(pdf_reader.pages) <= max_pages

# Verify first page readable
_first_page = pdf_reader.pages[0]

# Note: PDF metadata stripping is also implemented
# See: /docs/backend/PDF_METADATA_SANITIZATION_IMPLEMENTATION.md
```

**Blocked threats**:
- Corrupted files (parsing errors detected)
- Decompression bombs (excessive dimensions)
- Malformed PDFs (cannot be parsed)
- Resource exhaustion (too many PDF pages)

## Privacy Protection

### EXIF Metadata Stripping (`file_sanitization.py`)

**Problem**: Image files contain metadata that can reveal:
- GPS coordinates (patient home address, clinic location)
- Camera make/model/serial (device tracking)
- Timestamp (when photo was taken)
- Software used (version fingerprinting)
- Author/copyright (PHI in description fields)

**Solution**: Strip all EXIF metadata before storage

**Implementation**:
```python
# Open image
img = Image.open(io.BytesIO(file_content))

# Load pixel data (strips metadata)
img_data = img.convert(img.mode)

# Save without EXIF
output = io.BytesIO()
img_data.save(output, format=format, quality=85, optimize=True)
return output.getvalue()
```

**What's removed**:
- GPS coordinates (GPSInfo tag)
- Camera make/model (Make, Model tags)
- Timestamps (DateTime, DateTimeOriginal)
- Software info (Software tag)
- Author/description (Artist, ImageDescription)
- All custom EXIF tags

**What's preserved**:
- Pixel data (image content)
- Dimensions (width × height)
- Color profile (RGB, RGBA)

**Privacy example**:
```
Before: photo.jpg (GPS: 40.7128° N, 74.0060° W, Camera: Canon EOS R5)
After: photo.jpg (no metadata, only pixels)
```

### Filename Sanitization (`file_sanitization.py`)

**Problem**: Filenames can contain malicious paths or special characters

**Threats**:
- Path traversal: `../../etc/passwd.jpg`
- Absolute paths: `/root/secrets.jpg`
- Special characters: `file<script>.jpg`
- Null bytes: `file\x00.php.jpg`

**Solution**: Sanitize filenames to safe ASCII

**Implementation**:
```python
# Extract extension
extension = Path(filename).suffix.lower()

# Remove path components
basename = Path(filename).name

# Replace dangerous characters
basename = re.sub(r'[^\w\s\-]', '_', basename)

# Collapse multiple underscores
basename = re.sub(r'[_\s]+', '_', basename)

# Remove leading/trailing junk
basename = basename.strip('_').strip()

# Fallback if empty
if not basename:
    basename = "attachment"

return f"{basename}{extension}"
```

**Examples**:
```
../../etc/passwd.jpg → passwd.jpg
file<script>.jpg → file_script_.jpg
my photo.jpg → my_photo.jpg
C:\Windows\file.jpg → file.jpg
```

## Secure Storage

### UUID-Based Storage Keys

**Problem**: User-controlled filenames in storage paths enable:
- Directory traversal attacks
- Filename collisions
- Predictable paths (guessing attack)
- Information disclosure

**Solution**: Generate secure S3 keys with UUIDs

**Implementation**:
```python
def generate_secure_filename(workspace_id, session_id, file_type):
    attachment_id = uuid.uuid4()
    extension = FILE_TYPE_TO_EXTENSION[file_type]
    return f"workspaces/{workspace_id}/sessions/{session_id}/attachments/{attachment_id}.{extension}"
```

**Example**:
```
User uploads: ../../../secrets.jpg
Stored as: workspaces/a3b2c1.../sessions/d4e5f6.../attachments/12ab34cd-56ef-78gh.jpg
```

**Security benefits**:
- No user-controlled content in path
- UUIDs prevent filename collisions
- Unpredictable paths (cannot guess URLs)
- Workspace/session hierarchy enforces isolation

### S3/MinIO Storage

**Storage location**: `/data/s3/pazpaz-attachments/`

**Bucket structure**:
```
pazpaz-attachments/
├── workspaces/
│   ├── {workspace_uuid_1}/
│   │   ├── sessions/
│   │   │   ├── {session_uuid_1}/
│   │   │   │   ├── attachments/
│   │   │   │   │   ├── {uuid_1}.jpg
│   │   │   │   │   ├── {uuid_2}.pdf
│   │   │   │   │   └── {uuid_3}.png
│   │   │   └── {session_uuid_2}/
│   │   │       └── attachments/
│   │   │           └── {uuid_4}.jpg
│   │   └── ...
│   └── {workspace_uuid_2}/
│       └── ...
```

**Encryption**:
- **At rest**: Server-side encryption (SSE-S3 with AES-256)
- **In transit**: TLS/SSL for all S3 operations
- **Access**: Pre-signed URLs with time expiration

**Pre-signed URLs**:
```python
url = generate_presigned_download_url(
    s3_key=attachment.s3_key,
    expiration=timedelta(hours=1)  # URL valid for 1 hour
)
```

**Benefits**:
- No AWS credentials required by client
- Time-limited access (1 hour default)
- Cannot guess other file URLs
- Revocable by changing S3 credentials

## Workspace Isolation

### Multi-Tenant Security

**Enforcement points**:
1. **API endpoint**: `current_user.workspace_id` from JWT
2. **Database query**: `WHERE workspace_id = :workspace_id`
3. **S3 key**: `workspaces/{workspace_id}/...`
4. **Audit log**: Records workspace_id for all operations

**Example**:
```python
@router.post("/{session_id}/attachments")
async def upload_session_attachment(
    session_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace_id = current_user.workspace_id  # From JWT (server-side)

    # Verify session belongs to workspace
    session = await get_or_404(db, Session, session_id, workspace_id)

    # Generate workspace-scoped S3 key
    s3_key = generate_secure_filename(workspace_id, session_id, file_type)

    # Store attachment with workspace_id
    attachment = SessionAttachment(
        workspace_id=workspace_id,  # Enforced in database
        session_id=session_id,
        s3_key=s3_key,
    )
```

**Security guarantees**:
- Workspace ID derived from authenticated JWT (not user input)
- Cross-workspace access returns 404 (not 403 - prevents info leak)
- S3 paths include workspace ID for additional isolation
- Audit logs track workspace for compliance

## Threat Model

### Prevented Attacks

| Attack | Prevention Mechanism |
|--------|----------------------|
| **Arbitrary file execution** | MIME validation + content parsing (no executables) |
| **Type confusion (PHP → .jpg)** | Triple validation (extension + MIME + content) |
| **Path traversal (../../etc/passwd)** | Filename sanitization + UUID-based storage keys |
| **Directory traversal (../../../)** | Filename sanitization, no user paths in S3 keys |
| **Oversized files (100 GB)** | File size limits (10 MB per file, 50 MB per session) |
| **Decompression bomb (ZIP bomb)** | Content validation (max pixels for images, max pages for PDF) |
| **Resource exhaustion (1M uploads)** | Rate limiting + storage quotas |
| **MIME sniffing** | Server sends `X-Content-Type-Options: nosniff` |
| **EXIF GPS tracking** | EXIF metadata stripping before storage |
| **Camera fingerprinting** | EXIF metadata stripping (removes make/model) |
| **Cross-workspace access** | JWT-based workspace_id + database scoping |
| **Predictable URLs** | UUID-based storage keys + pre-signed URLs |
| **Malicious filenames** | Filename sanitization (path traversal, special chars) |
| **File collision** | UUID-based filenames (no collisions) |

### Security Test Cases

**Type Confusion**:
```bash
# Test 1: PHP file renamed to .jpg
echo '<?php system($_GET["cmd"]); ?>' > malicious.jpg
→ REJECTED (MIME mismatch: text/x-php)

# Test 2: PDF with .jpg extension
cp document.pdf fake-image.jpg
→ REJECTED (MIME mismatch: application/pdf != image/jpeg)
```

**Path Traversal**:
```bash
# Test 3: Directory traversal in filename
curl -F 'file=@photo.jpg' -F 'filename=../../etc/passwd.jpg'
→ Sanitized to: passwd.jpg
→ Stored as: workspaces/{uuid}/sessions/{uuid}/attachments/{uuid}.jpg
```

**Oversized Files**:
```bash
# Test 4: 15 MB file (exceeds 10 MB limit)
dd if=/dev/zero of=large.jpg bs=1M count=15
→ REJECTED (413 Payload Too Large)
```

**EXIF Privacy**:
```bash
# Test 5: Image with GPS coordinates
exiftool -GPSLatitude=40.7128 -GPSLongitude=-74.0060 photo.jpg
→ STRIPPED (no GPS in stored file)
```

## API Endpoints

### Upload Attachment

```http
POST /api/v1/sessions/{session_id}/attachments
Content-Type: multipart/form-data
Authorization: Bearer {jwt_token}

file: (binary)
```

**Security checks**:
1. Authenticate user (JWT validation)
2. Verify session belongs to workspace
3. Validate file size (< 10 MB)
4. Validate total attachments size (< 50 MB)
5. Triple validation (extension + MIME + content)
6. Strip EXIF metadata
7. Generate UUID-based S3 key
8. Upload to S3 with encryption
9. Save metadata to database
10. Log to audit trail

**Response** (201 Created):
```json
{
  "id": "12ab34cd-56ef-78gh-90ij-1234567890ab",
  "session_id": "d4e5f6...",
  "filename": "wound_photo.jpg",
  "file_type": "image/jpeg",
  "file_size_bytes": 524288,
  "created_at": "2025-10-12T14:30:00Z"
}
```

### Download Attachment

```http
GET /api/v1/sessions/{session_id}/attachments/{attachment_id}/download
Authorization: Bearer {jwt_token}
```

**Security checks**:
1. Authenticate user
2. Verify session belongs to workspace
3. Verify attachment belongs to session
4. Generate pre-signed S3 URL (1 hour expiration)
5. Log download to audit trail

**Response** (200 OK):
```json
{
  "download_url": "https://s3.../file?X-Amz-Signature=...",
  "expires_in_seconds": 3600
}
```

### Delete Attachment

```http
DELETE /api/v1/sessions/{session_id}/attachments/{attachment_id}
Authorization: Bearer {jwt_token}
```

**Security checks**:
1. Authenticate user
2. Verify session belongs to workspace
3. Verify attachment belongs to session
4. Soft delete (set `deleted_at` timestamp)
5. Log deletion to audit trail
6. S3 cleanup via background job

**Response**: 204 No Content

## Audit Logging

### Logged Events

All file operations are automatically logged by `AuditMiddleware`:

**Upload** (CREATE):
```json
{
  "user_id": "user-uuid",
  "workspace_id": "workspace-uuid",
  "action": "CREATE",
  "resource_type": "SessionAttachment",
  "resource_id": "attachment-uuid",
  "metadata": {
    "filename": "wound_photo.jpg",
    "file_type": "image/jpeg",
    "file_size_bytes": 524288,
    "session_id": "session-uuid"
  },
  "ip_address": "192.168.1.100",
  "timestamp": "2025-10-12T14:30:00Z"
}
```

**Download** (READ):
```json
{
  "action": "READ",
  "resource_type": "SessionAttachment",
  "resource_id": "attachment-uuid",
  "metadata": {
    "presigned_url_generated": true,
    "expiration_seconds": 3600
  }
}
```

**Delete** (DELETE):
```json
{
  "action": "DELETE",
  "resource_type": "SessionAttachment",
  "metadata": {
    "soft_delete": true,
    "s3_key": "workspaces/.../attachments/uuid.jpg"
  }
}
```

### Compliance

- **HIPAA**: Audit trail for all PHI access
- **Retention**: 7 years minimum (HIPAA requirement)
- **Immutable**: Audit events cannot be modified or deleted
- **Searchable**: Query by user, workspace, resource, time range

## Error Handling

### Client-Facing Errors

**413 Payload Too Large**:
```json
{
  "detail": "File size 15728640 bytes exceeds maximum of 10485760 bytes (10 MB)"
}
```

**415 Unsupported Media Type**:
```json
{
  "detail": "File extension .php not allowed. Allowed types: .jpg, .jpeg, .png, .webp, .pdf"
}
```

**422 Unprocessable Entity**:
```json
{
  "detail": "File extension .jpg does not match detected MIME type application/pdf"
}
```

**404 Not Found**:
```json
{
  "detail": "Resource not found"
}
```

### Security Considerations

- **Generic errors**: Don't reveal whether resource exists in other workspace
- **No stack traces**: Don't expose internal implementation details
- **Rate limiting**: Prevent brute-force upload attacks
- **Logging**: Log all rejection reasons server-side (not client-facing)

## Configuration

### Environment Variables

```bash
# S3/MinIO Configuration
S3_ENDPOINT_URL=http://localhost:9000  # MinIO dev
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin123
S3_BUCKET_NAME=pazpaz-attachments
S3_REGION=us-east-1

# File Upload Limits
MAX_FILE_SIZE_MB=10
MAX_TOTAL_ATTACHMENTS_MB=50
```

### Production Settings

```bash
# AWS S3 (Production)
S3_ENDPOINT_URL=https://s3.us-east-1.amazonaws.com
S3_ACCESS_KEY=<aws-access-key>
S3_SECRET_KEY=<aws-secret-key>
S3_BUCKET_NAME=pazpaz-prod-attachments
S3_REGION=us-east-1

# Enable server-side encryption
S3_SERVER_SIDE_ENCRYPTION=AES256

# TLS/SSL enforced (use_ssl=True)
```

## Testing

### Unit Tests

- `tests/test_file_validation.py` - Validation logic (100+ test cases)
- `tests/test_file_sanitization.py` - EXIF stripping, filename sanitization
- `tests/test_file_upload.py` - S3 upload/download (mocked)

### Security Tests

Run security-focused tests:
```bash
# Type confusion attacks
pytest tests/test_file_validation.py::TestSecurityValidation -v

# EXIF privacy protection
pytest tests/test_file_sanitization.py::TestPrivacyProtection -v

# Path traversal prevention
pytest tests/test_file_sanitization.py::TestFilenameSanitization -v
```

### Manual Testing

```bash
# Test 1: Upload valid JPEG
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/attachments \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg"

# Test 2: Upload PHP file (should be rejected)
echo '<?php echo "test"; ?>' > malicious.php
curl -X POST ... -F "file=@malicious.php;filename=image.jpg"
# Expected: 422 Unprocessable Entity (MIME mismatch)

# Test 3: Upload oversized file (should be rejected)
dd if=/dev/zero of=large.jpg bs=1M count=15
curl -X POST ... -F "file=@large.jpg"
# Expected: 413 Payload Too Large
```

## Maintenance

### Monitoring

**Metrics to track**:
- Upload success/failure rate
- Average file size
- Total storage usage per workspace
- Validation rejection reasons
- S3 upload latency

**Alerts**:
- High validation failure rate (>5%) → Investigate malicious uploads
- S3 upload latency >1s → Check S3 connectivity
- Storage usage >80% quota → Notify workspace owner

### Cleanup

**Soft-deleted attachments**:
- Marked with `deleted_at` timestamp
- Retained for 30 days (grace period for recovery)
- Background job purges after 30 days

**S3 lifecycle policy**:
```xml
<LifecycleConfiguration>
  <Rule>
    <Id>Delete expired attachments</Id>
    <Status>Enabled</Status>
    <Expiration>
      <Days>30</Days>
    </Expiration>
  </Rule>
</LifecycleConfiguration>
```

## Future Enhancements

### V2 Features

1. **Virus scanning**: Integrate ClamAV for malware detection
2. **Image optimization**: Auto-resize large images to reduce storage
3. **PDF metadata stripping**: Remove PDF metadata (author, keywords) - **Already implemented!** See [PDF Metadata Sanitization](/docs/backend/PDF_METADATA_SANITIZATION_IMPLEMENTATION.md)
4. **OCR integration**: Extract text from uploaded images/PDFs
5. **Thumbnails**: Generate thumbnails for image attachments
6. **Video support**: Add MP4 video attachments for treatment demos
7. **Client-side validation**: Pre-flight checks before upload
8. **Progress tracking**: WebSocket-based upload progress

### Security Improvements

1. **Content Security Policy**: Stricter CSP for uploaded content
2. **Sandboxed preview**: Render files in isolated iframe
3. **Watermarking**: Add visible watermark to downloaded images
4. **Download tracking**: Track who downloads which files
5. **Expiring attachments**: Auto-delete after retention period
6. **Encrypted metadata**: Encrypt S3 keys in database

## References

### Standards

- **OWASP File Upload Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- **HIPAA Security Rule**: 45 CFR §164.312(a)(2)(iv) - Encryption
- **NIST SP 800-53**: SC-28 Protection of Information at Rest

### Libraries

- **python-magic**: MIME type detection (libmagic wrapper)
- **Pillow (PIL)**: Image validation and EXIF stripping
- **pypdf**: PDF validation and parsing
- **boto3**: AWS S3 client

### Related Documentation

- [Encryption Usage Guide](/docs/security/encryption/ENCRYPTION_USAGE_GUIDE.md) - PHI encryption
- [S3 Credential Management](S3_CREDENTIAL_MANAGEMENT.md) - Storage security
- [Storage Configuration](STORAGE_CONFIGURATION.md) - S3/MinIO setup
- [Security Implementation Plan](/docs/SECURITY_FIRST_IMPLEMENTATION_PLAN.md) - Master plan
- [Security Audit Reports](/docs/reports/security/) - Security audits

---

**Document Version**: 1.1
**Last Updated**: 2025-10-20
**Status**: Validated against codebase
**Review**: Completed 2025-10-20
