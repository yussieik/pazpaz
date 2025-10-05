# Agent Routing Test Scenarios

This document contains test scenarios to validate the agent routing system works correctly.

## Test Scenarios

### Scenario 1: Database Schema Request
**User:** "Add a `phone_number` field to the Client table"

**Expected Routing:** `database-architect`

**Reasoning:**
- Modifies database schema
- Requires migration
- Database domain expertise needed

**Validation:** ✅ PASS if routed to database-architect

---

### Scenario 2: Backend API Implementation
**User:** "Create CRUD endpoints for managing clients"

**Expected Routing:** `fullstack-backend-specialist`

**Reasoning:**
- Implements API endpoints
- Backend business logic
- FastAPI/Pydantic work

**Validation:** ✅ PASS if routed to fullstack-backend-specialist

---

### Scenario 3: Frontend Component
**User:** "Build a calendar view component for appointments"

**Expected Routing:** `fullstack-frontend-specialist`

**Reasoning:**
- Vue component creation
- Frontend UI work
- Client-side logic

**Validation:** ✅ PASS if routed to fullstack-frontend-specialist

---

### Scenario 4: Security Review
**User:** "Review the authentication implementation for vulnerabilities"

**Expected Routing:** `security-auditor`

**Reasoning:**
- Security audit request
- Authentication is security-sensitive
- Requires security expertise

**Validation:** ✅ PASS if routed to security-auditor

---

### Scenario 5: Backend QA
**User:** "Review the appointment API I just implemented"

**Expected Routing:** `backend-qa-specialist`

**Reasoning:**
- Code review request
- Backend implementation review
- Quality assurance needed

**Validation:** ✅ PASS if routed to backend-qa-specialist

---

### Scenario 6: Complex Feature (Multi-Agent)
**User:** "Implement the Plan of Care feature"

**Expected Routing:**
1. `database-architect` - Design PlanOfCare schema
2. `fullstack-backend-specialist` - Implement API endpoints
3. `fullstack-frontend-specialist` - Build UI components
4. `backend-qa-specialist` - Review backend implementation
5. `security-auditor` - Audit (PHI data involved)

**Reasoning:**
- Full-stack feature requiring all layers
- Involves PHI (security-sensitive)
- Needs comprehensive implementation and review

**Validation:** ✅ PASS if all agents engaged in correct order

---

### Scenario 7: Performance Issue
**User:** "The appointment queries are taking 2 seconds, need optimization"

**Expected Routing:**
1. `database-architect` - Analyze queries and add indexes
2. `backend-qa-specialist` - Validate p95 <150ms target met

**Reasoning:**
- Performance problem at database level
- Requires query optimization
- Needs validation against requirements

**Validation:** ✅ PASS if routed to database-architect first, then QA

---

### Scenario 8: Trivial Configuration
**User:** "Update the Docker Compose file to expose port 8001"

**Expected Routing:** `self` (no agent delegation)

**Reasoning:**
- Trivial configuration change
- No specialized expertise needed
- Simple edit to YAML file

**Validation:** ✅ PASS if handled directly without agent

---

### Scenario 9: Documentation
**User:** "Add setup instructions to the backend README"

**Expected Routing:** `self` (no agent delegation)

**Reasoning:**
- Documentation task
- No code implementation
- Straightforward writing

**Validation:** ✅ PASS if handled directly without agent

---

### Scenario 10: Codebase Exploration
**User:** "Where is the client creation logic located?"

**Expected Routing:** `self` (no agent delegation)

**Reasoning:**
- Search/exploration task
- No implementation needed
- Uses Grep/Read tools

**Validation:** ✅ PASS if handled directly with search tools

---

### Scenario 11: Authentication Implementation
**User:** "Implement passwordless magic link authentication"

**Expected Routing:**
1. `fullstack-backend-specialist` - Implement auth flow
2. `security-auditor` - Security audit
3. `backend-qa-specialist` - QA review

**Reasoning:**
- Backend implementation (auth logic)
- Security-sensitive (magic links, tokens)
- Needs thorough review

**Validation:** ✅ PASS if all three agents engaged

---

### Scenario 12: Migration Creation
**User:** "Create a migration to add workspace scoping to all tables"

**Expected Routing:** `database-architect`

**Reasoning:**
- Database migration task
- Schema modification across multiple tables
- Requires careful planning

**Validation:** ✅ PASS if routed to database-architect

---

### Scenario 13: Frontend-Backend Integration
**User:** "Connect the client form to the backend API"

**Expected Routing:**
1. `fullstack-frontend-specialist` - Implement API client calls
2. Could coordinate with `fullstack-backend-specialist` if API changes needed

**Reasoning:**
- Frontend integration task
- May need backend coordination
- Primarily frontend work

**Validation:** ✅ PASS if routed to fullstack-frontend-specialist

---

### Scenario 14: File Upload Feature
**User:** "Add file upload for SOAP note attachments"

**Expected Routing:**
1. `fullstack-backend-specialist` - Implement upload endpoint
2. `fullstack-frontend-specialist` - Build upload UI
3. `security-auditor` - Audit file upload security

**Reasoning:**
- Full-stack feature
- Security-sensitive (file uploads)
- Needs security validation

**Validation:** ✅ PASS if all three agents engaged

---

### Scenario 15: Ambiguous Request
**User:** "Make the app faster"

**Expected Routing:** Ask user for clarification

**Reasoning:**
- Too vague to route
- Could be database, backend, or frontend
- Need specific details

**Validation:** ✅ PASS if clarifying questions asked before routing

---

## Routing Validation Results

To validate the routing system is working:

1. Present these scenarios to Claude Code
2. Observe which agent(s) are engaged
3. Verify against expected routing
4. Mark each as PASS/FAIL

**Success Criteria:**
- 14/15 scenarios routed correctly (93%+)
- All security-sensitive features route to security-auditor
- All database changes route to database-architect
- All backend implementation routes to fullstack-backend-specialist
- All frontend implementation routes to fullstack-frontend-specialist
- Trivial tasks handled directly without unnecessary delegation

## Anti-Patterns to Watch For

❌ **Bad:** Claude implements database schema changes directly
❌ **Bad:** Claude writes backend API code without fullstack-backend-specialist
❌ **Bad:** Claude builds Vue components without fullstack-frontend-specialist
❌ **Bad:** Claude skips security review for auth/PII features
❌ **Bad:** Claude over-delegates trivial tasks (asking agent to update README)

✅ **Good:** All domain-specific work routed to specialists
✅ **Good:** Multi-agent coordination for complex features
✅ **Good:** Trivial tasks handled efficiently without overhead
✅ **Good:** Security reviews proactively included for sensitive features