# Agent Routing Guide for Claude Code

This document ensures proper delegation of tasks to specialized agents in the PazPaz project.

## Quick Reference Matrix

| Task Type | Primary Agent | Secondary Agent(s) | When to Self-Implement |
|-----------|--------------|-------------------|------------------------|
| Database schema design | `database-architect` | - | Never |
| Database migrations | `database-architect` | `fullstack-backend-specialist` | Never |
| Query optimization | `database-architect` | - | Never |
| Backend API endpoints | `fullstack-backend-specialist` | - | Never |
| Backend business logic | `fullstack-backend-specialist` | - | Never |
| Authentication/Auth | `fullstack-backend-specialist` | `security-auditor` (review) | Never |
| UX/UI design | `ux-design-consultant` | `fullstack-frontend-specialist` | Never |
| Design review | `ux-design-consultant` | - | Never |
| User flow design | `ux-design-consultant` | - | Never |
| Frontend components | `fullstack-frontend-specialist` | `ux-design-consultant` (review) | Never |
| Frontend state management | `fullstack-frontend-specialist` | - | Never |
| API client integration | `fullstack-frontend-specialist` | `fullstack-backend-specialist` | Never |
| Security review | `security-auditor` | - | Never |
| Backend code review | `backend-qa-specialist` | - | Never |
| Code cleanup/refactoring | `code-cleaner` | - | Never |
| Config files (Docker, etc.) | Self | - | Yes (trivial changes) |
| Documentation | Self | - | Yes |
| Codebase exploration | Self | - | Yes |

## Decision Algorithm

```python
def route_task(task_description: str) -> Agent:
    # Step 1: Identify task domain
    if involves_database_schema(task):
        return "database-architect"

    # Step 2: Check if design/UX work needed
    if involves_ui_design(task) or involves_user_flow(task):
        return "ux-design-consultant"

    # Step 3: Check implementation type
    if involves_backend_code(task):
        return "fullstack-backend-specialist"

    if involves_frontend_code(task):
        # Check if design review needed first
        if is_new_feature(task) and not has_design_specs(task):
            return "ux-design-consultant"  # Design first
        return "fullstack-frontend-specialist"

    # Step 4: Check if review/audit needed
    if is_design_review(task):
        return "ux-design-consultant"

    if is_security_review(task) or handles_sensitive_data(task):
        return "security-auditor"

    if is_backend_review(task):
        return "backend-qa-specialist"

    # Step 5: Self-implement only if trivial/exploratory
    if is_trivial_config(task) or is_documentation(task) or is_exploration(task):
        return "self"

    # Step 6: If unsure, ask user for clarification
    return "ask_user_for_clarification"
```

## Pattern Matching Rules

### Database-Architect Triggers
**Positive patterns:**
- "schema", "table", "column", "migration", "index"
- "database", "query performance", "slow query"
- "foreign key", "relationship", "data model"
- "Alembic", "SQL", "PostgreSQL"

**Example phrases:**
- "add a field to..."
- "create a new table for..."
- "optimize the query for..."
- "design the schema for..."

### Fullstack-Backend-Specialist Triggers
**Positive patterns:**
- "API", "endpoint", "REST", "GraphQL"
- "business logic", "service layer", "authentication"
- "FastAPI", "Pydantic", "SQLAlchemy ORM"
- "implement", "create endpoint", "add feature"

**Example phrases:**
- "create CRUD endpoints"
- "implement authentication"
- "add conflict detection"
- "build the email service"

### Fullstack-Frontend-Specialist Triggers
**Positive patterns:**
- "component", "UI", "page", "view"
- "Vue", "React", "frontend", "client-side"
- "state management", "Pinia", "routing"
- "form", "button", "modal", "calendar view"

**Example phrases:**
- "build the calendar component"
- "create a form for..."
- "implement drag and drop"
- "add autosave to the editor"

### Security-Auditor Triggers
**Positive patterns:**
- "security", "audit", "vulnerability", "review"
- "authentication", "authorization", "PII", "PHI"
- "encryption", "token", "session", "CSRF"
- "file upload", "sensitive data"

**Example phrases:**
- "review this for security"
- "is this secure?"
- "audit the authentication"
- "check for vulnerabilities"

### Backend-QA-Specialist Triggers
**Positive patterns:**
- "review", "code review", "quality", "test coverage"
- "production ready", "performance test", "validate"
- "before merging", "pull request review"

**Example phrases:**
- "review my implementation"
- "is this code production-ready?"
- "check the test coverage"
- "validate performance requirements"

### Code-Cleaner Triggers
**Positive patterns:**
- "cleanup", "clean up", "remove", "delete unused"
- "refactor", "simplify", "consolidate", "organize"
- "dead code", "unused imports", "obsolete files"
- "technical debt", "code smell"

**Example phrases:**
- "clean up unused imports"
- "remove dead code"
- "refactor this messy function"
- "organize the codebase"

### UX-Design-Consultant Triggers
**Positive patterns:**
- "design", "UX", "UI", "user experience", "user interface"
- "layout", "visual", "interaction", "flow", "wireframe"
- "form design", "modal", "empty state", "error message"
- "feedback", "animation", "transition", "accessibility"

