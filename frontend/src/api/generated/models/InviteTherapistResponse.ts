/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for therapist invitation.
 *
 * Example:
 * ```json
 * {
     * "workspace_id": "123e4567-e89b-12d3-a456-426614174000",
     * "user_id": "987e6543-e21b-34c5-b678-123456789012",
     * "invitation_url": "https://app.pazpaz.com/accept-invitation?token=..."
     * }
     * ```
     */
    export type InviteTherapistResponse = {
        /**
         * UUID of the created workspace
         */
        workspace_id: string;
        /**
         * UUID of the created user (therapist)
         */
        user_id: string;
        /**
         * Magic link URL to send to therapist via email
         */
        invitation_url: string;
    };

