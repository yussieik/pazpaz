# PazPaz Backend

FastAPI-based backend for PazPaz practice management application.

## Setup

1. Install Python 3.13.5:
```bash
uv python install 3.13.5
uv python pin 3.13.5
```

2. Install dependencies:
```bash
uv sync
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Development

Run the development server:
```bash
uv run fastapi dev src/pazpaz/main.py
```

Run tests:
```bash
uv run pytest
```

Lint and format:
```bash
uv run ruff check --fix
uv run ruff format
```

## Security

### Critical Security Configurations

Before deploying to any environment, ensure you have reviewed and configured:

#### S3/MinIO Credentials
**CRITICAL:** Never use default MinIO credentials (`minioadmin`/`minioadmin123`) in any exposed environment.

Review the comprehensive [S3 Credential Management Guide](docs/storage/S3_CREDENTIAL_MANAGEMENT.md) for:
- Secure credential generation
- Environment-specific configuration (dev/staging/production)
- Credential rotation procedures (90-day schedule)
- Emergency response for compromised credentials
- Integration with AWS Secrets Manager and IAM roles

**Quick Check:**
```bash
# Verify you're not using default credentials in production
grep -E "minioadmin|minioadmin123" .env
# Should return NO results if configured securely
```

#### Encryption
All PHI (Protected Health Information) must be encrypted at rest and in transit:
- Database fields: See [Encryption Architecture](../docs/security/encryption/ENCRYPTION_ARCHITECTURE.md)
- S3/MinIO files: Server-side encryption (SSE-S3/AES-256) enabled automatically
- Master encryption key: Stored in AWS Secrets Manager (production) or `.env` (development only)

#### Additional Security Resources
- [File Upload Security](../docs/backend/storage/FILE_UPLOAD_SECURITY.md)
- [Storage Configuration](../docs/backend/storage/STORAGE_CONFIGURATION.md)
- [S3 Credential Management](../docs/backend/storage/S3_CREDENTIAL_MANAGEMENT.md)
- [Security Audit Reports](../docs/reports/security/)

## Project Structure

```
backend/
├── src/pazpaz/
│   ├── api/          # API route handlers
│   ├── core/         # Core configuration
│   ├── db/           # Database setup
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic
│   └── main.py       # FastAPI app entry point
└── tests/            # Test suite
```