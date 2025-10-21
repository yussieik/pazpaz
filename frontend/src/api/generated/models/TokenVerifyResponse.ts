/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UserInToken } from './UserInToken';
/**
 * Response schema for token verification.
 */
export type TokenVerifyResponse = {
    /**
     * JWT access token
     */
    access_token: string;
    /**
     * Token type
     */
    token_type?: string;
    /**
     * Authenticated user information
     */
    user: UserInToken;
};

