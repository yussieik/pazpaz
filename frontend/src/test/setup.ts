/**
 * Vitest setup file
 *
 * Runs before each test suite. Use this for global test configuration,
 * mock setup, and test utilities.
 */

import { beforeAll, afterEach, afterAll, vi } from 'vitest'
import { config } from '@vue/test-utils'
import nodeCrypto from 'crypto'

// Polyfill for crypto.hash (Node.js 20.11 compatibility with Vite Vue plugin)
// The crypto.hash method was added in Node.js v21.7.0, but we're on v20.11
if (!nodeCrypto.hash) {
  // @ts-ignore - Adding missing method for Node.js v20
  nodeCrypto.hash = (algorithm: string, data: string | Buffer): string => {
    return nodeCrypto.createHash(algorithm).update(data).digest('hex')
  }
}

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
