/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppointmentStatus } from './AppointmentStatus';
import type { ClientSummary } from './ClientSummary';
import type { LocationType } from './LocationType';
/**
 * Schema for appointment API responses.
 */
export type AppointmentResponse = {
    id: string;
    workspace_id: string;
    client_id: string;
    scheduled_start: string;
    scheduled_end: string;
    location_type: LocationType;
    location_details: (string | null);
    status: AppointmentStatus;
    notes: (string | null);
    created_at: string;
    updated_at: string;
    /**
     * When appointment was last edited (NULL if never edited)
     */
    edited_at?: (string | null);
    /**
     * Number of times this appointment has been edited
     */
    edit_count?: number;
    /**
     * Client information (included when requested)
     */
    client?: (ClientSummary | null);
};

