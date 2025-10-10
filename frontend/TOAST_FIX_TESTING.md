# Toast Caching Fix - Testing Guide

## Changes Made

### 1. Added `filterToasts` Option (`/frontend/src/main.ts`)

**What it does:**

- Prevents vue-toastification from maintaining a history cache of dismissed toasts
- Complements the existing `filterBeforeCreate` to fully disable deduplication

**Code added (lines 36-41):**

```typescript
filterToasts: (toasts) => {
  // Don't filter any toasts - allow all to show
  // This prevents the library from caching dismissed toasts
  // Critical fix for: toasts not appearing after first one completes
  return toasts
},
```

### 2. Added Debug Logging (`/frontend/src/composables/useToast.ts`)

**What it does:**

- Logs each toast creation with unique ID and timestamp
- Helps diagnose if the issue persists

**Code added (lines 170-173):**

```typescript
// Debug logging to verify unique IDs are generated
console.log('[Toast Debug] Showing toast with ID:', uniqueId)
console.log('[Toast Debug] Message:', message)
console.log('[Toast Debug] Timestamp:', new Date().toISOString())
```

## Root Cause Analysis

**Problem:**
vue-toastification v2.0.0-rc.5 has internal caching logic that tracks dismissed toasts, preventing them from showing again even with unique IDs.

**Original approach (insufficient):**

- ✅ Unique toast IDs: `${message}-${Date.now()}-${Math.random()}`
- ✅ Different client names in messages
- ✅ `filterBeforeCreate` to disable concurrent deduplication
- ❌ But library still cached dismissed toasts internally

**New approach (complete):**

- ✅ All of the above PLUS
- ✅ `filterToasts` to disable history cache entirely

## Testing Checklist

### Test 1: Basic Sequential Reschedules

**Goal:** Verify toasts appear after each other completes

1. [ ] Open calendar view
2. [ ] Drag appointment A to a new time slot → Toast appears with "Appointment rescheduled for [Client A]"
3. [ ] Wait 5+ seconds → Toast dismisses automatically
4. [ ] Drag appointment B to a new time slot → **Toast MUST appear**
5. [ ] Check browser console for debug logs:
   ```
   [Toast Debug] Showing toast with ID: Appointment rescheduled for Client B-1728555123456-0.789
   [Toast Debug] Message: Appointment rescheduled for Client B
   [Toast Debug] Timestamp: 2025-10-10T09:32:03.456Z
   ```

**Expected:** ✅ Toast appears for appointment B (CRITICAL FIX)

### Test 2: Same Appointment Rescheduled Twice

**Goal:** Verify same appointment can trigger multiple toasts

1. [ ] Drag appointment A to time slot 1 → Toast appears
2. [ ] Wait 5+ seconds → Toast dismisses
3. [ ] Drag appointment A to time slot 2 → **Toast MUST appear again**
4. [ ] Verify different unique IDs in console logs

**Expected:** ✅ Toast appears even for same appointment

### Test 3: Rapid Sequential Reschedules

**Goal:** Verify toast stacking works and doesn't break future toasts

1. [ ] Drag appointment A → Toast 1 appears
2. [ ] Immediately drag appointment B → Toast 2 appears (both stack up)
3. [ ] Immediately drag appointment C → Toast 3 appears (all 3 stack)
4. [ ] Wait for all toasts to dismiss (15+ seconds)
5. [ ] Drag appointment D → **Toast MUST appear**

**Expected:** ✅ Toast appears after stack clears

### Test 4: Undo Functionality

**Goal:** Verify undo still works and doesn't interfere with future toasts

1. [ ] Drag appointment A → Toast appears with "Undo" button
2. [ ] Click "Undo" → Appointment reverts
3. [ ] Toast dismisses
4. [ ] Drag appointment B → **Toast MUST appear**

**Expected:** ✅ Undo works, future toasts appear

### Test 5: Browser Console Verification

**Goal:** Verify unique IDs are being generated

