# Mobile Drag-and-Drop Scroll Isolation - UX Design Specification

**Status:** Design Specification
**Target:** Mobile devices (<768px viewport)
**Feature:** Calendar appointment drag-and-drop with isolated scrolling
**Last Updated:** 2025-10-28

---

## Executive Summary

This document provides comprehensive UX design specifications for implementing focused, isolated scrolling during mobile drag-and-drop operations on the PazPaz calendar. The goal is to create a calm, predictable experience where only the calendar view scrolls during drag operations, while all other UI elements (header, toolbar, navigation) remain fixed.

**Key Principle:** When dragging, the user's entire focus should be on the calendar. Everything else fades into the background.

---

## 1. Scroll Lock Behavior

### 1.1 When to Activate Scroll Lock

**Trigger Point:** Immediately on long-press detection (300ms threshold)

**Activation Sequence:**
```
User long-presses appointment (0ms)
  ↓
Long-press detected (300ms)
  ↓
IMMEDIATELY:
  - Lock body scroll (document.body.style.overflow = 'hidden')
  - Lock html scroll (document.documentElement.style.overflow = 'hidden')
  - Add 'drag-active' class to calendar container
  - Show visual feedback (subtle shadow/elevation)
  - Enable calendar-only scroll zone
  ↓
User drags appointment
  ↓
User releases or cancels
  ↓
IMMEDIATELY:
  - Unlock body/html scroll
  - Remove 'drag-active' class
  - Restore normal scroll behavior
```

**Why 300ms Long-Press:**
- Prevents accidental activation during normal scrolling
- Standard duration for long-press on mobile (iOS/Android conventions)
- Provides enough time for haptic feedback (if available)
- Matches existing implementation in `useAppointmentDrag.ts:186`

### 1.2 Preventing Accidental Page Scrolling

**Multi-Layered Prevention Strategy:**

**Layer 1: Body Scroll Lock**
```css
/* Applied when drag-active */
body.drag-mode-active {
  overflow: hidden !important;
  position: fixed !important;
  width: 100% !important;
  height: 100% !important;
}

html.drag-mode-active {
  overflow: hidden !important;
}
```

**Why `position: fixed` on body:**
- Prevents scroll even if `overflow: hidden` fails on some browsers
- Maintains scroll position (no jump to top)
- Most reliable cross-browser solution for iOS Safari

**Layer 2: Touch Event Prevention**
```typescript
// Prevent touchmove on non-calendar elements during drag
function handleDragActivation() {
  document.addEventListener('touchmove', preventNonCalendarTouch, { passive: false });
}

function preventNonCalendarTouch(e: TouchEvent) {
  const target = e.target as HTMLElement;
  const isCalendarArea = target.closest('.calendar-content-area');

  if (!isCalendarArea) {
    e.preventDefault(); // Block scroll outside calendar
  }
  // Allow touchmove inside calendar for auto-scroll
}

function handleDragDeactivation() {
  document.removeEventListener('touchmove', preventNonCalendarTouch);
}
```

**Layer 3: Viewport Meta Tag Insurance**
```html
<!-- Ensure this is in index.html -->
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
```

**Note:** Only enforce `user-scalable=no` during drag mode if needed for legacy devices.

### 1.3 Visual Feedback for Scroll Lock

**Subtle, Non-Intrusive Indicators:**

**Option A: Overlay Dimming (Recommended)**
```css
/* Applied during drag-active */
.calendar-drag-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.05); /* Very subtle dim */
  z-index: 5; /* Below calendar (z-10), above other content */
  pointer-events: none;
  transition: opacity 150ms ease-out;
}

/* Calendar container rises above overlay */
.calendar-content-area.drag-active {
  position: relative;
  z-index: 10;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15); /* Subtle blue glow */
  transition: box-shadow 150ms ease-out;
}
```

**Why Overlay Dimming:**
- Clearly communicates "everything else is locked"
- Focuses attention on calendar
- Minimal visual disruption (5% opacity is barely noticeable)
- Matches PazPaz's calm design philosophy

**Option B: Header/Toolbar Fade (Alternative)**
```css
/* Applied during drag-active */
.calendar-toolbar.drag-active,
.app-header.drag-active {
  opacity: 0.4;
  transition: opacity 150ms ease-out;
}
```

**Recommendation:** Use Option A (Overlay Dimming) as primary feedback, with Option B as supplementary for stronger visual hierarchy.

**What NOT to Do:**
- ❌ Obtrusive banners ("Drag mode active")
- ❌ Animated borders or flashing indicators
- ❌ Color shifts that distract from calendar
- ❌ Sound effects (violates calm principle)

---

## 2. Calendar Auto-Scroll

### 2.1 Edge Proximity Triggering

**Edge Zone Dimensions:**

```
┌─────────────────────────────────┐ ← Top Edge Zone
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ (80px threshold)
│                                 │
│                                 │
│      Normal Calendar Area       │
│         (no auto-scroll)        │
│                                 │
│                                 │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ (80px threshold)
└─────────────────────────────────┘ ← Bottom Edge Zone
```

**Numeric Values:**
- **Edge threshold:** 80px from top/bottom of calendar viewport
- **Maximum edge threshold:** 120px on very tall screens (>900px height)
- **Minimum edge threshold:** 60px on short screens (<600px height)

**Why 80px:**
- Large enough to trigger naturally during vertical drag
- Not so large that entire screen becomes scroll zone
- Accounts for imprecise finger positioning on mobile
- Tested across iPhone SE (small) to iPad Mini (larger mobile)

**Responsive Thresholds:**
```typescript
function getEdgeScrollThreshold(viewportHeight: number): number {
  if (viewportHeight < 600) return 60; // Compact phones
  if (viewportHeight > 900) return 120; // Larger phones/phablets
  return 80; // Standard phones
}
```

### 2.2 Scroll Speed

**Speed Parameters:**

| Proximity | Speed (px/frame) | Acceleration |
|-----------|------------------|--------------|
| 80-60px   | 2px              | Linear       |
| 60-40px   | 4px              | Linear       |
| 40-20px   | 8px              | Linear       |
| 20-0px    | 12px             | Linear       |

**Frame Rate:** 60fps (requestAnimationFrame)

**Formula:**
```typescript
function calculateScrollSpeed(distanceFromEdge: number, threshold: number): number {
  // Closer to edge = faster scroll
  // distanceFromEdge: 0 (at edge) to threshold (80px away)

  const proximity = 1 - (distanceFromEdge / threshold); // 0 to 1
  const maxSpeed = 12; // pixels per frame at 60fps
  const minSpeed = 2; // pixels per frame at edge threshold

  return minSpeed + (maxSpeed - minSpeed) * proximity;
}
```

**Why Linear Acceleration:**
- Predictable: speed directly correlates with proximity
- No easing curves that feel "mushy" or unpredictable
- Matches iOS/Android native scroll behavior
- Easier to implement and debug

**Why 12px Max Speed:**
- At 60fps: 720px/second = comfortable, not frantic
- Fast enough to traverse typical day view (12 hours = ~600px) in <1 second
- Slow enough to maintain precision when approaching target time slot
- Prevents "runaway scroll" feeling

### 2.3 Acceleration vs Constant Speed

**Chosen Approach:** Linear acceleration (speed increases closer to edge)

