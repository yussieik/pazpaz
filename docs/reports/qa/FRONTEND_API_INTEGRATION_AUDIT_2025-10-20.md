# Frontend API Integration & Error Handling Audit

**Date**: 2025-10-20
**Auditor**: fullstack-frontend-specialist (Claude Code)
**Scope**: Vue 3 frontend integration with FastAPI backend
**Backend Changes Audited**: Commits `985f5a8`, `ecb400f` (security enhancements)

---

## Executive Summary

The frontend has a **well-architected API client** using Axios with proper credentials and CSRF handling. However, **2 CRITICAL ISSUES** were identified:

1. **BREAKING CHANGE - TOTP Disable**: The 2FA disable functionality **IS NOT IMPLEMENTED** in frontend, so there's no breaking bug to fix yet. Settings page is a placeholder.
2. **MISSING - Request ID Handling**: Frontend error handlers **DO NOT extract or display `request_id`** from error responses, making debugging difficult.
3. **MISSING - Encryption Metadata**: Frontend file upload types **DO NOT include `encryption_metadata`** field from backend responses.

**Overall Security Score**: 7/10 (Good architecture, missing observability features)

---

## 1. API Client Integration

### Architecture: Axios-based Custom Client

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/client.ts`

**Implementation Quality**: EXCELLENT

**Key Features**:
- OpenAPI-generated TypeScript types (`schema.ts`)
- Axios instance with base URL `/api/v1`
- `withCredentials: true` (HttpOnly cookies sent automatically)
- CSRF token extraction from cookies and automatic header injection
- Request/response interceptors for workspace ID and error handling
- 10-second timeout on all requests

### CSRF Handling: IMPLEMENTED

**Status**: SECURE

```typescript
// Request interceptor adds CSRF token for state-changing requests
if (['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
  const csrfToken = getCsrfToken()
  if (csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken
  }
}
```

**Security Assessment**:
- CSRF tokens correctly extracted from cookies via regex
- Only added to mutating requests (POST, PUT, PATCH, DELETE)
- Warning logged if CSRF token missing (good observability)

### Authentication: Cookie-based (JWT in HttpOnly cookies)

**Status**: SECURE

- JWT tokens stored in HttpOnly cookies (backend manages this)
- Cookies sent automatically via `withCredentials: true`
- Frontend cannot access tokens via JavaScript (prevents XSS token theft)
- Workspace ID hardcoded for development (`X-Workspace-ID: 00000000-0000-0000-0000-000000000001`)

**TODO Comment Found**:
```typescript
// TODO: Get workspace ID from auth store/context
// For now, use test workspace ID
config.headers['X-Workspace-ID'] = '00000000-0000-0000-0000-000000000001'
```

**Recommendation**: Implement workspace ID from auth context once backend authentication is fully connected.

### Proxy Configuration: CORRECT

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/vite.config.ts`

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://localhost:8000',
    ws: true,
  },
}
```

**Assessment**: Correct proxy setup for development. Production will use same-origin reverse proxy (documented in architecture).

---

## 2. BREAKING CHANGE: TOTP Disable Flow

### Status: NOT APPLICABLE (Feature Not Implemented)

**Frontend State**: Settings page is a **PLACEHOLDER** for M3 milestone.

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/SettingsView.vue`

**Code**:
```vue
<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mx-auto max-w-2xl text-center">
      <h1 class="mb-3 text-2xl font-semibold text-slate-900">Settings</h1>
      <p class="text-gray-600">
        Settings and preferences will be available in M3. This page will include
        account, workspace, and service configuration.
      </p>
      <div class="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
        <strong>Planned sections:</strong>
        <ul class="mt-2 space-y-1 text-left">
          <li>• Account settings (profile, password, 2FA)</li>
          <li>• Workspace configuration</li>
          <li>• Services and locations management</li>
          <li>• Preferences (calendar defaults, notifications)</li>
        </ul>
      </div>
    </div>
  </div>
</template>
```

**Search Results**: No implementation of:
- TOTP enable/disable UI
- DELETE `/auth/totp` API calls
- 2FA settings components

**Conclusion**: The backend breaking change **DOES NOT AFFECT** the frontend yet because 2FA UI is not implemented. When implementing 2FA settings (M3), developers MUST follow the migration guide in `/docs/backend/api/BREAKING_CHANGES.md`.

