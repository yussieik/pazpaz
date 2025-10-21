/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request schema for magic link token verification.
 *
 * Security: Token length validation prevents malformed or suspicious tokens.
 * - Min 32 chars: Ensures sufficient entropy (minimum 256 bits for URL-safe base64)
 * - Max 128 chars: Prevents buffer overflow or DOS attacks via oversized tokens
 * - 384-bit tokens: 48 bytes base64url encoded = 64 characters
 */
export type TokenVerifyRequest = {
    /**
     * Magic link token from email (384-bit entropy)
     */
    token: string;
};

