/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LocationResponse } from './LocationResponse';
/**
 * Schema for paginated location list response.
 */
export type LocationListResponse = {
    items: Array<LocationResponse>;
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
};

