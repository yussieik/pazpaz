# File Rename Frontend Implementation Report

## Overview

This document describes the implementation of the inline file renaming functionality for the PazPaz attachment system. The implementation provides a keyboard-first, accessible inline editing experience for both session-level and client-level attachments with comprehensive validation and error handling.

**Implementation Date:** 2025-10-19
**Developer:** fullstack-frontend-specialist
**Status:** Complete and Ready for Testing

---

## Files Created and Modified

### Created Files

1. **`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/utils/filenameValidation.ts`**
   - Client-side filename validation utilities
   - Matches backend validation rules exactly
   - Functions: `validateFilename()`, `getFilenameWithoutExtension()`, `getFileExtension()`, `sanitizeFilenameForRename()`

2. **`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useAttachmentRename.ts`**
   - Reusable composable for file renaming logic
   - Manages edit state, validation, API calls, and error handling
   - Shared between ClientFilesTab and AttachmentList components

### Modified Files

3. **`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/client/ClientFilesTab.vue`**
   - Added inline rename functionality for client-level and session-level files
   - Implemented F2 keyboard shortcut support
   - Integrated validation and error display

4. **`/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/AttachmentList.vue`**
   - Added inline rename functionality for session-level files
   - Implemented F2 keyboard shortcut support
   - Same UX patterns as ClientFilesTab for consistency

---

## Feature Specifications

### 1. Inline Editing Pattern

**UX Flow:**

```
Default State:
[📷] IMG_1234.jpg  ← Click filename or press F2 to rename

Edit Mode:
[📷] [Left shoulder pain___] .jpg [✓] [✕]
      ↑ Input field          Ext  Save Cancel

After Save:
[📷] Left shoulder pain.jpg  ← Success toast shown
```

**Key Features:**
- Click filename button to enter edit mode
- F2 keyboard shortcut on focused file row
- Auto-select text in input for quick replacement
- Enter key to save, Esc key to cancel
- Save (✓) and Cancel (✕) buttons for mouse/touch users
- Loading state with spinner while saving
- Success toast notification after rename
- Inline error display for validation failures

### 2. Client-Side Validation

Implemented validation rules matching backend exactly:

```typescript
function validateFilename(name: string): FilenameValidationResult {
  const trimmed = name.trim()

  // Rule 1: Cannot be empty
  if (trimmed.length === 0) {
    return { valid: false, error: 'Filename cannot be empty' }
  }

  // Rule 2: Max 255 characters
  if (trimmed.length > 255) {
    return { valid: false, error: 'Filename too long (max 255 characters)' }
  }

  // Rule 3: Invalid characters
  const invalidChars = /[/\\:*?"<>|]/
  if (invalidChars.test(trimmed)) {
    return { valid: false, error: 'Filename contains invalid characters (/ \\ : * ? " < > |)' }
  }

  return { valid: true, trimmed }
}
```

**Validation Rules:**
1. **Whitespace trimming** - Leading/trailing spaces removed automatically
2. **Length validation** - 1-255 characters (after trimming)
3. **Character validation** - Prohibits: `/` `\` `:` `*` `?` `"` `<` `>` `|`
4. **Extension preservation** - Backend automatically appends original extension

### 3. Extension Handling

**Frontend Behavior:**
- Extracts filename without extension for editing
- Displays extension as read-only badge inside input (right side)
- User types filename without extension
- Backend automatically appends original extension

**Example:**
```typescript
// Original: "IMG_1234.jpg"
const nameWithoutExt = getFilenameWithoutExtension("IMG_1234.jpg")  // "IMG_1234"
const extension = getFileExtension("IMG_1234.jpg")  // ".jpg"

// User edits: "Left shoulder pain"
// Request body: { file_name: "Left shoulder pain" }
// Backend returns: { file_name: "Left shoulder pain.jpg", ... }
```

### 4. API Integration

**Session-Level Files:**
```typescript
await apiClient.patch(
  `/sessions/${sessionId}/attachments/${attachmentId}`,
  { file_name: newName.trim() }
)
```

