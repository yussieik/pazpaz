/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Schema for creating a new client.
 *
 * SECURITY: workspace_id is NOT accepted from client requests.
 * It is automatically injected from the authenticated user's session.
 * This prevents workspace injection vulnerabilities.
 */
export type ClientCreate = {
  /**
   * Client's first name
   */
  first_name: string
  /**
   * Client's last name
   */
  last_name: string
  /**
   * Client's email address
   */
  email?: string | null
  /**
   * Client's phone number
   */
  phone?: string | null
  /**
   * Client's date of birth
   */
  date_of_birth?: string | null
  /**
   * Client's physical address
   */
  address?: string | null
  /**
   * Relevant medical history and conditions (PHI)
   */
  medical_history?: string | null
  /**
   * Emergency contact person's name
   */
  emergency_contact_name?: string | null
  /**
   * Emergency contact phone number
   */
  emergency_contact_phone?: string | null
  /**
   * Active status (false = archived/soft deleted)
   */
  is_active?: boolean
  /**
   * Client consent to store and process data
   */
  consent_status?: boolean
  /**
   * General notes about the client
   */
  notes?: string | null
  /**
   * Tags for categorization and filtering
   */
  tags?: Array<string> | null
}
