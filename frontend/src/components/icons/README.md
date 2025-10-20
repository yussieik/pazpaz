# Icon Components

Reusable SVG icon components for consistent iconography across the application.

## Usage

```vue
<script setup lang="ts">
import IconClose from '@/components/icons/IconClose.vue'
import IconCheck from '@/components/icons/IconCheck.vue'
import IconTrash from '@/components/icons/IconTrash.vue'
</script>

<template>
  <!-- Default size (h-5 w-5) -->
  <IconClose />

  <!-- Custom size and color -->
  <IconCheck class="h-4 w-4 text-emerald-600" />

  <!-- In buttons -->
  <button>
    <IconTrash class="h-4 w-4" />
    Delete
  </button>
</template>
```

## Available Icons

- **IconCalendar** - Calendar icon
- **IconCheck** - Checkmark icon
- **IconChevronLeft** - Left arrow
- **IconChevronRight** - Right arrow
- **IconClock** - Clock/time icon
- **IconClose** - X/close icon
- **IconCopy** - Copy to clipboard icon
- **IconDocument** - Document/file icon
- **IconTrash** - Delete/trash icon
- **IconWarning** - Warning/alert icon
- **IconXCircle** - X in circle (error/remove icon)

## Props

All icon components accept a `class` prop:

- **class** (string): CSS classes for the SVG element. Default: `"h-5 w-5"`

## Benefits

1. **Consistency** - All icons use the same stroke width and styling
2. **Maintainability** - Update icon in one place, changes everywhere
3. **Type Safety** - TypeScript props for class customization
4. **Performance** - Smaller bundle size vs. icon libraries
5. **Accessibility** - Icons inherit `currentColor` for proper contrast

## Adding New Icons

1. Create a new `.vue` file in this directory
2. Follow the naming convention: `Icon{Name}.vue`
3. Use the same prop interface as existing icons
4. Add to this README

## Migration from Inline SVGs

When refactoring, replace inline SVG tags:

```diff
- <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
-   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
-     d="M6 18L18 6M6 6l12 12" />
- </svg>
+ <IconClose class="h-5 w-5" />
```