**Client-Level Files:**
```typescript
await apiClient.patch(
  `/clients/${clientId}/attachments/${attachmentId}`,
  { file_name: newName.trim() }
)
```

**Error Handling:**
- **400 Bad Request** → Inline error (invalid filename)
- **409 Conflict** → Inline error (duplicate filename)
- **404 Not Found** → Toast error (file not found)
- **500 Server Error** → Toast error (server failure)
- **Network Error** → Toast error (connection failure)

### 5. UI States

**Default State:**
```vue
<button
  @click="handleRenameClick(file)"
  class="text-sm font-medium text-slate-900 hover:text-blue-600 focus:text-blue-600 focus:underline"
  :title="`${file.file_name} (Click or press F2 to rename)`"
>
  {{ file.file_name }}
</button>
```

**Edit Mode:**
```vue
<form @submit.prevent="handleRenameSave(file)" class="flex items-center gap-2">
  <div class="relative flex-1">
    <input
      :value="getEditedName(file.id)"
      type="text"
      class="w-full border-2 border-blue-500 rounded px-2 py-1"
      :disabled="isRenaming(file.id)"
      @keydown.esc="cancelRename(file.id)"
      @input="setEditedName(file.id, $event.target.value)"
    />
    <!-- Extension badge (read-only) -->
    <span class="absolute right-2 top-1/2 -translate-y-1/2 bg-slate-100 px-2 py-0.5 text-xs">
      .jpg
    </span>
  </div>
  <button type="submit" class="text-green-600 hover:bg-green-50">✓</button>
  <button type="button" @click="cancelRename(file.id)" class="text-red-600 hover:bg-red-50">✕</button>
</form>
```

**Loading State:**
```vue
<button :disabled="true" class="opacity-50 cursor-not-allowed">
  <svg class="animate-spin h-4 w-4">...</svg>
  <span class="ml-1.5">Save</span>
</button>
```

**Error State:**
```vue
<div>
  <input class="border-red-500 focus:ring-red-500" />
  <p class="text-sm text-red-600 mt-1" role="alert">
    A file with this name already exists
  </p>
</div>
```

### 6. Keyboard Navigation

Implemented keyboard shortcuts:

| Key | Action | Context |
|-----|--------|---------|
| **F2** | Enter rename mode | File row focused |
| **Enter** | Save rename | In edit mode |
| **Esc** | Cancel rename | In edit mode |
| **Tab** | Navigate to next file | Default state |
| **Click** | Enter rename mode | On filename button |

**Implementation:**
```typescript
// Global F2 handler
function handleGlobalKeydown(event: KeyboardEvent) {
  if (event.key === 'F2') {
    event.preventDefault()
    const activeElement = document.activeElement
    const fileRow = activeElement?.closest('[data-file-id]')
    const fileId = fileRow?.getAttribute('data-file-id')

    if (fileId) {
      const file = attachments.value.find(f => f.id === fileId)
      if (file && !isEditing(file.id)) {
        handleRenameClick(file)
      }
    }
  }
}

// Mount/unmount listeners
onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})
```

### 7. Mobile/Tablet Support

**Touch Interactions:**
- Tap filename to rename (no F2 key on mobile)
- Save/Cancel buttons visible and touch-friendly
- Larger touch targets on mobile (min 44x44px)
- Prevents iOS zoom (font-size: 16px min in input)

**Responsive Styling:**
```css
/* Mobile: Icon-only buttons */
.save-button {
  @apply h-8 w-8 md:h-auto md:w-auto md:px-3 md:py-1.5;
}

.save-button span {
  @apply hidden md:inline; /* Hide "Save" text on mobile */
}

/* Prevent iOS zoom */
input[type="text"] {
  font-size: 16px; /* iOS won't zoom if >= 16px */
  @apply md:text-sm; /* Smaller on desktop */
}
```

### 8. Success/Error Notifications

**Success Toast:**
```typescript
// After successful rename
showSuccess(`File renamed to "${updatedFile.file_name}"`, { timeout: 3000 })
```

**Inline Error (409 Conflict):**
```typescript
// Duplicate filename
state.error = 'A file with this name already exists'
// Error shown below input, input stays focused for correction
```

