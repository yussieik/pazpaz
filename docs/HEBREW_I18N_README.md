# Hebrew Internationalization (i18n) - Documentation Index

**Status:** Planning Complete - Ready for Implementation
**Last Updated:** 2025-11-03

---

## Quick Start

**New to this project?** Start here:

1. **Read the Implementation Plan** → `/docs/HEBREW_I18N_IMPLEMENTATION_PLAN.md`
2. **Use the Quick Checklist** → `/docs/HEBREW_I18N_QUICK_CHECKLIST.md`
3. **Reference Medical Terms** → `/docs/HEBREW_MEDICAL_TERMINOLOGY_GUIDE.md`

---

## Documentation Overview

### 📋 [HEBREW_I18N_IMPLEMENTATION_PLAN.md](HEBREW_I18N_IMPLEMENTATION_PLAN.md)

**Purpose:** Comprehensive step-by-step implementation guide

**Length:** ~1,700 lines

**Contents:**
- 7 implementation phases with detailed tasks
- Code examples for every pattern
- Verification steps for each task
- Time estimates per phase
- RTL CSS conversion guide
- TypeScript configuration
- Testing strategies

**Use this when:**
- Starting implementation
- Need detailed technical specs
- Writing code (has before/after examples)
- Troubleshooting issues

---

### ✅ [HEBREW_I18N_QUICK_CHECKLIST.md](HEBREW_I18N_QUICK_CHECKLIST.md)

**Purpose:** Quick reference checklist for implementation progress

**Length:** ~300 lines

**Contents:**
- Phase-by-phase checkboxes
- Component translation checklist
- Quick command reference
- CSS conversion patterns
- Progress tracking table

**Use this when:**
- Tracking daily progress
- Need quick commands
- Checking completion status
- Quick reference during development

---

### 🏥 [HEBREW_MEDICAL_TERMINOLOGY_GUIDE.md](HEBREW_MEDICAL_TERMINOLOGY_GUIDE.md)

**Purpose:** Professional Hebrew medical terminology reference

**Length:** ~450 lines

**Contents:**
- SOAP note terminology
- Clinical terms (therapy types, body parts)
- UI-specific translations
- Business/payment terms
- Error messages
- Time-related terms
- Professional translation notes

**Use this when:**
- Translating clinical features
- Need professional medical terms
- Unsure about Hebrew terminology
- Writing translation files (en.json → he.json)

**Important:** Requires professional medical translator review before production.

---

## Implementation Phases Summary

### Phase 1: Infrastructure Setup (4-6 hours)
Install vue-i18n, configure Vite plugin, create locale files, set up TypeScript types.

**Deliverables:**
- `package.json` with vue-i18n dependencies
- `vite.config.ts` with i18n plugin
- `/src/locales/` directory with JSON files
- TypeScript type definitions

### Phase 2: Core Framework (8-10 hours)
Initialize i18n plugin, create composable, implement locale detection and persistence.

**Deliverables:**
- `/src/plugins/i18n.ts`
- `/src/composables/useI18n.ts`
- Document direction updates
- localStorage persistence

### Phase 3: High-Priority Components (20-25 hours)
Translate authentication, calendar, and client management (most critical user flows).

**Components:**
- LoginView, AuthVerifyView
- CalendarView, AppointmentFormModal
- ClientsView, ClientFormModal

### Phase 4: Medium-Priority Components (15-20 hours)
Translate session documentation, settings, common components.

**Components:**
- SessionView, SessionEditor
- SettingsLayout, NotificationsView
- AppNavigation, EmptyState

### Phase 5: Low-Priority Components (10-15 hours)
Translate remaining views, modals, edge cases.

**Components:**
- PaymentsView, PlatformAdminPage
- Modals (timeout, delete, preview)

### Phase 6: Third-Party Libraries (6-8 hours)
Configure FullCalendar and date-fns for Hebrew locale.

**Tasks:**
- Import Hebrew locale for FullCalendar
- Configure Sunday week start
- Set 24-hour time format
- Create date formatting utility

### Phase 7: Testing & QA (12-15 hours)
Comprehensive testing of translations, RTL layouts, accessibility.