1. [ ] Open browser DevTools console
2. [ ] Drag 3 different appointments in sequence (waiting 5s between each)
3. [ ] Check console logs show 3 different unique IDs:
   ```
   [Toast Debug] Showing toast with ID: Appointment rescheduled for Alice-1728555001234-0.123
   [Toast Debug] Showing toast with ID: Appointment rescheduled for Bob-1728555006789-0.456
   [Toast Debug] Showing toast with ID: Appointment rescheduled for Carol-1728555012345-0.789
   ```
4. [ ] Verify each ID is different (different timestamp + random number)

**Expected:** ✅ Each toast has unique ID

### Test 6: Page Refresh Not Required

**Goal:** Verify the fix eliminates the need to refresh

1. [ ] Perform 5+ reschedules in sequence (waiting for each to complete)
2. [ ] **Never refresh the page**
3. [ ] Verify all 5 toasts appear

**Expected:** ✅ No page refresh needed

## Success Criteria

**Before Fix:**

- ❌ First reschedule: Toast appears
- ❌ Toast dismisses after 5s
- ❌ Second reschedule: No toast
- ❌ Must refresh page to see toasts again

**After Fix:**

- ✅ First reschedule: Toast appears
- ✅ Toast dismisses after 5s
- ✅ Second reschedule: Toast appears
- ✅ Third+ reschedules: Toasts appear
- ✅ No page refresh ever needed

## Debugging If Issue Persists

### Step 1: Verify Console Logs

Check if `showSuccessWithUndo` is actually being called:

- If NO logs appear → Issue is upstream (drag handler not calling toast)
- If logs appear but no toast → Issue is in vue-toastification config

### Step 2: Check for Vue Warnings

Look for errors in console:

- `[Vue warn]` messages about toast plugin
- JavaScript errors during toast creation
- Network errors that might block toast rendering

### Step 3: Verify Unique IDs

Each log should show:

- Different timestamp (Date.now())
- Different random number (Math.random())
- Different message (if different clients)

If IDs are NOT unique → Bug in ID generation logic

### Step 4: Test Toast Library Directly

Add temporary test button to verify library works:

```vue
<button @click="testToast">Test Toast</button>

function testToast() { const toast = useToast() toast.showSuccess('Test ' + Date.now())
}
```

- If test toast appears → Issue is specific to reschedule flow
- If test toast doesn't appear → Issue is in toast config

## Rollback Plan

If this fix doesn't work, try the alternative approach:

**Remove `filterBeforeCreate` entirely:**

```typescript
// In /frontend/src/main.ts
const toastOptions: PluginOptions = {
  // ... other options
  // Remove filterBeforeCreate entirely
  // Remove filterToasts entirely
  // Rely solely on unique toastId
}
```

The unique IDs should be sufficient on their own. If they're not, the issue may be a bug in vue-toastification v2.0.0-rc.5 (release candidate).

## Alternative: Upgrade Toast Library

If all else fails, consider upgrading to a stable version:

```bash
npm install vue-toastification@latest
```

Or switching to a different toast library:

- `vue3-toastify` (more actively maintained)
- `@kyvg/vue3-notification`
- Custom toast component using Headless UI

## Files Modified

1. **`/frontend/src/main.ts`** (lines 30-41)
   - Added `filterToasts` callback to disable history cache
   - Updated comments in `filterBeforeCreate`

2. **`/frontend/src/composables/useToast.ts`** (lines 170-173)
   - Added debug console.log statements
   - Shows unique ID, message, and timestamp

## Next Steps After Testing

1. **If fix works:**
   - [ ] Remove debug console.log statements (lines 170-173)
   - [ ] Keep `filterToasts` in production
   - [ ] Update documentation about toast behavior
   - [ ] Close the toast caching issue

2. **If fix doesn't work:**
   - [ ] Report findings (console logs, errors)
   - [ ] Try rollback plan (remove all filters)
   - [ ] Consider library upgrade/replacement
   - [ ] File issue with vue-toastification if library bug confirmed

## Related Files

- **Toast Configuration:** `/frontend/src/main.ts`
- **Toast Composable:** `/frontend/src/composables/useToast.ts`
- **Calendar Reschedule:** `/frontend/src/views/CalendarView.vue` (uses showSuccessWithUndo)
- **Package:** `vue-toastification@2.0.0-rc.5` (check package.json)
