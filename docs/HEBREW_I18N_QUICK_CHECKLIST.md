# Hebrew i18n Implementation - Quick Checklist

**Reference:** See `/docs/HEBREW_I18N_IMPLEMENTATION_PLAN.md` for detailed implementation steps

---

## Phase 1: Infrastructure Setup ✅ COMPLETE (4-6 hours)

- [x] Install dependencies: `npm install vue-i18n@^10.0.4 @intlify/unplugin-vue-i18n@^5.2.0`
- [x] Configure Vite plugin in `vite.config.ts`
- [x] Create `/src/locales/` directory with `en.json`, `he.json`, `index.ts`
- [x] Create `/src/types/i18n.d.ts` for TypeScript types
- [x] Update `tsconfig.app.json` to include i18n types
- [x] Verify: `npm run dev` and `npm run type-check` pass

**Deliverables Created:**
- `/frontend/src/locales/en.json` - English translations (starter)
- `/frontend/src/locales/he.json` - Hebrew translations (starter)
- `/frontend/src/locales/index.ts` - Locale exports
- `/frontend/src/types/i18n.d.ts` - TypeScript type safety
- `/frontend/vite.config.ts` - Updated with VueI18nPlugin
- `/frontend/tsconfig.app.json` - Updated with vue-i18n types

---

## Phase 2: Core Framework ✅ COMPLETE (8-10 hours)

- [x] Create `/src/plugins/i18n.ts` with locale detection
- [x] Register i18n plugin in `main.ts`
- [x] Create `/src/composables/useI18n.ts` wrapper
- [x] Set document `dir` attribute on app mount
- [x] Create date formatting utility (`useDateFormat`)
- [x] Verify type check passes

**Deliverables Created:**
- `/frontend/src/plugins/i18n.ts` - i18n plugin with locale detection ✅
- `/frontend/src/main.ts` - Updated with i18n plugin registration ✅
- `/frontend/src/composables/useI18n.ts` - Composable with locale switching & RTL ✅
- `/frontend/src/utils/dateFormat.ts` - Locale-aware date formatting ✅

**Features:**
- ✅ Automatic locale detection (localStorage → browser → default)
- ✅ Israeli users get Hebrew by default (he/iw locale)
- ✅ Document direction toggle (LTR/RTL)
- ✅ Locale persistence in localStorage
- ✅ Type-safe translation keys
- ✅ Date formatting with Hebrew locale support

---

## Phase 3: High-Priority Components 🟡 IN PROGRESS (~5/17 complete) ⏱️ 20-25 hours

### Authentication (~105 strings total) ✅ COMPLETE
- [x] LoginView (~50 strings) ✅ Complete
- [x] AuthVerifyView (~20 strings) ✅ Complete
- [x] SessionExpirationModal (~15 strings) ✅ Complete
- [x] SessionExpirationBanner (~5 strings) ✅ Complete
- [x] LogoutConfirmationModal (~12 strings) ✅ Complete

### Calendar (~150 strings)
- [ ] CalendarView
- [ ] AppointmentFormModal
- [ ] AppointmentDetailsModal
- [x] CalendarToolbar (~14 strings) ✅ Complete
- [ ] CancelAppointmentDialog
- [ ] DragConflictModal
- [ ] MobileRescheduleModal

### Clients (~100 strings)
- [ ] ClientsView
- [ ] ClientFormModal
- [ ] ClientDetailView
- [ ] ClientCombobox
- [ ] ClientQuickAddForm

---

## Phase 4: Medium-Priority Components ⏱️ 15-20 hours

### Sessions (~80 strings)
- [ ] SessionView
- [ ] SessionEditor
- [ ] PreviousSessionPanel
- [ ] SessionAttachments

### Settings (~60 strings)
- [ ] SettingsLayout
- [ ] SettingsSidebar
- [ ] NotificationsView
- [ ] IntegrationsView
- [ ] **Add language switcher to Settings**

### Common (~40 strings)
- [ ] AppNavigation
- [ ] PageHeader
- [ ] EmptyState
- [ ] AutosaveBanner
- [ ] RateLimitBanner

---

## Phase 5: Low-Priority Components ⏱️ 10-15 hours

### Payments (~30 strings)
- [ ] PaymentsView
- [ ] PaymentDetailsForm

### Admin (~40 strings)
- [ ] PlatformAdminPage
- [ ] WorkspaceDetailsModal

### Modals (~30 strings)
- [ ] SessionTimeoutModal
- [ ] DeleteAppointmentModal
- [ ] ImagePreviewModal
- [ ] PDFPreviewModal

---

## Phase 6: Third-Party Libraries ⏱️ 6-8 hours

### FullCalendar
- [ ] Import Hebrew locale in `useCalendar.ts`
- [ ] Configure Sunday week start for Hebrew
- [ ] Set 24-hour time format for Hebrew
- [ ] Test RTL calendar layout

