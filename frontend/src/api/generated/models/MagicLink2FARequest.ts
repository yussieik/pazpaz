/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request to complete authentication with 2FA after magic link.
 */
export type MagicLink2FARequest = {
    /**
     * Temporary token from magic link verification
     */
    temp_token: string;
    /**
     * 6-digit TOTP code or 8-character backup code
     */
    totp_code: string;
};

