# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Routing System

**CRITICAL**: Before implementing any task that involves backend, frontend, database, security, or QA work, you MUST check if a specialized agent exists and delegate to them. This ensures expert-level implementation and quality.

### Decision Tree for Task Routing

```
User Request → Analyze Task Type → Check for Specialized Agent → Delegate or Implement

Task Categories:
├── Database/Schema Design → database-architect
├── Backend API/Features → fullstack-backend-specialist
├── Frontend UI/Components → fullstack-frontend-specialist
├── UX/UI Design & Patterns → ux-design-consultant
├── Security/Auth Review → security-auditor
└── Backend Code Review → backend-qa-specialist
```

### Agent Routing Rules

#### 1. **database-architect** - USE WHEN:
- Designing or modifying database schemas
- Creating database migrations (Alembic)
- Optimizing slow queries or adding indexes
- Designing data models for new features
- Planning relationships between entities
- Performance issues with database queries

**Examples:**
- "Add a new table for treatment plans"
- "The appointment queries are slow"
- "Design the schema for session notes"
- "Create a migration to add workspace_id"

#### 2. **fullstack-backend-specialist** - USE WHEN:
- Implementing API endpoints (REST/GraphQL)
- Adding backend features or business logic
- Integrating frontend with backend
- Implementing authentication/authorization
- Working with backend services or utilities
- Refactoring backend code

**Examples:**
- "Create CRUD endpoints for clients"
- "Implement magic link authentication"
- "Add conflict detection for appointments"
- "Build the reminder email service"

#### 3. **fullstack-frontend-specialist** - USE WHEN:
- Building Vue components or pages
- Implementing frontend features
- Setting up frontend architecture/tooling
- Creating API client integrations
- Working with state management (Pinia)
- Frontend routing or navigation

**Examples:**
- "Create the calendar view component"
- "Build the client management UI"
- "Add autosave for SOAP notes"
- "Implement drag-and-drop scheduling"

#### 4. **security-auditor** - USE WHEN:
- Reviewing authentication/authorization code
- Implementing security-sensitive features
- Handling PII/PHI data
- File upload functionality
- Database queries with user input
- After implementing auth, payment, or sensitive data features

**Examples:**
- "Review the magic link implementation"
- "Check if workspace isolation is secure"
- "Audit the session notes encryption"
- "Is this file upload safe?"

#### 5. **backend-qa-specialist** - USE WHEN:
- Reviewing backend code quality
- After implementing backend features
- Before merging backend pull requests
- Checking test coverage
- Validating performance requirements
- Ensuring production readiness

**Examples:**
- "Review the appointment API I just built"
- "Check if my migration is safe"
- "Validate the workspace isolation implementation"
- "Is this backend code production-ready?"

#### 6. **ux-design-consultant** - USE WHEN:
- Designing user interfaces or user flows
- Making design decisions for new features
- Evaluating UX patterns and interaction design
- Ensuring visual consistency and design system adherence
- Reviewing frontend implementations for UX quality
- Planning feature design before implementation

**Examples:**
- "Design the client intake form"
- "Review the calendar component design"
- "How should we visualize the treatment timeline?"
- "The SOAP notes autosave feels clunky, how can we improve it?"

### Routing Priority

**ALWAYS delegate in this order:**

1. **Planning Phase:**
   - UX/UI design → `ux-design-consultant` (before implementation)
   - Database design → `database-architect`

2. **Implementation Phase:**
   - Backend implementation → `fullstack-backend-specialist`
   - Frontend implementation → `fullstack-frontend-specialist`

3. **Quality Assurance Phase:**
   - UX review → `ux-design-consultant` (review implemented designs)
   - Backend QA → `backend-qa-specialist`
   - Security review → `security-auditor` (if auth/sensitive data involved)

4. **Full-Stack Features:**
   - When task spans frontend + backend, use MULTIPLE agents in sequence
   - Example: "Build client CRUD feature" = `ux-design-consultant` → `fullstack-backend-specialist` + `fullstack-frontend-specialist` → `ux-design-consultant` (review)

### Self-Implementation Guidelines

**Only implement yourself when:**
- No specialized agent exists for the task
- Task is trivial configuration or documentation
- Task is exploratory/research (searching codebase)
- User explicitly requests you handle it directly

**Never implement yourself when:**
- Task involves database schema changes
- Task creates/modifies API endpoints
- Task builds/modifies Vue components
- Task involves security-sensitive code
- Task requires backend code review

### Validation Checklist

Before starting any implementation, ask yourself:

- [ ] Does this involve database design? → `database-architect`
- [ ] Does this create/modify backend code? → `fullstack-backend-specialist`
- [ ] Does this create/modify frontend code? → `fullstack-frontend-specialist`
- [ ] Does this involve auth/security/PII? → Consider `security-auditor` after implementation
- [ ] Should this be reviewed for quality? → Consider `backend-qa-specialist` after backend work