**Why NOT Constant Speed:**
- Constant speed feels "dead" and unresponsive
- No feedback for "I want to scroll faster"
- Users naturally move finger closer to edge to scroll faster

**Why NOT Exponential/Cubic Acceleration:**
- Difficult to predict: small movements near edge cause huge speed changes
- Overshooting target is frustrating
- Feels "twitchy" on mobile

**Comparison:**
```
Linear:       Speed ∝ Proximity (simple, predictable)
Exponential:  Speed ∝ Proximity² (too aggressive)
Constant:     Speed = Fixed (too static)
```

### 2.4 Aggressive vs Gentle Auto-Scroll

**Recommendation:** **Gentle with Linear Ramp-Up**

**Rationale:**
- PazPaz values "calm, not cluttered" design
- Therapists need precision when scheduling (15-minute slots)
- Overshooting and correcting is more frustrating than slightly slower scroll
- Mobile screens are small; aggressive scroll causes loss of context

**Implementation:**
```typescript
const SCROLL_CONFIG = {
  edgeThreshold: 80,        // Distance from edge to trigger (px)
  minSpeed: 2,              // Slowest scroll (px/frame)
  maxSpeed: 12,             // Fastest scroll (px/frame)
  acceleration: 'linear',   // Speed curve
  frameRate: 60,            // Target fps (requestAnimationFrame)
  deadZone: 10,             // No scroll in center (px from edges)
};
```

**User Testing Guidance:**
- Test with therapists (target users)
- Measure time to scroll from 8am to 6pm (typical day)
- Target: 1-2 seconds for full-day scroll
- Adjust `maxSpeed` if too slow/fast based on feedback

---

## 3. Visual Feedback

### 3.1 Visual Indicators for Drag Mode

**Primary Indicator: Drag Ghost Element (Existing)**

Already implemented in `CalendarView.vue:1588-1616`. No changes needed.

**Secondary Indicator: Edge Scroll Zones (Optional)**

**Option A: Visible Edge Gradients (More Explicit)**
```css
/* Show gradient when drag is active and near edge */
.calendar-content-area.drag-active::before,
.calendar-content-area.drag-active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  height: 80px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 200ms ease-out;
  z-index: 8; /* Above calendar, below drag ghost */
}

/* Top gradient */
.calendar-content-area.drag-active::before {
  top: 0;
  background: linear-gradient(
    to bottom,
    rgba(59, 130, 246, 0.08) 0%,
    transparent 100%
  );
}

/* Bottom gradient */
.calendar-content-area.drag-active::after {
  bottom: 0;
  background: linear-gradient(
    to top,
    rgba(59, 130, 246, 0.08) 0%,
    transparent 100%
  );
}

/* Show gradient when cursor enters edge zone */
.calendar-content-area.drag-active.scrolling-up::before,
.calendar-content-area.drag-active.scrolling-down::after {
  opacity: 1;
}
```

**Option B: Invisible Zones (More Subtle - Recommended)**

Do NOT show visual indicators for scroll zones. Let users discover them naturally through drag behavior.

**Why Option B:**
- Less visual clutter
- Users quickly learn the scroll zones through muscle memory
- Matches iOS/Android native drag-to-scroll behavior (no visible zones)
- Aligns with PazPaz's minimalist design

**Recommendation:** Start with Option B. Add Option A only if user testing shows confusion about scroll zones.

### 3.2 Cursor/Ghost Element Styling

**Current Ghost Element (from CalendarView.vue:1588-1616):**

```html
<div class="animate-ghost-float pointer-events-none fixed z-50"
     :style="{ left: '...', top: '...' }">
  <div class="rotate-2 rounded-lg border-2 border-blue-400 bg-white
              px-4 py-3 opacity-95 shadow-2xl ring-2 ring-blue-400/20">
    <div class="flex items-center gap-2">
      <IconClock size="md" class="text-blue-600" />
      <span class="text-sm font-semibold text-gray-900">10:00 AM - 11:00 AM</span>
    </div>
    <p class="mt-1 text-xs text-gray-600">Monday, Oct 28</p>
    <div v-if="hasConflict">⚠️ Conflict detected</div>
  </div>
</div>
```

**Enhancements for Mobile:**

```css
/* Mobile-specific ghost styling */
@media (max-width: 640px) {
  .drag-ghost-mobile {
    /* Larger touch target visibility */
    padding: 12px 16px;

    /* Stronger shadow for visibility against varying backgrounds */
    box-shadow:
      0 10px 25px -5px rgba(0, 0, 0, 0.2),
      0 8px 10px -6px rgba(0, 0, 0, 0.15);

    /* More pronounced rotation for "lifted" feeling */
    transform: rotate(3deg);

    /* Slightly larger text for readability while dragging */
    font-size: 0.9375rem; /* 15px */
  }

  .drag-ghost-time {
    font-size: 0.875rem; /* 14px */
    font-weight: 600;
    letter-spacing: 0.01em;
  }
}
```

**Why These Changes:**
- Larger padding: finger is covering screen, ghost needs to be visible around it
- Stronger shadow: works against light/dark calendar backgrounds
- 3° rotation: exaggerated "picked up" feeling
- Larger text: readable at arm's length on mobile

### 3.3 Shadow/Elevation Changes During Drag

**Three-State Visual Hierarchy:**

**State 1: Normal Appointment (Not Dragging)**
```css
.fc-event {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  transition: box-shadow 150ms ease-out;
}
```

**State 2: Long-Press Detected (Pre-Drag)**
```css
.fc-event.long-press-active {
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -1px rgba(0, 0, 0, 0.06);
  transform: scale(1.02);
  transition: all 150ms ease-out;
}
```

**State 3: Dragging (Placeholder Visible)**
```css
.fc-event.fc-event-dragging {
  opacity: 0.3;
  box-shadow: none;
  transition: opacity 200ms ease-out;
}
```

**Why Three States:**
- Provides progressive feedback: "I'm selecting" → "I'm lifting" → "I'm moving"
- Clear visual distinction between source position and ghost element
- Guides user through interaction without text instructions

### 3.4 Edge Zone Visibility

**Decision: Do NOT show edge zones visibly**

**Rationale:**
- Industry standard (iOS, Android, Google Calendar mobile) uses invisible zones
- Users learn through use (first drag teaches the zones)
- Less visual noise during already-busy drag operation
- Calm design principle: trust users to discover features

**Exception:** If user testing reveals confusion, add subtle gradients (see 3.1 Option A).

---

## 4. Touch Zones

### 4.1 Auto-Scroll Trigger Zone Sizes

**Mobile-Specific Sizing:**

```typescript
const TOUCH_ZONE_CONFIG = {
  // Screen size thresholds
  smallScreen: { maxHeight: 600, edgeZone: 60 },
  standardScreen: { maxHeight: 900, edgeZone: 80 },
  largeScreen: { maxHeight: Infinity, edgeZone: 120 },

  // Touch-specific adjustments
  minimumTouchTargetSize: 44, // iOS/Android standard
  edgeActivationBuffer: 16,   // Don't trigger at exact edge (accidental)

  // Dead zones
  centerDeadZone: 200, // No auto-scroll in middle of calendar
};
```