**Action Required**: Add task to M3 milestone to implement TOTP disable with `totp_code` in request body.

---

## 3. File Upload Integration

### Implementation: GOOD with MISSING METADATA FIELD

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useFileUpload.ts`

### Upload Flow

**Status**: ROBUST

```typescript
async function uploadFile(
  sessionId: string,
  file: File,
  progressRef?: Ref<UploadProgress>,
  maxRetries = 3
): Promise<AttachmentResponse>
```

**Features**:
- Client-side validation (file type, size)
- FormData multipart upload
- Progress tracking with `onUploadProgress`
- Exponential backoff retry (3 attempts)
- 30-second timeout per upload
- Comprehensive error handling with user-friendly messages

### Error Handling: EXCELLENT

**HTTP Status Code Coverage**:
- 401: Session expired
- 403: Permission denied
- 404: Session not found
- 413: File too large
- 415: Unsupported file type
- 422: Validation failed
- 429: Rate limit exceeded
- 500: Server error
- Network errors (timeout, connection lost)

**User-Friendly Messages**:
```typescript
case 413:
  return 'File too large (max 10 MB). Consider compressing the file.'
case 415:
  return 'Unsupported file type. Accepted: JPEG, PNG, WebP, PDF.'
case 429:
  return 'Upload rate limit exceeded. Please wait 60 seconds and try again.'
```

**Assessment**: Excellent error messaging with actionable advice for users.

### ISSUE: Missing Encryption Metadata Field

**Backend Changes** (Commit `985f5a8`):
- Backend now returns `encryption_metadata` in upload responses
- Includes: `algorithm`, `key_id`, `verified_at`, `bucket_encryption`

**Frontend Type Definition** (`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/types/attachments.ts`):

```typescript
export interface AttachmentResponse {
  id: string
  session_id: string | null
  client_id: string
  file_name: string
  file_type: string
  file_size_bytes: number
  created_at: string
  session_date: string | null
  is_session_file: boolean
  // MISSING: encryption_metadata field
}
```

**Impact**: LOW (metadata not displayed in UI, but should be available for debugging)

**Recommendation**: Update TypeScript types to include optional `encryption_metadata` field:

```typescript
export interface AttachmentResponse {
  id: string
  session_id: string | null
  client_id: string
  file_name: string
  file_type: string
  file_size_bytes: number
  created_at: string
  session_date: string | null
  is_session_file: boolean
  encryption_metadata?: {
    algorithm: string
    key_id: string
    verified_at: string
    bucket_encryption: string
  }
}
```

### Encryption Verification Error Handling

**Backend Behavior**: Returns HTTP 500 if S3 encryption verification fails.

**Frontend Handling**: Generic "Upload failed due to a server error" message.

**Assessment**: ADEQUATE. HTTP 500 is correctly categorized as server error. Frontend doesn't need to know specific encryption details.

---

## 4. Error Handling & Request ID

### Current Implementation: INCOMPLETE

**Response Interceptor** (`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/client.ts`):

```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          console.error('Unauthorized - authentication required')
          break
        case 403:
          console.error('Forbidden - insufficient permissions')
          break
        // ... more status codes
      }
    }
    return Promise.reject(error)
  }
)
```

**ISSUE**: `request_id` is **NOT EXTRACTED** from error responses.

### Backend Error Response Format

**All error responses now include** (Commit `985f5a8`):
- `request_id` in response body
- `X-Request-ID` header

**Example Error Response**:
```json
{
  "detail": "Validation error",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**HTTP Headers**:
```
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

### CRITICAL ISSUE: Missing Request ID Extraction

**Status**: NOT IMPLEMENTED

**Impact**: HIGH (debugging production issues is difficult without request ID)

**Current Behavior**:
- Errors logged to console with status code only
- No `request_id` displayed to users or logged
- Support team cannot correlate frontend errors with backend logs

**Recommended Fix**:

```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Extract request_id from response body or header
    const requestId =
      error.response?.data?.request_id ||
      error.response?.headers?.['x-request-id'] ||
      'unknown'

    if (error.response) {
      const status = error.response.status
      console.error(
        `API Error [${status}] - Request ID: ${requestId}`,
        error.response.data
      )

      // Attach request_id to error object for UI display
      error.requestId = requestId

      switch (status) {
        case 401:
          // TODO: Redirect to login or refresh token
          break
        case 403:
          // TODO: Show permission denied message with request_id
          break
        // ... more status codes
      }
    } else if (error.request) {
      console.error('Network error - no response received')
    }

    return Promise.reject(error)
  }
)
```

**UI Display Recommendation**:

```typescript
// In error toast or modal
function showError(error: AxiosError) {
  const requestId = error.requestId || 'N/A'
  const message = getUserFriendlyMessage(error)

  toast.error(`${message}\n\nReference: ${requestId}`)
}
```

### File Upload Error Handling: PARTIALLY COMPLETE

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useFileUpload.ts`