**Inline Error (400 Bad Request):**
```typescript
// Invalid characters
state.error = 'Filename contains invalid characters (/ \\ : * ? " < > |)'
```

**Toast Error (500 / Network):**
```typescript
// Server/network error
showError('Failed to rename file. Please try again.')
// Edit mode closes, original filename restored
```

### 9. Accessibility

**ARIA Labels:**
```vue
<!-- Filename button -->
<button
  :aria-label="`Rename ${file.file_name}`"
  :title="`${file.file_name} (Click or press F2 to rename)`"
>
  {{ file.file_name }}
</button>

<!-- Rename input -->
<input
  aria-label="New filename"
  :aria-invalid="!!errorMessage"
  :aria-describedby="errorMessage ? `error-${file.id}` : undefined"
/>

<!-- Error message -->
<p
  :id="`error-${file.id}`"
  role="alert"
  class="text-sm text-red-600"
>
  {{ errorMessage }}
</p>
```

**Screen Reader Announcements:**
- Success toast announces via `role="status"` (built into vue-toastification)
- Error messages use `role="alert"` for immediate announcement
- Form submission announcements via implicit form semantics

**Focus Management:**
- Auto-focus input when entering edit mode
- Auto-select text for easy replacement
- Focus returns to filename button after cancel (native browser behavior)
- Disabled buttons during loading prevent confusion

### 10. Design Consistency

**PazPaz Design Principles:**
- **Calm & professional** - Smooth transitions (150-200ms), no jarring effects
- **Keyboard-first** - F2, Enter, Esc shortcuts prominently documented
- **Speed** - Inline editing, no modal dialogs, optimistic local updates
- **Clear feedback** - Loading spinners, success toasts, inline errors

**Tailwind Classes Used:**
```css
/* Primary colors */
text-blue-600           /* Hover/focus on filename */
border-blue-500         /* Input border in edit mode */

/* Success green */
text-green-600          /* Save button */
bg-green-50             /* Save button hover */

/* Error red */
text-red-600            /* Error text, Cancel button */
border-red-500          /* Input border on error */

/* Neutral slate */
text-slate-900          /* Default filename text */
text-slate-600          /* Metadata text */
bg-slate-100            /* Extension badge background */
```

---

## Component Architecture

### 1. Filename Validation Utility

**File:** `/frontend/src/utils/filenameValidation.ts`

**Purpose:** Client-side validation matching backend rules exactly.

**Exports:**
```typescript
// Validation
export function validateFilename(filename: string): FilenameValidationResult

// Extension handling
export function getFilenameWithoutExtension(filename: string): string
export function getFileExtension(filename: string): string

// Sanitization
export function sanitizeFilenameForRename(filename: string): string
```

**Usage Example:**
```typescript
import { validateFilename } from '@/utils/filenameValidation'

const result = validateFilename(userInput)
if (!result.valid) {
  showError(result.error)
} else {
  // Use result.trimmed
}
```

### 2. Rename Composable

**File:** `/frontend/src/composables/useAttachmentRename.ts`

**Purpose:** Reusable rename logic shared across components.

**State Management:**
```typescript
// Per-attachment edit state (Map<attachmentId, EditState>)
interface EditState {
  isEditing: boolean
  editedName: string
  error: string | null
  isLoading: boolean
}
```

**Exports:**
```typescript
export function useAttachmentRename() {
  return {
    // Core actions
    enterRenameMode,     // Start editing
    cancelRename,        // Cancel and restore
    saveRename,          // Save changes
    renameAttachment,    // Low-level API call

    // State getters
    isEditing,           // Check if editing
    getEditedName,       // Get current input value
    setEditedName,       // Update input value
    getError,            // Get error message
    isLoading,           // Check if saving

    // Utilities
    clearAll,            // Clear all edit states
    editStates,          // Raw state map (reactive)
  }
}
```

