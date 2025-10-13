# AppointmentFormModal P0 Keyboard Interactions - Manual Testing Guide

## Overview

This document provides step-by-step instructions for manually testing the three P0 keyboard interactions implemented in the AppointmentFormModal component.

## Setup

1. Start the development server: `npm run dev`
2. Navigate to the Calendar view
3. Ensure you have at least one client in the database

---

## Feature 1: ⌘Enter / Ctrl+Enter to Submit Form

### Test 1.1: Submit with Valid Data (macOS)

**Steps:**

1. Click "+ New Appointment" button
2. Fill in the client field (select a client from dropdown)
3. Set start time (e.g., 10:00 AM)
4. Set end time (e.g., 11:00 AM)
5. Press `⌘ + Enter` (Command + Enter)

**Expected Result:**

- ✅ Form submits successfully
- ✅ Modal closes
- ✅ New appointment appears on calendar
- ✅ No page refresh or browser navigation

### Test 1.2: Submit with Valid Data (Windows/Linux)

**Steps:**

1. Click "+ New Appointment" button
2. Fill in the client field
3. Set start time
4. Set end time
5. Press `Ctrl + Enter`

**Expected Result:**

- ✅ Form submits successfully (same as Test 1.1)

### Test 1.3: Attempt Submit with Invalid Data

**Steps:**

1. Click "+ New Appointment" button
2. Leave client field empty
3. Press `⌘ + Enter` (or `Ctrl + Enter`)

**Expected Result:**

- ❌ Form does NOT submit
- ✅ Validation error "Client is required" appears in red text
- ✅ Modal stays open
- ✅ Client field is highlighted with red border

### Test 1.4: Submit with Conflicting Time Slot

**Steps:**

1. Create an appointment from 10:00 AM - 11:00 AM
2. Click "+ New Appointment" again
3. Fill in client
4. Set start time to 10:30 AM (overlaps with first appointment)
5. Set end time to 11:30 AM
6. Wait for conflict warning to appear (amber/yellow box)
7. Press `⌘ + Enter` (or `Ctrl + Enter`)

**Expected Result:**

- ✅ Form submits despite conflict warning
- ✅ Submit button text shows "⚠️ Create Anyway"
- ✅ Appointment is created
- ✅ Both appointments are visible on calendar

---

## Feature 2: Auto-Focus First Field on Modal Open

### Test 2.1: Focus Client Field (No Prefill)

**Steps:**

1. Click "+ New Appointment" button
2. Observe which field is focused immediately

**Expected Result:**

- ✅ Client combobox is automatically focused
- ✅ Cursor is in the client search input
- ✅ You can immediately start typing to search clients
- ✅ No manual clicking needed

### Test 2.2: Focus Start Time (Client Prefilled)

**Steps:**

1. Navigate to a Client Detail page
2. Click "+ New Appointment" from the client detail page
   (This should prefill the client field)
3. Observe which field is focused

**Expected Result:**

- ✅ Client field is pre-filled with the client from detail page
- ✅ Start Time input is automatically focused
- ✅ Cursor is in the start time field
- ✅ Client field is disabled/locked (shows "Client is pre-selected" hint)

### Test 2.3: Focus Location (Both Client and Time Prefilled)

**Steps:**

1. Navigate to Calendar view
2. Double-click on an empty time slot on the calendar
   (This should prefill both client and time)
3. If prompted, select a client
4. Observe which field is focused

**Expected Result:**

- ✅ Client field is pre-filled
- ✅ Start time and end time are pre-filled
- ✅ Location Type dropdown is automatically focused
- ✅ You can immediately press arrow keys to change location

### Test 2.4: Focus Client Field in Edit Mode

**Steps:**

1. Create an appointment
2. Click on the appointment in the calendar to edit it
3. Observe which field is focused

**Expected Result:**

- ✅ Client combobox is automatically focused
- ✅ All fields are pre-filled with existing appointment data
- ✅ You can immediately change the client if needed

### Test 2.5: Screen Reader Announcement