**Current Implementation**:
```typescript
function getUploadErrorMessage(error: AxiosError<{ detail?: string }>): string {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  // ... status code handling ...
}
```

**MISSING**: `request_id` extraction from upload errors.

**Recommended Fix**:
```typescript
function getUploadErrorMessage(
  error: AxiosError<{ detail?: string; request_id?: string }>
): { message: string; requestId?: string } {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  const requestId =
    error.response?.data?.request_id ||
    error.response?.headers?.['x-request-id']

  let message = 'Upload failed. Please try again.'

  switch (status) {
    case 413:
      message = 'File too large (max 10 MB). Consider compressing the file.'
      break
    // ... more cases ...
  }

  return { message, requestId }
}
```

---

## 5. Security Assessment

### JWT Storage: SECURE

**Implementation**: HttpOnly cookies (backend-managed)

**Score**: 10/10

**Details**:
- JWT stored in HttpOnly cookie (JavaScript cannot access)
- Cookies sent automatically via `withCredentials: true`
- CSRF protection via `X-CSRF-Token` header
- Prevents XSS token theft

**No Issues Found**.

### XSS Prevention: EXCELLENT

**Score**: 10/10

**Assessment**:
- Vue 3 templates auto-escape by default
- No `v-html` directive usage found in codebase
- SOAP notes rendered in `<textarea>` with `v-model` (auto-escaped)
- Client names, emails rendered via template syntax `{{ }}` (auto-escaped)

**Search Results**:
```
Grep: v-html
Result: No files found
```

**SOAP Field Rendering** (`SessionEditor.vue`):
```vue
<textarea
  v-model="formData.subjective"
  placeholder="Client's subjective experience..."
/>
```

**Conclusion**: Vue's default template escaping prevents XSS attacks. No raw HTML injection found.

### Input Validation: GOOD

**Client-side Validation**:
- File uploads: type and size validated before submission
- Form inputs: basic HTML5 validation (required, maxlength)
- SOAP fields: 5000 character limit enforced client-side

**File Upload Validation** (`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/types/attachments.ts`):
```typescript
export function validateFile(file: File): string | null {
  if (!ALLOWED_FILE_TYPES.includes(file.type as AllowedType)) {
    return 'Unsupported file type. Please upload JPEG, PNG, WebP, or PDF.'
  }
  if (file.size > MAX_FILE_SIZE) {
    return `File too large (max ${formatFileSize(MAX_FILE_SIZE)})`
  }
  return null
}
```

**Assessment**: Good client-side validation. Backend validation is primary defense (follows security best practices).

### HTTPS & Secure Communication

**Development**: HTTP (localhost only)
**Production**: HTTPS (reverse proxy configuration documented)

**Vite Proxy Configuration**:
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

**Production Architecture** (documented in `/docs/architecture/`):
- Reverse proxy (nginx) terminates TLS
- `/api` and `/ws` proxied to backend
- Single-origin deployment (no CORS needed)

**Score**: 10/10 (architecture is correct)

**Note**: No environment files (`.env`) found in frontend. API base URL is relative (`/api/v1`) which is correct for same-origin deployment.

---

## 6. Authentication Flow Assessment

### Current State: PARTIAL IMPLEMENTATION

