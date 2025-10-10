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
# AUDIT LOGGING
# ============================================================================

# Standard audit metadata keys
AUDIT_METADATA_SOFT_DELETE = "soft_delete"
AUDIT_METADATA_AMENDMENT = "amendment"
AUDIT_METADATA_DELETED_REASON = "deleted_reason"
AUDIT_METADATA_PERMANENT_DELETE_AFTER = "permanent_delete_after"
