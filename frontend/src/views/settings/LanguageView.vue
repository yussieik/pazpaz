<script setup lang="ts">
/**
 * Language Settings View
 *
 * Allows users to change the interface language between English and Hebrew.
 * Features:
 * - Radio button selection for language
 * - Visual indication of current language
 * - Toast notification on language change
 * - Automatic RTL/LTR direction switching
 */

import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'

const { locale, setLocale, t } = useI18n()
const { showSuccess } = useToast()

function handleLanguageChange(newLocale: 'en' | 'he') {
  setLocale(newLocale)
  showSuccess(t('settings.language.changeSuccess'))
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-slate-900">
        {{ t('settings.language.title') }}
      </h1>
      <p class="mt-2 text-sm text-slate-600">
        {{ t('settings.language.description') }}
      </p>
    </div>

    <!-- Language Selection Card -->
    <div class="max-w-2xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 class="mb-4 text-base font-semibold text-slate-900">
        {{ t('settings.language.currentLanguage') }}
      </h2>

      <div class="space-y-3">
        <!-- English Option -->
        <label
          class="flex cursor-pointer items-center gap-4 rounded-lg border-2 p-4 transition-all"
          :class="{
            'border-emerald-600 bg-emerald-50': locale === 'en',
            'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50':
              locale !== 'en',
          }"
        >
          <input
            type="radio"
            name="language"
            value="en"
            :checked="locale === 'en'"
            class="h-4 w-4 border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            @change="handleLanguageChange('en')"
          />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-slate-900">
                {{ t('settings.language.english') }}
              </span>
              <span
                v-if="locale === 'en'"
                class="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white"
              >
                {{ t('settings.language.currentLanguage') }}
              </span>
            </div>
          </div>
        </label>

        <!-- Hebrew Option -->
        <label
          class="flex cursor-pointer items-center gap-4 rounded-lg border-2 p-4 transition-all"
          :class="{
            'border-emerald-600 bg-emerald-50': locale === 'he',
            'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50':
              locale !== 'he',
          }"
        >
          <input
            type="radio"
            name="language"
            value="he"
            :checked="locale === 'he'"
            class="h-4 w-4 border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            @change="handleLanguageChange('he')"
          />
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-slate-900">
                {{ t('settings.language.hebrew') }}
              </span>
              <span
                v-if="locale === 'he'"
                class="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-medium text-white"
              >
                {{ t('settings.language.currentLanguage') }}
              </span>
            </div>
          </div>
        </label>
      </div>
    </div>
  </div>
</template>
