/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LocationType } from './LocationType';
/**
 * Schema for creating a new location.
 *
 * SECURITY: workspace_id is NOT accepted from client requests.
 * It is automatically injected from the authenticated user's session.
 * This prevents workspace injection vulnerabilities.
 */
export type LocationCreate = {
    /**
     * Location name
     */
    name: string;
    /**
     * Type: clinic, home, or online
     */
    location_type: LocationType;
    /**
     * Physical address for clinic or home visits
     */
    address?: (string | null);
    /**
     * Additional details (room, video link, parking)
     */
    details?: (string | null);
    /**
     * Active locations appear in scheduling UI
     */
    is_active?: boolean;
};

