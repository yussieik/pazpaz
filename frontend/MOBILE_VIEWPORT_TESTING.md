# Mobile Viewport Testing Guide

## Overview

This guide explains how to test the mobile immersive viewport implementation on real devices and browser dev tools.

## What We're Testing

The viewport optimization uses a **CSS-first approach** with progressive enhancement:

1. **Modern browsers** (iOS Safari 15.4+, Chrome 108+): CSS `100dvh` handles everything automatically
2. **Legacy browsers**: JavaScript fallback via `useImmersiveViewport` composable
3. **Address bar hiding**: Natural browser behavior (no forced scrolling)

## Testing Checklist

### 1. Modern Mobile Browsers (Primary Testing)

**iOS Safari 15.4+ (iPhone/iPad)**

- [ ] App occupies full viewport height on page load
- [ ] Address bar visible on initial page load (expected behavior)
- [ ] Address bar hides smoothly when user scrolls down
- [ ] Address bar reappears when user scrolls to top
- [ ] Viewport adapts correctly when address bar shows/hides
- [ ] No janky 1px scroll on page load (removed in refactor)
- [ ] Safe area insets respected on notched devices (iPhone X+)
- [ ] Orientation change works smoothly (portrait ↔ landscape)

**Chrome Android 108+**

- [ ] App occupies full viewport height on page load
- [ ] Toolbar visible on initial page load (expected behavior)
- [ ] Toolbar hides when user scrolls down
- [ ] Toolbar reappears when user scrolls to top
- [ ] Viewport adapts correctly when toolbar shows/hides
- [ ] No janky 1px scroll on page load (removed in refactor)
- [ ] Orientation change works smoothly (portrait ↔ landscape)

### 2. Legacy Browser Testing (Fallback)

**iOS Safari 14.x - 15.3 (iPhone/iPad)**

- [ ] App occupies full viewport height on page load
- [ ] `--app-height` CSS variable set correctly
- [ ] Viewport updates on resize
- [ ] Viewport updates on orientation change

**Chrome Android 100-107**

- [ ] App occupies full viewport height on page load
- [ ] `--app-height` CSS variable set correctly
- [ ] Viewport updates on resize

### 3. Keyboard Behavior Testing

**iOS Safari**

- [ ] Keyboard opens smoothly without breaking layout
- [ ] Viewport adjusts when keyboard appears
- [ ] Viewport restores when keyboard closes
- [ ] No content hidden behind keyboard

**Chrome Android**

- [ ] Keyboard opens smoothly without breaking layout
- [ ] Viewport adjusts when keyboard appears
- [ ] Viewport restores when keyboard closes
- [ ] No content hidden behind keyboard

### 4. Edge Cases

- [ ] Works correctly when app is added to home screen (PWA mode)
- [ ] Landscape mode works correctly
- [ ] Split-screen mode works correctly (Android)
- [ ] Tablet landscape mode (iPad, Android tablets)
- [ ] Desktop browsers show no issues (no mobile-specific behavior)
- [ ] Rapid orientation changes don't break layout

### 5. Accessibility Testing

- [ ] VoiceOver (iOS) works correctly
- [ ] TalkBack (Android) works correctly
- [ ] Zoom controls work correctly
- [ ] No interference with browser chrome accessibility features
- [ ] Address bar remains accessible to users who need it

## How to Test

### Browser Dev Tools (Initial Testing)

**Chrome DevTools**

1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M / Cmd+Shift+M)
3. Select device preset (e.g., "iPhone 12 Pro")
4. Refresh page
5. Check:
   - Console for `--app-height` value: `getComputedStyle(document.documentElement).getPropertyValue('--app-height')`
   - Viewport height matches device: `window.innerHeight`
   - No forced scroll on load (check scroll position: `window.scrollY` should be 0)

**Firefox DevTools**

1. Open DevTools (F12)
2. Click Responsive Design Mode (Ctrl+Shift+M / Cmd+Opt+M)
3. Select device preset (e.g., "iPhone 12/13 Pro")
4. Refresh page
5. Check same items as Chrome above

### Real Device Testing (Required)

**iOS Safari (Most Important)**

1. **Initial Load Test**
   - Open PazPaz in Safari
   - Observe: Address bar should be visible
   - Observe: App should occupy full viewport height
   - Check: No 1px scroll or jank on page load

2. **Scroll Behavior Test**
   - Scroll down slowly on calendar page
   - Observe: Address bar hides smoothly
   - Scroll to top
   - Observe: Address bar reappears

3. **Orientation Test**
   - Rotate device to landscape
   - Check: Layout adjusts correctly
   - Rotate back to portrait
   - Check: Layout adjusts correctly

4. **Keyboard Test**
   - Tap into a text input (e.g., search client)
   - Observe: Keyboard appears, viewport adjusts
   - Tap outside or close keyboard
   - Observe: Viewport restores

5. **Home Screen App (PWA)**
   - Add to Home Screen
   - Open from home screen
   - Test same behaviors as above

**Chrome Android**

1. Follow same test steps as iOS Safari
2. Pay special attention to toolbar hiding behavior
3. Test split-screen mode if available

### DevTools Console Debugging

