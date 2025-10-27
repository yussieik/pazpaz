# Mobile Calendar Navigation

## Overview

Mobile-friendly touch gesture navigation for the PazPaz calendar view, allowing therapists to swipe left/right to navigate between calendar periods on mobile devices.

## Features

### 1. Touch Swipe Gestures

- **Swipe Left** → Navigate to next period (day/week/month depending on view)
- **Swipe Right** → Navigate to previous period
- **Minimum Distance Threshold**: 50px swipe distance prevents accidental navigation
- **Works in All Views**: Day view, Week view, Month view

### 2. Responsive Design

- **Mobile (≤640px)**:
  - Arrow navigation buttons hidden
  - Touch swipe gestures enabled
  - Divider between navigation controls hidden

- **Desktop (>640px)**:
  - Arrow navigation buttons visible
  - Swipe gestures still work (if touch-enabled device)
  - Standard click navigation

### 3. Accessibility

- **Reduced Motion Support**: Respects `prefers-reduced-motion` preference
- **Screen Reader Friendly**: Navigation still announced properly
- **Keyboard Navigation**: Existing keyboard shortcuts (arrow keys) remain functional
- **No Text Selection Interference**: Text selection disabled during swipes on mobile

## Implementation

### Composable: `useCalendarSwipe`

Location: `/frontend/src/composables/useCalendarSwipe.ts`

```typescript
import { useCalendarSwipe } from '@/composables/useCalendarSwipe'

// Usage in component
const calendarContainerRef = ref<HTMLElement | null>(null)

useCalendarSwipe(
  calendarContainerRef,  // Element to attach swipe listeners to
  handlePrev,            // Callback for previous navigation
  handleNext             // Callback for next navigation
)
```

**Parameters:**
- `target`: Vue ref to the DOM element (typically calendar container)
- `onPrevious`: Function to call when user swipes right
- `onNext`: Function to call when user swipes left

**Features:**
- Built on `@vueuse/core` `useSwipe` composable
- 50px minimum swipe threshold
- Respects reduced motion preferences
- Passive event listeners for performance
- Only handles horizontal swipes

### Template Integration

```vue
<div ref="calendarContainerRef" class="calendar-container">
  <!-- Calendar content -->
</div>
```

### Styling Considerations

```css
/* Mobile: Prevent text selection during swipes */
@media (max-width: 640px) {
  .calendar-container {
    -webkit-user-select: none;
    user-select: none;
    -webkit-overflow-scrolling: touch;
  }
}

/* Desktop: Re-enable text selection */
@media (min-width: 641px) {
  .calendar-container {
    -webkit-user-select: auto;
    user-select: auto;
  }
}
```

## Files Modified

### 1. `/frontend/src/composables/useCalendarSwipe.ts` (NEW)
- Core swipe gesture logic
- Wraps `@vueuse/core` `useSwipe` with calendar-specific behavior

### 2. `/frontend/src/composables/useCalendarSwipe.spec.ts` (NEW)
- Unit tests for the composable
- Validates initialization and ref handling

### 3. `/frontend/src/views/CalendarView.vue`
- Added import for `useCalendarSwipe`
- Created `calendarContainerRef` to attach swipe listeners
- Initialized composable with navigation callbacks
- Added CSS for mobile touch optimization

### 4. `/frontend/src/components/calendar/CalendarToolbar.vue`
- Hidden arrow buttons on mobile (`hidden sm:flex`)
- Hidden divider on mobile (`hidden sm:block`)
- Maintained full desktop functionality

## User Experience

### Mobile Behavior

1. User opens calendar on mobile device
2. Navigation arrows are hidden (cleaner UI)
3. User can swipe left/right anywhere on calendar to navigate
4. Smooth, natural gesture feels like native mobile app
5. Visual feedback through calendar transition animations
6. Today button remains visible for quick return

### Desktop Behavior

1. Arrow buttons remain visible and functional
2. Swipe gestures still work on touch-enabled devices (2-in-1 laptops, touchscreens)
3. Keyboard shortcuts (arrow keys, T for today) continue working
4. Full mouse-based interaction preserved

## Performance Considerations

- **Passive Event Listeners**: Swipe listeners use passive mode for better scroll performance
- **Minimal DOM Updates**: Only updates when swipe threshold is met
- **No Re-renders**: Composable doesn't cause unnecessary component re-renders
- **Efficient Detection**: Uses `@vueuse/core` optimized gesture detection

## Browser Support

- **Modern Mobile Browsers**: iOS Safari 12+, Chrome Mobile 90+
- **Touch Events**: All modern touch-capable devices
- **Fallback**: Arrow buttons remain for non-touch devices
- **Progressive Enhancement**: Feature works when supported, graceful degradation otherwise

## Testing

### Unit Tests

```bash
npm run test:run -- src/composables/useCalendarSwipe.spec.ts
```

**Test Coverage:**
- Composable initialization
- Null target handling
- Direction object returned

### Manual Testing Checklist

- [ ] Swipe left navigates to next period (week/day/month)
- [ ] Swipe right navigates to previous period
- [ ] Arrow buttons hidden on mobile (≤640px)
- [ ] Arrow buttons visible on desktop (>640px)
- [ ] Divider hidden on mobile
- [ ] Small swipes (<50px) don't trigger navigation
- [ ] Reduced motion preference respected
- [ ] Works in all calendar views (day, week, month)
- [ ] Keyboard shortcuts still work
- [ ] Today button still functional
- [ ] Smooth transitions between periods

## Accessibility Compliance

### WCAG 2.1 AA Compliance

✅ **1.4.13 Content on Hover or Focus**: Swipe gestures don't interfere with hover states
✅ **2.1.1 Keyboard**: Keyboard navigation remains fully functional
✅ **2.2.2 Pause, Stop, Hide**: Respects reduced motion preferences
✅ **2.5.1 Pointer Gestures**: Single-finger swipe is simple gesture, arrow buttons available
✅ **2.5.2 Pointer Cancellation**: Swipe uses standard touch events with proper cancellation
✅ **4.1.3 Status Messages**: Navigation changes announced to screen readers

## Future Enhancements

### Potential Improvements

1. **Visual Swipe Feedback**: Show subtle drag indicator during swipe
2. **Haptic Feedback**: Vibration on successful navigation (iOS/Android)
3. **Custom Threshold**: Allow users to adjust swipe sensitivity in settings
4. **Momentum Scrolling**: Multiple period navigation with fast swipe
5. **Vertical Swipe**: Up/down to change view type (day ↔ week ↔ month)

## Known Limitations

1. **No Visual Feedback During Swipe**: Users don't see preview of next period during gesture
2. **Single Period Navigation**: Each swipe navigates exactly one period (not momentum-based)
3. **Horizontal Only**: Vertical swipes not utilized (could add view switching)
4. **No Undo Gesture**: Swipe navigation can't be undone with reverse gesture

## Related Documentation

- [Calendar View Architecture](/docs/frontend/calendar-view.md)
- [Mobile Responsiveness](/docs/frontend/responsive-design.md)
- [Touch Interaction Patterns](/docs/frontend/touch-patterns.md)
- [Accessibility Guidelines](/docs/frontend/accessibility.md)

## Changelog

### 2025-10-27
- Initial implementation of mobile swipe navigation
- Hidden arrow buttons on mobile devices
- Added `useCalendarSwipe` composable
- Integrated with existing CalendarView component
- Added unit tests and documentation
