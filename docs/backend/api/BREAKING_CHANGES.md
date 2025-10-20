# API Breaking Changes

This document tracks breaking changes to the PazPaz API to help frontend developers migrate their code.

## Format

Each breaking change includes:
- **Date**: When the change was introduced
- **Endpoint**: The affected API endpoint
- **Change Type**: Breaking change category (required field, response format, behavior change, etc.)
- **Migration**: Step-by-step migration guide with code examples

---

## DELETE /api/v1/auth/totp - TOTP Disable Requires Verification (2025-10-20)

**Change Type**: Required request body added

**Severity**: MEDIUM (Security enhancement)

**Reason**: Prevents session hijacking attacks from disabling 2FA protection.

### What Changed

The DELETE `/api/v1/auth/totp` endpoint now requires TOTP code verification in the request body. Previously, any authenticated user could disable 2FA with just their JWT session.

### Before (Vulnerable)

```http
DELETE /api/v1/auth/totp HTTP/1.1
Authorization: Bearer <jwt>
```

```typescript
// Old implementation (DO NOT USE)
async function disable2FA() {
  const response = await fetch('/api/v1/auth/totp', {
    method: 'DELETE',
    credentials: 'include',
  });
  return response.json();
}
```

### After (Secure)

```http
DELETE /api/v1/auth/totp HTTP/1.1
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "totp_code": "123456"
}
```

```typescript
// New implementation (REQUIRED)
async function disable2FA(totpCode: string) {
  const response = await fetch('/api/v1/auth/totp', {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      totp_code: totpCode,
    }),
  });

  if (response.status === 401) {
    throw new Error('Invalid TOTP code. Please try again.');
  }

  return response.json();
}
```

### Migration Steps

1. **Update API client** to include `totp_code` in request body
2. **Add UI prompt** to ask user for TOTP code before disabling 2FA
3. **Handle 401 errors** when user enters invalid TOTP code
4. **Test with both TOTP codes and backup codes** (both are accepted)

### Request Schema

```typescript
interface TOTPDisableRequest {
  totp_code: string; // 6-digit TOTP code OR 8-character backup code
}
```

**Field validation:**
- `totp_code`: Required, 6-8 characters
- Accepts 6-digit TOTP codes (e.g., "123456")
- Accepts 8-character backup codes (e.g., "A1B2C3D4")

### Response Codes

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | 2FA disabled successfully | Show success message |
| 401 | Invalid TOTP code | Prompt user to retry |
| 422 | Missing or invalid request body | Fix request format |
| 400 | User doesn't have 2FA enabled | Handle edge case |

### Error Response Examples

**Invalid TOTP code (401):**
```json
{
  "detail": "Invalid TOTP code. Verification required to disable 2FA."
}
```

**Missing totp_code field (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "totp_code"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Security Implications

**Attack Scenario Prevented:**
1. Attacker steals valid JWT cookie (XSS, MITM, physical access)
2. User has 2FA enabled for protection
3. ~~Attacker calls DELETE `/auth/totp` with stolen JWT~~
4. ~~2FA is disabled without TOTP verification~~
5. ~~Attacker can now authenticate with magic link alone~~

**Now (with fix):**
- Attacker cannot disable 2FA without access to the TOTP device
- 2FA protection remains intact even with compromised session

### Example Frontend Component (Vue 3)

```vue
<script setup lang="ts">
import { ref } from 'vue';

const totpCode = ref('');
const error = ref('');
const loading = ref(false);

async function handleDisable2FA() {
  error.value = '';
  loading.value = true;

  try {
    const response = await fetch('/api/v1/auth/totp', {
      method: 'DELETE',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        totp_code: totpCode.value,
      }),
    });

    if (response.status === 401) {
      error.value = 'Invalid TOTP code. Please check and try again.';
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to disable 2FA');
    }

    const data = await response.json();
    console.log('2FA disabled:', data.message);
    // Redirect or show success message
  } catch (err) {
    error.value = 'An error occurred. Please try again.';
    console.error('Disable 2FA error:', err);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div>
    <h2>Disable Two-Factor Authentication</h2>
    <p>Enter your current TOTP code or backup code to disable 2FA.</p>

    <form @submit.prevent="handleDisable2FA">
      <input
        v-model="totpCode"
        type="text"
        placeholder="Enter 6-digit code"
        maxlength="8"
        required
        :disabled="loading"
      />
      <button type="submit" :disabled="loading">
        {{ loading ? 'Disabling...' : 'Disable 2FA' }}
      </button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>
```

### Testing Checklist

- [ ] User can disable 2FA with valid TOTP code
- [ ] User can disable 2FA with valid backup code
- [ ] Invalid TOTP code returns 401 error
- [ ] Missing `totp_code` field returns 422 error
- [ ] Error message is shown to user
- [ ] Success message is shown after disable
- [ ] User is redirected appropriately after disable

---

## Future Breaking Changes

*This section will be updated as breaking changes are introduced.*