**Example phrases:**
- "design the intake form"
- "how should we visualize..."
- "review the calendar design"
- "improve the autosave experience"
- "what's the best way to show..."

## Multi-Agent Workflows

### Feature Implementation Flow
```
1. Requirements → Self (analyze and plan)
2. UX Design → ux-design-consultant (design interface and flows)
3. Database → database-architect
4. Backend → fullstack-backend-specialist
5. Frontend → fullstack-frontend-specialist
6. Design Review → ux-design-consultant (review implementation)
7. Backend QA → backend-qa-specialist
8. Security Audit → security-auditor (if sensitive)
```

### Bug Fix Flow
```
1. Investigation → Self (identify root cause)
2. Database fix → database-architect
   OR Backend fix → fullstack-backend-specialist
   OR Frontend fix → fullstack-frontend-specialist
3. Review → backend-qa-specialist (if backend changed)
```

### Performance Optimization Flow
```
1. Profiling → Self (identify bottleneck)
2. Query optimization → database-architect
3. Code optimization → fullstack-backend-specialist
4. Validation → backend-qa-specialist (verify p95 <150ms)
```

## Common Mistakes to Avoid

### ❌ DON'T:
1. Implement database schema changes yourself
2. Create API endpoints without using fullstack-backend-specialist
3. Build Vue components without using fullstack-frontend-specialist
4. Skip security review for auth/PII features
5. Merge backend code without QA review

### ✅ DO:
1. Always delegate database work to database-architect
2. Use fullstack-backend-specialist for all backend implementation
3. Use fullstack-frontend-specialist for all frontend implementation
4. Proactively engage security-auditor for sensitive features
5. Get backend-qa-specialist review before considering code "done"

## Validation Checklist for Each Request

Before responding to any user request, check:

- [ ] **Is this a UX/UI design decision?**
  - If YES → Route to `ux-design-consultant`

- [ ] **Is this a database change?**
  - If YES → Route to `database-architect`

- [ ] **Is this backend implementation?**
  - If YES → Route to `fullstack-backend-specialist`

- [ ] **Is this frontend implementation?**
  - If YES → Check if design exists first
    - If NO design → Route to `ux-design-consultant` first
    - If design exists → Route to `fullstack-frontend-specialist`

- [ ] **Is this a design review?**
  - If YES → Route to `ux-design-consultant`

- [ ] **Does this involve security/auth/PII?**
  - If YES → Route to `security-auditor` (after implementation)

- [ ] **Is this a backend review/QA request?**
  - If YES → Route to `backend-qa-specialist`

- [ ] **Is this trivial config/docs/exploration?**
  - If YES → Self-implement
  - If NO and none of the above → Ask user for clarification

## Example Routing Decisions

### Example 1: "Add reminder preferences to User table"
**Analysis:**
- Involves database schema modification
- Needs migration
- Affects User model

**Routing:** `database-architect` → Design schema + migration

---

### Example 2: "Build the client CRUD API"
**Analysis:**
- Backend API endpoints needed
- Business logic for CRUD operations
- Pydantic schemas required

**Routing:** `fullstack-backend-specialist` → Implement API endpoints

---

### Example 3: "Create the client list page"
**Analysis:**
- Frontend Vue component
- UI/presentation layer
- State management might be needed

**Routing:** `fullstack-frontend-specialist` → Build Vue component

---

### Example 4: "Implement magic link authentication"
**Analysis:**
- Backend auth implementation
- Security-sensitive feature
- Needs both implementation and security review

**Routing:**
1. `fullstack-backend-specialist` → Implement auth logic
2. `security-auditor` → Audit for vulnerabilities
3. `backend-qa-specialist` → QA review

---

### Example 5: "Update README with setup instructions"
**Analysis:**
- Documentation update
- No code changes
- Trivial task

**Routing:** `self` → Update documentation directly

---

### Example 6: "The appointment query is taking 2 seconds"
**Analysis:**
- Performance issue
- Likely needs query optimization or indexes
- Database-level problem

**Routing:** `database-architect` → Analyze and optimize query

---

### Example 7: "Design the client intake form"
**Analysis:**
- UI/UX design task
- Needs user flow and form design
- Should be done before implementation

**Routing:** `ux-design-consultant` → Design form layout, fields, validation patterns

---

### Example 8: "Build the client intake form"
**Analysis:**
- Frontend implementation task
- Requires design specifications first
- Multi-step process

**Routing:**
1. `ux-design-consultant` → Design the form (if not already done)
2. `fullstack-frontend-specialist` → Implement the designed form
3. `ux-design-consultant` → Review implementation

---

## Enforcement Mechanism

This routing system is enforced through:

1. **CLAUDE.md** - Contains the routing rules as mandatory instructions
2. **Agent descriptions** - Each agent's description includes collaboration guidelines
3. **This guide** - Provides detailed reference and decision algorithms
4. **Code review** - security-auditor and backend-qa-specialist validate proper delegation

## Remember

**The routing system exists to ensure:**
- Expert-level implementation in each domain
- Consistent quality across the codebase
- Proper security reviews for sensitive features
- Thorough QA before merging code
- Maintainable, scalable architecture

**When in doubt:** Route to the specialist rather than implementing yourself. It's better to over-delegate than to implement without proper expertise.