**Tests:**
- Translation coverage
- RTL layout verification
- Date/time formatting
- Screen reader testing
- Performance benchmarks

**Total Time:** 75-99 hours (single developer, 2-4 weeks)

---

## Key Technical Decisions

### Technology Stack

```json
{
  "i18n-library": "vue-i18n@^10.0.4",
  "build-plugin": "@intlify/unplugin-vue-i18n@^5.2.0",
  "date-localization": "date-fns@^4.1.0 (existing)",
  "calendar-localization": "@fullcalendar/core@^6.1.19 (existing, includes Hebrew)"
}
```

### RTL Strategy

**Use CSS Logical Properties exclusively:**

```css
/* ❌ Physical properties */
margin-left: 1rem;
text-align: left;

/* ✅ Logical properties */
margin-inline-start: 1rem;
text-align: start;
```

**Tailwind CSS v4** (via `@tailwindcss/postcss`) automatically converts directional utilities to logical properties. No configuration needed.

### Locale Detection Priority

1. **localStorage** (user explicitly changed language)
2. **Browser locale** (`navigator.language`)
3. **Default to English**

**Israeli users** (browser locale = `he` or `he-IL`) automatically get Hebrew.

### Translation Key Structure

```
{domain}.{feature}.{component}.{element}

Examples:
- auth.login.title
- calendar.appointment.create
- common.actions.save
- sessions.soap.subjectiveLabel
```

### Type Safety

**TypeScript auto-generates types from `en.json`:**

```typescript
// This will error if key doesn't exist in en.json
t('auth.login.title') // ✅ Valid
t('auth.login.typo')  // ❌ TypeScript error
```

---

## Common Patterns

### Component Translation Pattern

```vue
<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
const { t } = useI18n()
</script>

<template>
  <h2>{{ t('auth.login.title') }}</h2>
  <button>{{ t('common.actions.save') }}</button>
</template>
```

### Date Formatting Pattern

```vue
<script setup lang="ts">
import { useDateFormat } from '@/utils/dateFormat'
const { formatDate } = useDateFormat()

const formattedDate = computed(() =>
  formatDate(appointment.value.start, 'PPP')
)
</script>

<template>
  <span>{{ formattedDate }}</span>
  <!-- English: "January 5, 2025" -->
  <!-- Hebrew: "5 בינואר 2025" -->
</template>
```

### RTL Icon Mirroring

```vue
<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
const { isRTL } = useI18n()
</script>

<template>
  <IconChevronRight :class="{ 'scale-x-[-1]': isRTL }" />
</template>
```

---

## Verification Commands

```bash
# Install dependencies
cd frontend
npm install vue-i18n@^10.0.4 @intlify/unplugin-vue-i18n@^5.2.0

# Type check
npm run type-check

# Build and check bundle size
npm run build
ls -lh dist/assets/*.js

# Search for hardcoded strings
grep -r "Email\|Save\|Cancel" src/components --include="*.vue" | grep -v "t('"

# Search for CSS physical properties
grep -r "margin-left\|margin-right" src --include="*.vue"
```

---

## Critical Notes

### Before Starting Implementation

- [ ] Review all three documentation files
- [ ] Understand RTL CSS principles
- [ ] Install required dependencies
- [ ] Set up translation review process

### During Implementation

