# Manual Testing Guide: Session Restoration Bug Fix

## Quick Test Procedure

### Prerequisites
1. Have the frontend dev server running (`npm run dev`)
2. Have the backend API running
3. Have at least one client in the system

---

## Test Case 1: Basic Restore-Delete Cycle ✅

**Objective**: Verify that restored sessions can be deleted again

### Steps:

1. **Navigate to Client Detail Page**
   - Go to Calendar view
   - Click on any appointment
   - Click "View Client Profile"

2. **Create a Session Note**
   - In the client detail page, click "New Note" button (or press `n`)
   - Fill in some SOAP content (Subjective, Objective, Assessment, Plan)
   - Click "Save Draft" or "Finalize"
   - Note the session date/time

3. **Delete the Session**
   - In the "Treatment History" tab, find your session
   - Click the kebab menu (⋮) on the session card
   - Click "Delete"
   - Confirm deletion if prompted

4. **Verify Session in Deleted Notes**
   - Scroll down to "Deleted Notes" section
   - Click to expand it
   - ✅ **Expected**: Your session should appear here with a countdown timer

5. **Restore the Session**
   - Click the "Restore" button on the deleted session
   - ✅ **Expected**: Toast notification "Session note restored successfully"
   - ✅ **Expected**: Session disappears from "Deleted Notes"
   - ✅ **Expected**: Session appears back in "Treatment History" (AUTOMATIC REFRESH)

6. **Delete the Restored Session Again**
   - In the "Treatment History" tab, find your restored session
   - Click the kebab menu (⋮) on the session card
   - Click "Delete"
   - Confirm deletion if prompted

7. **Verify Final State**
   - ✅ **Expected**: Session moves back to "Deleted Notes"
   - ✅ **Expected**: Session is removed from "Treatment History"
   - ✅ **Expected**: Badge count on "Deleted Notes" increases

---

## Test Case 2: Multiple Restore Operations ✅

**Objective**: Verify repeated restore operations work correctly

### Steps:

1. Create a session note (steps 1-2 from Test Case 1)

2. **Perform Multiple Restore-Delete Cycles**
   - Delete session → Verify in "Deleted Notes"
   - Restore session → **Verify it appears in "Treatment History"**
   - Delete again → Verify in "Deleted Notes"
   - Restore again → **Verify it appears in "Treatment History"**
   - Repeat 2-3 more times

3. **Verify Consistency**
   - ✅ **Expected**: Each restore operation shows the session in timeline
   - ✅ **Expected**: Each delete operation moves it to deleted notes
   - ✅ **Expected**: No duplicate sessions appear
   - ✅ **Expected**: Badge count is always accurate

---

## Test Case 3: Multiple Sessions Restoration ✅

**Objective**: Verify restoring multiple sessions works correctly

### Steps:

1. **Create Multiple Sessions**
   - Create 3 session notes with different dates
   - Note their dates/content

2. **Delete All Sessions**
   - Delete all 3 sessions
   - ✅ **Expected**: All appear in "Deleted Notes" section
   - ✅ **Expected**: Badge shows "3"

3. **Restore Sessions One by One**
   - Restore the first session
   - ✅ **Expected**: Appears in "Treatment History"
   - ✅ **Expected**: Badge changes to "2"

   - Restore the second session
   - ✅ **Expected**: Both sessions visible in "Treatment History"
   - ✅ **Expected**: Badge changes to "1"

   - Restore the third session
   - ✅ **Expected**: All 3 sessions visible in "Treatment History"
   - ✅ **Expected**: Badge disappears (count = 0)

4. **Verify Order**
   - ✅ **Expected**: Sessions appear in chronological order (newest first)

---

## Test Case 4: Badge Pulse Animation ✅

**Objective**: Verify badge pulse when section is collapsed

### Steps:

1. Create a session note
2. **Collapse "Deleted Notes" Section**
   - Click the "Deleted Notes" header to collapse it
   - Badge should show "0"

3. **Delete the Session**
   - Delete your session from "Treatment History"
   - ✅ **Expected**: Badge pulses with blue animation
   - ✅ **Expected**: Badge count increases to "1"

4. **Expand and Verify**
   - Click to expand "Deleted Notes"
   - ✅ **Expected**: Your deleted session is visible

---

## Test Case 5: Restoration with Associated Appointment ✅

**Objective**: Verify sessions linked to appointments restore correctly

### Steps:

1. **Create Session from Appointment**
   - Create an appointment in calendar
   - Go to client detail → Treatment History
   - Click "Create Session Note" from the appointment
   - Fill in SOAP content

2. **Delete and Restore**
   - Delete the session
   - Verify in "Deleted Notes"
   - Restore the session
   - ✅ **Expected**: Session appears in timeline
   - ✅ **Expected**: Appointment link is maintained

