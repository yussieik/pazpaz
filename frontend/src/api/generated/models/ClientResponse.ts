/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
/**
 * Schema for client API responses.
 */
export type ClientResponse = {
    /**
     * Client's first name
     */
    first_name: string;
    /**
     * Client's last name
     */
    last_name: string;
    /**
     * Client's email address
     */
    email?: (string | null);
    /**
     * Client's phone number
     */
    phone?: (string | null);
    /**
     * Client's date of birth
     */
    date_of_birth?: (string | null);
    /**
     * Client's physical address
     */
    address?: (string | null);
    /**
     * Relevant medical history and conditions (PHI)
     */
    medical_history?: (string | null);
    /**
     * Emergency contact person's name
     */
    emergency_contact_name?: (string | null);
    /**
     * Emergency contact phone number
     */
    emergency_contact_phone?: (string | null);
    /**
     * Active status (false = archived/soft deleted)
     */
    is_active?: boolean;
    /**
     * Client consent to store and process data
     */
    consent_status?: boolean;
    /**
     * General notes about the client
     */
    notes?: (string | null);
    /**
     * Tags for categorization and filtering
     */
    tags?: (Array<string> | null);
    id: string;
    workspace_id: string;
    created_at: string;
    updated_at: string;
    /**
     * Next scheduled appointment after now
     */
    next_appointment?: (string | null);
    /**
     * Most recent completed appointment
     */
    last_appointment?: (string | null);
    /**
     * Total number of appointments
     */
    appointment_count?: number;
    /**
     * Full name of the client.
     */
    readonly full_name: string;
};

