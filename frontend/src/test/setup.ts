/**
 * Vitest setup file
 *
 * Runs before each test suite. Use this for global test configuration,
 * mock setup, and test utilities.
 */

import { beforeAll, beforeEach, afterEach, afterAll, vi } from 'vitest'
import { config } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import nodeCrypto from 'crypto'

// Polyfill for crypto.hash (Node.js 20.11 compatibility with Vite Vue plugin)
// The crypto.hash method was added in Node.js v21.7.0, but we're on v20.11
if (!nodeCrypto.hash) {
  // @ts-expect-error - Adding polyfill for missing crypto.hash in Node.js v20
  nodeCrypto.hash = (
    algorithm: string,
    data: string | Buffer,
    outputEncoding?: string
  ): Buffer | string => {
    const hash = nodeCrypto.createHash(algorithm).update(data)
    return outputEncoding
      ? hash.digest(outputEncoding as BufferEncoding)
      : hash.digest()
  }
}

// Create i18n instance for tests with minimal config
const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: {
    en: {},
    he: {},
  },
  missingWarn: false,
  fallbackWarn: false,
})

// Setup Vue Test Utils global config
// Note: Router is NOT installed globally - each test file creates its own router
// as needed to avoid conflicts and allow test-specific routing scenarios
// i18n IS installed globally since most components need it
config.global.plugins = [i18n]
config.global.mocks = {
  // Add global mocks if needed
}

// Setup console error/warning suppression for expected errors in tests
const originalConsoleError = console.error
const originalConsoleWarn = console.warn

beforeAll(() => {
  // Suppress Vue warnings in tests (unless debugging)
  console.warn = vi.fn()

  // Filter out expected error messages
  console.error = (...args: unknown[]) => {
    const message = args[0]?.toString() || ''

    // Allow through real errors
    if (!message.includes('[Vue warn]') && !message.includes('Not implemented')) {
      originalConsoleError(...args)
    }
  }
})

afterAll(() => {
  console.error = originalConsoleError
  console.warn = originalConsoleWarn
})

// Clean up after each test to ensure isolation
// Note: We do cleanup in afterEach (not beforeEach) to allow test files'
// beforeEach hooks to run first and set up their required state
afterEach(() => {
  // 1. Clear localStorage
  localStorage.clear()

  // 2. Clear sessionStorage
  sessionStorage.clear()

  // 3. Reset Pinia stores
  setActivePinia(createPinia())

  // 4. Clear mocks
  vi.clearAllMocks()
})
