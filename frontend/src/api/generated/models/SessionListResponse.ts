/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { SessionResponse } from './SessionResponse'
/**
 * Schema for paginated session list response.
 */
export type SessionListResponse = {
  items: Array<SessionResponse>
  total: number
  page: number
  page_size: number
  total_pages: number
}