**Implemented**:
- Magic link verification endpoint (`/auth/verify`)
- Logout with encrypted backup cleanup
- Auth store with user state management

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/stores/auth.ts`

**Logout Implementation**: EXCELLENT

```typescript
async function logout() {
  try {
    // 1. Call backend logout endpoint (blacklist JWT)
    await apiClient.post('/auth/logout')
  } catch (error) {
    console.error('Logout API call failed:', error)
    // Continue with client-side cleanup even if server logout fails
  }

  // 2. Clear all encrypted session backups from localStorage
  clearAllBackups()

  // 3. Clear auth state
  user.value = null
  isAuthenticated.value = false

  // 4. Redirect to login
  window.location.href = '/login'
}
```

**Security Assessment**:
- Proper cleanup of encrypted backups (HIPAA compliance)
- Graceful degradation if backend logout fails
- Hard redirect to login (clears SPA state)

**MISSING**:
- 401 response handler (should redirect to login)
- Token refresh mechanism (if using refresh tokens)
- 2FA/TOTP UI (planned for M3)

**Recommendation**: Implement global 401 handler in response interceptor:

```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth state
      const authStore = useAuthStore()
      authStore.clearUser()

      // Redirect to login
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

---

## 7. Recommendations (Priority Order)

### CRITICAL (Implement Immediately)

#### 1. Add Request ID Extraction and Display

**Impact**: HIGH - Essential for debugging production issues

**Files to Modify**:
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/client.ts` (response interceptor)
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useFileUpload.ts` (error handler)

**Implementation**:
```typescript
// In response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestId =
      error.response?.data?.request_id ||
      error.response?.headers?.['x-request-id'] ||
      null

    // Attach to error for UI display
    if (requestId) {
      error.requestId = requestId
      console.error(`Request ID: ${requestId}`, error)
    }

    return Promise.reject(error)
  }
)
```

**UI Display**: Show request ID in error toasts/modals for user support.

**Estimated Effort**: 2 hours

---

#### 2. Implement Global 401 Handler

**Impact**: HIGH - Prevents stale sessions from causing errors

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/client.ts`

**Implementation**:
```typescript
import { useAuthStore } from '@/stores/auth'

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestId = extractRequestId(error)

    if (error.response?.status === 401) {
      // Get auth store
      const authStore = useAuthStore()

      // Clear auth state and redirect
      authStore.clearUser()
      window.location.href = '/login'
    }

    return Promise.reject(error)
  }
)
```

**Estimated Effort**: 1 hour

---

### HIGH (Implement in M3 Milestone)

#### 3. Implement TOTP Disable with Verification

**Impact**: HIGH - Required for 2FA settings (M3 feature)

**Reference**: `/docs/backend/api/BREAKING_CHANGES.md`

**Implementation Checklist**:
- [ ] Create 2FA settings component
- [ ] Add UI prompt for TOTP code input
- [ ] Send `totp_code` in DELETE `/auth/totp` request body
- [ ] Handle 401 errors (invalid TOTP)
- [ ] Test with both TOTP codes and backup codes

**Example Component**:
```vue
<script setup lang="ts">
import { ref } from 'vue'
import apiClient from '@/api/client'

const totpCode = ref('')
const loading = ref(false)
const error = ref('')

async function disable2FA() {
  error.value = ''
  loading.value = true

  try {
    await apiClient.delete('/auth/totp', {
      data: { totp_code: totpCode.value }
    })
    // Show success message
  } catch (err) {
    if (err.response?.status === 401) {
      error.value = 'Invalid TOTP code. Please try again.'
    } else {
      error.value = `An error occurred. Reference: ${err.requestId || 'N/A'}`
    }
  } finally {
    loading.value = false
  }
}
</script>
```

**Estimated Effort**: 4 hours (including tests)

---

#### 4. Update Attachment Types with Encryption Metadata

**Impact**: MEDIUM - Improves type safety and future debugging

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/types/attachments.ts`

**Implementation**:
```typescript
export interface AttachmentResponse {
  id: string
  session_id: string | null
  client_id: string
  file_name: string
  file_type: string
  file_size_bytes: number
  created_at: string
  session_date: string | null
  is_session_file: boolean
  encryption_metadata?: {
    algorithm: string
    key_id: string
    verified_at: string
    bucket_encryption: string
  }
}
```

**Estimated Effort**: 15 minutes

---

### MEDIUM (Nice to Have)

#### 5. Regenerate OpenAPI TypeScript Client

**Impact**: MEDIUM - Ensures types match backend schema

**Command**:
```bash
cd frontend
npm run generate-api
```

**File**: `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/schema.ts`

**Note**: Current schema does not include `/auth/totp` endpoint or `AttachmentResponse` with encryption metadata. Regenerating from latest backend will update types.

**Estimated Effort**: 5 minutes

---

#### 6. Implement Dynamic Workspace ID from Auth Context