3. **Verify Appointment Association**
   - The session should show the original appointment details
   - No duplicate appointment cards should appear

---

## Test Case 6: UI Responsiveness ✅

**Objective**: Verify UI updates are smooth and instant

### Steps:

1. Create a session note

2. **Test Deletion Speed**
   - Delete the session
   - ✅ **Expected**: Session disappears immediately (optimistic update)
   - ✅ **Expected**: Smooth slide-out animation
   - ✅ **Expected**: Appears in deleted section within 1 second

3. **Test Restoration Speed**
   - Click "Restore"
   - ✅ **Expected**: Session disappears from deleted section immediately
   - ✅ **Expected**: Timeline refreshes within 500ms
   - ✅ **Expected**: No loading spinner blocks the UI

---

## Edge Cases to Test

### Edge Case 1: Tab Switching During Restore
1. Click "Restore" on a session
2. Immediately switch to "Overview" tab
3. Switch back to "History" tab
4. ✅ **Expected**: Restored session is visible in timeline

### Edge Case 2: Multiple Browser Tabs
1. Open client detail in two browser tabs
2. Delete session in Tab 1
3. Restore session in Tab 2
4. Refresh Tab 1
5. ✅ **Expected**: Tab 1 shows restored session after refresh

### Edge Case 3: Network Error During Restore
1. Open browser DevTools → Network tab
2. Click "Restore" on a session
3. Before request completes, set network to "Offline"
4. ✅ **Expected**: Error toast appears
5. ✅ **Expected**: Session remains in "Deleted Notes"
6. Re-enable network and try again
7. ✅ **Expected**: Restore succeeds

---

## Common Issues to Watch For

### ❌ Bug Indicators (Should NOT happen)

1. **Stale Timeline**: Restored session doesn't appear in "Treatment History"
   - This was the original bug - should be fixed now

2. **Duplicate Sessions**: Same session appears multiple times
   - Indicates race condition in data fetching

3. **Badge Mismatch**: Badge count doesn't match actual deleted notes
   - Indicates state sync issue

4. **Failed Deletion After Restore**: Can't delete a restored session
   - This was the critical bug symptom - should be fixed now

5. **Loading State Stuck**: UI shows loading spinner indefinitely
   - Indicates error in async handling

---

## Performance Expectations

### Response Times

- **Delete Operation**: < 100ms (optimistic update)
- **Restore Operation**: < 200ms (optimistic + server reconciliation)
- **Timeline Refresh**: < 500ms (concurrent API calls)
- **Badge Update**: < 50ms (reactive state)

### Animation Smoothness

- **Deletion Animation**: Smooth 300ms slide-out
- **Badge Pulse**: Smooth 600ms pulse animation
- **Section Collapse**: Smooth 200ms accordion animation

---

## Test Environment Setup

### Frontend Dev Server
```bash
cd /Users/yussieik/Desktop/projects/pazpaz/frontend
npm run dev
```

### Backend API Server
```bash
cd /Users/yussieik/Desktop/projects/pazpaz/backend
# Start backend according to project setup
```

### Browser DevTools

**Recommended Settings**:
- Open DevTools (F12)
- Enable "Preserve log" in Console
- Watch Network tab for API calls
- Use Vue DevTools extension for state inspection

**API Endpoints to Monitor**:
- `GET /api/v1/sessions?client_id=...` (fetch sessions)
- `GET /api/v1/appointments?client_id=...&status=completed` (fetch appointments)
- `POST /api/v1/sessions/{id}/restore` (restore session)
- `DELETE /api/v1/sessions/{id}` (soft delete session)

---

## Success Criteria

All tests pass if:

✅ Sessions can be restored and appear in timeline **immediately**
✅ Restored sessions can be deleted again **without issues**
✅ Badge counts are **always accurate**
✅ No duplicate sessions appear
✅ UI updates are **smooth and instant**
✅ Multiple restore-delete cycles work **flawlessly**
✅ No console errors or warnings

---

## Reporting Issues

If you find any issues during testing, please report with:

1. **Steps to reproduce** (exactly what you did)
2. **Expected behavior** (what should happen)
3. **Actual behavior** (what actually happened)
4. **Screenshots** (if applicable)
5. **Console errors** (from browser DevTools)
6. **Network requests** (from Network tab)

---

## Quick Checklist

Use this checklist for rapid testing:

- [ ] Create session note
- [ ] Delete session
- [ ] Verify in "Deleted Notes"
- [ ] Restore session
- [ ] **Verify appears in "Treatment History"**
- [ ] Delete restored session
- [ ] **Verify moves to "Deleted Notes" again**
- [ ] Badge count is correct
- [ ] No console errors
- [ ] Smooth animations

**Estimated Test Time**: 3-5 minutes per test case

---

**Status**: Ready for manual testing ✅
