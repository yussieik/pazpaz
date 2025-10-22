/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { AppointmentResponse } from './AppointmentResponse'
/**
 * Schema for paginated appointment list response.
 */
export type AppointmentListResponse = {
  items: Array<AppointmentResponse>
  total: number
  page: number
  page_size: number
  total_pages: number
}
