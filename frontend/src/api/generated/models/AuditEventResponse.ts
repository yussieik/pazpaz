/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditAction } from './AuditAction'
/**
 * Response schema for a single audit event.
 */
export type AuditEventResponse = {
  /**
   * Unique identifier for the audit event
   */
  id: string
  /**
   * Workspace this event belongs to
   */
  workspace_id: string
  /**
   * User who performed the action (None for system events)
   */
  user_id: string | null
  /**
   * Event type (e.g., 'client.read', 'session.create')
   */
  event_type: string
  /**
   * Type of resource (Client, Session, Appointment, etc.)
   */
  resource_type: string
  /**
   * ID of the resource being accessed or modified
   */
  resource_id: string | null
  /**
   * Action performed (CREATE, READ, UPDATE, DELETE, etc.)
   */
  action: AuditAction
  /**
   * IP address of the user
   */
  ip_address: string | null
  /**
   * User agent string from the request
   */
  user_agent: string | null
  /**
   * Additional context (NO PII/PHI)
   */
  metadata: Record<string, any> | null
  /**
   * When the event occurred
   */
  created_at: string
}
