/**
 * TypeScript type definitions for vue-i18n
 *
 * This ensures type safety for translation keys throughout the app.
 * Any typo in t('key') will be caught at compile time.
 */

import type en from '@/locales/en.json'

export type MessageSchema = typeof en

declare module 'vue-i18n' {
  // Type-safe translation keys
  export interface DefineLocaleMessage extends MessageSchema {}

  // Ensure strict typing for locale codes
  export interface DefineDateTimeFormat {}
  export interface DefineNumberFormat {}
}
