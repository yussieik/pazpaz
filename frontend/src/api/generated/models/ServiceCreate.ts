/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Schema for creating a new service.
 *
 * SECURITY: workspace_id is NOT accepted from client requests.
 * It is automatically injected from the authenticated user's session.
 * This prevents workspace injection vulnerabilities.
 */
export type ServiceCreate = {
    /**
     * Service name
     */
    name: string;
    /**
     * Optional description of the service
     */
    description?: (string | null);
    /**
     * Default duration in minutes (must be > 0)
     */
    default_duration_minutes: number;
    /**
     * Active services appear in scheduling UI
     */
    is_active?: boolean;
};

