/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { AppointmentStatus } from './AppointmentStatus';
import type { LocationType } from './LocationType';
/**
 * Schema for updating an existing appointment.
 */
export type AppointmentUpdate = {
    /**
     * ID of the client for this appointment
     */
    client_id?: (string | null);
    /**
     * Start time (timezone-aware UTC)
     */
    scheduled_start?: (string | null);
    /**
     * End time (timezone-aware UTC)
     */
    scheduled_end?: (string | null);
    /**
     * Type of location
     */
    location_type?: (LocationType | null);
    /**
     * Additional location details
     */
    location_details?: (string | null);
    /**
     * Appointment status. Valid transitions: scheduled→completed, scheduled→cancelled, scheduled→no_show, completed→no_show, cancelled→scheduled, no_show→scheduled, no_show→completed. Cannot cancel completed appointments with session notes (delete session first). Cannot revert completed appointments to scheduled.
     */
    status?: (AppointmentStatus | null);
    /**
     * Therapist notes
     */
    notes?: (string | null);
};

