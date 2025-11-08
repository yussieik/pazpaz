# AI Agent Extensibility Analysis

## Executive Summary

**Question:** Will it be easy to extend the agent's capabilities to recommend treatments and use tools like scheduling?

**Answer:** 🟡 **Moderately Easy** - The current architecture has good foundations but needs significant additions.

---

## Current Architecture Assessment

### ✅ What's Already in Place (Good Foundations)

#### 1. **LangChain Dependencies**
```toml
# pyproject.toml
"langchain>=1.0.3"
"langchain-cohere>=0.5.0"
```

**Status:** ✅ Installed, but **not currently used**

**What this means:**
- The dependencies are there for tool use and agent orchestration
- Current agent is a **simple RAG pipeline** (retrieve → synthesize → filter)
- No actual LangGraph state machine or tool-calling implemented yet

---

#### 2. **Async-First Architecture**
```python
class ClinicalAgent:
    async def query(self, workspace_id, query, ...):
        # Fully async
```

**Status:** ✅ Perfect for tool calling

**Why this helps:**
- Tool calls (like scheduling API) can run concurrently
- No blocking I/O
- Scales well with multiple tool invocations

---

#### 3. **Clean Service Layer Separation**
```
ai/
├── agent.py          # Orchestration
├── retrieval.py      # RAG retrieval
├── embeddings.py     # Cohere embeddings
├── vector_store.py   # pgvector operations
└── prompts.py        # System prompts
```

**Status:** ✅ Well-structured for extension

**Why this helps:**
- Easy to add `tools.py` module
- Clear separation of concerns
- Can add tool execution without touching retrieval logic

---

#### 4. **Cohere Command-R (RAG-Optimized)**
```python
response = await self.cohere_client.chat(
    model="command-a-03-2025",
    ...
)
```

**Status:** ✅ Cohere models support tool use natively

**Why this helps:**
- Cohere has built-in tool/function calling
- Optimized for grounded responses
- Can return structured outputs

---

#### 5. **Workspace Scoping (Multi-Tenant)**
```python
await agent.query(
    workspace_id=workspace_id,  # MANDATORY everywhere
    ...
)
```

**Status:** ✅ Security-first design

**Why this helps:**
- Tools will inherit workspace isolation
- Can't schedule appointments across tenants
- Already enforced at all layers

---

#### 6. **Audit Logging Infrastructure**
```python
await create_audit_event(
    db=self.db,
    action=AuditAction.READ,
    resource_type=ResourceType.AI_AGENT,
    ...
)
```

**Status:** ✅ HIPAA-compliant logging in place

**Why this helps:**
- Tool invocations can be logged automatically
- Already tracking user actions
- Easy to extend for "AI scheduled appointment" events

---

### ❌ What's Missing (Needs to Be Built)

#### 1. **No LangGraph State Machine**

**Current implementation:**
```python
# Simple linear pipeline
retrieved = await retrieve_sessions(...)
answer = await synthesize_answer(...)
filtered = filter_output(answer)
return AgentResponse(...)
```

**What's needed for tools:**
```python
# LangGraph state machine
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)
graph.add_node("retrieve", retrieve_node)
graph.add_node("reason", reason_node)
graph.add_node("use_tool", tool_node)
graph.add_node("synthesize", synthesize_node)

# Conditional edges (decides whether to use tools)
graph.add_conditional_edges(
    "reason",
    should_use_tool,  # Function that decides
    {
        "use_tool": "use_tool",
        "synthesize": "synthesize",
    }
)
```

**Complexity:** 🟡 **Medium** - LangGraph is already a dependency, just not used

---

#### 2. **No Tool Definitions**

