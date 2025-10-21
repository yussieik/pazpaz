/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Schema for updating an existing client.
 */
export type ClientUpdate = {
    first_name?: (string | null);
    last_name?: (string | null);
    email?: (string | null);
    phone?: (string | null);
    date_of_birth?: (string | null);
    address?: (string | null);
    medical_history?: (string | null);
    emergency_contact_name?: (string | null);
    emergency_contact_phone?: (string | null);
    is_active?: (boolean | null);
    consent_status?: (boolean | null);
    notes?: (string | null);
    tags?: (Array<string> | null);
};