**Steps:**

1. Enable screen reader (VoiceOver on macOS, NVDA on Windows)
2. Click "+ New Appointment"
3. Listen for screen reader announcement

**Expected Result:**

- ✅ Screen reader announces "Client, combobox" or similar
- ✅ Focused field is clearly announced
- ✅ Required field status is announced

---

## Feature 3: Visual Keyboard Hints Below Submit Button

### Test 3.1: Keyboard Hint Visible on macOS

**Steps:**

1. Use macOS (or set user agent to Mac)
2. Click "+ New Appointment"
3. Scroll to the bottom of the modal
4. Observe the text below the submit button

**Expected Result:**

- ✅ Text reads "or press ⌘Enter"
- ✅ "⌘Enter" is styled as a keyboard key (rounded, gray background, monospace font)
- ✅ Hint is clearly visible but subtle (small, muted color)
- ✅ Hint is centered below the submit button

### Test 3.2: Keyboard Hint Visible on Windows

**Steps:**

1. Use Windows (or set user agent to Windows)
2. Click "+ New Appointment"
3. Scroll to the bottom of the modal
4. Observe the text below the submit button

**Expected Result:**

- ✅ Text reads "or press CtrlEnter"
- ✅ "CtrlEnter" is styled as a keyboard key
- ✅ Platform detection correctly shows "Ctrl" instead of "⌘"

### Test 3.3: Keyboard Hint Visible on Linux

**Steps:**

1. Use Linux (or set user agent to Linux)
2. Click "+ New Appointment"
3. Scroll to the bottom of the modal
4. Observe the text below the submit button

**Expected Result:**

- ✅ Text reads "or press CtrlEnter"
- ✅ Same as Windows test

### Test 3.4: Keyboard Hint Styling

**Steps:**

1. Click "+ New Appointment"
2. Inspect the keyboard hint visually

**Expected Result:**

- ✅ `<kbd>` element has:
  - Rounded corners
  - Light gray background (`bg-slate-100`)
  - Monospace font (`font-mono`)
  - Small text size (`text-xs`)
  - Dark gray text (`text-slate-700`)
  - Small padding (`px-1.5 py-0.5`)
- ✅ Hint text is muted gray (`text-slate-500`)
- ✅ Hint is positioned 0.5rem below the submit button (`gap-2`)

### Test 3.5: Hint Not Visible When Modal Closed

**Steps:**

1. Ensure modal is closed (click Cancel or close button)
2. Inspect the page

**Expected Result:**

- ❌ Keyboard hint is NOT visible anywhere on the page
- ✅ Hint only appears when modal is open

---

## Integration Test: Full Keyboard Workflow

### Test 4.1: Complete Appointment Creation via Keyboard Only

**Steps:**

1. Click "+ New Appointment" (with mouse)
2. Observe: Client field is auto-focused
3. Type client name to search, use arrow keys to select, press Enter
4. Press Tab to move to Start Time
5. Enter start time
6. Press Tab to move to End Time
7. Enter end time
8. Press Tab to move to Location Type
9. Use arrow keys to select location
10. Press `⌘ + Enter` (or `Ctrl + Enter`)

**Expected Result:**

- ✅ Entire form can be filled using only keyboard
- ✅ Auto-focus saves one Tab press at the start
- ✅ Submit shortcut saves clicking the button
- ✅ Total time savings: ~2-3 seconds per appointment
- ✅ Appointment is created successfully

### Test 4.2: Edit Appointment via Keyboard

**Steps:**

1. Click on existing appointment
2. Observe: Client field is auto-focused
3. Press Tab to move to time field
4. Update time
5. Press `⌘ + Enter`

**Expected Result:**

- ✅ Appointment updates successfully
- ✅ Modal closes
- ✅ Changes are reflected on calendar

---

## Edge Cases

### Test 5.1: Rapid Modal Open/Close

**Steps:**

1. Click "+ New Appointment"
2. Immediately press Escape
3. Click "+ New Appointment" again
4. Fill in form and press `⌘ + Enter`

