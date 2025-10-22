/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Response model for workspace storage usage.
 */
export type WorkspaceStorageUsageResponse = {
  /**
   * Total bytes used by all files in workspace
   */
  used_bytes: number
  /**
   * Maximum storage allowed for workspace in bytes
   */
  quota_bytes: number
  /**
   * Bytes remaining (can be negative if quota exceeded)
   */
  remaining_bytes: number
  /**
   * Percentage of quota used (0-100+)
   */
  usage_percentage: number
  /**
   * True if storage usage exceeds quota
   */
  is_quota_exceeded: boolean
  /**
   * Storage used in megabytes
   */
  used_mb: number
  /**
   * Quota in megabytes
   */
  quota_mb: number
  /**
   * Remaining storage in megabytes
   */
  remaining_mb: number
}