**What's needed:**
```python
# ai/tools.py (NEW FILE)

from langchain.tools import tool
from datetime import datetime

@tool
async def schedule_appointment(
    workspace_id: str,
    client_id: str,
    therapist_id: str,
    datetime: datetime,
    duration_minutes: int,
) -> dict:
    """
    Schedule an appointment for a client with a therapist.

    Args:
        workspace_id: Workspace ID for multi-tenant isolation
        client_id: UUID of the client
        therapist_id: UUID of the therapist
        datetime: Appointment date and time
        duration_minutes: Duration in minutes

    Returns:
        dict with appointment details or error
    """
    # Call existing appointment creation service
    from pazpaz.services.appointment_service import create_appointment

    appointment = await create_appointment(
        db=get_db(),
        workspace_id=workspace_id,
        client_id=client_id,
        therapist_id=therapist_id,
        appointment_datetime=datetime,
        duration_minutes=duration_minutes,
    )

    return {
        "success": True,
        "appointment_id": str(appointment.id),
        "scheduled_time": appointment.start_time.isoformat(),
    }


@tool
async def get_available_slots(
    workspace_id: str,
    therapist_id: str,
    date: str,
) -> list[dict]:
    """Get available appointment slots for a therapist on a specific date."""
    # Call scheduling service
    slots = await get_availability(workspace_id, therapist_id, date)
    return [{"start": s.start, "end": s.end} for s in slots]


@tool
async def recommend_exercises(
    condition: str,
    body_part: str,
    severity: str,
) -> list[dict]:
    """
    Recommend evidence-based exercises for a condition.

    This does NOT provide medical advice - it retrieves from a
    curated database of standard therapeutic exercises.
    """
    # Query exercise database
    exercises = await query_exercise_db(condition, body_part, severity)
    return exercises
```

**Complexity:** 🟢 **Easy** - Just wrapper functions around existing services

---

#### 3. **No Tool Execution Logic**

**What's needed:**
```python
# ai/agent.py modifications

from langchain_cohere import ChatCohere
from langchain.agents import create_cohere_tools_agent

class ClinicalAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

        # Initialize Cohere with tool support
        self.llm = ChatCohere(
            model="command-a-03-2025",
            temperature=0.3,
        )

        # Define available tools
        self.tools = [
            schedule_appointment,
            get_available_slots,
            recommend_exercises,
        ]

        # Create agent executor
        self.agent = create_cohere_tools_agent(
            llm=self.llm,
            tools=self.tools,
        )

    async def query_with_tools(
        self,
        workspace_id: UUID,
        query: str,
        ...
    ):
        # Agent decides whether to use tools
        result = await self.agent.ainvoke({
            "input": query,
            "workspace_id": workspace_id,
            ...
        })

        return result
```

**Complexity:** 🟡 **Medium** - Requires refactoring current agent

---

#### 4. **No Safety Guardrails for Tool Use**

**What's needed:**
```python
# ai/tool_policies.py (NEW FILE)

class ToolPolicy:
    """Enforce safety rules for tool invocations."""

    ALLOWED_TOOLS_BY_ROLE = {
        "therapist": [
            "schedule_appointment",
            "get_available_slots",
            "recommend_exercises",
            "view_client_history",
        ],
        "receptionist": [
            "schedule_appointment",
            "get_available_slots",
        ],
        "client": [
            "get_available_slots",  # Read-only
        ],
    }

    MAX_TOOL_CALLS_PER_QUERY = 5  # Prevent runaway loops

    REQUIRE_CONFIRMATION = [
        "schedule_appointment",  # Always ask user before scheduling
        "cancel_appointment",
        "modify_appointment",
    ]

    async def validate_tool_call(
        self,
        tool_name: str,
        user_role: str,
        workspace_id: UUID,
        params: dict,
    ) -> tuple[bool, str]:
        """
        Validate that a tool call is allowed.

        Returns:
            (is_allowed, reason)
        """
        # Check role permissions
        if tool_name not in self.ALLOWED_TOOLS_BY_ROLE.get(user_role, []):
            return False, f"User role '{user_role}' not authorized for {tool_name}"

        # Check workspace isolation
        if "workspace_id" in params and params["workspace_id"] != workspace_id:
            return False, "Cannot access other workspace resources"

        # Check for suspicious patterns
        if "client_id" in params and not self._is_valid_uuid(params["client_id"]):
            return False, "Invalid client_id format"

        return True, "OK"
```

**Complexity:** 🟡 **Medium** - Security-critical, needs careful design

---

#### 5. **No Conversational State Management**

**Current:** Each query is stateless (HIPAA compliant, no memory)

**Problem for tool use:**
```
User: "Schedule an appointment for John"
Agent: "Which date would you like?"
User: "Tomorrow at 3pm"
Agent: ❌ "Who do you want to schedule?"
       (No memory of "John" from previous message!)
```

