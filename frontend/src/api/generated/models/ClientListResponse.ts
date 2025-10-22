/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { ClientResponse } from './ClientResponse'
/**
 * Schema for paginated client list response.
 */
export type ClientListResponse = {
  items: Array<ClientResponse>
  total: number
  page: number
  page_size: number
  total_pages: number
}
