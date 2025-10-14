# Visual Testing Guide for SessionEditor Fixes

## Setup

1. Start the backend: `cd backend && docker compose up`
2. Start the frontend: `cd frontend && npm run dev`
3. Navigate to a session note (e.g., `/sessions/{session-id}`)

---

## Test Case 1: Finalize Button Click (CRITICAL)

**Steps:**
1. Open any draft session note
2. Add some content to at least one SOAP field
3. Wait for autosave to complete ("Saved X ago" appears)
4. Click "Finalize Session" button

**Expected Behavior:**
- ✅ Button text changes from "Finalize Session" to "Finalizing..." with spinner
- ✅ Button background color smoothly transitions green → green (same color, but shows spinner)
- ✅ **CRITICAL:** No form fields re-render or flicker
- ✅ **CRITICAL:** No cursor jumping or field value changes
- ✅ Badge smoothly fades from "Draft" (blue) to "Finalized" (green) with subtle scale animation
- ✅ Button text changes to "Revert to Draft" after completion
- ✅ Button background color changes to slate gray
- ✅ Total duration: ~200-300ms for all transitions

**Visual Quality:**
- Should feel **buttery-smooth** like a native app
- No visible layout shifts or content jumps
- Badge change should be elegant, not abrupt

---

## Test Case 2: Revert to Draft (Unfinalize)

**Steps:**
1. From a finalized session, click "Revert to Draft" button

**Expected Behavior:**
- ✅ Button text changes to "Reverting..." with spinner
- ✅ Background color stays slate gray during loading
- ✅ Badge smoothly fades from "Finalized" (green) to "Draft" (blue)
- ✅ Button changes back to "Finalize Session" with green background
- ✅ No form field glitches (this already worked perfectly)

---

## Test Case 3: Initial Page Load

**Steps:**
1. Navigate to `/sessions/{session-id}` directly (hard refresh)
2. Watch the page load sequence

**Expected Behavior:**
- ✅ Skeleton loader appears immediately
- ✅ **Single smooth transition** from skeleton to content
- ✅ No sequential loading jumps (no "content appears, then shifts")
- ✅ Previous Session Panel loads in parallel with main content
- ✅ If there's a backup prompt, it appears smoothly without layout shift

**What to Watch For:**
- ❌ No "double render" where content appears then re-adjusts
- ❌ No visible layout shift when Previous Session Panel loads
- ❌ No flicker when badges first appear

---

## Test Case 4: Rapid Finalize/Unfinalize Cycles

**Steps:**
1. Finalize a draft session
2. Immediately click "Revert to Draft" when it appears
3. Immediately click "Finalize Session" when it appears
4. Repeat 3-5 times rapidly

**Expected Behavior:**
- ✅ All transitions remain smooth even with rapid clicks
- ✅ No accumulated glitches or visual artifacts
- ✅ Badge transitions remain smooth throughout
- ✅ No spinner overlaps or button text glitches
- ✅ Form fields never re-render or lose focus

---

## Test Case 5: Autosave During Finalize

**Steps:**
1. Open a draft session
2. Start typing in a SOAP field
3. Immediately click "Finalize Session" (before autosave triggers)

**Expected Behavior:**
- ✅ Force save completes first (invisible to user)
- ✅ Finalize completes smoothly
- ✅ No double-save indicators or spinner confusion
- ✅ "Saved X ago" timestamp updates correctly
- ✅ No form re-render despite the force save

---

## Test Case 6: Badge Transition Quality

**Focus:** Specifically watch the Draft ↔ Finalized badge change

**Expected Animation:**
1. Current badge fades out with slight scale-down (95%) over 150ms
2. New badge fades in with slight scale-up (95% → 100%) over 150ms
3. Total transition: ~150ms (mode="out-in" means sequential)

**Visual Quality Checklist:**
- ✅ No "pop" or abrupt appearance
- ✅ Fade is smooth and consistent
- ✅ Scale animation is subtle, not distracting
- ✅ Badge container doesn't resize or shift position
- ✅ Text stays readable throughout transition

---

## Performance Benchmarks

Use Chrome DevTools Performance tab:

1. Start recording
2. Click "Finalize Session"
3. Stop recording when transition completes

**Target Metrics:**
- ✅ **No forced reflow/recalculation** during finalize (check Recalculate Style events)
- ✅ **No unnecessary paints** of form fields (should only repaint button + badge)
- ✅ **GPU-accelerated transitions** (check Layers panel for transform/opacity)
- ✅ **Total JS execution time:** <50ms (finalize API call excluded)

---

## Regression Testing

**Ensure these existing features still work:**

1. **Autosave:**
   - ✅ Still triggers every 5 seconds after typing stops
   - ✅ "Saving..." indicator appears correctly
   - ✅ "Saved X ago" updates after successful save

2. **Keyboard Shortcuts:**
   - ✅ Cmd/Ctrl+Enter still finalizes session
   - ✅ Works from any field (not just when button is focused)

3. **Offline Mode:**
   - ✅ Changes save to encrypted localStorage when offline
   - ✅ Restore prompt appears correctly on next visit
   - ✅ Offline badge displays correctly

4. **Version History:**
   - ✅ Amendment indicator appears after editing finalized session
   - ✅ "View Original Version" link works correctly

5. **Previous Session Panel:**
   - ✅ Loads independently without blocking main content
   - ✅ Collapse/expand works smoothly
   - ✅ No layout shift when it appears/disappears

---

## Visual Comparison (Before vs After)

### Before:
- 🔴 Finalize: Form fields visibly re-render, cursor jumps
- 🔴 Initial load: Sequential loading causes 2-3 layout shifts
- 🔴 Badge change: Abrupt color swap, no transition
- 🔴 Button: Text change feels instant and jarring

### After:
- ✅ Finalize: Zero form re-render, only button + badge change
- ✅ Initial load: Single smooth skeleton → content transition
- ✅ Badge change: Elegant 150ms fade + scale animation
- ✅ Button: Smooth 200ms color transition, no layout shift

---

## Browser Testing

Test on multiple browsers to ensure consistent behavior:

- **Chrome/Edge:** Primary target, should be perfect
- **Firefox:** Check CSS transitions work correctly
- **Safari:** Verify GPU acceleration and smooth animations

---

## Mobile Testing (Bonus)

On mobile devices (or Chrome DevTools mobile emulation):

1. Tap "Finalize Session" button
2. Verify touch feedback is responsive
3. Ensure badge transition is smooth even at 60fps
4. Check Previous Session Panel drawer transitions

---

## Known Expected Behaviors (Not Bugs)

1. **Unfinalize always calls loadSession(true):** This is intentional because draft state might have server-side changes
2. **"Saved X ago" updates after autosave:** This is a single field update, not a re-render
3. **Previous Session Panel has independent loading:** This is correct; it shouldn't block main content
4. **Badge transition takes 150ms:** This is intentional for smooth animation (not sluggish, not instant)

---

## Reporting Issues

If you observe any glitches, please report:

1. **Which test case failed**
2. **Browser and version**
3. **Screen recording** (if possible)
4. **Chrome DevTools Performance profile** (for technical analysis)
5. **Console errors** (if any)

---

## Success Criteria

All tests pass when:
- ✅ Zero visible glitches throughout all test cases
- ✅ Transitions feel smooth and professional
- ✅ No layout shifts or content jumps
- ✅ Performance metrics within target ranges
- ✅ All existing features still work correctly

**Target Feel:** Should feel like a polished native app, not a web page.