**Expected Result:**

- ✅ No errors in console
- ✅ Modal opens and closes smoothly
- ✅ Submit still works correctly

### Test 5.2: Keyboard Shortcut While Modal Closed

**Steps:**

1. Close the appointment modal
2. Press `⌘ + Enter` anywhere on the page

**Expected Result:**

- ❌ Nothing happens
- ✅ No errors in console
- ✅ Keyboard shortcut only works when modal is open

### Test 5.3: Multiple Modals/Forms on Page

**Steps:**

1. If there are other modals/forms on the page, open them
2. Try the `⌘ + Enter` shortcut

**Expected Result:**

- ✅ Shortcut only affects AppointmentFormModal when it's open
- ✅ No interference with other forms

---

## Accessibility Testing

### Test 6.1: Keyboard Navigation

**Steps:**

1. Click "+ New Appointment"
2. Use only Tab, Shift+Tab, Arrow keys, Enter, and Escape
3. Navigate through all form fields

**Expected Result:**

- ✅ All fields are keyboard accessible
- ✅ Tab order is logical (Client → Start Time → End Time → Location → Notes → Cancel → Submit)
- ✅ Focus indicators are clearly visible
- ✅ Escape closes modal
- ✅ Enter on submit button submits form

### Test 6.2: Screen Reader Compatibility

**Steps:**

1. Enable screen reader
2. Open modal
3. Navigate through form

**Expected Result:**

- ✅ All labels are announced
- ✅ Required fields are announced as required
- ✅ Error messages are announced
- ✅ Submit button state is announced (e.g., "Create" vs "Create Anyway")
- ✅ Keyboard hint is readable

---

## Performance

### Test 7.1: Auto-Focus Performance

**Steps:**

1. Open modal
2. Measure time until field is focused

**Expected Result:**

- ✅ Focus happens within 100ms of modal opening
- ✅ No visible delay or "jump"
- ✅ Smooth user experience

### Test 7.2: Keyboard Handler Performance

**Steps:**

1. Open modal
2. Press `⌘ + Enter` rapidly multiple times

**Expected Result:**

- ✅ Form only submits once
- ✅ No duplicate submissions
- ✅ No UI freezing

---

## Browser Compatibility

Test on:

- ✅ Chrome/Edge (macOS, Windows, Linux)
- ✅ Firefox (macOS, Windows, Linux)
- ✅ Safari (macOS)

**Expected Result:**

- ✅ All features work consistently across browsers
- ✅ Platform detection works correctly
- ✅ Keyboard shortcuts work as expected

---

## Success Metrics

After completing all tests, verify:

1. **⌘Enter / Ctrl+Enter Submit:**
   - ✅ Works on all platforms
   - ✅ Validates before submitting
   - ✅ Prevents default browser behavior

2. **Auto-Focus:**
   - ✅ Focuses correct field based on context
   - ✅ Works in create and edit modes
   - ✅ Screen reader compatible

3. **Visual Keyboard Hints:**
   - ✅ Shows correct modifier key per platform
   - ✅ Properly styled and positioned
   - ✅ Only visible when modal is open

4. **Integration:**
   - ✅ All features work together seamlessly
   - ✅ No regressions in existing functionality
   - ✅ Improves appointment creation speed by ~2-3 seconds

---

## Troubleshooting

### Issue: Auto-focus not working

- Check browser console for errors
- Verify `defineExpose` in ClientCombobox.vue includes `inputRef`
- Ensure modal is fully rendered before focus attempt

### Issue: Keyboard shortcut not working

- Verify event listener is attached on mount
- Check browser console for errors
- Try different modifier keys (Cmd vs Ctrl)

### Issue: Wrong platform detected

- Check `navigator.platform` in browser console
- Verify platform detection logic in computed property

---

## Notes

- These P0 features are essential for keyboard-first UX
- Users should feel significantly faster when creating appointments
- Features should be discoverable (keyboard hint) but not intrusive
- All interactions should be accessible to screen reader users
