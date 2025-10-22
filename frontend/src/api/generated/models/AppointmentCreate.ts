/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { LocationType } from './LocationType'
/**
 * Schema for creating a new appointment.
 *
 * SECURITY: workspace_id is NOT accepted from client requests.
 * It is automatically injected from the authenticated user's session.
 * This prevents workspace injection vulnerabilities.
 */
export type AppointmentCreate = {
  /**
   * ID of the client for this appointment
   */
  client_id: string
  /**
   * Start time (timezone-aware UTC)
   */
  scheduled_start: string
  /**
   * End time (timezone-aware UTC)
   */
  scheduled_end: string
  /**
   * Type of location (clinic/home/online)
   */
  location_type: LocationType
  /**
   * Additional location details
   */
  location_details?: string | null
  /**
   * Therapist notes for the appointment
   */
  notes?: string | null
}
