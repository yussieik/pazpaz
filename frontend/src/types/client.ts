/**
 * Client types matching backend schema
 * Backend: /backend/src/pazpaz/schemas/client.py
 */

export interface ClientBase {
  first_name: string
  last_name: string
  email?: string | null
  phone?: string | null
  date_of_birth?: string | null // ISO 8601 date
  address?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  medical_history?: string | null
  notes?: string | null
}

export type ClientCreate = ClientBase

export interface ClientUpdate {
  first_name?: string
  last_name?: string
  email?: string | null
  phone?: string | null
  date_of_birth?: string | null
  address?: string | null
  emergency_contact_name?: string | null
  emergency_contact_phone?: string | null
  medical_history?: string | null
  notes?: string | null
}

export interface Client extends ClientBase {
  id: string // UUID
  workspace_id: string // UUID
  full_name: string // Computed: first_name + last_name
  created_at: string // ISO 8601 datetime
  updated_at: string // ISO 8601 datetime
}

export interface ClientListItem extends Client {
  appointment_count?: number // Optional: total appointments
  last_appointment?: string | null // Optional: ISO 8601 datetime
  next_appointment?: string | null // Optional: ISO 8601 datetime
}
