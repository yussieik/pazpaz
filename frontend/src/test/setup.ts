/**
 * Vitest setup file
 *
 * Runs before each test suite. Use this for global test configuration,
 * mock setup, and test utilities.
 */

import { beforeAll, afterEach, afterAll, vi } from 'vitest'
import { config } from '@vue/test-utils'

// Setup Vue Test Utils global config
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

// Clean up after each test
afterEach(() => {
  vi.clearAllMocks()
})