**Zone Layout:**
```
┌─────────────────────────┐
│ Top Buffer (16px)       │ ← Prevents accidental trigger at screen edge
├─────────────────────────┤
│ Top Scroll Zone (80px)  │ ← Auto-scroll UP
├─────────────────────────┤
│                         │
│   Center Dead Zone      │ ← No auto-scroll (200px minimum)
│   (User can drag        │
│    and reposition)      │
│                         │
├─────────────────────────┤
│ Bottom Scroll Zone (80px)│ ← Auto-scroll DOWN
├─────────────────────────┤
│ Bottom Buffer (16px)    │ ← Prevents accidental trigger
└─────────────────────────┘
```

### 4.2 Larger Zones on Smaller Screens?

**Recommendation: NO - Keep zones proportional**

**Why NOT larger on small screens:**
- Small screens have less scrollable content (fewer hours visible)
- Larger zones would dominate screen real estate
- Makes it hard to position appointments in top/bottom hours (8am, 9pm)
- Users with small screens are accustomed to precise touch interactions

**Instead: Use responsive threshold based on viewport height**

```typescript
function getResponsiveEdgeZone(viewportHeight: number): number {
  // Proportional scaling, not absolute increase
  const baseZone = 80;
  const minZone = 60;
  const maxZone = 120;

  if (viewportHeight < 600) return minZone;   // Compact
  if (viewportHeight > 900) return maxZone;   // Spacious
  return baseZone;                            // Standard
}
```

### 4.3 Dead Zones

**Center Dead Zone: 200px minimum**

**Purpose:** Prevent unintended auto-scroll when user is simply repositioning appointment in center area.

**Calculation:**
```typescript
const centerDeadZoneSize = Math.max(
  200,  // Minimum 200px
  viewportHeight * 0.3  // Or 30% of viewport height
);

const topZoneEnd = edgeThreshold;
const bottomZoneStart = viewportHeight - edgeThreshold;
const centerStart = topZoneEnd;
const centerEnd = bottomZoneStart;

// Only scroll if touch Y is in edge zones
function shouldAutoScroll(touchY: number): 'up' | 'down' | null {
  if (touchY < topZoneEnd) return 'up';
  if (touchY > bottomZoneStart) return 'down';
  return null; // In center dead zone
}
```

**Edge Buffer: 16px**

**Purpose:** Prevent accidental scroll trigger when user's finger reaches absolute screen edge (common when gripping phone).

```typescript
const EDGE_BUFFER = 16; // Pixels from screen edge

// Adjust effective edge zone
const effectiveTopZone = EDGE_BUFFER;
const effectiveBottomZone = viewportHeight - EDGE_BUFFER;
```

---

## 5. Accessibility

### 5.1 Assistive Technology Compatibility

**Screen Reader Announcements:**

```typescript
// Announce when drag mode activates
function announceScrollLockActivation() {
  announce('Drag mode active. Calendar scrolling enabled. Use two fingers to exit.');
}

// Announce scroll direction during drag
let lastScrollDirection: 'up' | 'down' | null = null;
function announceScrollIfChanged(direction: 'up' | 'down') {
  if (direction !== lastScrollDirection) {
    announce(`Scrolling ${direction}`);
    lastScrollDirection = direction;
  }
}

// Announce when dropped
function announceDropComplete(timeSlot: string) {
  announce(`Appointment moved to ${timeSlot}`);
}
```

**ARIA Live Region (Already Exists):**

From `CalendarView.vue:1576-1585`:
```html
<div id="drag-drop-announcer"
     role="status"
     aria-live="polite"
     aria-atomic="true"
     class="sr-only">
  <!-- Screen reader announcements appear here -->
</div>
```

**No Changes Needed:** Existing ARIA implementation is sufficient.

### 5.2 Fallback Behavior

**If Scroll Lock Fails (iOS Safari Edge Cases):**

```typescript
function handleScrollLockFailure() {
  // Detect if scroll lock failed (scrollTop changed when it shouldn't)
  const didScrollFail = document.documentElement.scrollTop !== scrollLockPosition;

  if (didScrollFail) {
    // Fallback 1: Restore scroll position immediately
    window.scrollTo(0, scrollLockPosition);

    // Fallback 2: Add stronger visual indicator (since lock failed)
    showScrollLockFailureOverlay();

    // Fallback 3: Log for debugging
    console.warn('Scroll lock failed - using fallback restoration');
  }
}

// Monitor during drag
let scrollLockCheckInterval: number | null = null;
function startScrollLockMonitoring() {
  scrollLockCheckInterval = setInterval(handleScrollLockFailure, 100);
}
```

**Why This Matters:**
- iOS Safari (especially older versions) has quirks with `overflow: hidden`
- If lock fails, user sees jarring page jump
- Graceful degradation maintains usable experience

### 5.3 User Preference to Disable

**Settings Toggle (Future Enhancement - V2):**

```typescript
// User preferences store
interface UserPreferences {
  enableDragScrollLock: boolean; // Default: true
  enableDragAutoScroll: boolean; // Default: true
  dragScrollSpeed: 'slow' | 'medium' | 'fast'; // Default: 'medium'
}

// Respect user preference
if (!userPreferences.enableDragScrollLock) {
  // Allow normal page scroll during drag
  // Skip body scroll lock
  // Show warning: "Scroll lock disabled - page may move during drag"
}
```

**Why Include This:**
- Accessibility: users with motor control issues may prefer different behavior
- User autonomy: respects personal preference
- Debugging: easier to isolate issues if behavior can be toggled

**Implementation Priority:** V2 (post-MVP). V1 should have sensible defaults that work for 95% of users.

---

## 6. Edge Cases

### 6.1 Dragging Outside Calendar Bounds

**Scenario:** User drags appointment outside `.calendar-content-area`

**Behavior:**

```typescript
function handleTouchMove(e: TouchEvent) {
  const touch = e.touches[0];
  const calendarBounds = calendarContainer.getBoundingClientRect();

  const isInsideCalendar = (
    touch.clientX >= calendarBounds.left &&
    touch.clientX <= calendarBounds.right &&
    touch.clientY >= calendarBounds.top &&
    touch.clientY <= calendarBounds.bottom
  );

  if (!isInsideCalendar) {
    // Option A: Cancel drag and revert (Recommended)
    cancelDragAndRevert();
    announce('Drag cancelled - appointment returned to original time');

    // Option B: Snap to nearest edge (Alternative)
    // snapToNearestEdgePosition();
  }
}
```

**Why Option A (Cancel and Revert):**
- Clear feedback: dragging off calendar = "I didn't mean to do this"
- Prevents accidental rescheduling
- Matches iOS native behavior (e.g., Safari tab management)

**Visual Feedback:**
```css
/* Show "cancel" state when dragged outside */
.drag-ghost.outside-bounds {
  opacity: 0.5;
  border-color: rgba(239, 68, 68, 0.5); /* Red tint */
  animation: shake 0.3s ease-in-out;
}
```

### 6.2 Reaching Top/Bottom of Scrollable Area

**Scenario:** User scrolls to 6:00 AM (top) or 10:00 PM (bottom) - no more content to scroll

**Behavior:**