**What's needed:**
```python
# ai/conversation_state.py (NEW FILE)

from dataclasses import dataclass
from typing import Optional

@dataclass
class ConversationState:
    """
    Ephemeral conversation state for multi-turn tool interactions.

    IMPORTANT: This is NOT persisted to database (HIPAA compliance).
    Stored in Redis with short TTL (5 minutes).
    """
    session_id: str  # Random UUID, not linked to user
    workspace_id: UUID
    user_id: UUID
    messages: list[dict]  # Last 10 messages only
    pending_tool_call: Optional[dict] = None  # Tool awaiting confirmation
    created_at: datetime
    expires_at: datetime  # Auto-delete after 5 minutes

    def to_redis(self) -> str:
        """Serialize for Redis storage."""
        return json.dumps({
            "session_id": self.session_id,
            "workspace_id": str(self.workspace_id),
            "user_id": str(self.user_id),
            "messages": self.messages[-10:],  # Keep only last 10
            "pending_tool_call": self.pending_tool_call,
        })

    @classmethod
    def from_redis(cls, data: str) -> "ConversationState":
        """Deserialize from Redis."""
        parsed = json.loads(data)
        return cls(**parsed)


# Usage
async def get_or_create_conversation(
    session_id: str,
    workspace_id: UUID,
    user_id: UUID,
) -> ConversationState:
    """
    Get existing conversation from Redis or create new one.

    Redis key: conversation:{session_id}
    TTL: 300 seconds (5 minutes)
    """
    redis = get_redis()
    key = f"conversation:{session_id}"

    cached = await redis.get(key)
    if cached:
        return ConversationState.from_redis(cached)

    # Create new
    state = ConversationState(
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        messages=[],
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    await redis.setex(key, 300, state.to_redis())
    return state
```

**Complexity:** 🟡 **Medium** - Redis already available, just need state management

---

#### 6. **No User Confirmation Flow**

**What's needed:**
```python
# api/v1/ai.py modifications

@router.post("/ai/ask")
async def ask_agent(
    request: AgentQueryRequest,
    current_user: User = Depends(get_current_user),
):
    agent = get_clinical_agent(db)

    response = await agent.query_with_tools(
        workspace_id=current_user.workspace_id,
        query=request.query,
        conversation_id=request.conversation_id,
    )

    # Check if agent wants to use a tool
    if response.pending_tool_call:
        # Return confirmation prompt to user
        return {
            "type": "confirmation_required",
            "message": "I can schedule this appointment for you. Confirm?",
            "tool": response.pending_tool_call["name"],
            "params": response.pending_tool_call["params"],
            "confirmation_token": generate_token(),  # CSRF protection
        }

    return {
        "type": "answer",
        "answer": response.answer,
        "citations": response.citations,
    }


@router.post("/ai/confirm-tool")
async def confirm_tool_execution(
    request: ToolConfirmationRequest,
    current_user: User = Depends(get_current_user),
):
    """Execute a tool after user confirmation."""
    # Validate CSRF token
    if not validate_token(request.confirmation_token):
        raise HTTPException(status_code=403, detail="Invalid confirmation token")

    # Execute tool
    tool = get_tool(request.tool_name)
    result = await tool.invoke(
        workspace_id=current_user.workspace_id,
        **request.params,
    )

    return {
        "type": "tool_result",
        "result": result,
    }
```

**Complexity:** 🟡 **Medium** - UI changes needed for confirmation flow

---

## Implementation Roadmap

### Phase 1: Foundation (1-2 weeks)
**Goal:** Set up LangGraph and basic tool infrastructure

**Tasks:**
1. ✅ Install LangGraph: `uv add langgraph`
2. Create `ai/tools.py` with 1-2 simple tools (read-only)
   - Example: `get_available_slots` (safe, no mutations)
3. Refactor `ClinicalAgent` to use LangGraph `StateGraph`
4. Add basic tool execution (no confirmation yet)
5. Write tests for tool invocation

**Deliverables:**
- Agent can call read-only tools
- LangGraph state machine working
- Tool execution audited in logs

---

### Phase 2: Safety & Policies (1 week)
**Goal:** Add guardrails for safe tool use

**Tasks:**
1. Create `ai/tool_policies.py`
2. Implement role-based tool permissions
3. Add max tool calls limit (prevent runaway loops)
4. Add workspace isolation checks
5. Write security tests

**Deliverables:**
- Tool calls are authorized by user role
- Workspace boundaries enforced
- Runaway loop protection

---

### Phase 3: Stateful Conversations (1 week)
**Goal:** Enable multi-turn tool interactions

**Tasks:**
1. Create `ai/conversation_state.py`
2. Implement Redis-backed conversation storage
3. Add TTL and auto-cleanup
4. Modify agent to maintain context across turns
5. Write tests for state management

**Deliverables:**
- Agent remembers previous messages (5 min TTL)
- Multi-turn tool interactions work
- No HIPAA violations (ephemeral state only)

