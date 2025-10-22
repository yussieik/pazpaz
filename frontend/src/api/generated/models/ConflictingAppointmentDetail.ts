/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { AppointmentStatus } from './AppointmentStatus';
import type { LocationType } from './LocationType';
/**
 * Privacy-preserving details of a conflicting appointment.
 */
export type ConflictingAppointmentDetail = {
    /**
     * Appointment ID
     */
    id: string;
    /**
     * Start time
     */
    scheduled_start: string;
    /**
     * End time
     */
    scheduled_end: string;
    /**
     * Client initials for privacy (e.g., 'J.D.')
     */
    client_initials: string;
    /**
     * Location type
     */
    location_type: LocationType;
    /**
     * Appointment status
     */
    status: AppointmentStatus;
};

