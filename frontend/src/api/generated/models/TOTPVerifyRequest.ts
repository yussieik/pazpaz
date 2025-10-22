/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Request to verify TOTP code during enrollment.
 */
export type TOTPVerifyRequest = {
  /**
   * 6-digit TOTP code from authenticator app
   */
  code: string
}