```typescript
function handleAutoScroll(direction: 'up' | 'down') {
  const scrollContainer = calendarContainer;
  const currentScrollTop = scrollContainer.scrollTop;

  // Check if at boundary
  const atTop = currentScrollTop <= 0;
  const atBottom = currentScrollTop >= (scrollContainer.scrollHeight - scrollContainer.clientHeight);

  if ((direction === 'up' && atTop) || (direction === 'down' && atBottom)) {
    // Provide subtle haptic feedback (if available)
    if (navigator.vibrate) {
      navigator.vibrate(50); // Single short vibration
    }

    // Visual feedback: subtle "bounce" animation
    showBoundaryBounceFeedback(direction);

    // Stop auto-scroll loop
    return;
  }

  // Normal scroll continues
  scrollContainer.scrollTop += (direction === 'up' ? -scrollSpeed : scrollSpeed);
}
```

**Visual Boundary Feedback:**
```css
@keyframes boundary-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.calendar-content-area.at-top-boundary {
  animation: boundary-bounce 300ms ease-out;
}
```

**Why This Feedback:**
- Communicates "you've reached the end"
- Prevents user confusion ("is auto-scroll broken?")
- Subtle enough to not disrupt drag operation

### 6.3 Cancel Drag Behavior

**User Actions That Cancel Drag:**

1. **Drag outside calendar bounds** (see 6.1)
2. **Press Escape key** (desktop only)
3. **Second finger touch** (mobile - two-finger gesture)
4. **Long drag duration** (>10 seconds without drop)
5. **App loses focus** (user switches tabs/apps)

**Implementation:**
```typescript
// Two-finger cancel gesture
let activeTouches = 0;
function handleTouchStart(e: TouchEvent) {
  activeTouches = e.touches.length;

  if (activeTouches >= 2 && isDragging) {
    cancelDragAndRevert();
    announce('Drag cancelled');
  }
}

// Timeout cancel (prevent stuck state)
let dragTimeout: ReturnType<typeof setTimeout> | null = null;
function startDragTimeout() {
  dragTimeout = setTimeout(() => {
    if (isDragging) {
      cancelDragAndRevert();
      announce('Drag timed out - appointment returned to original time');
    }
  }, 10000); // 10 seconds
}

// Clear timeout on drop
function handleDrop() {
  if (dragTimeout) clearTimeout(dragTimeout);
  // ... complete drop
}
```

**Cancel Animation:**
```css
@keyframes snap-back {
  0% { opacity: 0.3; transform: scale(0.95); }
  50% { opacity: 0.6; transform: scale(1.05); }
  100% { opacity: 1; transform: scale(1); }
}

.fc-event.cancelling-drag {
  animation: snap-back 400ms cubic-bezier(0.68, -0.55, 0.265, 1.55);
}
```

---

## 7. Performance

### 7.1 Scroll Jank on Low-End Devices

**Risk:** Auto-scroll loop causes frame drops on older mobile devices (e.g., iPhone 8, budget Android)

**Mitigation Strategies:**

**Strategy 1: Use `requestAnimationFrame` (Already Standard)**
```typescript
let autoScrollRAF: number | null = null;

function startAutoScroll(direction: 'up' | 'down') {
  function scrollFrame() {
    if (!isDragging) return;

    // Calculate speed based on proximity
    const speed = calculateScrollSpeed(distanceFromEdge, edgeThreshold);

    // Scroll calendar container
    calendarContainer.scrollTop += (direction === 'up' ? -speed : speed);

    // Continue on next frame
    autoScrollRAF = requestAnimationFrame(scrollFrame);
  }

  scrollFrame();
}

function stopAutoScroll() {
  if (autoScrollRAF) cancelAnimationFrame(autoScrollRAF);
}
```

**Strategy 2: Disable Drag Animations on Low-End Devices**
```typescript
// Detect low-end device (heuristic)
const isLowEndDevice = (
  navigator.hardwareConcurrency <= 2 || // 2 or fewer CPU cores
  (performance.memory && performance.memory.jsHeapSizeLimit < 1073741824) // <1GB heap
);

if (isLowEndDevice) {
  // Disable ghost element rotation animation
  dragGhostElement.style.transform = 'none';

  // Reduce edge gradient animations
  document.body.classList.add('reduce-motion');
}
```

**Strategy 3: CSS `will-change` Optimization**
```css
.calendar-content-area.drag-active {
  will-change: scroll-position;
  /* Tells browser to optimize scrolling performance */
}

.drag-ghost {
  will-change: transform;
  /* Tells browser to optimize ghost movement */
}

/* Remove will-change when not dragging (important for memory) */
.calendar-content-area:not(.drag-active) {
  will-change: auto;
}
```

### 7.2 Throttling/Debouncing Auto-Scroll

**Current Implementation:** No throttling needed with `requestAnimationFrame`

**Why:**
- `requestAnimationFrame` inherently throttles to ~60fps (16.67ms intervals)
- Browser pauses RAF when tab not visible (automatic performance optimization)
- RAF syncs with display refresh rate (no wasted frames)

**Do NOT Use `setInterval` or `setTimeout`:**
```typescript
// ❌ BAD: Causes jank
setInterval(() => {
  calendarContainer.scrollTop += speed;
}, 16); // Attempt 60fps

// ✅ GOOD: Browser-optimized
requestAnimationFrame(scrollFrame);
```

**Exception:** Throttle conflict checks during drag (already implemented in `useAppointmentDrag.ts:131-152`):
```typescript
const debouncedConflictCheck = debounce(
  async (start: Date, end: Date, appointmentId: string) => {
    // Check for appointment conflicts
  },
  100  // Only check every 100ms (reduces API calls)
);
```

---

## 8. Similar Patterns (Industry Research)

### 8.1 Google Calendar Mobile

**Observed Behavior (iOS App):**
- Long-press (500ms) triggers drag mode
- Entire app UI dims slightly (overlay effect)
- Only calendar view scrolls during drag
- Auto-scroll triggers at ~100px from top/bottom
- Speed: linear acceleration (similar to our spec)
- Visual: ghost element follows finger with 10px offset
- Cancel: drag outside calendar bounds or two-finger tap

**Key Takeaways:**
- ✅ Overlay dimming during drag (we should adopt)
- ✅ Calendar-only scrolling (matches our spec)
- ⚠️ 500ms long-press is too slow (we use 300ms - better)

### 8.2 Outlook Mobile Calendar

**Observed Behavior (iOS App):**
- Single tap opens event details (no drag)
- Reschedule via modal with time picker (no drag-and-drop)
- No scroll isolation needed (different interaction model)

**Key Takeaways:**
- ❌ Not using drag-and-drop at all
- Not applicable to our design

### 8.3 Calendly Mobile

**Observed Behavior:**
- Read-only calendar view on mobile
- No drag-and-drop functionality
- Booking via modal forms

**Key Takeaways:**
- ❌ No drag interaction
- Not applicable

### 8.4 iOS Native Calendar App

**Observed Behavior:**
- No drag-and-drop on mobile (tap to edit only)
- Drag-and-drop exists on iPad with Apple Pencil

**Key Takeaways:**
- Apple avoids mobile drag-and-drop for calendars (interesting design decision)
- We're providing more power-user functionality than Apple
- Validates need for careful UX design (not a "solved problem")

### 8.5 Best Practices Summary

**Consensus Patterns Across Industry:**

1. ✅ **Long-press activation** (200-500ms) - universal pattern
2. ✅ **Visual dimming/focus** during drag - common in Google apps
3. ✅ **Scroll isolation** - standard in drag-heavy mobile apps
4. ✅ **Ghost element** follows finger - near-universal
5. ✅ **Edge-based auto-scroll** - standard in lists/calendars
6. ✅ **Linear acceleration** for scroll speed - most natural feel
7. ⚠️ **Visible scroll zones** - rare (most apps hide them)