- [ ] Follow phases sequentially (don't skip Phase 1-2)
- [ ] Test locale switching after each component
- [ ] Verify RTL layout after each view
- [ ] Check console for missing translation warnings

### Before Production Deployment

- [ ] **REQUIRED:** Professional medical translator review
- [ ] **REQUIRED:** Licensed therapist terminology verification
- [ ] **REQUIRED:** Hebrew native speaker UX review
- [ ] Complete all Phase 7 testing tasks
- [ ] Verify 100% translation coverage

---

## Translation Workflow

### Step 1: Extract Strings

Identify all hardcoded strings in component:

```vue
<!-- Before -->
<button>Save Changes</button>
```

### Step 2: Add to en.json

```json
{
  "settings": {
    "profile": {
      "saveButton": "Save Changes"
    }
  }
}
```

### Step 3: Translate to Hebrew (he.json)

```json
{
  "settings": {
    "profile": {
      "saveButton": "שמור שינויים"
    }
  }
}
```

**Use Medical Terminology Guide for professional terms.**

### Step 4: Update Component

```vue
<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
const { t } = useI18n()
</script>

<template>
  <button>{{ t('settings.profile.saveButton') }}</button>
</template>
```

### Step 5: Verify

1. Switch to Hebrew in Settings
2. Verify button shows "שמור שינויים"
3. Check console for warnings
4. Test RTL layout

---

## Troubleshooting

### Missing Translation Warning

**Symptom:** Console shows `[vue-i18n] Not found 'key' in 'he' locale messages`

**Fix:**
1. Check if key exists in `en.json`
2. Add corresponding key to `he.json`
3. Verify JSON syntax is valid

### RTL Layout Broken

**Symptom:** Layout doesn't flip correctly in RTL mode

**Fix:**
1. Search for physical CSS properties: `grep -r "margin-left" src/`
2. Convert to logical properties
3. Test with `<html dir="rtl">`

### Date Format Not Hebrew

**Symptom:** Dates still show in English

**Fix:**
1. Verify using `useDateFormat()` composable (not raw `format()`)
2. Check locale is set correctly: `console.log(locale.value)`
3. Verify date-fns Hebrew locale imported

### TypeScript Errors on t('key')

**Symptom:** TypeScript complains about translation key

**Fix:**
1. Verify key exists in `en.json`
2. Rebuild TypeScript: `npm run type-check`
3. Restart VS Code TypeScript server

---

## Success Metrics

### Translation Coverage

- [ ] 100% of UI strings translated
- [ ] Zero console warnings in Hebrew mode
- [ ] All forms, buttons, labels in Hebrew

### RTL Layout Quality

- [ ] No horizontal scrollbars in RTL mode
- [ ] Navigation menus mirror correctly
- [ ] Form layouts align properly
- [ ] Icons mirror where appropriate

### Performance

- [ ] Bundle size increase <15KB
- [ ] Initial load time degradation <5%
- [ ] No runtime performance issues

### Accessibility

- [ ] Hebrew screen readers work correctly
- [ ] Keyboard navigation works in RTL
- [ ] ARIA labels translated

---

## Resources

### External Documentation

- [vue-i18n Official Docs](https://vue-i18n.intlify.dev/)
- [CSS Logical Properties MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Logical_Properties)
- [date-fns Locales](https://date-fns.org/docs/Locale)
- [FullCalendar Localization](https://fullcalendar.io/docs/locales)

### Israeli Healthcare Standards

- Israeli Ministry of Health terminology guidelines
- Israeli Medical Association (IMA) resources
- Hebrew medical dictionaries

### Professional Services

Consider hiring:
- **Medical translator** (Hebrew ↔ English)
- **Licensed Israeli therapist** (terminology review)
- **Hebrew UX copywriter** (UI text review)

---

## Next Steps

1. **Review all documentation** (this README + 3 guides)
2. **Set up development environment** (install dependencies)
3. **Start Phase 1** (Infrastructure Setup)
4. **Track progress** using Quick Checklist
5. **Reference Medical Terminology Guide** during translation
6. **Complete all 7 phases** sequentially
7. **Professional review** before production

---

## Questions or Issues?

**Documentation unclear?** Open an issue with specific questions.

**Found a bug in the plan?** Submit a correction with suggested fix.

**Need clarification on medical terms?** Consult with licensed healthcare professional.

---

**Prepared By:** Frontend Specialist
**Date:** 2025-11-03
**Status:** ✅ Documentation Complete - Ready for Implementation

---

## File Locations

All documentation files are in `/docs/`:

```
docs/
├── HEBREW_I18N_README.md                    # ← You are here
├── HEBREW_I18N_IMPLEMENTATION_PLAN.md       # Detailed technical guide
├── HEBREW_I18N_QUICK_CHECKLIST.md           # Progress tracker
└── HEBREW_MEDICAL_TERMINOLOGY_GUIDE.md      # Translation reference
```

---

**Total Documentation:** 2,442 lines across 4 files

**Estimated Implementation Time:** 75-99 hours (2-4 weeks, single developer)

**Next Action:** Begin Phase 1 - Infrastructure Setup
