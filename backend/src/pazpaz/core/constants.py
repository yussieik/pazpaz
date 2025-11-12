"""Application-wide constants and configuration values."""

from datetime import timedelta

# ============================================================================
# SOFT DELETE CONFIGURATION
# ============================================================================

# Grace period before permanent deletion (30 days)
SESSION_SOFT_DELETE_GRACE_PERIOD_DAYS = 30
SESSION_SOFT_DELETE_GRACE_PERIOD = timedelta(days=SESSION_SOFT_DELETE_GRACE_PERIOD_DAYS)

# Maximum length for deletion reason text
DELETION_REASON_MAX_LENGTH = 500

# ============================================================================
# SESSION / SOAP NOTES CONFIGURATION
# ============================================================================

# Maximum length for encrypted SOAP fields (in plaintext)
SOAP_FIELD_MAX_LENGTH = 5000

# ============================================================================
# ENCRYPTION CONFIGURATION
# ============================================================================

# AES-256 key size (32 bytes = 256 bits)
ENCRYPTION_KEY_SIZE = 32

# AES-GCM nonce size (12 bytes = 96 bits, recommended for GCM)
NONCE_SIZE = 12

# AES-GCM authentication tag size (16 bytes = 128 bits)
TAG_SIZE = 16

# ============================================================================
# AUDIT LOGGING
# ============================================================================

# Standard audit metadata keys
AUDIT_METADATA_SOFT_DELETE = "soft_delete"
AUDIT_METADATA_AMENDMENT = "amendment"
AUDIT_METADATA_DELETED_REASON = "deleted_reason"
AUDIT_METADATA_PERMANENT_DELETE_AFTER = "permanent_delete_after"

# ============================================================================
# PHI/PII FIELD NAMES (HIPAA COMPLIANCE)
# ============================================================================

# Fields that contain Protected Health Information (PHI) or Personally
# Identifiable Information (PII) that must be redacted from logs, errors,
# and external monitoring systems (Sentry, etc.)
PHI_FIELDS = {
    # SOAP Notes (Session content)
    "subjective",
    "objective",
    "assessment",
    "plan",
    "medical_history",
    "notes",
    "treatment_notes",
    # Client PII
    "first_name",
    "last_name",
    "email",
    "phone",
    "address",
    "date_of_birth",
    "ssn",
    "insurance_id",
}
