/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { LocationType } from './LocationType'
/**
 * Schema for location API responses.
 */
export type LocationResponse = {
  /**
   * Location name
   */
  name: string
  /**
   * Type: clinic, home, or online
   */
  location_type: LocationType
  /**
   * Physical address for clinic or home visits
   */
  address?: string | null
  /**
   * Additional details (room, video link, parking)
   */
  details?: string | null
  /**
   * Active locations appear in scheduling UI
   */
  is_active?: boolean
  id: string
  workspace_id: string
  created_at: string
  updated_at: string
}
