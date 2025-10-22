/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { ServiceResponse } from './ServiceResponse';
/**
 * Schema for paginated service list response.
 */
export type ServiceListResponse = {
    items: Array<ServiceResponse>;
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
};