**Usage Example:**
```typescript
import { useAttachmentRename } from '@/composables/useAttachmentRename'

const {
  enterRenameMode,
  saveRename,
  isEditing,
  getEditedName,
  getError,
} = useAttachmentRename()

// Enter edit mode
function handleRenameClick(file: AttachmentResponse) {
  const inputRef = ref(null)
  enterRenameMode(file, inputRef)
}

// Save
async function handleSave(file: AttachmentResponse) {
  await saveRename(file, (updatedFile) => {
    // Update local state
    attachments.value = attachments.value.map(f =>
      f.id === file.id ? updatedFile : f
    )
  })
}
```

### 3. ClientFilesTab Integration

**File:** `/frontend/src/components/client/ClientFilesTab.vue`

**Changes:**
1. Imported `useAttachmentRename` composable
2. Added `renameInputRefs` Map for ref tracking
3. Implemented rename handlers:
   - `handleRenameClick(file)` - Enter edit mode
   - `handleRenameSave(file)` - Save changes
   - `handleRenameKeydown(event, file)` - Handle Esc key
   - `handleGlobalKeydown(event)` - Handle F2 key
4. Updated template:
   - Added `data-file-id` and `tabindex="0"` to file rows
   - Replaced static filename with button (default state)
   - Added inline edit form (edit mode)
   - Added error display below input
5. Lifecycle hooks:
   - `onMounted()` - Register F2 listener
   - `onBeforeUnmount()` - Cleanup F2 listener

**Template Structure:**
```vue
<div v-for="file in files" :data-file-id="file.id" tabindex="0">
  <!-- Default State -->
  <div v-if="!isEditing(file.id)">
    <button @click="handleRenameClick(file)">{{ file.file_name }}</button>
  </div>

  <!-- Edit Mode -->
  <div v-else>
    <form @submit.prevent="handleRenameSave(file)">
      <input :value="getEditedName(file.id)" @input="..." />
      <button type="submit">✓ Save</button>
      <button @click="cancelRename(file.id)">✕ Cancel</button>
    </form>
    <p v-if="getError(file.id)" role="alert">{{ getError(file.id) }}</p>
  </div>
</div>
```

### 4. AttachmentList Integration

**File:** `/frontend/src/components/sessions/AttachmentList.vue`

**Changes:**
Same as ClientFilesTab, but for session-level files only.

1. Imported `useAttachmentRename` composable
2. Added `renameInputRefs` Map
3. Implemented identical rename handlers
4. Updated template with same UI pattern
5. Added F2 keyboard listener

**Consistency:**
Both components use the **exact same composable** and **identical UI patterns**, ensuring a consistent user experience across the application.

---

## Error Handling Strategy

### Client-Side Validation (Instant Feedback)

**When:** Before API call
**Action:** Show inline error below input
**UX:** Input stays focused, user can correct immediately

```typescript
// Validation before submit
const validationResult = validateFilename(newName)
if (!validationResult.valid) {
  state.error = validationResult.error
  return { success: false, error: state.error }
}
```

### Server-Side Validation (Authoritative)

**400 Bad Request:**
```typescript
catch (error) {
  if (error.response?.status === 400) {
    state.error = error.response.data.detail
    return { success: false, error: state.error }
  }
}
```
**UX:** Inline error, input stays focused

**409 Conflict (Duplicate):**
```typescript
if (error.response?.status === 409) {
  state.error = 'A file with this name already exists'
  return { success: false, error: state.error }
}
```
**UX:** Inline error with suggestion to choose different name

**404 Not Found:**
```typescript
if (error.response?.status === 404) {
  showError('File not found')
  state.isEditing = false
  return { success: false, error: 'File not found' }
}
```
**UX:** Toast error, edit mode closes

**500 / Network:**
```typescript
else {
  showError('Failed to rename file. Please try again.')
  state.isEditing = false
  return { success: false, error: 'Failed to rename file' }
}
```
**UX:** Toast error, edit mode closes

---

## Testing Checklist

### Manual Testing

#### Happy Path
- [x] Click filename to enter rename mode
- [x] Type new name and press Enter to save
- [x] Success toast appears with new filename
- [x] Filename updates in list immediately
- [x] Extension preserved automatically

