/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { ConflictingAppointmentDetail } from './ConflictingAppointmentDetail'
/**
 * Schema for conflict check response.
 */
export type ConflictCheckResponse = {
  /**
   * Whether a conflict exists
   */
  has_conflict: boolean
  /**
   * List of conflicting appointments with privacy-preserving details
   */
  conflicting_appointments?: Array<ConflictingAppointmentDetail>
}
