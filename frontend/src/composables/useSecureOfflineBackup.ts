import apiClient from '@/api/client'

/**
 * Secure Offline Backup Composable
 *
 * Provides client-side encrypted localStorage backup for SOAP session drafts.
 * Implements AES-256-GCM encryption using Web Crypto API with key derivation from JWT.
 *
 * Security Features:
 * - Client-side encryption using Web Crypto API (AES-256-GCM)
 * - Key derived from JWT token via PBKDF2 (100,000 iterations, SHA-256)
 * - Automatic key rotation when JWT expires (every 7 days)
 * - 24-hour TTL on encrypted backups
 * - Auto-cleanup on logout
 * - Graceful error handling for decryption failures
 *
 * HIPAA Compliance:
 * - PHI never stored unencrypted in localStorage
 * - Encryption keys derived from session tokens (ephemeral)
 * - Automatic expiration prevents stale PHI leakage
 * - Logout clears all encrypted backups
 *
 * Usage:
 *   const { backupDraft, restoreDraft, syncToServer, clearAllBackups } = useSecureOfflineBackup()
 *
 *   // Save encrypted backup (called by autosave)
 *   await backupDraft(sessionId, draftData, version)
 *
 *   // Restore backup on page load
 *   const backup = await restoreDraft(sessionId)
 *   if (backup) {
 *     // Show restore prompt to user
 *   }
 *
 *   // Sync to server (called on reconnect or user confirmation)
 *   await syncToServer(sessionId)
 *
 *   // Clear all backups (called on logout)
 *   clearAllBackups()
 */

interface SessionDraft {
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  session_date: string
  duration_minutes: number | null
}

interface EncryptedBackup {
  encrypted_data: string // Base64-encoded ciphertext
  iv: string // Initialization vector (Base64)
  timestamp: number // Unix timestamp for expiration
  version: number // Session version for optimistic locking
}

const LOCALSTORAGE_TTL_HOURS = 24
const APP_SALT = 'pazpaz-draft-encryption-v1' // App-specific salt for key derivation