### Example Routing Scenarios

**Scenario 1:** "Add a Plan of Care feature"
```
1. database-architect → Design PlanOfCare schema
2. fullstack-backend-specialist → Implement PlanOfCare API
3. fullstack-frontend-specialist → Build PlanOfCare UI
4. backend-qa-specialist → Review backend implementation
5. security-auditor → Audit if PHI is involved
```

**Scenario 2:** "The appointment endpoint is slow"
```
1. database-architect → Analyze queries and add indexes
2. fullstack-backend-specialist → Optimize endpoint logic if needed
3. backend-qa-specialist → Validate p95 <150ms target met
```

**Scenario 3:** "Build client search functionality"
```
1. fullstack-backend-specialist → Implement search API endpoint
2. fullstack-frontend-specialist → Build search UI component
3. backend-qa-specialist → Review backend search implementation
```

**Scenario 4:** "Review magic link auth for security"
```
1. security-auditor → Audit authentication implementation
2. fullstack-backend-specialist → Implement recommended fixes
3. backend-qa-specialist → Validate fixes meet quality standards
```

## Project Context

**IMPORTANT**: Always read [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) before planning or implementing features.

**PazPaz** is a lightweight practice management web app for independent therapists (massage, physiotherapy, psychotherapy). It provides:
- Scheduling with conflict detection and calendar sync
- Client management with treatment history
- SOAP-based session documentation (Subjective, Objective, Assessment, Plan)
- Plan of care tracking with chronological timeline
- Email reminders and notifications
- Privacy-first architecture with workspace scoping and audit trails

**Key Principles**:
- Simplicity first — no unnecessary complexity
- Speed — p95 response time <150ms for schedule endpoints
- Privacy — therapist owns data; client data stays private
- Structure with flexibility — use SOAP best practices but allow customization

**Non-Goals (V1)**: Insurance billing, multi-clinic scheduling, inventory, EMR integrations

## Architecture

Full-stack application with:
- **Backend**: FastAPI (Python 3.13.5) + SQLAlchemy (async) + PostgreSQL 16
- **Frontend**: Vue 3 (Composition API) + TypeScript + Tailwind CSS
- **Infrastructure**: Docker Compose (api, web, db, redis)
- **Storage**: PostgreSQL for relational data, MinIO/S3 for attachments
- **Queue/Cache**: Redis for background tasks and caching
- **Auth**: Passwordless (magic link) + optional 2FA
- **Deployment**: Single-origin architecture (reverse proxy `/api` and `/ws` to backend)

**Key Entities**: Workspace, User, Client, Appointment, Session, Service, Location, PlanOfCare, AuditEvent

## Project Setup

### Python Version and Environment
- CPython version: `3.13.5`
- Install and pin: `uv python install 3.13.5 && uv python pin 3.13.5`

### Dependency Management
- Use `uv` exclusively; never use `pip`, `pip-tools`, or `poetry`
- Add dependencies: `uv add <package>`
- Remove dependencies: `uv remove <package>`
- Sync from lock: `uv sync`
- Run scripts: `uv run script.py` or `uv run -m package.module`

### Project Scripts
If `pyproject.toml` defines `[tool.uv.scripts]`, run them via:
- `uv run lint` - Format and lint code
- `uv run test` - Run tests
- `uv run run` - Run the main application

## Code Quality

### Ruff (Single Formatter and Linter)
- Format: `ruff format`
- Lint: `ruff check --fix`
- Configuration in `pyproject.toml` targets Python 3.13 with 88-char line length

### Python Style (TestDriven.io Clean Code)
- Use 4-space indentation, 88-char line length
- Naming: `CamelCase` classes, `snake_case` functions/variables, `UPPER_SNAKE_CASE` constants
- Functions: small, single-purpose, ≤3-5 arguments, prefer pure functions
- Prefer comprehensions, `enumerate`, `zip`, and generators over manual loops
- Use `dataclasses` for simple data containers
- Context managers (`with`) for resource management
- Catch specific exceptions; avoid bare `except`
- Docstrings for public APIs; avoid leaving commented-out code

### Python 3.13 Features
Leverage when they improve clarity/performance:
- Enhanced typing (`typing.override`)
- `match` statements for structured control flow
- F-string and interpreter improvements

## Git Commit Messages (Conventional Commits v1.0.0)

Format: `<type>(<scope>)!: <subject>`

### Types
- `feat`: new functionality
- `fix`: bug fix
- `docs`: documentation only
- `refactor`: code change without fixing bugs or adding features
- `perf`: performance improvement
- `test`: test changes only
- `build`: build system or dependency changes (use `build(deps): ...` for `uv` updates)
- `ci`: CI configuration
- `chore`: routine maintenance
- `revert`: revert previous commit

