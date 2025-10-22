/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
/**
 * Schema for creating a new session.
 *
 * SECURITY: workspace_id is NOT accepted from client requests.
 * It is automatically injected from the authenticated user's session.
 * This prevents workspace injection vulnerabilities.
 */
export type SessionCreate = {
    /**
     * Patient-reported symptoms (PHI - encrypted at rest)
     */
    subjective?: (string | null);
    /**
     * Therapist observations (PHI - encrypted at rest)
     */
    objective?: (string | null);
    /**
     * Clinical assessment (PHI - encrypted at rest)
     */
    assessment?: (string | null);
    /**
     * Treatment plan (PHI - encrypted at rest)
     */
    plan?: (string | null);
    /**
     * Date/time when session occurred (timezone-aware UTC)
     */
    session_date: string;
    /**
     * Session duration in minutes (0-480 min, i.e., 0-8 hours)
     */
    duration_minutes?: (number | null);
    /**
     * Client ID (must belong to same workspace)
     */
    client_id: string;
    /**
     * Optional appointment link
     */
    appointment_id?: (string | null);
};

