/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { UserInToken } from './UserInToken'
/**
 * Response for 2FA verification after magic link.
 */
export type MagicLink2FAResponse = {
  /**
   * JWT access token
   */
  access_token: string
  /**
   * Token type
   */
  token_type?: string
  /**
   * Authenticated user information
   */
  user: UserInToken
}
