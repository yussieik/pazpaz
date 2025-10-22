/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
/**
 * Request schema for bulk downloading multiple attachments as a ZIP file.
 *
 * Validation:
 * - At least 1 attachment ID required
 * - Maximum 50 attachments per request (prevents abuse)
 * - All attachment IDs must be valid UUIDs
 *
 * Security:
 * - All attachments must belong to the specified client
 * - All attachments must belong to user's workspace
 * - Total file size limited to 100 MB
 */
export type BulkDownloadRequest = {
    /**
     * List of attachment UUIDs to download (1-50 files)
     */
    attachment_ids: Array<string>;
};