---

### Phase 4: User Confirmation (1 week)
**Goal:** Require user approval for mutations

**Tasks:**
1. Add confirmation flow to API endpoints
2. Implement CSRF protection for confirmations
3. Build frontend UI for tool confirmations
4. Add timeout for pending confirmations
5. Write E2E tests

**Deliverables:**
- User must confirm before scheduling
- CSRF-protected confirmation tokens
- UI shows pending actions clearly

---

### Phase 5: Production Tools (2-3 weeks)
**Goal:** Add real business value tools

**Tools to implement:**
1. **Scheduling:**
   - `schedule_appointment` (with confirmation)
   - `reschedule_appointment` (with confirmation)
   - `cancel_appointment` (with confirmation)
   - `get_available_slots` (read-only)

2. **Recommendations:**
   - `recommend_exercises` (from curated DB, not AI-generated)
   - `suggest_followup_schedule` (based on treatment plan)
   - `find_similar_cases` (anonymized insights)

3. **Clinical Insights:**
   - `generate_progress_report` (summarize trend over time)
   - `highlight_red_flags` (detect concerning patterns)
   - `suggest_assessment_templates` (based on condition)

**Deliverables:**
- 8-10 production-ready tools
- Full test coverage
- Documentation for each tool

---

### Phase 6: Recommendations System (2 weeks)
**Goal:** AI-powered clinical recommendations (sensitive!)

**Approach:**
```python
@tool
async def suggest_treatment_plan(
    workspace_id: UUID,
    client_id: UUID,
    condition: str,
    severity: str,
) -> dict:
    """
    Suggest evidence-based treatment approaches.

    DISCLAIMER: This is NOT medical advice. Always use clinical judgment.
    Sources: Published guidelines, standard protocols, historical data.
    """
    # Retrieve from evidence-based database
    guidelines = await get_clinical_guidelines(condition, severity)

    # Find similar successful cases (anonymized)
    similar_cases = await find_similar_cases(
        workspace_id=workspace_id,
        condition=condition,
        min_similarity=0.85,
    )

    # Combine evidence + historical success
    recommendations = {
        "evidence_based": guidelines,
        "historical_success": [
            {
                "approach": case.treatment_approach,
                "outcome": case.outcome,  # Anonymized
                "success_rate": case.success_rate,
            }
            for case in similar_cases
        ],
        "disclaimer": "Always apply clinical judgment. Not medical advice.",
    }

    return recommendations
```

**Safety measures:**
- ⚠️ Always include disclaimers
- ⚠️ Source from evidence-based databases (not LLM generation)
- ⚠️ Show therapist similar anonymized cases
- ⚠️ Flag as "AI suggestion" in UI
- ⚠️ Require therapist review/approval

**Deliverables:**
- Treatment suggestion tool (with disclaimers)
- Exercise recommendation tool
- Follow-up scheduling suggestions
- All recommendations audited

---

## Cost-Benefit Analysis

### Easy Extensions (✅ Low Effort, High Value)

1. **Get Available Slots** (Read-only)
   - Effort: 🟢 1 day
   - Value: 🟢🟢🟢 High (immediate UX improvement)
   - Risk: 🟢 None (read-only)

2. **Recommend Exercises** (From curated DB)
   - Effort: 🟢 2-3 days
   - Value: 🟢🟢🟢 High (clinical value)
   - Risk: 🟢 Low (if curated, not AI-generated)

3. **Generate Progress Reports**
   - Effort: 🟢 3-4 days
   - Value: 🟢🟢🟢 High (saves therapist time)
   - Risk: 🟢 Low (just summarization)

---

### Medium Extensions (🟡 Moderate Effort, High Value)

4. **Schedule Appointment** (With confirmation)
   - Effort: 🟡 1-2 weeks
   - Value: 🟢🟢🟢 Very High (killer feature)
   - Risk: 🟡 Medium (needs confirmation flow + CSRF)

5. **Reschedule/Cancel Appointments**
   - Effort: 🟡 1 week
   - Value: 🟢🟢 High
   - Risk: 🟡 Medium (mutation, needs confirmation)

6. **Find Similar Cases** (Anonymized)
   - Effort: 🟡 1-2 weeks
   - Value: 🟢🟢 High (clinical insights)
   - Risk: 🟡 Medium (privacy risk if not anonymized properly)

---

### Hard Extensions (🔴 High Effort, High Risk)