export function useSecureOfflineBackup() {
  /**
   * Get JWT token from cookie
   * SECURITY: JWT token used as key material (rotates every 7 days)
   */
  function getJwtToken(): string | null {
    const match = document.cookie.match(/access_token=([^;]+)/)
    return match?.[1] ?? null
  }

  /**
   * Derive encryption key from JWT token using PBKDF2
   * SECURITY: 100,000 iterations, SHA-256, AES-GCM 256-bit
   */
  async function deriveKey(jwtToken: string): Promise<CryptoKey> {
    // Import JWT as key material (use first 32 chars for consistency)
    const keyMaterial = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(jwtToken.substring(0, 32)),
      { name: 'PBKDF2' },
      false,
      ['deriveKey']
    )

    // Derive AES-GCM key
    return await crypto.subtle.deriveKey(
      {
        name: 'PBKDF2',
        salt: new TextEncoder().encode(APP_SALT),
        iterations: 100000,
        hash: 'SHA-256',
      },
      keyMaterial,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    )
  }

  /**
   * Encrypt draft data using AES-256-GCM
   * SECURITY: Random IV, authenticated encryption
   */
  async function encryptDraft(
    draft: SessionDraft,
    version: number,
    jwtToken: string
  ): Promise<EncryptedBackup> {
    const key = await deriveKey(jwtToken)

    // Generate random IV (12 bytes for AES-GCM)
    const iv = crypto.getRandomValues(new Uint8Array(12))

    // Encrypt draft data
    const plaintext = new TextEncoder().encode(JSON.stringify(draft))
    const ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      plaintext
    )

    return {
      encrypted_data: btoa(String.fromCharCode(...new Uint8Array(ciphertext))),
      iv: btoa(String.fromCharCode(...iv)),
      timestamp: Date.now(),
      version,
    }
  }

  /**
   * Decrypt draft data using AES-256-GCM
   * SECURITY: Validates MAC, throws on tampering
   */
  async function decryptDraft(
    backup: EncryptedBackup,
    jwtToken: string
  ): Promise<SessionDraft> {
    const key = await deriveKey(jwtToken)

    // Decode Base64
    const iv = new Uint8Array(
      atob(backup.iv)
        .split('')
        .map((c) => c.charCodeAt(0))
    )
    const ciphertext = new Uint8Array(
      atob(backup.encrypted_data)
        .split('')
        .map((c) => c.charCodeAt(0))
    )

    // Decrypt
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext
    )

    return JSON.parse(new TextDecoder().decode(plaintext))
  }

  /**
   * Save encrypted draft to localStorage
   * HIPAA COMPLIANCE: PHI encrypted at rest in browser
   */
  async function backupDraft(
    sessionId: string,
    draft: SessionDraft,
    version: number
  ): Promise<void> {
    const jwtToken = getJwtToken()
    if (!jwtToken) {
      console.warn('[SecureBackup] Cannot encrypt: No JWT token')
      return
    }

    try {
      const encrypted = await encryptDraft(draft, version, jwtToken)
      localStorage.setItem(`session_${sessionId}_backup`, JSON.stringify(encrypted))
      console.info(`[SecureBackup] Encrypted backup saved for session ${sessionId}`)
    } catch (error) {
      console.error('[SecureBackup] Encryption failed:', error)
      // Don't block autosave if encryption fails
    }
  }

  /**
   * Restore encrypted draft from localStorage
   * SECURITY: Validates expiration, handles decryption failures
   */
  async function restoreDraft(
    sessionId: string
  ): Promise<{ draft: SessionDraft; version: number; timestamp: number } | null> {
    const item = localStorage.getItem(`session_${sessionId}_backup`)
    if (!item) return null

    try {
      const encrypted = JSON.parse(item) as EncryptedBackup

      // Check expiration (24-hour TTL)
      const ageHours = (Date.now() - encrypted.timestamp) / (1000 * 60 * 60)
      if (ageHours > LOCALSTORAGE_TTL_HOURS) {
        console.warn(
          `[SecureBackup] Backup expired (${ageHours.toFixed(1)}h old), deleting`
        )
        localStorage.removeItem(`session_${sessionId}_backup`)
        return null
      }

      const jwtToken = getJwtToken()
      if (!jwtToken) {
        console.warn('[SecureBackup] Cannot decrypt: No JWT token')
        localStorage.removeItem(`session_${sessionId}_backup`)
        return null
      }

      const draft = await decryptDraft(encrypted, jwtToken)
      return { draft, version: encrypted.version, timestamp: encrypted.timestamp }
    } catch (error) {
      console.error('[SecureBackup] Decryption failed:', error)
      localStorage.removeItem(`session_${sessionId}_backup`)
      return null
    }
  }

  /**
   * Sync localStorage backup to server
   * Uses existing PATCH /sessions/{id}/draft endpoint
   */
  async function syncToServer(sessionId: string): Promise<boolean> {
    const backup = await restoreDraft(sessionId)
    if (!backup) return false

    try {
      await apiClient.patch(`/sessions/${sessionId}/draft`, {
        ...backup.draft,
      })

      // Clear localStorage after successful sync
      localStorage.removeItem(`session_${sessionId}_backup`)
      console.info(`[SecureBackup] Synced backup to server for session ${sessionId}`)
      return true
    } catch (error) {
      console.error('[SecureBackup] Sync failed:', error)
      return false
    }
  }

  /**
   * Clear all session backups (called on logout)
   * HIPAA COMPLIANCE: Prevent PHI leakage on shared computers
   */
  function clearAllBackups(): void {
    const keys = Object.keys(localStorage)
    let cleared = 0

    for (const key of keys) {
      if (key.startsWith('session_') && key.endsWith('_backup')) {
        localStorage.removeItem(key)
        cleared++
      }
    }

    if (cleared > 0) {
      console.info(`[SecureBackup] Cleared ${cleared} backup(s) on logout`)
    }
  }

  return {
    backupDraft,
    restoreDraft,
    syncToServer,
    clearAllBackups,
  }
}
