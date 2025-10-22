/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
/**
 * Request to disable TOTP (requires verification).
 */
export type TOTPDisableRequest = {
    /**
     * Current 6-digit TOTP code or 8-character backup code
     */
    totp_code: string;
};