7. **AI-Generated Treatment Recommendations**
   - Effort: 🔴 2-3 weeks
   - Value: 🟢🟢🟢 Very High (if done right)
   - Risk: 🔴 High (liability, must be evidence-based)

8. **Multi-Step Tool Orchestration** (e.g., "Schedule and send reminder")
   - Effort: 🔴 2-3 weeks
   - Value: 🟢🟢 Medium-High
   - Risk: 🟡 Medium (complexity)

9. **Conversational Appointment Booking** (Multi-turn dialogue)
   - Effort: 🔴 3-4 weeks
   - Value: 🟢🟢🟢 Very High (best UX)
   - Risk: 🟡 Medium (state management complexity)

---

## Recommended Approach

### Start Small (MVP - 2-3 weeks)

**Phase 1: Read-Only Tools**
1. `get_available_slots` - Show open appointment times
2. `recommend_exercises` - Suggest exercises from curated DB
3. `generate_progress_report` - Summarize patient progress

**Why these first:**
- ✅ No mutations (safe)
- ✅ High value for therapists
- ✅ Build confidence in tool use
- ✅ Learn from user feedback

---

### Then Add Mutations (Week 4-6)

**Phase 2: Scheduling with Confirmation**
1. `schedule_appointment` - With user confirmation
2. Implement confirmation UI flow
3. Add CSRF protection

**Why second:**
- 🟡 Mutations require more safety
- 🟡 Need UI changes
- ✅ Delivers killer feature (AI scheduling)

---

### Finally, Advanced Features (Week 7+)

**Phase 3: Clinical Recommendations**
1. Treatment suggestions (evidence-based only)
2. Multi-turn conversations
3. Complex tool orchestration

**Why last:**
- 🔴 High liability risk
- 🔴 Needs more validation
- ✅ Can learn from previous phases

---

## Technical Debt Considerations

### What You'll Need to Refactor

1. **Current Agent Structure** (🟡 Medium)
   - Linear pipeline → LangGraph state machine
   - Estimated: 2-3 days

2. **API Response Format** (🟢 Easy)
   - Add support for pending tool calls
   - Estimated: 1 day

3. **Frontend Chat UI** (🟡 Medium)
   - Add confirmation dialogs
   - Show pending actions
   - Estimated: 3-4 days

4. **Audit Logging** (🟢 Easy)
   - Extend for tool invocations
   - Estimated: 1 day

---

## Security & Compliance Checklist

### Must-Haves for Tool Use

- [ ] Role-based permissions (who can use which tools?)
- [ ] Workspace isolation (can't access other tenants)
- [ ] User confirmation for mutations (schedule, cancel, etc.)
- [ ] CSRF protection on confirmations
- [ ] Rate limiting (prevent abuse)
- [ ] Audit logging (who did what, when?)
- [ ] Tool call timeouts (prevent hanging)
- [ ] Max tool calls per query (prevent runaway loops)
- [ ] Input validation (prevent injection attacks)
- [ ] Disclaimers for recommendations (liability protection)

---

## Bottom Line

### 🟢 Easy Parts (Already There)
- Async architecture
- Service layer separation
- Workspace scoping
- Audit logging
- Cohere tool support
- LangChain dependencies

### 🟡 Moderate Parts (Need Building)
- LangGraph state machine
- Tool definitions
- Tool execution logic
- Confirmation flows
- Conversational state (Redis)

### 🔴 Hard Parts (Design Carefully)
- Safety guardrails
- Liability protection for recommendations
- Multi-turn conversations
- Complex tool orchestration

---

## Time Estimates

| Capability | Effort | Timeline |
|-----------|--------|----------|
| **Read-only tools** (slots, exercises) | 🟢 Easy | 1-2 weeks |
| **Scheduling with confirmation** | 🟡 Medium | 2-3 weeks |
| **Clinical recommendations** | 🔴 Hard | 3-4 weeks |
| **Multi-turn conversations** | 🟡 Medium | 1-2 weeks |
| **Full production system** | 🔴 Hard | **2-3 months** |

---

## Final Recommendation

**Yes, it's feasible to extend the agent**, but:

1. **Start with read-only tools** (safe, fast ROI)
2. **Add mutations incrementally** (scheduling, then more)
3. **Save recommendations for last** (highest risk)
4. **Expect 2-3 months** for production-ready tool use

The foundations are solid, but you'll need to build the state machine, safety policies, and confirmation flows from scratch.

**TL;DR:** Architecture is 70% there, but need 30% more for safe, production-ready tool use.
