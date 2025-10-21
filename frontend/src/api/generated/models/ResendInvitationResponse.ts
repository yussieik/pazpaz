/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for resending invitation.
 *
 * Example:
 * ```json
 * {
     * "invitation_url": "https://app.pazpaz.com/accept-invitation?token=..."
     * }
     * ```
     */
    export type ResendInvitationResponse = {
        /**
         * New magic link URL to send to therapist via email
         */
        invitation_url: string;
    };

