# Frontend Documentation

Documentation for the Vue 3 frontend application.

## 📚 Core Documentation

### Essential Reference Guides

1. **[API_CLIENT.md](./API_CLIENT.md)** - TypeScript API client generation and usage
   - Generating types from OpenAPI spec
   - Using the API client with Pinia stores
   - Type-safe API calls and error handling

2. **[TESTING.md](./TESTING.md)** - Testing guide for frontend components
   - Running tests (Vitest + Vue Test Utils)
   - Writing component and store tests
   - Coverage thresholds and CI/CD integration

3. **[CSP_INTEGRATION.md](./CSP_INTEGRATION.md)** - Content Security Policy implementation
   - Nonce-based CSP for production security
   - Using CSP utilities for dynamic scripts/styles
   - Development vs production CSP policies

4. **[LOCALSTORAGE_ENCRYPTION_VERIFICATION.md](./LOCALSTORAGE_ENCRYPTION_VERIFICATION.md)** - PHI encryption verification
   - Manual testing guide for localStorage encryption
   - HIPAA compliance verification procedures
   - Security validation checklist

## 🏗️ Architecture Overview

The PazPaz frontend is built with:

- **Framework**: Vue 3 (Composition API with `<script setup>`)
- **Language**: TypeScript (strict mode)
- **State Management**: Pinia stores
- **Routing**: Vue Router 4
- **Styling**: Tailwind CSS 3 + PostCSS
- **Testing**: Vitest + Vue Test Utils
- **API**: OpenAPI-generated TypeScript client
- **Build**: Vite 5

## 🔑 Key Features

### Security-First Design
- AES-256-GCM encrypted localStorage for SOAP notes
- CSP nonce-based script execution
- Workspace isolation and audit logging
- PHI protection at every layer

### Performance
- Code splitting and lazy loading
- p95 <150ms for critical operations
- Optimistic UI updates
- Debounced autosave (5s default)

### Accessibility
- WCAG 2.1 AA compliant
- Keyboard-first navigation
- Screen reader support
- 44x44px minimum touch targets (iOS/Android standard)

### Mobile-First UX
- Responsive design (mobile → desktop)
- Touch-optimized interactions
- iOS Safari auto-zoom prevention (16px minimum inputs)
- Progressive enhancement

## 📂 Project Structure

```
frontend/
├── src/
│   ├── api/                    # API client & OpenAPI types
│   │   ├── client.ts           # Axios client with interceptors
│   │   └── schema.ts           # Auto-generated from backend OpenAPI
│   ├── components/
│   │   ├── appointments/       # Appointment modals & forms
│   │   ├── calendar/           # Calendar view components
│   │   ├── client/             # Individual client components
│   │   ├── clients/            # Client list/management UI
│   │   ├── common/             # Reusable components
│   │   ├── icons/              # SVG icon components
│   │   ├── navigation/         # App navigation
│   │   └── sessions/           # SOAP notes editor
│   ├── composables/            # Reusable Vue composition functions
│   │   ├── useAutosave.ts
│   │   ├── useSecureOfflineBackup.ts
│   │   ├── useCalendar.ts
│   │   ├── useFileUpload.ts
│   │   ├── useAppointmentDrag.ts
│   │   └── useGlobalKeyboardShortcuts.ts
│   ├── stores/                 # Pinia state management
│   │   ├── auth.ts
│   │   ├── appointments.ts
│   │   └── clients.ts
│   ├── views/                  # Route pages
│   │   ├── CalendarView.vue
│   │   ├── ClientDetailView.vue
│   │   └── SessionView.vue
│   ├── utils/                  # Helper functions
│   │   ├── csp.ts              # CSP nonce utilities
│   │   ├── calendar/           # Calendar date/time helpers
│   │   ├── dragHelpers.ts      # Drag & drop utilities
│   │   ├── filenameValidation.ts
│   │   └── textFormatters.ts
│   ├── types/                  # TypeScript type definitions
│   │   ├── calendar.ts
│   │   ├── client.ts
│   │   ├── sessions.ts
│   │   └── attachments.ts
│   ├── config/                 # Configuration files
│   │   └── keyboardShortcuts.ts
│   ├── constants/              # Application constants
│   │   └── sessions.ts
│   ├── directives/             # Custom Vue directives
│   │   └── clickOutside.ts
│   ├── router/                 # Vue Router configuration
│   └── test/                   # Test utilities
│       ├── setup.ts
│       └── integration/        # Integration tests
└── (docs are in /docs/frontend/)
```

## 🧪 Testing Philosophy

- **Unit Tests**: All composables and utilities
- **Component Tests**: Critical user interactions
- **Integration Tests**: Full user workflows
- **Coverage Target**: 85% lines, 80% branches

**Run Tests:**
```bash
npm test              # Watch mode (development)
npm run test:run      # Single run (CI/CD)
npm run test:coverage # Coverage report
```

## 🎨 Code Style

- **Format**: Prettier (auto-sort Tailwind classes)
- **Lint**: ESLint + Vue plugin
- **TypeScript**: Strict mode, no `any` types
- **Naming**:
  - Components: PascalCase (`SessionEditor.vue`)
  - Composables: camelCase with `use` prefix (`useAutosave.ts`)
  - Stores: camelCase with `use` prefix (`useAppointmentsStore`)

## 🚀 Development Workflow

1. **Generate API Client**: `npm run generate-api` (after backend changes)
2. **Run Dev Server**: `npm run dev` (http://localhost:5173)
3. **Run Tests**: `npm test`
4. **Build**: `npm run build` (outputs to `dist/`)
5. **Preview Production**: `npm run preview`

## 📖 Related Documentation

- **Backend API**: `/docs/backend/api/`
- **Security**: `/docs/security/`
- **Architecture**: `/docs/architecture/`
- **Project Overview**: `/docs/PROJECT_OVERVIEW.md`

## 🔄 Documentation Maintenance

This documentation is maintained by:
- `fullstack-frontend-specialist` - Core frontend reference docs
- `ux-design-consultant` - UX patterns and design decisions
- `security-auditor` - Security features and CSP

**Last Updated**: 2025-10-20
**Review Frequency**: After major frontend feature additions
