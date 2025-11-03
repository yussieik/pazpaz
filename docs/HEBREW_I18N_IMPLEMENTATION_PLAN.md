# Hebrew i18n Implementation Plan

**Document Version:** 1.0
**Last Updated:** 2025-11-03
**Status:** Ready for Implementation

---

## Table of Contents

1. [Overview](#overview)
2. [Technical Specifications](#technical-specifications)
3. [Phase 1: Infrastructure Setup](#phase-1-infrastructure-setup)
4. [Phase 2: Core Framework Implementation](#phase-2-core-framework-implementation)
5. [Phase 3: High-Priority Components](#phase-3-high-priority-components)
6. [Phase 4: Medium-Priority Components](#phase-4-medium-priority-components)
7. [Phase 5: Low-Priority Components](#phase-5-low-priority-components)
8. [Phase 6: Third-Party Library Localization](#phase-6-third-party-library-localization)
9. [Phase 7: Testing & QA](#phase-7-testing--qa)
10. [Rollback & Safety Considerations](#rollback--safety-considerations)
11. [Time Estimates](#time-estimates)

---

## Overview

### Objectives

Add full Hebrew language support to PazPaz with:
- 100% translation coverage before launch (no partial rollout)
- Full RTL (right-to-left) layout support using CSS logical properties
- Browser locale auto-detection (Hebrew default for Israeli users)
- Language switcher in Settings page only (not global nav)
- Professional Hebrew medical terminology
- Israeli date/time standards (Sunday week start, 24-hour format)

### Success Criteria

- [ ] All 94 components fully translated
- [ ] ~500 strings translated with professional medical terminology
- [ ] RTL layout renders correctly across all views
- [ ] FullCalendar and date-fns properly localized
- [ ] No missing translation warnings in console
- [ ] Language preference persists across sessions
- [ ] Zero layout breaks in RTL mode

### Non-Goals (V1)

- Multi-language support beyond Hebrew/English
- User-level language preferences (workspace-level only for V1)
- Dynamic translation loading (all translations bundled)
- Translation management UI

---

## Technical Specifications

### Core Technologies

**i18n Library:**
```json
"vue-i18n": "^10.0.4"
```

**TypeScript Support:**
```json
"@intlify/unplugin-vue-i18n": "^5.2.0"
```

**Date Localization:**
```json
"date-fns": "^4.1.0" (already installed)
```

**FullCalendar Locale:**
```json
"@fullcalendar/core": "^6.1.19" (already installed, includes Hebrew locale)
```

### File Structure

```
frontend/
├── src/
│   ├── locales/
│   │   ├── en.json          # English translations (source of truth)
│   │   ├── he.json          # Hebrew translations
│   │   └── index.ts         # Locale configuration
│   ├── composables/
│   │   └── useI18n.ts       # i18n composable wrapper
│   ├── plugins/
│   │   └── i18n.ts          # vue-i18n plugin configuration
│   └── types/
│       └── i18n.d.ts        # TypeScript type definitions
├── vite.config.ts           # Updated with i18n plugin
└── package.json             # Updated dependencies
```

### Translation Key Structure

**Hierarchical namespacing:**
```json
{
  "auth": {
    "login": {
      "title": "Sign In",
      "emailLabel": "Email Address",
      "submitButton": "Send Magic Link"
    }
  },
  "calendar": {
    "toolbar": {
      "today": "Today",
      "week": "Week",
      "day": "Day"
    },
    "appointment": {
      "create": "Create Appointment",
      "edit": "Edit Appointment"
    }
  },
  "common": {
    "actions": {
      "save": "Save",
      "cancel": "Cancel",
      "delete": "Delete"
    }
  }
}
```

### TypeScript Type Safety

**Auto-generated types from translation keys:**
```typescript
// src/types/i18n.d.ts
import type { DefineLocaleMessage } from 'vue-i18n'
import en from '@/locales/en.json'

export type MessageSchema = typeof en

declare module 'vue-i18n' {
  export interface DefineLocaleMessage extends MessageSchema {}
}
```

### RTL CSS Strategy

**Use CSS logical properties exclusively:**
```css
/* ❌ Old (physical properties) */
margin-left: 1rem;
padding-right: 2rem;
text-align: left;

/* ✅ New (logical properties) */
margin-inline-start: 1rem;
padding-inline-end: 2rem;
text-align: start;
```

**Tailwind RTL utilities (already supported in v4):**
```html
<!-- Tailwind automatically handles RTL with logical properties -->
<div class="ms-4 pe-2 text-start">
  <!-- ms-4 = margin-inline-start: 1rem -->
  <!-- pe-2 = padding-inline-end: 0.5rem -->
  <!-- text-start = text-align: start -->
</div>
```

**Global RTL class:**
```css
/* Applied to <html dir="rtl"> */
html[dir="rtl"] {
  direction: rtl;
}
```

---

## Phase 1: Infrastructure Setup

**Goal:** Install and configure vue-i18n with TypeScript support

**Duration:** 4-6 hours

### Tasks

- [ ] **Install vue-i18n and dependencies**
  - **Deliverable:** Updated `package.json` with new dependencies
  - **Verification:** `npm list vue-i18n @intlify/unplugin-vue-i18n`
  - **Command:**
    ```bash
    cd frontend
    npm install vue-i18n@^10.0.4 @intlify/unplugin-vue-i18n@^5.2.0
    ```

- [ ] **Configure Vite plugin for i18n**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/vite.config.ts`
  - **Dependencies:** vue-i18n installed
  - **Verification:** `npm run dev` starts without errors
  - **Implementation:**
    ```typescript
    // vite.config.ts
    import { fileURLToPath, URL } from 'node:url'
    import { defineConfig, loadEnv, type UserConfig } from 'vite'
    import vue from '@vitejs/plugin-vue'
    import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'
    import type { Plugin } from 'vite'
    import crypto from 'crypto'

    // ... existing polyfill code ...

    export function getViteConfig(mode: string): UserConfig {
      const env = loadEnv(mode, process.cwd(), 'VITE_')
      const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
      const wsProxyTarget = apiProxyTarget.replace('http://', 'ws://')

      return {
        plugins: [
          vue(),
          cspHtmlTransform(mode, env),
          VueI18nPlugin({
            // Locale files directory
            include: fileURLToPath(
              new URL('./src/locales/**/*.json', import.meta.url)
            ),
            // Enable strict mode for development
            strictMessage: mode === 'development',
            // Enable ESLint plugin integration
            escapeHtml: false,
          }),
        ],
        // ... rest of config unchanged
      }
    }
    ```

- [ ] **Create locale files directory structure**
  - **Deliverable:**
    - `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/locales/en.json`
    - `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/locales/he.json`
    - `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/locales/index.ts`
  - **Dependencies:** None
  - **Verification:** Files exist and are valid JSON
  - **Implementation:**
    ```bash
    mkdir -p /Users/yussieik/Desktop/projects/pazpaz/frontend/src/locales
    ```

    ```json
    // src/locales/en.json (starter)
    {
      "common": {
        "actions": {
          "save": "Save",
          "cancel": "Cancel",
          "delete": "Delete",
          "edit": "Edit",
          "close": "Close"
        },
        "status": {
          "loading": "Loading...",
          "error": "Error",
          "success": "Success"
        }
      }
    }
    ```

    ```json
    // src/locales/he.json (starter)
    {
      "common": {
        "actions": {
          "save": "שמור",
          "cancel": "בטל",
          "delete": "מחק",
          "edit": "ערוך",
          "close": "סגור"
        },
        "status": {
          "loading": "טוען...",
          "error": "שגיאה",
          "success": "הצלחה"
        }
      }
    }
    ```

    ```typescript
    // src/locales/index.ts
    import en from './en.json'
    import he from './he.json'

    export const messages = {
      en,
      he,
    }

    export const locales = [
      { code: 'en', name: 'English', dir: 'ltr' },
      { code: 'he', name: 'עברית', dir: 'rtl' },
    ] as const

    export type LocaleCode = 'en' | 'he'
    ```

- [ ] **Create TypeScript type definitions**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/types/i18n.d.ts`
  - **Dependencies:** Locale files created
  - **Verification:** No TypeScript errors in IDE
  - **Implementation:**
    ```typescript
    // src/types/i18n.d.ts
    import type en from '@/locales/en.json'

    /**
     * TypeScript type definitions for vue-i18n
     *
     * This ensures type safety for translation keys throughout the app.
     * Any typo in $t('key') will be caught at compile time.
     */

    export type MessageSchema = typeof en

    declare module 'vue-i18n' {
      // Type-safe translation keys
      export interface DefineLocaleMessage extends MessageSchema {}

      // Ensure strict typing for locale codes
      export interface DefineDateTimeFormat {}
      export interface DefineNumberFormat {}
    }
    ```

- [ ] **Update tsconfig.app.json for i18n types**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/tsconfig.app.json`
  - **Dependencies:** i18n.d.ts created
  - **Verification:** `npm run type-check` passes
  - **Implementation:**
    ```json
    {
      "extends": "@vue/tsconfig/tsconfig.dom.json",
      "compilerOptions": {
        "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
        "types": ["vite/client", "vue-i18n"],
        "baseUrl": ".",
        "paths": {
          "@/*": ["./src/*"]
        },
        "strict": true,
        "noUnusedLocals": true,
        "noUnusedParameters": true,
        "noFallthroughCasesInSwitch": true,
        "noUncheckedSideEffectImports": true
      },
      "include": [
        "src/**/*.ts",
        "src/**/*.tsx",
        "src/**/*.vue",
        "src/types/i18n.d.ts"
      ],
      "exclude": ["src/**/*.spec.ts", "src/test/**/*"]
    }
    ```

**Phase 1 Completion Checklist:**
- [ ] `npm run dev` starts without errors
- [ ] `npm run type-check` passes
- [ ] Locale files are valid JSON
- [ ] TypeScript recognizes i18n types

**Estimated Time:** 4-6 hours

---

## Phase 2: Core Framework Implementation

**Goal:** Initialize vue-i18n plugin and create locale detection/persistence logic

**Duration:** 8-10 hours

### Tasks

- [ ] **Create i18n plugin configuration**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/plugins/i18n.ts`
  - **Dependencies:** Phase 1 complete
  - **Verification:** Plugin exports valid i18n instance
  - **Implementation:**
    ```typescript
    // src/plugins/i18n.ts
    import { createI18n } from 'vue-i18n'
    import { messages } from '@/locales'
    import type { LocaleCode } from '@/locales'

    /**
     * Browser locale detection
     *
     * Priority:
     * 1. localStorage preference (user explicitly changed language)
     * 2. Browser locale (navigator.language)
     * 3. Default to English
     */
    function detectBrowserLocale(): LocaleCode {
      // Check localStorage for saved preference
      const savedLocale = localStorage.getItem('pazpaz_locale') as LocaleCode | null
      if (savedLocale && (savedLocale === 'en' || savedLocale === 'he')) {
        return savedLocale
      }

      // Check browser locale
      const browserLocale = navigator.language.toLowerCase()

      // Israeli users get Hebrew by default
      if (browserLocale.startsWith('he')) {
        return 'he'
      }

      // Default to English
      return 'en'
    }

    /**
     * Vue i18n instance
     *
     * Configuration:
     * - Legacy mode: false (use Composition API)
     * - Locale: auto-detected from browser or localStorage
     * - Fallback: English
     * - Missing warnings: enabled in development only
     */
    export const i18n = createI18n({
      legacy: false, // Use Composition API mode
      locale: detectBrowserLocale(),
      fallbackLocale: 'en',
      messages,
      // Development-only warnings
      missingWarn: import.meta.env.MODE === 'development',
      fallbackWarn: import.meta.env.MODE === 'development',
      // Preserve HTML in translations (needed for links, formatting)
      warnHtmlMessage: true,
    })

    /**
     * Get current locale direction (ltr/rtl)
     */
    export function getLocaleDirection(locale: LocaleCode): 'ltr' | 'rtl' {
      return locale === 'he' ? 'rtl' : 'ltr'
    }
    ```

- [ ] **Register i18n plugin in main.ts**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/main.ts`
  - **Dependencies:** i18n plugin created
  - **Verification:** App mounts without errors; `$t` is available in components
  - **Implementation:**
    ```typescript
    // src/main.ts
    import { createApp } from 'vue'
    import { createPinia } from 'pinia'
    import Toast, { POSITION } from 'vue-toastification'
    import type { PluginOptions } from 'vue-toastification/dist/types/types'
    import 'vue-toastification/dist/index.css'
    import router from './router'
    import './style.css'
    import './assets/calendar-patterns.css'
    import App from './App.vue'
    import { useAuthStore } from './stores/auth'
    import { configureApiClient } from './api/config'
    import { vRtl } from './directives/rtl'
    import { i18n } from './plugins/i18n' // ← New import

    const app = createApp(App)
    const pinia = createPinia()

    configureApiClient()

    const toastOptions: PluginOptions = {
      position: POSITION.TOP_RIGHT,
      timeout: 3000,
      closeOnClick: true,
      pauseOnFocusLoss: true,
      pauseOnHover: true,
      draggable: true,
      draggablePercent: 0.6,
      showCloseButtonOnHover: false,
      hideProgressBar: false,
      closeButton: 'button',
      icon: true,
      rtl: false, // ← Will be updated dynamically
      transition: 'Vue-Toastification__slideBlurred',
      maxToasts: 3,
      newestOnTop: true,
      filterBeforeCreate: (toast, _toasts) => toast,
      filterToasts: (toasts) => toasts,
    }

    // Install plugins
    app.use(pinia)
    app.use(Toast, toastOptions)
    app.use(i18n) // ← Register i18n plugin

    // Register global directives
    app.directive('rtl', vRtl)

    const authStore = useAuthStore()

    authStore.initializeAuth().finally(() => {
      app.use(router)
      app.mount('#app')

      console.debug('[App] Mounted with authentication state:', {
        isAuthenticated: authStore.isAuthenticated,
        userId: authStore.user?.id,
      })
    })
    ```

- [ ] **Create useI18n composable wrapper**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useI18n.ts`
  - **Dependencies:** i18n plugin registered
  - **Verification:** Composable works in test component
  - **Implementation:**
    ```typescript
    // src/composables/useI18n.ts
    import { useI18n as useVueI18n } from 'vue-i18n'
    import { computed, watch } from 'vue'
    import type { LocaleCode } from '@/locales'
    import { getLocaleDirection } from '@/plugins/i18n'

    /**
     * i18n composable for PazPaz
     *
     * Provides:
     * - Translation function (t)
     * - Locale switching (setLocale)
     * - RTL/LTR direction detection
     * - Locale persistence to localStorage
     * - Document direction updates
     *
     * Usage:
     *   const { t, locale, setLocale, isRTL } = useI18n()
     *   t('auth.login.title') // Type-safe translation keys
     */
    export function useI18n() {
      const { t, locale } = useVueI18n()

      // Current locale direction
      const isRTL = computed(() => locale.value === 'he')
      const direction = computed(() => getLocaleDirection(locale.value as LocaleCode))

      /**
       * Change application locale
       *
       * @param newLocale - 'en' or 'he'
       *
       * Side effects:
       * - Updates vue-i18n locale
       * - Saves to localStorage
       * - Updates document.documentElement.dir
       * - Updates document.documentElement.lang
       */
      function setLocale(newLocale: LocaleCode) {
        locale.value = newLocale

        // Persist to localStorage
        localStorage.setItem('pazpaz_locale', newLocale)

        // Update document attributes
        const dir = getLocaleDirection(newLocale)
        document.documentElement.setAttribute('dir', dir)
        document.documentElement.setAttribute('lang', newLocale)

        console.debug(`[i18n] Locale changed to ${newLocale} (${dir})`)
      }

      /**
       * Toggle between English and Hebrew
       */
      function toggleLocale() {
        const newLocale = locale.value === 'en' ? 'he' : 'en'
        setLocale(newLocale as LocaleCode)
      }

      // Watch locale changes and update document direction
      watch(locale, (newLocale) => {
        const dir = getLocaleDirection(newLocale as LocaleCode)
        document.documentElement.setAttribute('dir', dir)
        document.documentElement.setAttribute('lang', newLocale)
      })

      return {
        t,
        locale: computed(() => locale.value as LocaleCode),
        setLocale,
        toggleLocale,
        isRTL,
        direction,
      }
    }
    ```

- [ ] **Initialize document direction on app mount**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/main.ts`
  - **Dependencies:** useI18n composable created
  - **Verification:** `<html dir="rtl">` appears when locale is Hebrew
  - **Implementation:**
    ```typescript
    // src/main.ts (add after i18n plugin registration)
    import { i18n, getLocaleDirection } from './plugins/i18n'
    import type { LocaleCode } from './locales'

    // ... after app.use(i18n)

    // Set initial document direction based on detected locale
    const initialLocale = i18n.global.locale.value as LocaleCode
    const initialDir = getLocaleDirection(initialLocale)
    document.documentElement.setAttribute('dir', initialDir)
    document.documentElement.setAttribute('lang', initialLocale)
    ```

- [ ] **Add RTL support to Tailwind CSS**
  - **Deliverable:** `/Users/yussieik/Desktop/projects/pazpaz/frontend/tailwind.config.js`
  - **Dependencies:** None (Tailwind v4 supports RTL by default)
  - **Verification:** `ms-4` class works in RTL mode
  - **Implementation:**
    ```javascript
    // tailwind.config.js (no changes needed for v4)
    // Tailwind v4 automatically handles RTL with logical properties

    /** @type {import('tailwindcss').Config} */
    export default {
      content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
      theme: {
        extend: {
          // ... existing theme config
        },
      },
      plugins: [],
    }
    ```

    **Note:** Tailwind CSS v4 (via `@tailwindcss/postcss`) automatically converts directional utilities like `ml-4` to logical properties like `margin-inline-start`. No additional configuration needed.

- [ ] **Test locale switching manually**
  - **Deliverable:** Working locale switcher in browser console
  - **Dependencies:** All above tasks complete
  - **Verification:**
    1. Open browser console
    2. Execute: `window.__VUE_I18N__.global.locale.value = 'he'`
    3. Verify `<html dir="rtl">` appears
    4. Execute: `window.__VUE_I18N__.global.locale.value = 'en'`
    5. Verify `<html dir="ltr">` appears

**Phase 2 Completion Checklist:**
- [ ] i18n plugin registered in main.ts
- [ ] Document direction updates when locale changes
- [ ] localStorage persists locale preference
- [ ] useI18n composable available in all components
- [ ] No console warnings about missing translations

**Estimated Time:** 8-10 hours

---

## Phase 3: High-Priority Components

**Goal:** Translate authentication, calendar, and client management features first (most critical user flows)

**Duration:** 20-25 hours

### Component Translation Priority

**High-Priority Components (translate first):**
1. Authentication flow (LoginView, AuthVerifyView)
2. Calendar scheduling (CalendarView, AppointmentFormModal, AppointmentDetailsModal)
3. Client management (ClientsView, ClientFormModal, ClientDetailView)

### String Extraction Pattern

**Before (hardcoded strings):**
```vue
<template>
  <h2>Sign In</h2>
  <label>Email Address</label>
  <button>Send Magic Link</button>
</template>
```

**After (i18n):**
```vue
<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
</script>

<template>
  <h2>{{ t('auth.login.title') }}</h2>
  <label>{{ t('auth.login.emailLabel') }}</label>
  <button>{{ t('auth.login.submitButton') }}</button>
</template>
```

### Tasks

#### 3.1 Authentication Components (~500 strings)

- [ ] **Extract strings from LoginView**
  - **Deliverable:**
    - Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/LoginView.vue`
    - Added to `en.json` under `auth.login.*`
    - Translated in `he.json`
  - **Dependencies:** Phase 2 complete
  - **Verification:** Login page displays in Hebrew when `locale=he`
  - **Estimated Strings:** ~50
  - **Example:**
    ```json
    // en.json
    {
      "auth": {
        "login": {
          "title": "Sign In",
          "subtitle": "Practice Management for Therapists",
          "emailLabel": "Email Address",
          "emailPlaceholder": "you@example.com",
          "emailDescription": "We'll send you a magic link to sign in",
          "submitButton": "Send Magic Link",
          "submitButtonSending": "Sending...",
          "submitButtonSent": "Link Sent!",
          "success": {
            "title": "Check your email",
            "message": "We've sent a magic link to {email}. Click the link to sign in.",
            "editButton": "Edit",
            "linkExpires": "Link expires in:",
            "tips": {
              "spam": "Check your spam folder if you don't see it",
              "oneTime": "The link can only be used once"
            },
            "resend": {
              "label": "Didn't receive it?",
              "button": "Resend magic link",
              "buttonResending": "Resending...",
              "cooldown": "Resend available in {seconds}s"
            }
          },
          "errors": {
            "invalidEmail": "Please enter a valid email address",
            "invalidLink": "Invalid or expired magic link. Please request a new one.",
            "generic": "An error occurred. Please try again.",
            "rateLimit": "Too many requests. Please try again in {seconds} seconds."
          },
          "sessionExpired": {
            "title": "Session Expired",
            "message": "Your session has expired due to inactivity. Please sign in again to continue."
          },
          "security": {
            "note": "Secure passwordless authentication"
          },
          "dev": {
            "mailhogBanner": {
              "title": "Development Mode",
              "message": "Check {mailhog} for magic link emails during testing",
              "mailhogLink": "MailHog"
            }
          }
        }
      }
    }
    ```

    ```json
    // he.json
    {
      "auth": {
        "login": {
          "title": "כניסה למערכת",
          "subtitle": "ניהול קליניקה למטפלים",
          "emailLabel": "כתובת דוא״ל",
          "emailPlaceholder": "example@example.com",
          "emailDescription": "נשלח לך קישור קסם לכניסה למערכת",
          "submitButton": "שלח קישור קסם",
          "submitButtonSending": "שולח...",
          "submitButtonSent": "נשלח!",
          "success": {
            "title": "בדוק את תיבת הדואר",
            "message": "שלחנו קישור קסם לכתובת {email}. לחץ על הקישור כדי להיכנס.",
            "editButton": "ערוך",
            "linkExpires": "הקישור יפוג בעוד:",
            "tips": {
              "spam": "בדוק בתיקיית הספאם אם אינך רואה את ההודעה",
              "oneTime": "ניתן להשתמש בקישור פעם אחת בלבד"
            },
            "resend": {
              "label": "לא קיבלת את ההודעה?",
              "button": "שלח קישור מחדש",
              "buttonResending": "שולח מחדש...",
              "cooldown": "ניתן לשלוח מחדש בעוד {seconds} שניות"
            }
          },
          "errors": {
            "invalidEmail": "נא להזין כתובת דוא״ל תקינה",
            "invalidLink": "קישור לא תקין או שפג תוקפו. נא לבקש קישור חדש.",
            "generic": "אירעה שגיאה. נא לנסות שנית.",
            "rateLimit": "יותר מדי בקשות. נא לנסות שנית בעוד {seconds} שניות."
          },
          "sessionExpired": {
            "title": "תוקף ההתחברות פג",
            "message": "תוקף ההתחברות פג עקב חוסר פעילות. נא להתחבר שנית כדי להמשיך."
          },
          "security": {
            "note": "אימות מאובטח ללא סיסמה"
          },
          "dev": {
            "mailhogBanner": {
              "title": "מצב פיתוח",
              "message": "בדוק ב-{mailhog} את הודעות הקישור הקסם במהלך הבדיקות",
              "mailhogLink": "MailHog"
            }
          }
        }
      }
    }
    ```

- [ ] **Extract strings from AuthVerifyView**
  - **Deliverable:**
    - Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/AuthVerifyView.vue`
    - Added to `en.json` under `auth.verify.*`
  - **Estimated Strings:** ~20

- [ ] **Extract strings from SessionExpirationModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/auth/SessionExpirationModal.vue`
  - **Estimated Strings:** ~15

- [ ] **Extract strings from SessionExpirationBanner**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/auth/SessionExpirationBanner.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from LogoutConfirmationModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/auth/LogoutConfirmationModal.vue`
  - **Estimated Strings:** ~10

#### 3.2 Calendar Components (~150 strings)

- [ ] **Extract strings from CalendarView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/CalendarView.vue`
  - **Estimated Strings:** ~30
  - **Key Areas:**
    - Calendar toolbar buttons (Today, Week, Day, Month)
    - Appointment statuses (Scheduled, Completed, Cancelled)
    - Conflict warnings
    - Screen reader announcements

- [ ] **Extract strings from AppointmentFormModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/AppointmentFormModal.vue`
  - **Estimated Strings:** ~40
  - **Key Areas:**
    - Form labels (Client, Date, Time, Location, Notes)
    - Validation errors
    - Submit buttons (Create, Update, Cancel)

- [ ] **Extract strings from AppointmentDetailsModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/AppointmentDetailsModal.vue`
  - **Estimated Strings:** ~30

- [ ] **Extract strings from CalendarToolbar**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/CalendarToolbar.vue`
  - **Estimated Strings:** ~15

- [ ] **Extract strings from CancelAppointmentDialog**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/CancelAppointmentDialog.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from DragConflictModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/DragConflictModal.vue`
  - **Estimated Strings:** ~15

- [ ] **Extract strings from MobileRescheduleModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/MobileRescheduleModal.vue`
  - **Estimated Strings:** ~10

#### 3.3 Client Management Components (~100 strings)

- [ ] **Extract strings from ClientsView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/ClientsView.vue`
  - **Estimated Strings:** ~25

- [ ] **Extract strings from ClientFormModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/clients/ClientFormModal.vue`
  - **Estimated Strings:** ~30

- [ ] **Extract strings from ClientDetailView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/ClientDetailView.vue`
  - **Estimated Strings:** ~25

- [ ] **Extract strings from ClientCombobox**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/clients/ClientCombobox.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from ClientQuickAddForm**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/clients/ClientQuickAddForm.vue`
  - **Estimated Strings:** ~10

**Phase 3 Completion Checklist:**
- [ ] All authentication flows work in Hebrew
- [ ] Calendar scheduling fully translated
- [ ] Client management fully translated
- [ ] No hardcoded English strings in high-priority components
- [ ] RTL layout renders correctly in all high-priority views

**Estimated Time:** 20-25 hours

---

## Phase 4: Medium-Priority Components

**Goal:** Translate session documentation, settings, and forms

**Duration:** 15-20 hours

### Tasks

#### 4.1 Session Documentation (~80 strings)

- [ ] **Extract strings from SessionView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/SessionView.vue`
  - **Estimated Strings:** ~30
  - **Key Areas:**
    - SOAP note section labels (Subjective, Objective, Assessment, Plan)
    - Autosave status messages
    - File upload labels

- [ ] **Extract strings from SessionEditor**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/SessionEditor.vue`
  - **Estimated Strings:** ~25

- [ ] **Extract strings from PreviousSessionPanel**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/PreviousSessionPanel.vue`
  - **Estimated Strings:** ~15

- [ ] **Extract strings from SessionAttachments**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/SessionAttachments.vue`
  - **Estimated Strings:** ~10

#### 4.2 Settings Components (~60 strings)

- [ ] **Extract strings from SettingsLayout**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/layouts/SettingsLayout.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from SettingsSidebar**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/settings/SettingsSidebar.vue`
  - **Estimated Strings:** ~15

- [ ] **Extract strings from NotificationsView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/settings/NotificationsView.vue`
  - **Estimated Strings:** ~20

- [ ] **Extract strings from IntegrationsView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/settings/IntegrationsView.vue`
  - **Estimated Strings:** ~15

- [ ] **Create language switcher in Settings**
  - **Deliverable:** New component or section in Settings
  - **Implementation:**
    ```vue
    <!-- In Settings view -->
    <script setup lang="ts">
    import { useI18n } from '@/composables/useI18n'

    const { locale, setLocale, t } = useI18n()
    </script>

    <template>
      <div class="settings-section">
        <h3>{{ t('settings.language.title') }}</h3>
        <p class="text-sm text-slate-600">
          {{ t('settings.language.description') }}
        </p>

        <div class="mt-4 space-y-2">
          <label class="flex items-center gap-3">
            <input
              type="radio"
              :value="'en'"
              :checked="locale === 'en'"
              @change="setLocale('en')"
              class="h-4 w-4 text-emerald-600"
            />
            <span>English</span>
          </label>

          <label class="flex items-center gap-3">
            <input
              type="radio"
              :value="'he'"
              :checked="locale === 'he'"
              @change="setLocale('he')"
              class="h-4 w-4 text-emerald-600"
            />
            <span>עברית (Hebrew)</span>
          </label>
        </div>
      </div>
    </template>
    ```

#### 4.3 Common Components (~40 strings)

- [ ] **Extract strings from AppNavigation**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/navigation/AppNavigation.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from PageHeader**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/common/PageHeader.vue`
  - **Estimated Strings:** ~5

- [ ] **Extract strings from EmptyState**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/common/EmptyState.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from AutosaveBanner**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/common/AutosaveBanner.vue`
  - **Estimated Strings:** ~5

- [ ] **Extract strings from RateLimitBanner**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/RateLimitBanner.vue`
  - **Estimated Strings:** ~10

**Phase 4 Completion Checklist:**
- [ ] Session documentation fully translated
- [ ] Settings page includes language switcher
- [ ] All form validation messages translated
- [ ] Common components display in correct language

**Estimated Time:** 15-20 hours

---

## Phase 5: Low-Priority Components

**Goal:** Translate remaining views, modals, and edge case components

**Duration:** 10-15 hours

### Tasks

#### 5.1 Payment Components (~30 strings)

- [ ] **Extract strings from PaymentsView**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/settings/PaymentsView.vue`
  - **Estimated Strings:** ~15

- [ ] **Extract strings from PaymentDetailsForm**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/appointments/PaymentDetailsForm.vue`
  - **Estimated Strings:** ~15

#### 5.2 Platform Admin Components (~40 strings)

- [ ] **Extract strings from PlatformAdminPage**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/PlatformAdminPage.vue`
  - **Estimated Strings:** ~20

- [ ] **Extract strings from WorkspaceDetailsModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/platform-admin/WorkspaceDetailsModal.vue`
  - **Estimated Strings:** ~20

#### 5.3 Remaining Modals and Dialogs (~30 strings)

- [ ] **Extract strings from SessionTimeoutModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/SessionTimeoutModal.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from DeleteAppointmentModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/appointments/DeleteAppointmentModal.vue`
  - **Estimated Strings:** ~10

- [ ] **Extract strings from ImagePreviewModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/ImagePreviewModal.vue`
  - **Estimated Strings:** ~5

- [ ] **Extract strings from PDFPreviewModal**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/PDFPreviewModal.vue`
  - **Estimated Strings:** ~5

**Phase 5 Completion Checklist:**
- [ ] All remaining components translated
- [ ] No untranslated strings visible in UI
- [ ] Admin panel works in Hebrew

**Estimated Time:** 10-15 hours

---

## Phase 6: Third-Party Library Localization

**Goal:** Configure FullCalendar and date-fns for Hebrew locale

**Duration:** 6-8 hours

### Tasks

#### 6.1 FullCalendar Hebrew Locale

- [ ] **Import and configure Hebrew locale for FullCalendar**
  - **Deliverable:** Updated `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/composables/useCalendar.ts`
  - **Dependencies:** Phase 2 complete
  - **Verification:** Calendar displays Hebrew month/day names when `locale=he`
  - **Implementation:**
    ```typescript
    // src/composables/useCalendar.ts
    import heLocale from '@fullcalendar/core/locales/he'
    import { useI18n } from '@/composables/useI18n'

    export function useCalendar() {
      const { locale } = useI18n()

      // FullCalendar options
      const calendarOptions = computed(() => ({
        // ... existing options

        locale: locale.value === 'he' ? heLocale : undefined,

        // Israeli week starts on Sunday
        firstDay: locale.value === 'he' ? 0 : 1, // 0 = Sunday, 1 = Monday

        // Use 24-hour format for Hebrew
        eventTimeFormat: locale.value === 'he'
          ? { hour: '2-digit', minute: '2-digit', hour12: false }
          : { hour: 'numeric', minute: '2-digit', meridiem: 'short' },

        // Hebrew button text
        buttonText: locale.value === 'he'
          ? {
              today: 'היום',
              month: 'חודש',
              week: 'שבוע',
              day: 'יום',
              list: 'רשימה',
            }
          : undefined,
      }))

      return { calendarOptions }
    }
    ```

- [ ] **Test FullCalendar RTL layout**
  - **Deliverable:** Visual verification of RTL calendar
  - **Verification Steps:**
    1. Switch to Hebrew locale
    2. Verify calendar grid flows right-to-left
    3. Verify event times display in 24-hour format
    4. Verify week starts on Sunday
    5. Verify Hebrew month names (ינואר, פברואר, etc.)

#### 6.2 date-fns Hebrew Locale

- [ ] **Configure date-fns for Hebrew formatting**
  - **Deliverable:** New utility file `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/utils/dateFormat.ts`
  - **Dependencies:** Phase 2 complete
  - **Verification:** Dates display in Hebrew format (e.g., "5 בינואר 2025")
  - **Implementation:**
    ```typescript
    // src/utils/dateFormat.ts
    import { format as dateFnsFormat } from 'date-fns'
    import { he } from 'date-fns/locale'
    import { useI18n } from '@/composables/useI18n'

    /**
     * Locale-aware date formatting utility
     *
     * Usage:
     *   const { formatDate } = useDateFormat()
     *   formatDate(new Date(), 'PPP') // "5 January 2025" or "5 בינואר 2025"
     */
    export function useDateFormat() {
      const { locale } = useI18n()

      function formatDate(date: Date | string, formatStr: string): string {
        const dateObj = typeof date === 'string' ? new Date(date) : date

        return dateFnsFormat(dateObj, formatStr, {
          locale: locale.value === 'he' ? he : undefined,
        })
      }

      return { formatDate }
    }
    ```

- [ ] **Replace all date-fns format() calls with useDateFormat()**
  - **Deliverable:** Updated components using date formatting
  - **Files to update:**
    - `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/views/CalendarView.vue`
    - `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/calendar/AppointmentDetailsModal.vue`
    - `/Users/yussieik/Desktop/projects/pazpaz/frontend/src/components/sessions/SessionCard.vue`
    - Any other components using `format()` from date-fns
  - **Example:**
    ```vue
    <script setup lang="ts">
    // Before
    import { format } from 'date-fns'
    const formattedDate = format(new Date(), 'PPP')

    // After
    import { useDateFormat } from '@/utils/dateFormat'
    const { formatDate } = useDateFormat()
    const formattedDate = formatDate(new Date(), 'PPP')
    </script>
    ```

**Phase 6 Completion Checklist:**
- [ ] FullCalendar displays Hebrew locale
- [ ] Week starts on Sunday in Hebrew mode
- [ ] 24-hour time format in Hebrew
- [ ] date-fns formats dates in Hebrew
- [ ] All date displays use locale-aware formatting

**Estimated Time:** 6-8 hours

---

## Phase 7: Testing & QA

**Goal:** Comprehensive testing of i18n implementation

**Duration:** 12-15 hours

### Testing Checklist

#### 7.1 Translation Coverage Testing

- [ ] **Verify no missing translations**
  - **Deliverable:** Zero console warnings about missing translation keys
  - **Verification Steps:**
    1. Open app with `locale=he`
    2. Navigate through all views
    3. Check browser console for warnings like: `[vue-i18n] Not found 'key' in 'he' locale messages`
    4. Add any missing translations
  - **Tool:**
    ```bash
    # Run app in dev mode and check console
    npm run dev
    ```

- [ ] **Check for hardcoded English strings**
  - **Deliverable:** List of any remaining hardcoded strings
  - **Verification:**
    ```bash
    # Search for common English words in templates
    grep -r "Email\|Password\|Save\|Cancel\|Delete" frontend/src/components --include="*.vue" | grep -v "t('" | grep -v "//"
    ```
  - **Fix:** Replace any found hardcoded strings with `t('...')` calls

#### 7.2 RTL Layout Testing

- [ ] **Test RTL layout in all views**
  - **Deliverable:** Screenshot comparison doc (English LTR vs Hebrew RTL)
  - **Views to test:**
    - LoginView
    - CalendarView (week/day/month)
    - ClientsView (list and grid)
    - ClientDetailView
    - SessionView (SOAP notes)
    - Settings pages
  - **Verification Criteria:**
    - Navigation menu mirrors correctly
    - Form labels align to the right
    - Buttons appear in correct order (Cancel on right, Save on left in RTL)
    - Icons mirror where appropriate (arrows, chevrons)
    - Calendar grid flows right-to-left

- [ ] **Test CSS logical properties**
  - **Deliverable:** List of any CSS physical properties that need conversion
  - **Search for physical properties:**
    ```bash
    # Find any remaining physical direction properties
    grep -r "margin-left\|margin-right\|padding-left\|padding-right\|text-align: left\|text-align: right\|left:\|right:" frontend/src --include="*.vue" --include="*.css"
    ```
  - **Fix:** Convert to logical properties:
    - `margin-left` → `margin-inline-start`
    - `margin-right` → `margin-inline-end`
    - `text-align: left` → `text-align: start`

- [ ] **Test icon mirroring**
  - **Deliverable:** List of icons that need RTL mirroring
  - **Icons to check:**
    - Arrows (should flip: ← becomes →)
    - Chevrons (should flip)
    - Directional indicators
  - **Implementation:**
    ```vue
    <template>
      <IconChevronRight
        :class="{ 'scale-x-[-1]': isRTL }"
      />
    </template>
    ```

#### 7.3 Date/Time Formatting Testing

- [ ] **Verify date formatting in Hebrew**
  - **Deliverable:** Test report with examples
  - **Test Cases:**
    | Component | Expected Format (Hebrew) | Verified |
    |-----------|-------------------------|----------|
    | CalendarView | "5 בינואר 2025" | [ ] |
    | AppointmentDetailsModal | "יום ראשון, 5 בינואר" | [ ] |
    | SessionCard | "05/01/2025" | [ ] |

- [ ] **Verify time formatting (24-hour in Hebrew)**
  - **Test Cases:**
    - 3:00 PM → "15:00" in Hebrew
    - 9:30 AM → "09:30" in Hebrew

- [ ] **Verify week start (Sunday for Hebrew)**
  - **Test:** Open calendar in Hebrew mode
  - **Verify:** Sunday appears as first column

#### 7.4 Accessibility Testing

- [ ] **Test Hebrew screen reader support**
  - **Deliverable:** Screen reader test report
  - **Tools:** NVDA (Windows), VoiceOver (Mac), TalkBack (Android)
  - **Test Cases:**
    - Hebrew text read correctly
    - Form labels announced in Hebrew
    - Button labels announced in Hebrew
    - Error messages announced in Hebrew
  - **Note:** Hebrew screen readers should automatically detect `lang="he"` and use Hebrew voice

- [ ] **Test keyboard navigation in RTL**
  - **Deliverable:** Keyboard navigation test report
  - **Test Cases:**
    - Tab order follows visual order in RTL
    - Arrow keys work correctly (right goes to previous, left goes to next)
    - Shortcuts still work (Ctrl+S, Cmd+K, etc.)

#### 7.5 Locale Persistence Testing

- [ ] **Test localStorage persistence**
  - **Test Steps:**
    1. Set locale to Hebrew
    2. Refresh page
    3. Verify locale is still Hebrew
    4. Clear localStorage
    5. Verify locale resets to browser default

- [ ] **Test browser locale detection**
  - **Test Steps:**
    1. Clear localStorage
    2. Set browser language to Hebrew (he-IL)
    3. Load app
    4. Verify app loads in Hebrew
    5. Set browser language to English
    6. Load app
    7. Verify app loads in English

#### 7.6 Toast Notification Testing

- [ ] **Update vue-toastification RTL support**
  - **Deliverable:** Updated toast configuration in `main.ts`
  - **Implementation:**
    ```typescript
    // src/main.ts
    import { watch } from 'vue'
    import { i18n } from './plugins/i18n'

    // ... existing code

    // Watch locale changes and update toast RTL
    watch(
      () => i18n.global.locale.value,
      (newLocale) => {
        const toast = app.config.globalProperties.$toast
        if (toast && toast.updateOptions) {
          toast.updateOptions({
            rtl: newLocale === 'he',
          })
        }
      }
    )
    ```

- [ ] **Test toast messages in Hebrew**
  - **Test Cases:**
    - Success toast: "הפגישה נוצרה בהצלחה"
    - Error toast: "אירעה שגיאה בשמירת הנתונים"
    - Undo action: "ביטול"

#### 7.7 Performance Testing

- [ ] **Measure bundle size impact**
  - **Deliverable:** Bundle size comparison report
  - **Commands:**
    ```bash
    npm run build
    # Check dist/assets/*.js sizes
    ls -lh dist/assets/*.js
    ```
  - **Expected:** ~10-15KB increase for Hebrew translations

- [ ] **Test initial load time**
  - **Deliverable:** Performance comparison (English vs Hebrew)
  - **Tool:** Chrome DevTools Performance tab
  - **Metrics:**
    - Time to Interactive (TTI)
    - First Contentful Paint (FCP)
  - **Acceptance:** <5% performance degradation

#### 7.8 Edge Case Testing

- [ ] **Test mixed LTR/RTL content**
  - **Test Cases:**
    - English name in Hebrew interface
    - Email addresses in Hebrew text
    - Phone numbers in Hebrew text
  - **Verify:** `dir="auto"` on inputs handles mixed content correctly

- [ ] **Test locale switching mid-session**
  - **Test Steps:**
    1. Load app in English
    2. Navigate to Calendar view
    3. Switch to Hebrew in Settings
    4. Verify entire UI updates without refresh
    5. Verify no layout glitches

- [ ] **Test with incomplete translations**
  - **Test:** Remove a translation key from `he.json`
  - **Verify:** Falls back to English version
  - **Verify:** Console warning appears in dev mode

**Phase 7 Completion Checklist:**
- [ ] Zero missing translation warnings
- [ ] All RTL layouts render correctly
- [ ] Date/time formatting works in Hebrew
- [ ] Screen readers announce Hebrew correctly
- [ ] Locale persists across sessions
- [ ] Toast notifications work in RTL
- [ ] Bundle size impact acceptable (<15KB)

**Estimated Time:** 12-15 hours

---

## Rollback & Safety Considerations

### Feature Flag Strategy

**Option 1: Environment Variable (Recommended for Development)**

```typescript
// vite.config.ts or .env
VITE_I18N_ENABLED=true
```

```typescript
// src/main.ts
const i18nEnabled = import.meta.env.VITE_I18N_ENABLED === 'true'

if (i18nEnabled) {
  app.use(i18n)
} else {
  console.warn('[i18n] Internationalization disabled via environment variable')
}
```

**Option 2: Workspace-Level Feature Flag (Production)**

Once backend supports workspace settings:

```typescript
// Add to workspace settings
interface WorkspaceSettings {
  i18n_enabled: boolean
  default_locale: 'en' | 'he'
}

// Check in frontend
const workspaceStore = useWorkspaceStore()
if (workspaceStore.settings.i18n_enabled) {
  // Use i18n
} else {
  // Fallback to English only
}
```

### Missing Translation Detection

**Production Logging:**

```typescript
// src/plugins/i18n.ts
export const i18n = createI18n({
  legacy: false,
  locale: detectBrowserLocale(),
  fallbackLocale: 'en',
  messages,

  // Production: Log missing translations
  missing: (locale, key) => {
    if (import.meta.env.MODE === 'production') {
      // Send to error tracking (e.g., Sentry)
      console.error(`[i18n] Missing translation: ${locale}.${key}`)
    }
  },
})
```

### Graceful Fallback

**If i18n plugin fails to initialize:**

```typescript
// src/main.ts
try {
  app.use(i18n)
} catch (error) {
  console.error('[i18n] Failed to initialize i18n plugin:', error)
  // App continues without i18n (defaults to hardcoded strings)
}
```

### Rollback Procedure

**If critical i18n issues are found in production:**

1. **Quick Fix:** Set `VITE_I18N_ENABLED=false` in environment
2. **Redeploy:** Frontend rebuilds without i18n plugin
3. **Investigate:** Fix issues in development environment
4. **Re-enable:** Set `VITE_I18N_ENABLED=true` after verification

---

## Time Estimates

### Summary Table

| Phase | Description | Estimated Time |
|-------|-------------|---------------|
| 1 | Infrastructure Setup | 4-6 hours |
| 2 | Core Framework Implementation | 8-10 hours |
| 3 | High-Priority Components | 20-25 hours |
| 4 | Medium-Priority Components | 15-20 hours |
| 5 | Low-Priority Components | 10-15 hours |
| 6 | Third-Party Library Localization | 6-8 hours |
| 7 | Testing & QA | 12-15 hours |
| **Total** | **Full Implementation** | **75-99 hours** |

### Team Allocation (Recommended)

**Single Developer:**
- **Sprint 1 (Week 1):** Phases 1-2 (12-16 hours)
- **Sprint 2 (Week 2):** Phase 3 (20-25 hours)
- **Sprint 3 (Week 3):** Phases 4-5 (25-35 hours)
- **Sprint 4 (Week 4):** Phases 6-7 (18-23 hours)

**Two Developers (Parallel):**
- **Week 1:** Dev 1 (Phases 1-2), Dev 2 (Translate strings offline)
- **Week 2:** Dev 1 (Phase 3), Dev 2 (Phase 4)
- **Week 3:** Dev 1 (Phase 5), Dev 2 (Phase 6)
- **Week 4:** Both (Phase 7 - Testing & QA)

---

## Appendix: Code Examples

### A. Complete Component Translation Example

**Before (LoginView.vue):**
```vue
<template>
  <div class="login-container">
    <h2>Sign In</h2>
    <form @submit.prevent="handleSubmit">
      <label>Email Address</label>
      <input v-model="email" type="email" placeholder="you@example.com" />
      <button type="submit">Send Magic Link</button>
    </form>
  </div>
</template>
```

**After (LoginView.vue):**
```vue
<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
const email = ref('')

async function handleSubmit() {
  // ... submit logic
}
</script>

<template>
  <div class="login-container">
    <h2>{{ t('auth.login.title') }}</h2>
    <form @submit.prevent="handleSubmit">
      <label>{{ t('auth.login.emailLabel') }}</label>
      <input
        v-model="email"
        type="email"
        :placeholder="t('auth.login.emailPlaceholder')"
      />
      <button type="submit">{{ t('auth.login.submitButton') }}</button>
    </form>
  </div>
</template>
```

### B. RTL CSS Conversion Example

**Before (physical properties):**
```css
.sidebar {
  float: left;
  margin-right: 20px;
  padding-left: 10px;
  text-align: left;
}

.arrow-icon {
  margin-left: 8px;
}
```

**After (logical properties):**
```css
.sidebar {
  float: inline-start;
  margin-inline-end: 20px;
  padding-inline-start: 10px;
  text-align: start;
}

.arrow-icon {
  margin-inline-start: 8px;
}
```

### C. Date Formatting Example

**Before:**
```vue
<script setup lang="ts">
import { format } from 'date-fns'

const appointmentDate = ref(new Date())
const formattedDate = computed(() => format(appointmentDate.value, 'PPP'))
</script>

<template>
  <div>{{ formattedDate }}</div>
</template>
```

**After:**
```vue
<script setup lang="ts">
import { useDateFormat } from '@/utils/dateFormat'

const appointmentDate = ref(new Date())
const { formatDate } = useDateFormat()
const formattedDate = computed(() => formatDate(appointmentDate.value, 'PPP'))
</script>

<template>
  <div>{{ formattedDate }}</div>
</template>
```

---

## Next Steps

After completing this plan:

1. **Review with team:** Ensure all stakeholders understand timeline and scope
2. **Set up tracking:** Create GitHub issues for each phase
3. **Prepare translation resources:** Hire professional medical translator for Hebrew
4. **Begin Phase 1:** Install dependencies and configure Vite
5. **Daily standups:** Track progress against time estimates

---

**Document Prepared By:** Frontend Specialist
**Date:** 2025-11-03
**Status:** Ready for Implementation Review
