/**
 * i18n composable for PazPaz
 * ============================
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

import { useI18n as useVueI18n } from 'vue-i18n'
import { computed, watch } from 'vue'
import type { SupportedLocale } from '@/locales'
import { getLocaleDirection } from '@/plugins/i18n'

export function useI18n() {
  const { t, locale } = useVueI18n()

  // Current locale direction
  const isRTL = computed(() => locale.value === 'he')
  const direction = computed(() => getLocaleDirection(locale.value as SupportedLocale))

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
  function setLocale(newLocale: SupportedLocale) {
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
    setLocale(newLocale as SupportedLocale)
  }

  // Watch locale changes and update document direction
  watch(locale, (newLocale) => {
    const dir = getLocaleDirection(newLocale as SupportedLocale)
    document.documentElement.setAttribute('dir', dir)
    document.documentElement.setAttribute('lang', newLocale)
  })

  return {
    t,
    locale: computed(() => locale.value as SupportedLocale),
    setLocale,
    toggleLocale,
    isRTL,
    direction,
  }
}
