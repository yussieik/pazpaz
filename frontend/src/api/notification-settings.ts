/**
 * Notification Settings API Client
 *
 * Handles all API calls related to user notification preferences.
 */

import apiClient from './client'
import type {
  NotificationSettings,
  NotificationSettingsUpdate,
} from '@/types/notification-settings'

/**
 * Get current user's notification settings
 *
 * @returns Promise<NotificationSettings>
 * @throws Error if API call fails
 */
export async function getNotificationSettings(): Promise<NotificationSettings> {
  const response = await apiClient.get<NotificationSettings>(
    '/users/me/notification-settings'
  )
  return response.data
}

/**
 * Update current user's notification settings
 *
 * Supports partial updates - only provided fields will be updated.
 *
 * @param updates - Partial notification settings to update
 * @returns Promise<NotificationSettings>
 * @throws Error if API call fails
 */
export async function updateNotificationSettings(
  updates: NotificationSettingsUpdate
): Promise<NotificationSettings> {
  const response = await apiClient.put<NotificationSettings>(
    '/users/me/notification-settings',
    updates
  )
  return response.data
}
