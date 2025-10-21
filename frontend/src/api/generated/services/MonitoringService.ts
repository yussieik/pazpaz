/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MonitoringService {
    /**
     * Metrics
     * Prometheus metrics endpoint.
     *
     * Exposes application metrics in Prometheus format for scraping.
     *
     * Metrics include:
     * - audit_events_total: Audit events by resource type, action, workspace
     * - audit_failures_total: Audit failures by resource type, action, error
     * - audit_latency_seconds: Audit event write latency histogram by action
     *
     * Returns:
     * Prometheus-formatted metrics text
     *
     * Example:
     * # HELP audit_events_total Total audit events created
     * # TYPE audit_events_total counter
     * audit_events_total{resource_type="Client",action="CREATE"} 42.0
     * @returns any Successful Response
     * @throws ApiError
     */
    public static metricsMetricsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/metrics',
        });
    }
}
