/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
/**
 * Schema for session version history responses.
 *
 * Represents a historical snapshot of a session note at a specific point in time.
 */
export type SessionVersionResponse = {
    id: string;
    session_id: string;
    /**
     * Version number (1 = original, 2+ = amendments)
     */
    version_number: number;
    /**
     * Subjective snapshot (decrypted PHI)
     */
    subjective?: (string | null);
    /**
     * Objective snapshot (decrypted PHI)
     */
    objective?: (string | null);
    /**
     * Assessment snapshot (decrypted PHI)
     */
    assessment?: (string | null);
    /**
     * Plan snapshot (decrypted PHI)
     */
    plan?: (string | null);
    /**
     * When this version was created (finalized or amended)
     */
    created_at: string;
    /**
     * User who created this version
     */
    created_by_user_id: string;
};

