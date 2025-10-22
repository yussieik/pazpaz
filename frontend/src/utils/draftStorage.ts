/**
 * Draft Storage Utility
 *
 * HIPAA-compliant IndexedDB storage for SOAP note drafts
 * Provides automatic cleanup on logout and draft restoration
 *
 * Security Features:
 * - Client-side storage only (not sent to server until user saves)
 * - Automatic expiration (24-hour TTL)
 * - Cleared on logout for shared computer safety
 * - Protected from accidental data loss
 */

import { openDB, type IDBPDatabase } from 'idb'

const DB_NAME = 'pazpaz_drafts'
const DB_VERSION = 1
const STORE_NAME = 'soap_notes'
const DRAFT_TTL_MS = 24 * 60 * 60 * 1000 // 24 hours

export interface SOAPNoteDraft {
  id: string // session_id
  clientId: string
  clientName: string
  sessionDate: string
  subjective: string
  objective: string
  assessment: string
  plan: string
  savedAt: Date
  expiresAt: Date
}

let dbPromise: Promise<IDBPDatabase> | null = null

/**
 * Initialize IndexedDB connection (lazy)
 */
async function getDB(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
          // Index by expiration for efficient cleanup
          store.createIndex('expiresAt', 'expiresAt')
          console.info('[DraftStorage] Created IndexedDB store:', STORE_NAME)
        }
      },
    })
  }
  return dbPromise
}

/**
 * Save SOAP note draft to IndexedDB
 *
 * @param draft - Draft content to save
 * @returns true if saved successfully
 */
export async function saveDraft(draft: Omit<SOAPNoteDraft, 'savedAt' | 'expiresAt'>): Promise<boolean> {
  try {
    const db = await getDB()
    const now = new Date()
    const draftWithTimestamp: SOAPNoteDraft = {
      ...draft,
      savedAt: now,
      expiresAt: new Date(now.getTime() + DRAFT_TTL_MS),
    }

    await db.put(STORE_NAME, draftWithTimestamp)
    console.info(`[DraftStorage] Saved draft for session: ${draft.id}`)
    return true
  } catch (error) {
    console.error('[DraftStorage] Failed to save draft:', error)
    return false
  }
}

/**
 * Get SOAP note draft by session ID
 *
 * @param sessionId - Session ID to retrieve draft for
 * @returns Draft content or null if not found/expired
 */
export async function getDraft(sessionId: string): Promise<SOAPNoteDraft | null> {
  try {
    const db = await getDB()
    const draft = await db.get(STORE_NAME, sessionId)

    if (!draft) {
      return null
    }

    // Check if draft has expired
    const now = new Date()
    if (new Date(draft.expiresAt) < now) {
      console.info(`[DraftStorage] Draft expired, deleting: ${sessionId}`)
      await db.delete(STORE_NAME, sessionId)
      return null
    }

    console.info(`[DraftStorage] Retrieved draft for session: ${sessionId}`)
    return draft
  } catch (error) {
    console.error('[DraftStorage] Failed to get draft:', error)
    return null
  }
}

/**
 * Delete specific SOAP note draft
 *
 * @param sessionId - Session ID to delete draft for
 * @returns true if deleted successfully
 */
export async function deleteDraft(sessionId: string): Promise<boolean> {
  try {
    const db = await getDB()
    await db.delete(STORE_NAME, sessionId)
    console.info(`[DraftStorage] Deleted draft for session: ${sessionId}`)
    return true
  } catch (error) {
    console.error('[DraftStorage] Failed to delete draft:', error)
    return false
  }
}

/**
 * Get all active SOAP note drafts (not expired)
 *
 * @returns Array of all drafts
 */
export async function getAllDrafts(): Promise<SOAPNoteDraft[]> {
  try {
    const db = await getDB()
    const allDrafts = await db.getAll(STORE_NAME)
    const now = new Date()

    // Filter out expired drafts and delete them
    const activeDrafts = allDrafts.filter((draft) => {
      const isExpired = new Date(draft.expiresAt) < now
      if (isExpired) {
        db.delete(STORE_NAME, draft.id).catch(console.error)
        return false
      }
      return true
    })

    console.info(`[DraftStorage] Retrieved ${activeDrafts.length} active drafts (${allDrafts.length - activeDrafts.length} expired)`)
    return activeDrafts
  } catch (error) {
    console.error('[DraftStorage] Failed to get all drafts:', error)
    return []
  }
}

/**
 * Get descriptions of all unsaved drafts (for logout confirmation)
 *
 * @returns Array of human-readable draft descriptions
 */
export async function getUnsavedDraftDescriptions(): Promise<string[]> {
  try {
    const drafts = await getAllDrafts()
    return drafts.map((draft) => {
      const date = new Date(draft.sessionDate).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
      return `${draft.clientName} (Session at ${date})`
    })
  } catch (error) {
    console.error('[DraftStorage] Failed to get draft descriptions:', error)
    return []
  }
}

/**
 * Clear all SOAP note drafts (called on logout)
 *
 * SECURITY: This is critical for HIPAA compliance
 * Prevents PHI leakage on shared computers
 *
 * @returns true if all drafts cleared successfully
 */
export async function clearAllDrafts(): Promise<boolean> {
  try {
    const db = await getDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    await tx.objectStore(STORE_NAME).clear()
    await tx.done

    console.info('[DraftStorage] Cleared all drafts (logout cleanup)')
    return true
  } catch (error) {
    console.error('[DraftStorage] Failed to clear all drafts:', error)
    return false
  }
}

/**
 * Clean up expired drafts (maintenance)
 *
 * Called automatically during getAllDrafts()
 * Can also be called manually on app init
 *
 * @returns Number of drafts deleted
 */
export async function cleanupExpiredDrafts(): Promise<number> {
  try {
    const db = await getDB()
    const now = new Date()
    let deletedCount = 0

    const allDrafts = await db.getAll(STORE_NAME)
    const deletePromises = allDrafts
      .filter((draft) => new Date(draft.expiresAt) < now)
      .map(async (draft) => {
        await db.delete(STORE_NAME, draft.id)
        deletedCount++
      })

    await Promise.all(deletePromises)

    if (deletedCount > 0) {
      console.info(`[DraftStorage] Cleaned up ${deletedCount} expired drafts`)
    }

    return deletedCount
  } catch (error) {
    console.error('[DraftStorage] Failed to cleanup expired drafts:', error)
    return 0
  }
}

/**
 * Check if draft exists for session
 *
 * @param sessionId - Session ID to check
 * @returns true if draft exists and is not expired
 */
export async function hasDraft(sessionId: string): Promise<boolean> {
  const draft = await getDraft(sessionId)
  return draft !== null
}

/**
 * Get draft age in minutes
 *
 * @param sessionId - Session ID to check
 * @returns Age in minutes, or null if draft doesn't exist
 */
export async function getDraftAge(sessionId: string): Promise<number | null> {
  const draft = await getDraft(sessionId)
  if (!draft) {
    return null
  }

  const now = new Date()
  const savedAt = new Date(draft.savedAt)
  const ageMs = now.getTime() - savedAt.getTime()
  return Math.floor(ageMs / (60 * 1000))
}
