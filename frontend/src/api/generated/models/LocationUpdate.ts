/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LocationType } from './LocationType';
/**
 * Schema for updating an existing location.
 */
export type LocationUpdate = {
    name?: (string | null);
    location_type?: (LocationType | null);
    address?: (string | null);
    details?: (string | null);
    is_active?: (boolean | null);
};