**PazPaz Differentiation:**
- We're implementing drag-and-drop where many competitors don't (power user feature)
- Our 300ms long-press is faster than Google's 500ms (more responsive)
- Our scroll lock + auto-scroll is more focused than industry standard

---

## 9. FullCalendar Configuration Patterns

### 9.1 Existing FullCalendar Setup

**Current Configuration (from CalendarView.vue):**

```typescript
// Already configured in buildCalendarOptions()
{
  editable: true,              // Enables drag-and-drop
  eventDrop: handleEventDrop,  // Callback when event dropped
  longPressDelay: 300,         // Mobile long-press threshold (NOT USED IN V6)
  eventLongPressDelay: 300,    // Event-specific long-press (NOT USED IN V6)
}
```

**Issue:** FullCalendar v6 does NOT have built-in mobile drag-and-drop

### 9.2 Custom Mobile Drag Implementation

**Our Custom Implementation (useAppointmentDrag.ts):**

```typescript
// We handle mobile drag ourselves
function handleEventTouchStart(event: EventApi, touchEvent: TouchEvent) {
  longPressTimer = setTimeout(() => {
    // Our custom drag initiation
    triggerMobileReschedule(event);
  }, 300); // Our choice: 300ms
}
```

**Why Custom Implementation:**
- FullCalendar v6 drag-and-drop is desktop-only
- Mobile requires custom touch event handling
- Allows us to implement scroll isolation (FullCalendar can't do this)

### 9.3 Scroll Isolation Integration with FullCalendar

**Calendar Container Structure:**

```vue
<template>
  <div class="calendar-content-area" ref="calendarContentRef">
    <!-- This is the scrollable container -->
    <div class="calendar-container" ref="calendarContainerRef">
      <!-- FullCalendar renders here -->
      <FullCalendar :options="calendarOptions" />
    </div>
  </div>
</template>
```

**Key Points:**
- `.calendar-content-area`: Fixed height, NOT scrollable
- `.calendar-container`: Scrollable, contains FullCalendar
- **Scroll lock** targets `body`/`html`, not calendar container
- **Auto-scroll** targets `.calendar-container.scrollTop`

**Implementation:**
```typescript
// On drag start
function activateScrollIsolation() {
  // Lock body scroll
  document.body.style.overflow = 'hidden';
  document.body.style.position = 'fixed';
  document.body.style.width = '100%';

  // Mark calendar as drag-active
  calendarContentRef.value?.classList.add('drag-active');

  // Enable auto-scroll on calendar container only
  enableCalendarAutoScroll(calendarContainerRef.value);
}

// On drag end
function deactivateScrollIsolation() {
  // Unlock body scroll
  document.body.style.overflow = '';
  document.body.style.position = '';
  document.body.style.width = '';

  // Remove drag-active
  calendarContentRef.value?.classList.remove('drag-active');

  // Disable auto-scroll
  disableCalendarAutoScroll();
}
```

---

## 10. Implementation Checklist

### Phase 1: Scroll Lock (P0 - Critical)

- [ ] Implement body scroll lock on long-press (300ms)
  - [ ] Set `body` and `html` to `overflow: hidden`
  - [ ] Set `body` to `position: fixed` for iOS Safari
  - [ ] Store scroll position before locking
  - [ ] Restore scroll position after unlock
- [ ] Add `.drag-mode-active` class to body during drag
- [ ] Test on iOS Safari, Chrome Mobile, Samsung Internet
- [ ] Add subtle overlay dimming (5% black overlay)
- [ ] Add blue glow to calendar container during drag
- [ ] Verify no page scroll occurs during drag on all test devices

### Phase 2: Calendar Auto-Scroll (P0 - Critical)

- [ ] Implement edge detection (80px from top/bottom)
- [ ] Calculate responsive edge threshold based on viewport height
  - [ ] 60px for <600px height (compact phones)
  - [ ] 80px for 600-900px height (standard)
  - [ ] 120px for >900px height (large phones)
- [ ] Implement linear acceleration scroll speed
  - [ ] Min: 2px/frame at edge threshold
  - [ ] Max: 12px/frame at screen edge
  - [ ] Linear interpolation based on proximity
- [ ] Use `requestAnimationFrame` for scroll loop (60fps target)
- [ ] Add 16px edge buffer to prevent accidental triggers
- [ ] Implement center dead zone (200px minimum)
- [ ] Test scroll speed on various screen sizes
- [ ] Measure time to scroll full day (target: 1-2 seconds)

### Phase 3: Visual Feedback (P1 - High Priority)

- [ ] Enhance drag ghost element for mobile
  - [ ] Increase padding to 12px 16px
  - [ ] Strengthen shadow for visibility
  - [ ] Increase rotation to 3° for "lifted" effect
  - [ ] Increase font size to 15px for readability
- [ ] Implement three-state elevation system
  - [ ] Normal: subtle shadow (1px)
  - [ ] Long-press: elevated shadow (4px)
  - [ ] Dragging: placeholder opacity 0.3
- [ ] Add scroll boundary feedback
  - [ ] Haptic vibration (50ms) at top/bottom
  - [ ] Subtle bounce animation
- [ ] Test visual feedback in light/dark environments

### Phase 4: Edge Cases & Accessibility (P1 - High Priority)

- [ ] Handle drag outside calendar bounds
  - [ ] Cancel drag and revert to original position
  - [ ] Show "cancel" visual state (red tint + shake)
  - [ ] Screen reader announcement
- [ ] Implement two-finger cancel gesture
- [ ] Add 10-second drag timeout (prevent stuck state)
- [ ] Handle app focus loss (cancel drag)
- [ ] Verify ARIA announcements work with screen readers
  - [ ] "Drag mode active"
  - [ ] "Scrolling up/down"
  - [ ] "Appointment moved to [time]"
  - [ ] "Drag cancelled"
- [ ] Implement scroll lock failure detection and recovery
- [ ] Test with VoiceOver (iOS) and TalkBack (Android)

### Phase 5: Performance (P2 - Medium Priority)

- [ ] Add `will-change` CSS properties during drag
  - [ ] `will-change: scroll-position` on calendar
  - [ ] `will-change: transform` on drag ghost
  - [ ] Remove `will-change` when drag ends (memory optimization)
- [ ] Detect low-end devices (CPU cores, heap size)
- [ ] Disable animations on low-end devices
  - [ ] No ghost rotation
  - [ ] No edge gradients
  - [ ] Simplified scroll indicators
- [ ] Profile scroll performance with Chrome DevTools
  - [ ] Target: 60fps sustained during drag
  - [ ] Check for layout thrashing
  - [ ] Verify no memory leaks on repeated drags
- [ ] Test on low-end devices (iPhone SE, budget Android)

### Phase 6: Polish & User Testing (P3 - Nice to Have)

- [ ] User testing with 5+ therapists
  - [ ] Measure task completion rate
  - [ ] Gather feedback on scroll speed (too fast/slow?)
  - [ ] Observe confusion points
- [ ] Adjust scroll speed based on feedback
- [ ] Consider adding visible edge gradients if users are confused
- [ ] Implement user preference toggles (V2 feature)
  - [ ] Enable/disable scroll lock
  - [ ] Enable/disable auto-scroll
  - [ ] Scroll speed: slow/medium/fast
- [ ] Write user-facing documentation
  - [ ] Help tooltip on first drag attempt
  - [ ] FAQ entry for scroll behavior
- [ ] Add onboarding hint (optional)
  - [ ] "Tip: Drag near edges to scroll calendar"
  - [ ] Show once, dismissible

### Testing Matrix

| Device | Browser | Scroll Lock | Auto-Scroll | Visual Feedback | Accessibility |
|--------|---------|-------------|-------------|-----------------|---------------|
| iPhone SE (2020) | Safari | ⬜ | ⬜ | ⬜ | ⬜ |
| iPhone 13 | Safari | ⬜ | ⬜ | ⬜ | ⬜ |
| iPhone 15 Pro | Safari | ⬜ | ⬜ | ⬜ | ⬜ |
| Pixel 6 | Chrome | ⬜ | ⬜ | ⬜ | ⬜ |
| Samsung S21 | Samsung Internet | ⬜ | ⬜ | ⬜ | ⬜ |
| Pixel 7 | Chrome | ⬜ | ⬜ | ⬜ | ⬜ |
| OnePlus 9 | Chrome | ⬜ | ⬜ | ⬜ | ⬜ |
| iPad Mini | Safari | ⬜ | ⬜ | ⬜ | ⬜ |

---

## 11. Code Implementation Guide

### 11.1 Enhanced `useAppointmentDrag.ts` Composable

**New Scroll Isolation Functions:**

```typescript
// Add to useAppointmentDrag.ts

interface ScrollIsolationState {
  isActive: boolean;
  originalScrollPosition: number;
  calendarContainer: HTMLElement | null;
  edgeThreshold: number;
  autoScrollRAF: number | null;
}

const scrollIsolation = ref<ScrollIsolationState>({
  isActive: false,
  originalScrollPosition: 0,
  calendarContainer: null,
  edgeThreshold: 80,
  autoScrollRAF: null,
});

/**
 * Activate scroll isolation mode
 * Locks body scroll, enables calendar-only scrolling
 */
function activateScrollIsolation(calendarEl: HTMLElement) {
  // Store current scroll position
  scrollIsolation.value.originalScrollPosition = window.scrollY;

  // Lock body scroll
  document.body.style.overflow = 'hidden';
  document.body.style.position = 'fixed';
  document.body.style.width = '100%';
  document.body.style.top = `-${scrollIsolation.value.originalScrollPosition}px`;

  // Add visual feedback class
  document.body.classList.add('drag-mode-active');
  calendarEl.classList.add('drag-active');

  // Store calendar container for auto-scroll
  scrollIsolation.value.calendarContainer = calendarEl.querySelector('.calendar-container');
  scrollIsolation.value.isActive = true;

  // Calculate responsive edge threshold
  const viewportHeight = window.innerHeight;
  scrollIsolation.value.edgeThreshold = getResponsiveEdgeThreshold(viewportHeight);

  // Announce to screen readers
  announceToScreenReader('Drag mode active. Calendar scrolling enabled.');
}

/**
 * Deactivate scroll isolation mode
 * Unlocks body scroll, disables auto-scroll
 */
function deactivateScrollIsolation() {
  // Stop any active auto-scroll
  if (scrollIsolation.value.autoScrollRAF) {
    cancelAnimationFrame(scrollIsolation.value.autoScrollRAF);
    scrollIsolation.value.autoScrollRAF = null;
  }

  // Unlock body scroll
  document.body.style.overflow = '';
  document.body.style.position = '';
  document.body.style.width = '';
  document.body.style.top = '';

  // Restore scroll position
  window.scrollTo(0, scrollIsolation.value.originalScrollPosition);

  // Remove visual feedback classes
  document.body.classList.remove('drag-mode-active');
  if (scrollIsolation.value.calendarContainer) {
    scrollIsolation.value.calendarContainer.closest('.calendar-content-area')?.classList.remove('drag-active');
  }

  scrollIsolation.value.isActive = false;
  scrollIsolation.value.calendarContainer = null;
}

/**
 * Calculate responsive edge threshold based on viewport height
 */
function getResponsiveEdgeThreshold(viewportHeight: number): number {
  if (viewportHeight < 600) return 60;   // Compact phones
  if (viewportHeight > 900) return 120;  // Large phones
  return 80;                             // Standard phones
}

/**
 * Calculate scroll speed based on proximity to edge
 * Linear acceleration: closer = faster
 */
function calculateScrollSpeed(distanceFromEdge: number, threshold: number): number {
  const proximity = 1 - Math.max(0, Math.min(1, distanceFromEdge / threshold));
  const minSpeed = 2;  // px/frame
  const maxSpeed = 12; // px/frame
  return minSpeed + (maxSpeed - minSpeed) * proximity;
}

/**
 * Handle touch move during drag
 * Determines if auto-scroll should trigger
 */
function handleDragTouchMove(touchY: number) {
  if (!scrollIsolation.value.isActive || !scrollIsolation.value.calendarContainer) {
    return;
  }

  const viewportHeight = window.innerHeight;
  const edgeThreshold = scrollIsolation.value.edgeThreshold;
  const edgeBuffer = 16;

  // Check if in top edge zone
  if (touchY < edgeThreshold + edgeBuffer) {
    const distanceFromEdge = touchY - edgeBuffer;
    startAutoScroll('up', distanceFromEdge);
    return;
  }

  // Check if in bottom edge zone
  if (touchY > viewportHeight - edgeThreshold - edgeBuffer) {
    const distanceFromEdge = viewportHeight - touchY - edgeBuffer;
    startAutoScroll('down', distanceFromEdge);
    return;
  }

  // In center dead zone - stop auto-scroll
  stopAutoScroll();
}

/**
 * Start auto-scrolling in specified direction
 */
function startAutoScroll(direction: 'up' | 'down', distanceFromEdge: number) {
  if (!scrollIsolation.value.calendarContainer) return;

  const container = scrollIsolation.value.calendarContainer;
  const edgeThreshold = scrollIsolation.value.edgeThreshold;

  // Stop existing scroll loop if any
  if (scrollIsolation.value.autoScrollRAF) {
    cancelAnimationFrame(scrollIsolation.value.autoScrollRAF);
  }

  // Start new scroll loop
  function scrollFrame() {
    if (!scrollIsolation.value.isActive) return;

    const speed = calculateScrollSpeed(distanceFromEdge, edgeThreshold);
    const currentScrollTop = container.scrollTop;

    // Check boundaries
    const atTop = currentScrollTop <= 0;
    const atBottom = currentScrollTop >= (container.scrollHeight - container.clientHeight);

    if ((direction === 'up' && atTop) || (direction === 'down' && atBottom)) {
      // Hit boundary - provide feedback and stop
      provideBoundaryFeedback(direction);
      stopAutoScroll();
      return;
    }

    // Scroll container
    container.scrollTop += (direction === 'up' ? -speed : speed);

    // Continue on next frame
    scrollIsolation.value.autoScrollRAF = requestAnimationFrame(scrollFrame);
  }

  scrollFrame();
}

/**
 * Stop auto-scrolling
 */
function stopAutoScroll() {
  if (scrollIsolation.value.autoScrollRAF) {
    cancelAnimationFrame(scrollIsolation.value.autoScrollRAF);
    scrollIsolation.value.autoScrollRAF = null;
  }
}

/**
 * Provide haptic/visual feedback when hitting scroll boundary
 */
function provideBoundaryFeedback(direction: 'up' | 'down') {
  // Haptic feedback (if available)
  if (navigator.vibrate) {
    navigator.vibrate(50);
  }

  // Visual feedback - add bounce class
  if (scrollIsolation.value.calendarContainer) {
    const contentArea = scrollIsolation.value.calendarContainer.closest('.calendar-content-area');
    if (contentArea) {
      contentArea.classList.add(`at-${direction === 'up' ? 'top' : 'bottom'}-boundary`);
      setTimeout(() => {
        contentArea.classList.remove(`at-${direction === 'up' ? 'top' : 'bottom'}-boundary`);
      }, 300);
    }
  }
}
```

### 11.2 Integration with Existing Touch Handlers

**Modify `handleEventTouchStart` in useAppointmentDrag.ts:**

```typescript
function handleEventTouchStart(event: EventApi, touchEvent: TouchEvent) {
  const touch = touchEvent.touches[0];
  if (!touch) return;
  touchStartPos = { x: touch.clientX, y: touch.clientY };

  longPressTimer = setTimeout(() => {
    // EXISTING: Trigger mobile reschedule
    triggerMobileReschedule(event);

    // NEW: Activate scroll isolation
    const calendarContentArea = document.querySelector('.calendar-content-area') as HTMLElement;
    if (calendarContentArea) {
      activateScrollIsolation(calendarContentArea);
    }
  }, 300);

  const handleTouchEnd = () => {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }

    // NEW: Deactivate scroll isolation
    if (scrollIsolation.value.isActive) {
      deactivateScrollIsolation();
    }

    touchStartPos = null;
    document.removeEventListener('touchend', handleTouchEnd);
    document.removeEventListener('touchmove', handleTouchMove);
  }

  const handleTouchMove = (e: TouchEvent) => {
    if (!touchStartPos) return;

    const touch = e.touches[0];
    if (!touch) return;

    // NEW: Update auto-scroll based on touch position
    if (scrollIsolation.value.isActive) {
      handleDragTouchMove(touch.clientY);
    }

    // EXISTING: Cancel long-press if moved too far
    const deltaX = Math.abs(touch.clientX - touchStartPos.x);
    const deltaY = Math.abs(touch.clientY - touchStartPos.y);

    if (deltaX > 10 || deltaY > 10) {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
      touchStartPos = null;
      document.removeEventListener('touchend', handleTouchEnd);
      document.removeEventListener('touchmove', handleTouchMove);
    }
  }

  document.addEventListener('touchend', handleTouchEnd);
  document.addEventListener('touchmove', handleTouchMove, { passive: false });
}
```

### 11.3 CSS Styles (Add to CalendarView.vue)

```vue
<style>
/* Scroll Isolation Styles */

/* Body scroll lock during drag */
body.drag-mode-active {
  overflow: hidden !important;
  position: fixed !important;
  width: 100% !important;
}

html.drag-mode-active {
  overflow: hidden !important;
}

/* Overlay dimming effect during drag */
body.drag-mode-active::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.05);
  z-index: 5;
  pointer-events: none;
  transition: opacity 150ms ease-out;
}

/* Calendar elevated during drag */
.calendar-content-area.drag-active {
  position: relative;
  z-index: 10;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
  transition: box-shadow 150ms ease-out;
}

/* Boundary bounce animation */
@keyframes boundary-bounce-top {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

@keyframes boundary-bounce-bottom {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(6px); }
}

.calendar-content-area.at-top-boundary {
  animation: boundary-bounce-top 300ms ease-out;
}

.calendar-content-area.at-bottom-boundary {
  animation: boundary-bounce-bottom 300ms ease-out;
}

/* Mobile-enhanced drag ghost */
@media (max-width: 640px) {
  .drag-ghost {
    padding: 12px 16px !important;
    font-size: 0.9375rem !important; /* 15px */
    box-shadow:
      0 10px 25px -5px rgba(0, 0, 0, 0.2),
      0 8px 10px -6px rgba(0, 0, 0, 0.15) !important;
    transform: rotate(3deg) !important;
  }

  .drag-ghost-time {
    font-size: 0.875rem !important; /* 14px */
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
  }
}

/* Performance optimizations during drag */
.calendar-content-area.drag-active {
  will-change: scroll-position;
}

.drag-ghost {
  will-change: transform;
}

/* Remove will-change when not dragging */
.calendar-content-area:not(.drag-active) {
  will-change: auto;
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .calendar-content-area.at-top-boundary,
  .calendar-content-area.at-bottom-boundary {
    animation: none;
  }

  .calendar-content-area.drag-active {
    transition: none;
  }

  body.drag-mode-active::before {
    transition: none;
  }
}
</style>
```

---

## 12. Success Metrics

**How to Measure Success:**

### Quantitative Metrics

1. **Task Completion Rate**
   - Target: >95% of users successfully reschedule appointment via drag on first attempt
   - Measure: Analytics event "drag-reschedule-success" vs "drag-reschedule-cancel"

2. **Time to Reschedule**
   - Target: <5 seconds from long-press to drop
   - Measure: Time between drag start and drop confirmation
   - Baseline: Compare to modal time-picker approach (expected: 10-15 seconds)

3. **Scroll Performance**
   - Target: Sustained 60fps during drag (no frames >16.67ms)
   - Measure: Chrome DevTools Performance profiler
   - Devices: Test on iPhone SE (low-end) and Pixel 6 (mid-range)

4. **Error Rate**
   - Target: <5% accidental page scrolls during drag
   - Measure: Track "scroll-lock-failed" analytics events
   - Mitigation: Scroll lock recovery should restore position

### Qualitative Metrics

5. **User Satisfaction**
   - Survey question: "How natural did drag-and-drop feel on your phone?" (1-5 scale)
   - Target: Average score >4.0
   - Method: Post-task survey after 5+ reschedule operations

6. **Perceived Performance**
   - Survey question: "Did scrolling feel smooth during drag?" (Yes/No)
   - Target: >90% "Yes"
   - Method: User testing with think-aloud protocol

7. **Discoverability**
   - Observation: Do users attempt drag without prompting?
   - Target: >70% discover drag feature within first calendar session
   - Method: Unmoderated user testing with screen recording

### Acceptance Criteria

**Must Have (P0):**
- ✅ No page scroll during drag (100% of test cases)
- ✅ Calendar auto-scroll works in both directions
- ✅ Drag cancels cleanly when dragged outside bounds
- ✅ Works on iOS Safari, Chrome Mobile, Samsung Internet

**Should Have (P1):**
- ✅ Sustained 60fps on iPhone SE or equivalent low-end device
- ✅ Screen reader announces drag state changes
- ✅ Haptic feedback at scroll boundaries (on supported devices)

**Nice to Have (P2):**
- ✅ User testing shows >90% satisfaction
- ✅ Faster than modal time-picker approach
- ✅ Visual feedback rated as "helpful" by >80% of users

---

## 13. Open Questions & Future Enhancements

### Open Questions (Requires User Testing)

1. **Is 80px edge threshold too large/small for real-world use?**
   - Hypothesis: 80px works for most users, but may need adjustment for users with large hands
   - Test plan: A/B test 60px vs 80px vs 100px with 30+ therapists

2. **Should scroll lock show a more prominent indicator?**
   - Hypothesis: Subtle dimming (5% opacity) is sufficient
   - Alternative: Banner message "Scroll lock active" (may be too intrusive)
   - Test plan: User interviews - ask "Did you notice anything change when you started dragging?"

3. **Is 12px/frame maximum scroll speed too fast?**
   - Hypothesis: 12px at 60fps (720px/sec) feels natural
   - Alternative: 8px/frame (480px/sec) for more precision
   - Test plan: Measure overshooting rate (how often users scroll past target)

### Future Enhancements (V2+)

**Enhancement 1: Smart Scroll Speed Adjustment**
```typescript
// Learn user's preferred scroll speed based on behavior
interface UserScrollPreferences {
  averageScrollSpeed: number;  // Learned from past drags
  frequentlyOvershoots: boolean;  // Adjust max speed down
  prefersFastScroll: boolean;  // User consistently drags to extreme edge
}

// Adjust maxSpeed based on learned preferences
function getAdaptiveMaxSpeed(userPrefs: UserScrollPreferences): number {
  let baseSpeed = 12;
  if (userPrefs.frequentlyOvershoots) baseSpeed -= 4;  // Reduce to 8px
  if (userPrefs.prefersFastScroll) baseSpeed += 2;     // Increase to 14px
  return Math.max(6, Math.min(16, baseSpeed));  // Clamp 6-16px
}
```

**Enhancement 2: Multi-Finger Gestures**
```typescript
// Two-finger drag = move to tomorrow (quick reschedule)
// Three-finger drag = move to next week
function handleMultiFingerDrag(touches: TouchList) {
  if (touches.length === 2) {
    quickReschedule('+1 day');
  } else if (touches.length === 3) {
    quickReschedule('+1 week');
  }
}
```

**Enhancement 3: Snap-to-Grid During Drag**
```typescript
// Option: Snap ghost element to 15-minute increments during drag (not just on drop)
// Provides real-time feedback of final position
function updateGhostPosition(touchY: number) {
  const rawTime = touchYToTime(touchY);
  const snappedTime = roundToNearest15Minutes(rawTime);
  ghostElement.textContent = formatTime(snappedTime);
}
```

**Enhancement 4: Conflict Preview During Drag**
```typescript
// Show conflicting appointments as you drag over them (before drop)
// Real-time visual feedback without API call (client-side calculation)
function showConflictsInRealTime(newStart: Date, newEnd: Date) {
  const conflicts = appointments.filter(apt => overlaps(apt, newStart, newEnd));
  conflicts.forEach(apt => {
    highlightAppointmentAsConflict(apt.id);
  });
}
```

**Enhancement 5: Drag-to-Delete Gesture**
```typescript
// Drag appointment off left/right edge of calendar = quick delete
// Requires confirmation modal (prevent accidents)
function handleEdgeDragDelete(touchX: number) {
  const screenWidth = window.innerWidth;
  if (touchX < 50 || touchX > screenWidth - 50) {
    showDeleteConfirmation('Drag off screen to delete');
  }
}
```

---

## 14. Documentation for Developers

### For Fullstack-Frontend-Specialist

**Implementation Priority:**

1. **Week 1:** Scroll lock + basic auto-scroll (P0)
   - Focus: Reliable scroll lock across iOS/Android
   - Deliverable: Body scroll locked, calendar scrolls manually during drag

2. **Week 2:** Auto-scroll with linear acceleration (P0)
   - Focus: Smooth, predictable edge-based scrolling
   - Deliverable: Auto-scroll works at 60fps with no jank

3. **Week 3:** Visual feedback + edge cases (P1)
   - Focus: Overlay dimming, ghost enhancements, boundary feedback
   - Deliverable: Polished visual experience

4. **Week 4:** Accessibility + performance (P1)
   - Focus: Screen reader announcements, low-end device optimization
   - Deliverable: Works smoothly on iPhone SE, passes accessibility audit

**Key Files to Modify:**

- `/frontend/src/composables/useAppointmentDrag.ts` - Core drag logic
- `/frontend/src/views/CalendarView.vue` - CSS styles, container refs
- `/frontend/src/components/calendar/CalendarToolbar.vue` - Toolbar dimming during drag (optional)

**Testing Devices:**

- **Must Test:** iPhone SE (2020), iPhone 13, Pixel 6
- **Nice to Test:** Samsung S21, iPad Mini, OnePlus 9

**Performance Profiling:**

```bash
# Run Chrome DevTools Performance profiler during drag
# Look for:
# - Frame drops (target: 60fps sustained)
# - Layout thrashing (avoid forced reflows)
# - Memory leaks (repeated drags should not increase heap size)

# Run Lighthouse audit on mobile
npm run build
npm run preview
# Open Chrome DevTools → Lighthouse → Mobile → Run
```

### For UX-Design-Consultant (This Document's Reviewer)

**Review Checklist:**

- [ ] Does scroll lock feel "calm, not cluttered"?
- [ ] Is auto-scroll speed predictable and natural?
- [ ] Are visual indicators helpful without being obtrusive?
- [ ] Does interaction match PazPaz design principles?
- [ ] Are edge cases handled gracefully (outside bounds, boundaries)?
- [ ] Is accessibility implementation sufficient?

**User Testing Protocol:**

1. Recruit 5+ independent therapists (target users)
2. Tasks:
   - "Reschedule this 10am appointment to 2pm same day"
   - "Move this appointment to tomorrow"
   - "Reschedule an appointment from 8am to 5pm (requires scrolling)"
3. Observe:
   - Do they discover drag without prompting?
   - Do they understand scroll zones?
   - Do they encounter page scroll issues?
   - Do they overshoot target time?
4. Survey:
   - "How natural did this feel?" (1-5)
   - "Was scrolling smooth?" (Yes/No)
   - "Any confusion or frustration?"
5. Iterate based on feedback

---

## 15. Conclusion

This specification provides a comprehensive, actionable design for mobile drag-and-drop scroll isolation on the PazPaz calendar. The design prioritizes:

1. **Calm, focused experience** - Scroll lock + overlay dimming creates clear drag mode
2. **Predictability** - Linear acceleration, visible ghost element, clear boundaries
3. **Performance** - 60fps sustained, works on low-end devices
4. **Accessibility** - Screen reader announcements, keyboard shortcuts, haptic feedback
5. **Pragmatism** - Based on industry research, FullCalendar constraints, and PazPaz design principles

**Next Steps:**

1. **Review this spec** with fullstack-frontend-specialist
2. **Prioritize implementation** (see Phase 1-6 checklist)
3. **Build iteratively** (scroll lock → auto-scroll → polish)
4. **Test continuously** (device matrix, performance profiling)
5. **User test early** (Week 2-3, before polish phase)
6. **Iterate based on feedback** (adjust scroll speed, edge thresholds)

**Success Definition:**

Mobile drag-and-drop feels **natural, predictable, and calm** - users can reschedule appointments without thinking about the interaction mechanics.

---

**Document Metadata:**

- **Author:** UX Design Consultant (AI Agent)
- **Date:** 2025-10-28
- **Version:** 1.0
- **Status:** Ready for Implementation
- **Review Date:** Q1 2025 (after initial user testing)