### date-fns
- [ ] Create `/src/utils/dateFormat.ts` with Hebrew locale support
- [ ] Replace all `format()` calls with `useDateFormat()`
- [ ] Test Hebrew date formatting

---

## Phase 7: Testing & QA ⏱️ 12-15 hours

### Translation Coverage
- [ ] Check console for missing translation warnings
- [ ] Search for hardcoded English strings: `grep -r "Email\|Save\|Cancel" src/components --include="*.vue"`
- [ ] Verify 100% translation coverage

### RTL Layout
- [ ] Test all views in RTL mode
- [ ] Screenshot comparison (LTR vs RTL)
- [ ] Check for CSS physical properties: `grep -r "margin-left\|margin-right" src`
- [ ] Test icon mirroring (arrows, chevrons)

### Date/Time
- [ ] Verify Hebrew date formatting
- [ ] Verify 24-hour time format
- [ ] Verify Sunday week start

### Accessibility
- [ ] Test Hebrew screen readers (NVDA, VoiceOver)
- [ ] Test keyboard navigation in RTL
- [ ] Verify `lang="he"` attribute set

### Performance
- [ ] Measure bundle size impact (`npm run build`)
- [ ] Test initial load time (TTI, FCP)
- [ ] Accept <5% performance degradation

### Edge Cases
- [ ] Test mixed LTR/RTL content (emails, names)
- [ ] Test locale switching mid-session
- [ ] Test fallback for missing translations

---

## Quick Commands Reference

```bash
# Install dependencies
cd frontend
npm install vue-i18n@^10.0.4 @intlify/unplugin-vue-i18n@^5.2.0

# Create directory structure
mkdir -p src/locales src/plugins src/utils

# Search for hardcoded strings
grep -r "Email\|Password\|Save\|Cancel\|Delete" src/components --include="*.vue" | grep -v "t('" | grep -v "//"

# Search for CSS physical properties
grep -r "margin-left\|margin-right\|padding-left\|padding-right\|text-align: left\|text-align: right" src --include="*.vue" --include="*.css"

# Build and check bundle size
npm run build
ls -lh dist/assets/*.js

# Type check
npm run type-check

# Run dev server
npm run dev
```

---

## Translation Key Naming Convention

```
{domain}.{feature}.{component}.{element}

Examples:
auth.login.title
auth.login.emailLabel
calendar.appointment.create
calendar.appointment.edit
common.actions.save
common.status.loading
sessions.soap.subjectiveLabel
```

---

## RTL CSS Quick Reference

```css
/* Physical → Logical */
margin-left → margin-inline-start
margin-right → margin-inline-end
padding-left → padding-inline-start
padding-right → padding-inline-end
text-align: left → text-align: start
text-align: right → text-align: end
float: left → float: inline-start
float: right → float: inline-end

/* Tailwind utilities (automatic) */
ml-4 → ms-4 (margin-inline-start)
mr-4 → me-4 (margin-inline-end)
text-left → text-start
```

---

## Icon Mirroring Pattern

```vue
<template>
  <IconChevronRight :class="{ 'scale-x-[-1]': isRTL }" />
</template>

<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
const { isRTL } = useI18n()
</script>
```

---

## Locale Switcher (Settings Page)

```vue
<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
const { locale, setLocale, t } = useI18n()
</script>

<template>
  <div class="settings-section">
    <h3>{{ t('settings.language.title') }}</h3>

    <label class="flex items-center gap-3">
      <input
        type="radio"
        value="en"
        :checked="locale === 'en'"
        @change="setLocale('en')"
      />
      <span>English</span>
    </label>

    <label class="flex items-center gap-3">
      <input
        type="radio"
        value="he"
        :checked="locale === 'he'"
        @change="setLocale('he')"
      />
      <span>עברית (Hebrew)</span>
    </label>
  </div>
</template>
```

---

## Progress Tracking

**Total Estimated Time:** 75-99 hours

| Phase | Hours | Status |
|-------|-------|--------|
| Phase 1: Infrastructure | 4-6 | ⬜ |
| Phase 2: Core Framework | 8-10 | ⬜ |
| Phase 3: High-Priority | 20-25 | ⬜ |
| Phase 4: Medium-Priority | 15-20 | ⬜ |
| Phase 5: Low-Priority | 10-15 | ⬜ |
| Phase 6: Third-Party | 6-8 | ⬜ |
| Phase 7: Testing & QA | 12-15 | ⬜ |

**Legend:** ⬜ Not Started | 🟡 In Progress | ✅ Complete

---

## Verification Commands

```bash
# Check for missing translations (run app in dev mode)
# Look for: [vue-i18n] Not found 'key' in 'he' locale messages

# Type safety check
npm run type-check

# Build verification
npm run build

# Lint check
npm run lint
```

---

**Last Updated:** 2025-11-03
