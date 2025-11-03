/**
 * Locale Configuration
 * ====================
 * Exports locale messages for vue-i18n
 */

import en from './en.json'
import he from './he.json'

export const messages = {
  en,
  he,
}

export const defaultLocale = 'en'

export const supportedLocales = ['en', 'he'] as const

export type SupportedLocale = (typeof supportedLocales)[number]
