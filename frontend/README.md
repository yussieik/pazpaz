# PazPaz Frontend

Vue 3 + TypeScript + Tailwind CSS frontend for PazPaz practice management application.

## Quick Start

```bash
# Install dependencies
npm install

# Run development server (http://localhost:5173)
npm run dev

# Run tests
npm test

# Generate API client types (requires backend running)
npm run generate-api
```

## Documentation

**Complete documentation is in `/docs/frontend/`:**

- **[Frontend README](/docs/frontend/README.md)** - Architecture overview, project structure, development workflow
- **[API Client](/docs/frontend/API_CLIENT.md)** - TypeScript API client generation and usage
- **[Testing Guide](/docs/frontend/TESTING.md)** - Vitest, Vue Test Utils, coverage requirements
- **[CSP Integration](/docs/frontend/CSP_INTEGRATION.md)** - Content Security Policy implementation
- **[localStorage Encryption Verification](/docs/frontend/LOCALSTORAGE_ENCRYPTION_VERIFICATION.md)** - PHI encryption manual testing

## Available Scripts

```bash
npm run dev              # Development server (Vite)
npm run build            # Production build (TypeScript + Vite)
npm run preview          # Preview production build
npm run lint             # ESLint with auto-fix
npm run format           # Prettier formatting
npm test                 # Run tests in watch mode
npm run test:ui          # Interactive test UI
npm run test:run         # Single test run (CI)
npm run test:coverage    # Coverage report
npm run generate-api     # Generate TypeScript types from backend OpenAPI
```

## Tech Stack

- **Vue 3** - Composition API with `<script setup>`
- **TypeScript** - Strict mode type safety
- **Tailwind CSS 4** - Utility-first styling with PostCSS
- **Pinia** - State management
- **Vue Router 4** - Client-side routing
- **Vite 5** - Build tool and dev server
- **Vitest** - Unit and integration testing
- **Axios** - HTTP client
- **FullCalendar** - Calendar components
- **VueUse** - Composition utilities

## Project Structure

See [/docs/frontend/README.md](/docs/frontend/README.md#-project-structure) for complete directory structure.

## Development Workflow

1. **Backend must be running** for API calls: `cd backend && uv run uvicorn pazpaz.main:app`
2. **Generate API types** after backend changes: `npm run generate-api`
3. **Start dev server**: `npm run dev`
4. **Run tests**: `npm test`

## Security Features

- AES-256-GCM encrypted localStorage for SOAP notes
- Nonce-based Content Security Policy (CSP)
- CSRF protection on state-changing requests
- Workspace isolation and audit logging

For detailed security documentation, see [/docs/security/](/docs/security/).