```javascript
// Check if dvh is supported
const supportsDvh = CSS.supports('height', '100dvh')
console.log('Browser supports dvh:', supportsDvh)

// Check current --app-height value
const appHeight = getComputedStyle(document.documentElement).getPropertyValue(
  '--app-height'
)
console.log('--app-height:', appHeight)

// Check viewport dimensions
console.log('window.innerHeight:', window.innerHeight)
console.log('window.innerWidth:', window.innerWidth)

// Check scroll position (should be 0 on load with new implementation)
console.log('window.scrollY:', window.scrollY)

// Check safe area insets (iOS only)
const safeAreaTop = getComputedStyle(document.documentElement).getPropertyValue(
  'padding-top'
)
console.log('Safe area top:', safeAreaTop)
```

## Expected Behavior Summary

### Modern Browsers (iOS Safari 15.4+, Chrome 108+)

- ✅ CSS `100dvh` handles viewport adaptation
- ✅ Address bar visible on page load
- ✅ Address bar hides naturally when user scrolls
- ✅ No forced scroll on page load
- ✅ Smooth, native browser behavior

### Legacy Browsers (iOS Safari <15.4, Chrome <108)

- ✅ JavaScript calculates viewport height
- ✅ `--app-height` CSS variable set on mount
- ✅ Updates on resize/orientation change
- ✅ Graceful degradation

### Desktop Browsers

- ✅ No mobile-specific behavior
- ✅ Standard viewport sizing
- ✅ No performance impact

## Common Issues and Solutions

### Issue: Address bar doesn't hide

**Possible Causes:**

- Expected behavior on page load (modern approach)
- Browser version doesn't support dvh
- Content not tall enough to scroll

**Solution:**

- If modern browser: This is expected; address bar hides on user scroll
- If legacy browser: Check console for JavaScript errors
- Ensure content is taller than viewport

### Issue: Layout jumps when address bar hides

**Possible Causes:**

- Using fixed `height` instead of `min-height`
- Not using `100dvh` properly

**Solution:**

- Verify `#app` uses `min-height: var(--app-height)`
- Verify CSS cascade isn't overriding with fixed height

### Issue: Keyboard pushes content off-screen

**Possible Causes:**

- iOS Safari viewport resize behavior
- Fixed positioning issues

**Solution:**

- Use `position: sticky` instead of `position: fixed` where possible
- Ensure input fields have proper focus scrolling

### Issue: Safe area insets not working (iPhone notch)

**Possible Causes:**

- `viewport-fit=cover` not set
- Safe area inset CSS not applied

**Solution:**

- Verify `<meta name="viewport" content="viewport-fit=cover">` in index.html
- Verify `padding-*: env(safe-area-inset-*)` on `#app`

## Browser Support Matrix

| Browser          | Version   | dvh Support | Fallback    | Status    |
| ---------------- | --------- | ----------- | ----------- | --------- |
| iOS Safari       | 15.4+     | ✅ Yes      | N/A         | Primary   |
| iOS Safari       | 14.x-15.3 | ❌ No       | JS fallback | Supported |
| Chrome Android   | 108+      | ✅ Yes      | N/A         | Primary   |
| Chrome Android   | 100-107   | ❌ No       | JS fallback | Supported |
| Firefox Mobile   | 110+      | ✅ Yes      | N/A         | Primary   |
| Firefox Mobile   | <110      | ❌ No       | JS fallback | Supported |
| Samsung Internet | 20+       | ✅ Yes      | N/A         | Primary   |
| Desktop Chrome   | All       | ✅ Yes      | N/A         | Works     |
| Desktop Firefox  | All       | ✅ Yes      | N/A         | Works     |
| Desktop Safari   | All       | ✅ Yes      | N/A         | Works     |

## Performance Testing

### Metrics to Monitor

1. **Page Load Performance**
   - No visible scroll jank on initial load
   - `--app-height` set within 100ms on legacy browsers
   - No layout shift (CLS score)

2. **Runtime Performance**
   - Resize event handlers debounced (100ms delay)
   - No performance impact on scroll
   - No excessive CSS variable updates

3. **Memory Usage**
   - Event listeners properly cleaned up on unmount
   - No memory leaks from resize listeners

### How to Measure

**Chrome DevTools Performance Tab**

1. Start recording
2. Refresh page
3. Scroll up/down
4. Rotate device (in device mode)
5. Stop recording
6. Check for:
   - Layout shifts
   - Long tasks
   - Excessive reflows

**Lighthouse**

1. Run Lighthouse audit (mobile)
2. Check Performance score
3. Check for CLS issues related to viewport

## Regression Testing

When making changes to viewport code, always verify:

- [ ] Unit tests pass: `npm run test:unit useImmersiveViewport.spec.ts`
- [ ] No console errors on page load
- [ ] `window.scrollY === 0` on page load (no forced scroll)
- [ ] Real device testing on iOS Safari and Chrome Android
- [ ] Keyboard behavior unchanged
- [ ] Safe area insets still work on notched devices

## References

- [Web.dev: The large, small, and dynamic viewport units](https://web.dev/viewport-units/)
- [Can I Use: CSS viewport units (dvh, lvh, svh)](https://caniuse.com/viewport-unit-variants)
- [MDN: env(safe-area-inset-\*)](https://developer.mozilla.org/en-US/docs/Web/CSS/env)
- [CSS Tricks: The viewport-fit descriptor](https://css-tricks.com/the-notch-and-css/)
