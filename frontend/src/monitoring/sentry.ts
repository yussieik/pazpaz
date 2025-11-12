/**
 * Sentry configuration with PII stripping for frontend errors.
 *
 * This module configures Sentry error tracking for the Vue application
 * with HIPAA-compliant PII/PHI stripping to ensure no sensitive data
 * is sent to external monitoring systems.
 */

import * as Sentry from '@sentry/vue'
import type { App } from 'vue'
import type { Router } from 'vue-router'

/**
 * Strip PII from Sentry events (HIPAA compliance).
 *
 * Removes sensitive data before sending to Sentry:
 * - User email/phone (keeps ID only for tracking)
 * - Request cookies and headers (may contain auth tokens)
 * - API response data (may contain PHI from backend)
 * - Query strings (may contain tokens or PII)
 *
 * @param event - Sentry event to sanitize
 * @returns Sanitized event, or null to drop the event
 */
function stripPii(event: Sentry.Event): Sentry.Event | null {
  // Remove user email/phone (keep ID only for tracking)
  if (event.user) {
    event.user = { id: event.user.id }
  }

  // Scrub request data
  if (event.request) {
    // Remove cookies (may contain session tokens, auth headers)
    delete event.request.cookies

    // Remove all headers (may contain Authorization, X-CSRF-Token, etc.)
    delete event.request.headers

    // Remove query string (may contain tokens or PII)
    delete event.request.query_string
  }

  // Scrub breadcrumbs (may contain PHI in API responses)
  if (event.breadcrumbs) {
    event.breadcrumbs = event.breadcrumbs.map((crumb) => {
      // Redact API response data (may contain client info, session notes, etc.)
      if (crumb.category === 'fetch' || crumb.category === 'xhr') {
        if (crumb.data && crumb.data.response) {
          crumb.data.response = '[REDACTED]'
        }
        // Also redact request body (may contain PHI being sent to API)
        if (crumb.data && crumb.data.body) {
          crumb.data.body = '[REDACTED]'
        }
      }

      // Redact console logs (developers may accidentally log PHI)
      if (crumb.category === 'console') {
        if (crumb.message) {
          // Keep error type but redact message content
          crumb.message = '[REDACTED CONSOLE MESSAGE]'
        }
      }

      return crumb
    })
  }

  return event
}

/**
 * Initialize Sentry for Vue app.
 *
 * Configuration:
 * - Environment-based DSN from Vite env vars
 * - 10% transaction sampling for cost control
 * - Vue integration for component tracking
 * - Browser tracing integration for performance
 * - Session replay for error debugging (with PII masking)
 * - PII stripping via beforeSend hook
 *
 * @param app - Vue application instance
 * @param router - Vue Router instance
 */
export function initSentry(app: App, router: Router) {
  const dsn = import.meta.env.VITE_SENTRY_DSN

  // Sentry not configured - acceptable in local dev
  if (!dsn) {
    console.warn('[Sentry] DSN not configured, error tracking disabled')
    return
  }

  Sentry.init({
    app,
    dsn,
    // Environment tag for filtering in Sentry dashboard
    environment: import.meta.env.MODE, // "production" or "development"

    // Integrations
    integrations: [
      // Vue integration: Tracks Vue component errors and lifecycle
      // Router integration: Tracks page navigations as transactions
      Sentry.browserTracingIntegration({ router }),

      // Session replay: Records user sessions for error debugging
      // Automatically masks sensitive form inputs (passwords, credit cards, etc.)
      Sentry.replayIntegration(),
    ],

    // Performance monitoring
    tracesSampleRate: 0.1, // 10% of transactions (cost control)

    // Session replay sampling
    replaysSessionSampleRate: 0.1, // 10% of normal sessions
    replaysOnErrorSampleRate: 1.0, // 100% of sessions with errors get replay

    // PII/PHI stripping (HIPAA compliance)
    beforeSend: stripPii,

    // Additional settings
    attachStacktrace: true, // Include stack traces for all events
    maxBreadcrumbs: 50, // Limit breadcrumb history
    sendDefaultPii: false, // Never send PII automatically
  })

  console.warn('[Sentry] Initialized for environment:', import.meta.env.MODE)
}
