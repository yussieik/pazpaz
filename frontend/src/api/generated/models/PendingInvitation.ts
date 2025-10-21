/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Single pending invitation details.
 *
 * Example:
 * ```json
 * {
     * "user_id": "987e6543-e21b-34c5-b678-123456789012",
     * "email": "sarah@example.com",
     * "full_name": "Sarah Chen",
     * "workspace_name": "Sarah's Massage Therapy",
     * "invited_at": "2025-10-15T10:30:00Z",
     * "expires_at": "2025-10-22T10:30:00Z"
     * }
     * ```
     */
    export type PendingInvitation = {
        /**
         * UUID of the user
         */
        user_id: string;
        /**
         * Email address of the therapist
         */
        email: string;
        /**
         * Full name of the therapist
         */
        full_name: string;
        /**
         * Name of the workspace
         */
        workspace_name: string;
        /**
         * When invitation was sent (UTC timezone)
         */
        invited_at: string;
        /**
         * When invitation expires (UTC timezone)
         */
        expires_at: string;
    };

