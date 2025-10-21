/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response for TOTP enrollment.
 */
export type TOTPEnrollResponse = {
    /**
     * Base32-encoded TOTP secret (store securely in authenticator)
     */
    secret: string;
    /**
     * Data URI with QR code image (scan with authenticator app)
     */
    qr_code: string;
    /**
     * One-time backup codes (save offline, shown only once)
     */
    backup_codes: Array<string>;
};