**Impact**: MEDIUM - Replaces hardcoded test workspace ID

**Current**:
```typescript
// TODO: Get workspace ID from auth store/context
config.headers['X-Workspace-ID'] = '00000000-0000-0000-0000-000000000001'
```

**Recommended**:
```typescript
import { useAuthStore } from '@/stores/auth'

apiClient.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.user?.workspace_id) {
    config.headers['X-Workspace-ID'] = authStore.user.workspace_id
  }
  // ... rest of interceptor
})
```

**Estimated Effort**: 30 minutes

---

## 8. Testing Recommendations

### Add Integration Tests

**Missing Test Coverage**:
- Request ID extraction in error scenarios
- 401 redirect to login flow
- CSRF token injection on mutating requests
- File upload error handling with `request_id`

**Test Framework**: Vitest + Mock Service Worker (MSW) already configured

**Example Test**:
```typescript
import { describe, it, expect, vi } from 'vitest'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import apiClient from '@/api/client'

describe('API Client - Request ID', () => {
  const server = setupServer()

  it('should extract request_id from error response body', async () => {
    server.use(
      http.get('/api/v1/test', () => {
        return HttpResponse.json(
          { detail: 'Test error', request_id: 'test-123' },
          { status: 500 }
        )
      })
    )

    try {
      await apiClient.get('/test')
    } catch (error) {
      expect(error.requestId).toBe('test-123')
    }
  })
})
```

---

## 9. Files Reviewed

### Configuration
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/vite.config.ts`
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/package.json`
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/tsconfig.json`

### API Client
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/client.ts` (PRIMARY)
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/api/schema.ts` (OpenAPI types)

### Composables
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useFileUpload.ts`

### Stores
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/stores/auth.ts`

### Types
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/types/attachments.ts`

### Components
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/SettingsView.vue`
- `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/SessionEditor.vue`

### Backend Documentation
- `/Users/yussieik/Desktop/projects/pazpaz/docs/backend/api/BREAKING_CHANGES.md`
- `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/api/auth.py` (lines 696-739)
- `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/schemas/auth.py` (lines 142-149)
- `/Users/yussieik/Desktop/projects/pazpaz/backend/src/pazpaz/main.py` (error handlers)

---

## 10. Summary of Findings

### What's Working Well

- Axios-based API client with proper structure
- CSRF token handling implemented correctly
- HttpOnly cookie-based authentication (secure)
- File upload with comprehensive error messages
- XSS prevention via Vue's default escaping
- No `v-html` usage (prevents XSS)
- Client-side input validation
- Logout with HIPAA-compliant backup cleanup
- Graceful error degradation in file uploads

### Critical Issues

1. **Request ID not extracted or displayed** - Blocks production debugging
2. **No global 401 handler** - Users see errors instead of login redirect

### High-Priority Issues

3. **TOTP disable breaking change** - Not applicable yet (Settings is placeholder)
4. **Encryption metadata missing from types** - Minor type safety issue

### Medium-Priority Issues

5. **Hardcoded workspace ID** - Replace with auth context
6. **OpenAPI types may be stale** - Regenerate from backend

---

## 11. Compliance Assessment

### HIPAA Compliance: GOOD

- PHI stored in encrypted session backups (cleared on logout)
- No PHI logged to console in production
- HttpOnly cookies prevent XSS token theft
- File uploads validated client-side and server-side
- Encryption metadata tracked (backend)

**Gap**: Request ID should not include PHI (currently UUID-based, so safe).

### Security Best Practices: GOOD

- Defense in depth: client-side + server-side validation
- CSRF protection on mutating requests
- HttpOnly cookies for authentication
- No XSS vulnerabilities found
- Proper error handling with fallback messages

---

## Conclusion

The frontend has a **solid foundation** with good security practices. The critical gaps are **observability-related** (missing `request_id` extraction) rather than security vulnerabilities. Implementing the recommendations will improve debugging, error tracking, and prepare for M3 features (2FA settings).

**No immediate security vulnerabilities found** in current production code.

**Action Items for Next Sprint**:
1. Implement request ID extraction (2 hours)
2. Add global 401 handler (1 hour)
3. Update attachment types with encryption metadata (15 min)
4. Plan M3 implementation of TOTP settings with breaking change fix (4 hours)

---

**Audit Completed**: 2025-10-20
**Next Review**: After M3 milestone (2FA implementation)
