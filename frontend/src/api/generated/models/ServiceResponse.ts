/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Schema for service API responses.
 */
export type ServiceResponse = {
  /**
   * Service name
   */
  name: string
  /**
   * Optional description of the service
   */
  description?: string | null
  /**
   * Default duration in minutes (must be > 0)
   */
  default_duration_minutes: number
  /**
   * Active services appear in scheduling UI
   */
  is_active?: boolean
  id: string
  workspace_id: string
  created_at: string
  updated_at: string
}
