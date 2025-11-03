/**
 * Vue I18n Plugin Configuration
 * ===============================
 * Configures internationalization with auto-detected locale and RTL support
 */

import { createI18n } from 'vue-i18n'
import { messages, supportedLocales, type SupportedLocale } from '@/locales'

/**
 * Browser locale detection
 *
 * Priority:
 * 1. localStorage preference (user explicitly changed language)
 * 2. Browser locale (navigator.language)
 * 3. Default to English
 */
function detectBrowserLocale(): SupportedLocale {
  // Check localStorage for saved preference
  const savedLocale = localStorage.getItem('pazpaz_locale') as SupportedLocale | null
  if (savedLocale && supportedLocales.includes(savedLocale)) {
    return savedLocale
  }

  // Check browser locale
  const browserLocale = navigator.language.toLowerCase()

  // Israeli users get Hebrew by default
  if (browserLocale.startsWith('he') || browserLocale.startsWith('iw')) {
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
export function getLocaleDirection(locale: SupportedLocale): 'ltr' | 'rtl' {
  return locale === 'he' ? 'rtl' : 'ltr'
}
