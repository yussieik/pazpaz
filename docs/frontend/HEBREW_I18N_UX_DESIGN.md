# Hebrew i18n UX Design Guide

**Document Status:** Design Specification
**Created:** 2025-11-03
**Target Users:** Israeli independent therapists
**Product:** PazPaz Practice Management

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Philosophy](#design-philosophy)
3. [Language Switcher Design](#language-switcher-design)
4. [Default Language Strategy](#default-language-strategy)
5. [RTL Layout Considerations](#rtl-layout-considerations)
6. [Translation Fallback Strategy](#translation-fallback-strategy)
7. [Professional Terminology](#professional-terminology)
8. [Date, Time & Number Formatting](#date-time--number-formatting)
9. [Feature Rollout Strategy](#feature-rollout-strategy)
10. [Accessibility Considerations](#accessibility-considerations)
11. [Implementation Checklist](#implementation-checklist)

---

## Executive Summary

PazPaz is implementing bilingual support (English/Hebrew) to serve Israeli therapists who are the primary target market. The implementation must maintain the app's core design principle of **calm, professional simplicity** while respecting Israeli cultural norms and Hebrew typography.

**Key Decisions:**
- **Hebrew is the default language** for new Israeli users (browser locale detection)
- **Language switcher in Settings** (not global nav) — minimal visual noise
- **Full translation required before launch** — no partial rollout
- **Professional Hebrew terminology** with English fallback for clinical terms where appropriate
- **24-hour time format** and Israeli date standards (DD/MM/YYYY)
- **Sunday as week start** in Hebrew mode
- **Graceful fallback to English** for missing translations (dev mode only)

---

## Design Philosophy

### Core Principles for Hebrew i18n

**1. Calm, Not Cluttered**
- Language switcher should be **discoverable but not prominent**
- No flag icons (culturally sensitive) — use text labels only
- RTL flip should feel seamless, not jarring

**2. Respect Cultural Context**
- Hebrew is the primary language for Israeli therapists
- English is the fallback/technical documentation language
- Professional medical terminology may stay in English when Hebrew equivalents are uncommon

**3. Speed & Responsiveness**
- Locale changes take effect **instantly** without page reload
- Translations cached in localStorage to avoid lookup delays
- No loading spinners for language switches

**4. Trustworthy & Professional**
- Hebrew typography must be clean and readable (system font stack)
- Clinical terms translated by native Hebrew speakers with medical background
- Date/time formats match Israeli government standards

**5. Progressive Enhancement**
- RTL support already exists via `v-rtl` directive (auto text direction)
- Browser locale detection with manual override
- Works gracefully if user disables localStorage

---

## Language Switcher Design

### Placement: Settings Page Only

**Rationale:**
- PazPaz emphasizes **minimal navigation clutter**
- Israeli users expect language settings in app preferences (not global nav)
- Reduces cognitive load on main interfaces (Calendar, Clients, Sessions)

**Visual Design:**

```
┌─────────────────────────────────────────────────────────┐
│  Settings                                               │
│                                                         │
│  General Settings                                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Language / שפה                                  │   │
│  │  ┌─────────────────────────────────────────┐    │   │
│  │  │ ○ English                               │    │   │
│  │  │ ● עברית (Hebrew)                        │    │   │
│  │  └─────────────────────────────────────────┘    │   │
│  │  Changes apply immediately                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Component Specification:**

```vue
<!-- Settings Page: Language Section -->
<SettingsCard>
  <template #title>{{ t('settings.language.title') }}</template>
  <template #description>
    {{ t('settings.language.description') }}
  </template>

  <div class="space-y-3">
    <label class="flex items-center gap-3 rounded-md border border-gray-200 px-4 py-3 hover:bg-gray-50 cursor-pointer">
      <input
        type="radio"
        name="language"
        value="en"
        v-model="selectedLocale"
        @change="changeLocale"
        class="h-4 w-4 text-emerald-600 focus:ring-emerald-500"
      />
      <span class="text-sm font-medium text-gray-900">English</span>
    </label>

    <label class="flex items-center gap-3 rounded-md border border-gray-200 px-4 py-3 hover:bg-gray-50 cursor-pointer">
      <input
        type="radio"
        name="language"
        value="he"
        v-model="selectedLocale"
        @change="changeLocale"
        class="h-4 w-4 text-emerald-600 focus:ring-emerald-500"
      />
      <span class="text-sm font-medium text-gray-900">עברית (Hebrew)</span>
    </label>
  </div>

  <p class="mt-2 text-xs text-gray-500">
    {{ t('settings.language.changeNote') }}
  </p>
</SettingsCard>
```

**Interaction Behavior:**
- Radio button group (mutually exclusive)
- **Instant application** — no "Save" button needed
- Persist to `localStorage` (`pazpaz_locale`)
- Show subtle toast: "Language changed to Hebrew" / "שפה שונתה לעברית"

**Accessibility:**
- Keyboard navigable (arrow keys between options)
- Screen reader announces: "Language selection. English, not selected. Hebrew, selected."
- Focus ring on radio inputs (emerald-500)

---

## Default Language Strategy

### Locale Detection Logic

**On First Visit (no stored preference):**

```typescript
function detectDefaultLocale(): 'en' | 'he' {
  // 1. Check localStorage first (returning user)
  const stored = localStorage.getItem('pazpaz_locale')
  if (stored === 'en' || stored === 'he') {
    return stored
  }

  // 2. Detect browser locale
  const browserLocale = navigator.language || navigator.languages?.[0] || 'en'

  // 3. Hebrew detection (he, he-IL, iw, iw-IL)
  if (browserLocale.startsWith('he') || browserLocale.startsWith('iw')) {
    return 'he'
  }

  // 4. Default to English for all other locales
  return 'en'
}
```

**Why Hebrew as Default for Israeli Users:**
- Target market is 95%+ Israeli therapists
- Browser locale `he-IL` is strong signal of Hebrew preference
- Reduces friction: no need to switch language on first use
- Matches expectation for Israeli-focused product

**No Onboarding Language Selection:**
- Auto-detection is accurate enough (browser locale)
- Users can change in Settings if needed
- Avoids extra modal/step during signup flow

---

## RTL Layout Considerations

### Current RTL Support

PazPaz already has the `v-rtl` directive for **auto text direction**:

```typescript
// directives/rtl.ts
// Sets dir="auto" on text inputs for bidirectional text
```

**This handles text inputs but NOT full layout flip.**

### Full RTL Layout Implementation

**What Changes in RTL Mode:**

| Element | LTR | RTL | Implementation |
|---------|-----|-----|----------------|
| **Navigation Sidebar** | Left-aligned | Right-aligned | CSS `[dir="rtl"] .sidebar { right: 0 }` |
| **Text Alignment** | Left | Right | CSS `[dir="rtl"] { text-align: right }` |
| **Padding/Margin** | `padding-left` | `padding-right` | Use logical properties: `padding-inline-start` |
| **Icons (Directional)** | → | ← | Mirror chevrons, arrows via CSS `transform: scaleX(-1)` |
| **Icons (Non-Directional)** | No change | No change | Calendar, clock, settings stay the same |
| **Calendar Week Start** | Sunday or Monday | **Sunday** | Israeli standard |
| **Form Labels** | Left | Right | Auto via `text-align: right` |

**CSS Strategy:**

Use Tailwind's **logical properties** where possible:

```css
/* Instead of this: */
.element {
  margin-left: 1rem;  /* LTR-specific */
}

/* Use this: */
.element {
  margin-inline-start: 1rem;  /* Auto-adapts to RTL */
}
```

**HTML `dir` Attribute:**

Set `dir` on `<html>` element based on locale:

```vue
<!-- App.vue setup -->
<script setup>
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

watch(locale, (newLocale) => {
  document.documentElement.dir = newLocale === 'he' ? 'rtl' : 'ltr'
  document.documentElement.lang = newLocale
}, { immediate: true })
</script>
```

### Icons That Need Mirroring

**Mirror in RTL:**
- Chevron right (`IconChevronRight`) → chevron left
- Arrow right/left in navigation
- "Back" button arrows

**Do NOT Mirror:**
- Calendar icon
- Clock icon
- Close (X) icon
- Checkmark
- Warning/error icons
- Calendar grid layout (dates)

**Implementation:**

```vue
<!-- IconChevronRight.vue -->
<svg
  :class="['transition-transform', { 'rtl:scale-x-[-1]': true }]"
  ...
>
```

Or via Tailwind CSS:

```html
<IconChevronRight class="rtl:scale-x-[-1]" />
```

### Calendar Week Start

**Israeli Standard: Sunday**

When locale is Hebrew (`he`), calendar week starts on **Sunday** (יום ראשון).

```typescript
// composables/useCalendar.ts
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()
const weekStartsOn = computed(() => locale.value === 'he' ? 0 : 1)
// 0 = Sunday (Israeli), 1 = Monday (International)
```

**Calendar Header:**

```
Hebrew Mode:
ראשון | שני | שלישי | רביעי | חמישי | שישי | שבת
(Sun)  (Mon) (Tue)   (Wed)   (Thu)  (Fri) (Sat)

English Mode:
Mon | Tue | Wed | Thu | Fri | Sat | Sun
```

---

## Translation Fallback Strategy

### Production: Full Translation Required

**Before launching Hebrew support:**
- ✅ All ~500 strings must be translated
- ✅ QA review by native Hebrew speaker with medical background
- ✅ No partial translation (no "half English, half Hebrew" UI)

**No visible fallback in production:**
- If translation missing → log error to console + Sentry
- Display English fallback **only in development mode**

### Development: Visible Fallback

**During development, show missing translations clearly:**

```typescript
// i18n config (dev mode only)
const i18n = createI18n({
  locale: 'he',
  fallbackLocale: 'en',
  missingWarn: true,  // Warn in console
  fallbackWarn: true,
  missing: (locale, key) => {
    // Dev mode: show key in UI for visibility
    if (import.meta.env.DEV) {
      console.warn(`Missing translation: ${locale}.${key}`)
      return `[MISSING: ${key}]`
    }
    // Production: silent fallback to English
    return undefined
  }
})
```

**Why No Partial Rollout:**
- Mixed language UI is confusing and unprofessional
- Therapists need consistency for trust
- Better to delay launch than ship partial translation
- Israeli users expect fully Hebrew-ized apps

---

## Professional Terminology

### Clinical Terms: Translation Guidelines

**Principle:** Use **Hebrew equivalents when common in Israeli medical practice**; keep English when Hebrew term is rare or ambiguous.

| English Term | Hebrew Translation | Decision | Rationale |
|--------------|-------------------|----------|-----------|
| **Client** | **לקוח/ה** (lako'ach/laka'chat) | ✅ Translate | Standard in Israeli therapy |
| **Patient** | **מטופל/ת** (metupel/metupelet) | ✅ Translate (alternative) | Common in physio/medical |
| **Appointment** | **תור** (tor) | ✅ Translate | Universal in Hebrew |
| **Session** | **פגישה** (pgisha) or **טיפול** (tipul) | ✅ Translate | "פגישה" for psychotherapy, "טיפול" for physical therapy |
| **SOAP Notes** | **SOAP** (keep acronym) + explanation | ⚠️ Hybrid | SOAP is international standard; explain in Hebrew: "רישום מובנה (SOAP)" |
| **Subjective** | **סובייקטיבי** (sub'yektivi) | ✅ Translate | Hebrew medical term exists |
| **Objective** | **אובייקטיבי** (ob'yektivi) | ✅ Translate | Hebrew medical term exists |
| **Assessment** | **הערכה** (ha'aracha) | ✅ Translate | Common term |
| **Plan** | **תכנית טיפול** (tochnit tipul) | ✅ Translate | Standard |
| **Calendar** | **לוח שנה** (luach shana) | ✅ Translate | Common |
| **Settings** | **הגדרות** (hagdarot) | ✅ Translate | Universal |
| **Payment** | **תשלום** (tashlum) | ✅ Translate | Universal |
| **Invoice** | **חשבונית** (cheshbonit) | ✅ Translate | Legal term in Israel |

### SOAP Notes Special Handling

**Display in UI:**

```vue
<!-- English -->
<h2>SOAP Session Notes</h2>
<p class="text-sm text-gray-600">
  Structured clinical documentation (Subjective, Objective, Assessment, Plan)
</p>

<!-- Hebrew -->
<h2>רישום SOAP</h2>
<p class="text-sm text-gray-600">
  תיעוד קליני מובנה (Subjective, Objective, Assessment, Plan)
</p>
```

**Section Labels:**

```json
{
  "session.soap.subjective": {
    "en": "Subjective",
    "he": "סובייקטיבי (Subjective)"
  },
  "session.soap.objective": {
    "en": "Objective",
    "he": "אובייקטיבי (Objective)"
  },
  "session.soap.assessment": {
    "en": "Assessment",
    "he": "הערכה (Assessment)"
  },
  "session.soap.plan": {
    "en": "Plan",
    "he": "תכנית טיפול (Plan)"
  }
}
```

**Rationale:**
- Israeli therapists familiar with SOAP (international training)
- Showing both Hebrew + English in parentheses aids clarity
- Reduces ambiguity for bilingual users

### Client vs. Patient

**Recommendation: Use "Client" (לקוח/ה)**

**Rationale:**
- Israeli private practice standard is "לקוח/ה" (client)
- "מטופל/ת" (patient) is more clinical/hospital
- Matches private practice tone (client-centered)
- Consistent with English version

**Gender-Aware Language:**

Hebrew requires gender agreement. Use:
- **Singular:** "לקוח/ה" (lako'ach/laka'chat) — shows both
- **Plural:** "לקוחות" (lekochot) — neutral

**Implementation:**

```json
{
  "clients.title": {
    "en": "Clients",
    "he": "לקוחות"
  },
  "clients.new": {
    "en": "New Client",
    "he": "לקוח/ה חדש/ה"
  }
}
```

---

## Date, Time & Number Formatting

### Date Formatting

**Israeli Standard: DD/MM/YYYY**

```typescript
// composables/useLocaleFormat.ts
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat(locale.value === 'he' ? 'he-IL' : 'en-US', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  }).format(date)
}

// Returns:
// en-US: 11/03/2025
// he-IL: 03/11/2025 (DD/MM/YYYY)
```

**Long Date Format:**

```typescript
function formatLongDate(date: Date): string {
  return new Intl.DateTimeFormat(locale.value === 'he' ? 'he-IL' : 'en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  }).format(date)
}

// Returns:
// en-US: Sunday, November 3, 2025
// he-IL: יום ראשון, 3 בנובמבר 2025
```

### Time Formatting

**Israeli Standard: 24-hour (HH:mm)**

```typescript
function formatTime(date: Date): string {
  return new Intl.DateTimeFormat(locale.value === 'he' ? 'he-IL' : 'en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false  // Force 24-hour for Hebrew
  }).format(date)
}

// Returns:
// en-US: 14:30 (or 2:30 PM if user prefers 12-hour)
// he-IL: 14:30 (always 24-hour)
```

**Time Picker UI:**

```vue
<!-- TimePickerDropdown.vue -->
<template>
  <select v-model="selectedHour">
    <!-- Hebrew: 00-23 (24-hour) -->
    <!-- English: 00-23 or 1-12 AM/PM based on user preference -->
    <option v-for="hour in hours" :value="hour">
      {{ formatHour(hour) }}
    </option>
  </select>
</template>

<script setup>
const { locale } = useI18n()
const hours = locale.value === 'he'
  ? Array.from({length: 24}, (_, i) => i)  // 0-23
  : Array.from({length: 24}, (_, i) => i)  // 0-23 (let user choose 12/24 in settings)
</script>
```

**Design Decision:**
- Hebrew mode: **Always 24-hour** (Israeli standard)
- English mode: **Allow user preference** (12-hour or 24-hour in settings)

### Number Formatting

**Currency (NIS - Israeli Shekel):**

```typescript
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat(locale.value === 'he' ? 'he-IL' : 'en-US', {
    style: 'currency',
    currency: locale.value === 'he' ? 'ILS' : 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  }).format(amount)
}

// Returns:
// en-US: $120.00 (or user's currency)
// he-IL: ‏120 ₪ (shekel symbol)
```

**Decimal Separator:**

Hebrew uses **comma** as decimal separator (not period):

```
English: 1,234.56
Hebrew:  1,234.56 or 1.234,56 (depends on locale)
```

Use `Intl.NumberFormat` to handle automatically.

---

## Feature Rollout Strategy

### Recommended Approach: 100% Translation Before Launch

**Why No Partial Rollout:**
- **Professional credibility:** Mixed language UI damages trust
- **User confusion:** Inconsistent terminology breaks mental models
- **QA complexity:** Hard to test partial state
- **Support burden:** Users report "bugs" for untranslated text

**Rollout Plan:**

**Phase 1: Translation Preparation (Week 1-2)**
- ✅ Extract all ~500 strings to translation keys
- ✅ Set up vue-i18n with English/Hebrew locales
- ✅ Implement locale detection and switcher UI
- ✅ Test RTL layout with Hebrew text

**Phase 2: Professional Translation (Week 2-3)**
- ✅ Translate all strings by native Hebrew speaker with medical background
- ✅ Review clinical terminology for accuracy
- ✅ QA by second Hebrew speaker for consistency

**Phase 3: Testing & Refinement (Week 3-4)**
- ✅ Visual QA: Check all screens in Hebrew mode
- ✅ RTL layout bugs (alignment, icon mirroring)
- ✅ Date/time formatting validation
- ✅ Keyboard shortcuts compatibility

**Phase 4: Launch (Week 4)**
- ✅ Deploy Hebrew support to production
- ✅ Default Hebrew for Israeli users (browser locale detection)
- ✅ Monitor for missing translations via Sentry
- ✅ Collect user feedback on terminology

**Acceptance Criteria:**
- [ ] All 94 components translated
- [ ] All ~500 strings have Hebrew equivalents
- [ ] RTL layout works on all screen sizes
- [ ] Date/time formats match Israeli standards
- [ ] No console warnings for missing translations
- [ ] Accessibility audit passes in both locales

---

## Accessibility Considerations

### Screen Readers in Hebrew

**HTML `lang` Attribute:**

```vue
<script setup>
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

watch(locale, (newLocale) => {
  document.documentElement.lang = newLocale
}, { immediate: true })
</script>
```

**Why This Matters:**
- Screen readers use `lang` to select voice/pronunciation
- Hebrew TTS requires `lang="he"` for correct pronunciation
- Improves experience for visually impaired therapists

### ARIA Labels

**All ARIA labels must be translated:**

```vue
<!-- English -->
<button aria-label="Close dialog">X</button>

<!-- Hebrew -->
<button :aria-label="t('common.close')">X</button>

<!-- Translation file -->
{
  "common.close": {
    "en": "Close dialog",
    "he": "סגור חלון"
  }
}
```

**Common ARIA Labels:**
- Form field descriptions (`aria-describedby`)
- Button actions (`aria-label`)
- Live region announcements (`aria-live`)
- Modal dialogs (`aria-labelledby`)

### Keyboard Shortcuts

**No Changes Needed:**

Keyboard shortcuts (e.g., `g c` for Calendar) work identically in Hebrew mode:
- Shortcuts based on English mnemonics
- Displayed with English letters (not Hebrew)
- No need to translate shortcut keys

**Visual Display:**

```vue
<!-- Same in both locales -->
<kbd class="...">g c</kbd>

<!-- But tooltip translates -->
<span :title="t('shortcuts.calendar')">
  <kbd>g c</kbd>
</span>

{
  "shortcuts.calendar": {
    "en": "Go to Calendar",
    "he": "עבור ללוח שנה"
  }
}
```

### Color Contrast

**Hebrew Typography Considerations:**

Hebrew characters have **different stroke weights** than Latin characters. Ensure:
- ✅ Minimum contrast ratio: 4.5:1 (WCAG AA)
- ✅ Test with Hebrew system fonts (Arial, Tahoma, Segoe UI)
- ✅ Avoid thin font weights (<400) for Hebrew text
- ✅ Increase letter spacing if Hebrew text feels cramped

**Recommended Hebrew Font Stack:**

```css
/* Tailwind config */
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        sans: [
          // English fonts
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          // Hebrew fonts
          'Arial Hebrew',
          'Tahoma',
          'sans-serif'
        ]
      }
    }
  }
}
```

---

## Implementation Checklist

### Before Starting Development

- [ ] Read [docs/PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)
- [ ] Review existing `v-rtl` directive implementation
- [ ] Audit all 94 components for hardcoded strings
- [ ] Set up vue-i18n with TypeScript support
- [ ] Create translation file structure (`/locales/en.json`, `/locales/he.json`)

### During Development

**i18n Setup:**
- [ ] Install `vue-i18n` and configure with TypeScript
- [ ] Set up locale detection (browser + localStorage)
- [ ] Implement locale switcher in Settings page
- [ ] Add `dir` and `lang` attribute watchers to `<html>`

**Translation Extraction:**
- [ ] Extract all hardcoded strings to translation keys
- [ ] Organize keys by feature domain (e.g., `calendar.*`, `clients.*`, `session.*`)
- [ ] Document terminology decisions in translation comments

**RTL Layout:**
- [ ] Convert spacing utilities to logical properties (`margin-inline-start`)
- [ ] Implement icon mirroring for directional icons
- [ ] Test navigation sidebar flip (left → right)
- [ ] Validate form label alignment
- [ ] Test calendar week start (Sunday for Hebrew)

**Date/Time Formatting:**
- [ ] Create `useLocaleFormat` composable
- [ ] Implement `formatDate()`, `formatTime()`, `formatCurrency()`
- [ ] Use `Intl.DateTimeFormat` for all date displays
- [ ] Update time picker to 24-hour for Hebrew

**Testing:**
- [ ] Visual QA all screens in Hebrew mode
- [ ] Test RTL layout on mobile (Android/iOS)
- [ ] Validate keyboard shortcuts work in both locales
- [ ] Test accessibility with Hebrew screen reader
- [ ] Check color contrast for Hebrew text

### Before Launch

- [ ] Professional translation review (native Hebrew medical professional)
- [ ] QA all clinical terminology for accuracy
- [ ] No missing translations in production build
- [ ] Add Sentry alerts for missing translation keys
- [ ] Document rollback plan if critical issues found
- [ ] Prepare user announcement (email/in-app notification)

---

## Appendix: Translation File Structure

**Recommended i18n File Organization:**

```
frontend/src/locales/
├── en.json          # English translations
├── he.json          # Hebrew translations
└── index.ts         # i18n setup

en.json structure:
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "close": "Close"
  },
  "navigation": {
    "calendar": "Calendar",
    "clients": "Clients",
    "settings": "Settings"
  },
  "calendar": {
    "title": "Calendar",
    "newAppointment": "New Appointment",
    "conflictDetected": "Schedule conflict detected"
  },
  "clients": {
    "title": "Clients",
    "newClient": "New Client",
    "searchPlaceholder": "Search clients..."
  },
  "session": {
    "soap": {
      "title": "SOAP Notes",
      "subjective": "Subjective",
      "objective": "Objective",
      "assessment": "Assessment",
      "plan": "Plan"
    }
  },
  "settings": {
    "language": {
      "title": "Language",
      "description": "Choose your preferred language",
      "changeNote": "Changes apply immediately"
    }
  }
}
```

**Type Safety:**

```typescript
// types/i18n.d.ts
import 'vue-i18n'
import type en from '@/locales/en.json'

type MessageSchema = typeof en

declare module 'vue-i18n' {
  export interface DefineLocaleMessage extends MessageSchema {}
}
```

---

## Summary of Recommendations

**Language Switcher:**
- **Location:** Settings page only
- **Design:** Radio button group, no flags, instant application
- **Persistence:** localStorage (`pazpaz_locale`)

**Default Language:**
- **Hebrew for Israeli users** (browser locale `he`, `he-IL`, `iw`)
- **English for all others**
- No onboarding modal (auto-detection)

**RTL Layout:**
- Full layout flip via `dir="rtl"` on `<html>`
- Logical CSS properties (`margin-inline-start`)
- Mirror directional icons only (chevrons, arrows)
- Sunday week start for Hebrew calendar

**Translation Strategy:**
- **100% translation required** before launch
- No partial rollout
- Professional review by Hebrew medical expert
- Graceful dev-mode fallback for missing keys

**Terminology:**
- "Client" = "לקוח/ה"
- "SOAP Notes" = "רישום SOAP" (hybrid: Hebrew + English acronym)
- Clinical terms translated where Hebrew equivalents common

**Date/Time:**
- **DD/MM/YYYY** for Hebrew dates
- **24-hour time** for Hebrew (HH:mm)
- `Intl.DateTimeFormat` with `he-IL` locale

**Accessibility:**
- `lang` attribute on `<html>` for screen readers
- Translate all ARIA labels
- Test Hebrew TTS pronunciation
- Validate color contrast for Hebrew fonts

**Feature Rollout:**
- ✅ Full translation before production launch
- ✅ Visual QA all 94 components
- ✅ Monitor Sentry for missing keys
- ✅ Collect user feedback post-launch

---

**Next Steps:**
1. Implement locale detection and switcher UI
2. Extract all strings to translation keys
3. Hire native Hebrew medical translator
4. Implement RTL layout adjustments
5. QA testing with Israeli therapists
6. Launch Hebrew support to production

**Questions or Feedback:**
Contact UX Design Consultant for clarifications on design decisions.

**Document Version:** 1.0
**Last Updated:** 2025-11-03