### Rules
- Subject: imperative mood, ≤50 chars, no period
- Body: wrap at 72 chars, explain why (not how)
- Breaking changes: append `!` after scope and/or add `BREAKING CHANGE:` footer
- Reference issues: `Closes #123`, `Fixes #123`, or `Refs #123`
- Atomic commits: one logical change per commit

## Backend (FastAPI)

### API Design
- Version endpoints under `/api/v1/...`
- REST for CRUD operations; WebSockets/SSE for realtime updates
- Define request/response models with Pydantic; maintain OpenAPI docs
- Error responses: RFC 7807 problem details format
- Pagination: `?page`, `?page_size` params; include `total` in response
- Structured JSON logs for requests/errors
- **Performance**: Target p95 <150ms for schedule endpoints

### Authentication & Security
- Passwordless authentication via magic link + optional 2FA
- HttpOnly cookies with SameSite=Lax
- CSRF protection on state-changing requests
- No CORS in production (same-origin); enable only in dev if needed
- **Workspace scoping**: All queries must respect workspace boundaries
- **Audit logging**: Log all data access/modifications to AuditEvent table

### Data Layer
- SQLAlchemy async ORM with PostgreSQL 16
- Use transactions for multi-step operations
- Index strategy for performance (schedule queries, client lookups)
- MinIO/S3 for file attachments (SOAP notes photos)

### OpenAPI Contract
- Treat OpenAPI spec as source of truth
- Generate TypeScript client for frontend from OpenAPI
- Regenerate client in CI when backend API changes

## Frontend (Vue 3 + TypeScript + Tailwind)

### Development Commands
- Format: `prettier --write .`
- Lint: `eslint . --ext .vue,.ts,.tsx,.js,.jsx --fix`

### Vue 3 Conventions
- Use Composition API with `<script setup lang="ts">`
- TypeScript-first in components and composables
- Reusable logic in `/src/composables`; global state in Pinia stores (`/src/stores`)
- Define props/emits with TypeScript types; use `withDefaults` for validation
- Co-locate tests: `Component.spec.ts` (Vue Test Utils + Vitest)
- Import alias: `@` for `src/`

### API Integration
- Use generated TypeScript client from OpenAPI spec for all HTTP calls
- Wrap API calls in composables (e.g., `useUsersApi`)
- Send `credentials: 'include'` for authenticated requests
- Vite dev proxy: configure `/api` → `http://localhost:8000` and `/ws` → `ws://localhost:8000`

### Tailwind CSS
- Formatter: Prettier with `prettier-plugin-tailwindcss` (auto-sorts classes)
- JIT mode (default in v3); keep `content` paths accurate
- Centralize design tokens in `tailwind.config.ts` theme extensions
- Extract repeated patterns to `@apply` or components; avoid long one-off chains
- Responsive/state variants: use sparingly in logical order
- Accessibility: ensure focus-visible styles, respect reduced-motion

### Component Guidelines
- Keep templates simple and declarative
- Split large components; one root component per file
- Scope styles with `<style scoped>` or CSS Modules
- Use slots for content projection
- Lazy-load routes and heavy components via dynamic imports
- Manage focus and ARIA for accessibility

### UX Principles (PazPaz-specific)
- **Keyboard-first**: Quick actions and shortcuts
- **Weekly calendar view**: Drag-and-drop for appointments
- **Clean and calm**: Visual design should reduce cognitive load
- **Autosave**: Session notes autosave as user types
- **Offline-tolerant**: Draft notes persist locally until synced
- **Speed**: UI should feel instantaneous; optimistic updates where safe

## Development Workflow

### Planning Tasks
1. **Always read** [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) first
2. Align implementation with product objectives and success metrics
3. Keep features test-driven with clear layer separation
4. Respect workspace scoping in all database queries
5. Ask for clarifications if requirements are ambiguous

### Testing Requirements
- Unit tests for business logic
- Integration tests for API endpoints
- Verify workspace isolation in all tests
- Test performance against <150ms p95 target for schedule endpoints
- Validate audit logging captures all data modifications

### Security Checklist
- All endpoints must validate workspace access
- Sensitive data encrypted at rest and in transit
- PII never logged or exposed in error messages
- CSRF protection on state-changing requests
- Input validation on all user-supplied data

## ByteRover MCP Tools

When using ByteRover MCP server tools:

### `byterover-store-knowledge`
Use when:
- Learning new patterns, APIs, or architectural decisions
- Finding error solutions or debugging techniques
- Discovering reusable code patterns or utility functions
- Completing significant tasks or implementations

### `byterover-retrieve-knowledge`
Use when:
- Starting new tasks or implementations
- Making architectural decisions
- Debugging issues
- Working with unfamiliar codebase areas