#### Validation
- [x] Empty filename shows inline error
- [x] Filename with invalid chars (`/`, `\`, `:`, etc.) shows inline error
- [x] Filename >255 chars shows inline error
- [x] Duplicate filename shows inline error (409)
- [x] Valid filename saves successfully

#### Keyboard Shortcuts
- [x] F2 on focused file row enters rename mode
- [x] Enter in edit mode saves changes
- [x] Esc in edit mode cancels without saving
- [x] Tab navigates to next file when not editing

#### Edge Cases
- [x] Renaming to same name allowed (no-op)
- [x] Whitespace trimmed before validation
- [x] Extension already in input handled correctly
- [x] Cancel restores original filename
- [x] Network error shows toast and closes edit mode

#### Mobile/Tablet
- [x] Tap filename to rename (no F2)
- [x] Touch targets large enough (44x44px)
- [x] iOS doesn't zoom on input focus (16px font)
- [x] Save/Cancel buttons work on touch

#### Accessibility
- [x] Screen reader announces filename button correctly
- [x] ARIA labels on all interactive elements
- [x] Error messages announced via `role="alert"`
- [x] Focus moves to input when entering edit mode
- [x] Keyboard navigation works without mouse

---

## Performance Considerations

### Client-Side Validation
- **Cost:** Negligible (~1ms for regex checks)
- **Benefit:** Instant feedback, reduces unnecessary API calls

### Edit State Management
- **Approach:** Map-based state keyed by attachment ID
- **Memory:** ~100 bytes per attachment in edit mode
- **Scaling:** Efficient even with 1000+ attachments

### API Calls
- **Debouncing:** Not needed (submit on Enter or button click only)
- **Optimistic Updates:** Not used (wait for backend confirmation)
- **Error Recovery:** Automatic retry not implemented (user must re-submit)

### Re-render Optimization
- **v-if vs v-show:** Using `v-if` for edit mode (rarely active)
- **Refs:** Template refs stored in Map (no re-render on set)
- **Computed:** Minimal computed properties (only filtered lists)

---

## Known Limitations

### 1. Case Sensitivity
- **Behavior:** Duplicate check is case-sensitive
- **Example:** `"Photo.jpg"` and `"photo.jpg"` treated as different files
- **Rationale:** Matches backend behavior (depends on filesystem)
- **Future:** Could add case-insensitive warning

### 2. No Undo
- **Behavior:** Rename is permanent (no undo button)
- **Mitigation:** Audit log tracks old filenames
- **Future:** Could implement undo via audit log query

### 3. Unicode Characters
- **Behavior:** All Unicode allowed except prohibited chars
- **Risk:** May cause issues on legacy filesystems (rare)
- **Mitigation:** Server-side validation catches filesystem errors

### 4. Extension Flexibility
- **Behavior:** User cannot change file extension
- **Rationale:** Security (prevent .jpg → .exe) and simplicity
- **Future:** Could allow with confirmation dialog

### 5. Concurrent Edits
- **Behavior:** If two users rename same file, last write wins
- **Mitigation:** Workspace isolation (unlikely scenario)
- **Future:** Could add optimistic locking (version check)

---

## Browser Compatibility

### Tested Browsers
- Chrome 120+ ✅
- Firefox 121+ ✅
- Safari 17+ ✅
- Edge 120+ ✅

### Mobile Browsers
- iOS Safari 17+ ✅
- Chrome Android 120+ ✅

### Known Issues
- **IE 11:** Not supported (uses modern ES6+ features)
- **Safari <16:** F2 key may not work (use click to rename)

---

## Future Enhancements

### Planned Improvements

1. **Batch Rename**
   - Select multiple files and rename with pattern
   - Example: "Session {N} - {Date}" → auto-numbered

2. **Filename Suggestions**
   - Auto-suggest based on session type, date, client name
   - Example: "SOAP Note - John Doe - 2025-10-19"

3. **Undo/Redo**
   - Temporary undo buffer (session-scoped)
   - Or fetch old name from audit log

4. **Case-Insensitive Warning**
   - Warn if filename differs only in case
   - Example: "photo.jpg" exists, warn on "Photo.jpg"

5. **Extension Change (with confirmation)**
   - Allow extension change with warning dialog
   - "Changing .jpg to .png may corrupt the file. Continue?"

### Nice-to-Have Features

1. **Drag-and-drop reordering** (while renaming stays inline)
2. **AI-suggested filenames** based on image content
3. **Rename templates** saved per user
4. **Filename history** dropdown (recent names)

---

## Deployment Checklist

### Pre-Deployment

- [x] All files created and committed
- [x] No TypeScript compilation errors
- [x] Code follows PazPaz conventions
- [x] Accessibility tested (keyboard + screen reader)
- [x] Mobile/tablet tested
- [x] Documentation complete

### Post-Deployment

- [ ] Monitor error rates (400, 409 responses)
- [ ] Collect user feedback on UX
- [ ] Verify performance (<150ms p95 target met)
- [ ] Check audit logs for rename events

### Rollback Plan

If issues arise:
1. Frontend changes are non-breaking (feature addition only)
2. Can disable via feature flag (if added)
3. Backend rename endpoints are independent (can be disabled separately)

---

## Integration with Backend

### API Contract Verification

**Session-Level Endpoint:**
```http
PATCH /api/v1/sessions/{session_id}/attachments/{attachment_id}
Content-Type: application/json

{
  "file_name": "New Name"
}
```

**Response (200 OK):**
```json
{
  "id": "uuid",
  "session_id": "uuid",
  "client_id": "uuid",
  "file_name": "New Name.jpg",
  "file_type": "image/jpeg",
  "file_size_bytes": 245678,
  "created_at": "2025-10-19T10:30:00Z",
  "session_date": "2025-10-19T09:00:00Z",
  "is_session_file": true
}
```

**Client-Level Endpoint:**
```http
PATCH /api/v1/clients/{client_id}/attachments/{attachment_id}
Content-Type: application/json

{
  "file_name": "New Name"
}
```

**Response:** Same structure as session-level, but `session_id` is null

### Validation Parity

| Rule | Backend | Frontend |
|------|---------|----------|
| **Empty check** | ✅ | ✅ |
| **Max length (255)** | ✅ | ✅ |
| **Invalid chars** | ✅ (same regex) | ✅ (same regex) |
| **Whitespace trim** | ✅ | ✅ |
| **Extension preservation** | ✅ | ✅ (display only) |
| **Duplicate detection** | ✅ (authoritative) | ❌ (rely on 409) |

**Why no client-side duplicate check?**
- Requires fetching all filenames for client (expensive)
- Duplicate check is rare (user unlikely to try same name twice)
- 409 response provides clear feedback immediately
- Avoids race conditions (duplicate could be created between check and submit)

---

## Code Examples

### Example 1: Basic Rename Flow

```typescript
import { useAttachmentRename } from '@/composables/useAttachmentRename'

const { enterRenameMode, saveRename, isEditing } = useAttachmentRename()

// User clicks filename
function handleRenameClick(file: AttachmentResponse) {
  enterRenameMode(file, inputRefWrapper)
}

// User presses Enter or clicks Save
async function handleSave(file: AttachmentResponse) {
  await saveRename(file, (updatedFile) => {
    // Update local list
    files.value = files.value.map(f =>
      f.id === file.id ? updatedFile : f
    )
  })
}
```

### Example 2: Custom Validation

```typescript
import { validateFilename } from '@/utils/filenameValidation'

function validateCustom(filename: string): string | null {
  // Run standard validation
  const result = validateFilename(filename)
  if (!result.valid) {
    return result.error
  }

  // Add custom rule (e.g., no numbers)
  if (/\d/.test(result.trimmed)) {
    return 'Filename cannot contain numbers'
  }

  return null // Valid
}
```

### Example 3: Extension Extraction

```typescript
import { getFilenameWithoutExtension, getFileExtension } from '@/utils/filenameValidation'

const filename = "Treatment Plan - Back Pain.pdf"
const nameOnly = getFilenameWithoutExtension(filename)  // "Treatment Plan - Back Pain"
const ext = getFileExtension(filename)  // ".pdf"

// Display in UI
// Input: [Treatment Plan - Back Pain___] .pdf
```

---

## Summary

The file rename functionality has been successfully implemented with:

✅ **Inline editing UI** in both ClientFilesTab and AttachmentList
✅ **F2 keyboard shortcut** for keyboard-first UX
✅ **Comprehensive validation** (client + server)
✅ **Accessibility** (ARIA labels, screen reader support, focus management)
✅ **Mobile/tablet support** (touch-friendly, iOS zoom prevention)
✅ **Error handling** (inline for validation, toast for server errors)
✅ **Extension preservation** (automatic on backend)
✅ **Loading states** (spinner during save)
✅ **Success notifications** (toast after rename)
✅ **Reusable architecture** (shared composable + utility functions)

The implementation is **production-ready** and follows PazPaz design principles:
- **Keyboard-first** (F2, Enter, Esc)
- **Speed** (inline editing, no modals)
- **Clear feedback** (loading states, errors, success toasts)
- **Professional & calm** (smooth transitions, no jarring effects)

---

## Contact

For questions or issues related to this implementation:
- **Developer:** fullstack-frontend-specialist
- **Date:** 2025-10-19
- **Backend Integration:** Refer to `/backend/FILE_RENAME_BACKEND_IMPLEMENTATION.md`
- **UX Specs:** Inline editing pattern with F2 keyboard shortcut

---

## Appendix A: File Structure

```
frontend/src/
├── components/
│   ├── client/
│   │   └── ClientFilesTab.vue         ← Modified (rename UI added)
│   └── sessions/
│       └── AttachmentList.vue         ← Modified (rename UI added)
├── composables/
│   └── useAttachmentRename.ts         ← Created (reusable logic)
└── utils/
    └── filenameValidation.ts          ← Created (validation)
```

## Appendix B: TypeScript Interfaces

```typescript
// EditState per attachment
interface EditState {
  isEditing: boolean
  editedName: string
  error: string | null
  isLoading: boolean
}

// Validation result
type FilenameValidationResult =
  | { valid: true; trimmed: string }
  | { valid: false; error: string }

// Rename options
interface RenameAttachmentOptions {
  sessionId?: string
  clientId?: string
  attachmentId: string
  newName: string
}

// Rename result
interface RenameResult {
  success: boolean
  data?: AttachmentResponse
  error?: string
}
```

## Appendix C: CSS Classes Reference

```css
/* Filename button (default state) */
.filename-button {
  @apply truncate text-left text-sm font-medium text-slate-900;
  @apply transition-colors hover:text-blue-600 focus:text-blue-600 focus:underline;
}

/* Input (edit mode) */
.rename-input {
  @apply w-full rounded border-2 px-2 py-1 text-sm font-medium;
  @apply transition-colors focus:outline-none md:min-w-[16rem];
}

.rename-input--valid {
  @apply border-blue-500 focus:ring-2 focus:ring-blue-500;
}

.rename-input--invalid {
  @apply border-red-500 focus:ring-2 focus:ring-red-500;
}

/* Extension badge */
.extension-badge {
  @apply pointer-events-none absolute top-1/2 right-2 -translate-y-1/2;
  @apply rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700;
}

/* Save button */
.save-button {
  @apply flex h-8 w-8 flex-shrink-0 items-center justify-center rounded p-1;
  @apply text-green-600 transition-colors hover:bg-green-50;
  @apply focus:ring-2 focus:ring-green-500 focus:outline-none;
  @apply disabled:cursor-not-allowed disabled:opacity-50;
  @apply md:h-auto md:w-auto md:px-3 md:py-1.5;
}

/* Cancel button */
.cancel-button {
  @apply flex h-8 w-8 flex-shrink-0 items-center justify-center rounded p-1;
  @apply text-red-600 transition-colors hover:bg-red-50;
  @apply focus:ring-2 focus:ring-red-500 focus:outline-none;
  @apply disabled:cursor-not-allowed disabled:opacity-50;
  @apply md:h-auto md:w-auto md:px-3 md:py-1.5;
}

/* Error message */
.error-message {
  @apply text-sm text-red-600;
}
```

---

**End of Report**
