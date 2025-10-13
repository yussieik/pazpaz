# API Client Generation

This document describes how to generate and use the TypeScript API client from the backend's OpenAPI specification.

## Generating the API Client

The TypeScript types are auto-generated from the backend's OpenAPI spec using `openapi-typescript`.

### Prerequisites

1. Backend server must be running on `http://localhost:8000`
2. `openapi-typescript` must be installed (already included in dev dependencies)

### Generate Types

```bash
# From the frontend directory
npm run generate-api

# Or manually:
npx openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/api/schema.ts
```

### Regenerate After Backend Changes

Whenever the backend API changes (new endpoints, modified schemas, etc.), regenerate the types:

```bash
cd frontend
npm run generate-api
```

## Using the API Client

### Basic Usage

```typescript
import apiClient from '@/api/client'
import type { paths } from '@/api/schema'

// Type-safe API calls
const response = await apiClient.get<AppointmentResponse>('/appointments')
const appointments = response.data.items
```

### With Pinia Stores

The recommended pattern is to use Pinia stores for state management:

```typescript
import { defineStore } from 'pinia'
import apiClient from '@/api/client'
import type { paths } from '@/api/schema'

export const useAppointmentsStore = defineStore('appointments', () => {
  const appointments = ref([])

  async function fetchAppointments() {
    const response = await apiClient.get('/appointments')
    appointments.value = response.data.items
  }

  return { appointments, fetchAppointments }
})
```

### Type Definitions

Extract types from the OpenAPI schema:

```typescript
import type { paths } from '@/api/schema'

// Response types
type AppointmentResponse =
  paths['/api/v1/appointments']['get']['responses']['200']['content']['application/json']

// Request types
type AppointmentCreate =
  paths['/api/v1/appointments']['post']['requestBody']['content']['application/json']
```

## API Client Configuration

The API client is configured in `src/api/client.ts`:

- Base URL: `/api/v1` (proxied to backend via Vite)
- Credentials: Included with every request
- Timeout: 10 seconds
- Workspace ID: Injected in request interceptor (TODO: Replace with auth)

### Request Interceptor

Automatically adds workspace ID to all requests:

```typescript
apiClient.interceptors.request.use((config) => {
  config.headers['X-Workspace-ID'] = '00000000-0000-0000-0000-000000000001'
  return config
})
```

### Response Interceptor

Handles common HTTP errors and logs them appropriately.

## Development Workflow

1. **Backend changes**: Make changes to backend API
2. **Regenerate types**: Run `npm run generate-api`
3. **Update stores**: Update Pinia stores to use new types
4. **Update components**: Update components to use new data structures

## Security Notes

- Workspace ID is currently hardcoded for testing
- TODO: Replace with real authentication when magic link auth is implemented
- All API calls include `withCredentials: true` for cookie-based auth
- CSRF protection will be added when authentication is implemented

## Troubleshooting

### Backend Not Running

```
Error: connect ECONNREFUSED localhost:8000
```

Solution: Start the backend server first:

```bash
cd backend
uv run uvicorn pazpaz.main:app --host 0.0.0.0 --port 8000
```

### Type Errors After Backend Changes

Solution: Regenerate the API client types:

```bash
npm run generate-api
```

### CORS Errors

The Vite dev server proxies `/api` requests to the backend, so CORS should not be an issue in development. If you see CORS errors, check `vite.config.ts` proxy configuration.
