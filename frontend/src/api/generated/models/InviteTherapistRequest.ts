/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
/**
 * Request schema for inviting a therapist.
 *
 * Example:
 * ```json
 * {
     * "workspace_name": "Sarah's Massage Therapy",
     * "therapist_email": "sarah@example.com",
     * "therapist_full_name": "Sarah Chen"
     * }
     * ```
     */
    export type InviteTherapistRequest = {
        /**
         * Name of the workspace to create
         */
        workspace_name: string;
        /**
         * Email address of the therapist (must be unique)
         */
        therapist_email: string;
        /**
         * Full name of the therapist
         */
        therapist_full_name: string;
    };

