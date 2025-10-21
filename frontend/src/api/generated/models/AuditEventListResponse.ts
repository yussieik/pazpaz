/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditEventResponse } from './AuditEventResponse';
/**
 * Paginated response for audit event list.
 */
export type AuditEventListResponse = {
    /**
     * List of audit events
     */
    items: Array<AuditEventResponse>;
    /**
     * Total number of audit events matching filters
     */
    total: number;
    /**
     * Current page number (1-indexed)
     */
    page: number;
    /**
     * Number of items per page
     */
    page_size: number;
    /**
     * Total number of pages
     */
    total_pages: number;
};

