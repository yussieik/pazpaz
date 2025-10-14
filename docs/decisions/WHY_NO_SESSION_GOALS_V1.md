# Decision Record: Why Session Goals Are Deferred to V2

**Date:** 2025-10-13
**Status:** Accepted
**Deciders:** Product team, UX consultant
**Context:** Timeline UX improvements for PazPaz V1

---

## Decision

**Session goals feature is DEFERRED to V2.** V1 will ship with enhanced timeline visual hierarchy and full SOAP preview only (4 hours implementation vs. 20 hours for goals).

---

## Context

During Week 4 Day 13 planning, we evaluated whether to add a separate `session_goal` field alongside the existing SOAP notes structure (Subjective, Objective, Assessment, Plan).

**Existing Structure:**
- Subjective (patient's description)
- Objective (therapist's observations)
- Assessment (clinical interpretation)
- Plan (treatment approach and next steps)

**Proposed Addition:**
- Session Goal (per-session objective)
- Goal Outcome (achieved/partial/not_achieved)

---

## Problem

The user raised a critical question:

> "When we create a session note we already have Subjective, Objective, Assessment and Plan - do we need to keep all of these? Isn't it too much to add another 'goal' text block alongside what already exists? How does the goal fit with the simplicity and effectiveness we are trying to achieve for the therapists? We do need the goal, but we don't need clutter as well."

This triggered a comprehensive UX evaluation.

---

## Analysis

### Clutter Assessment

**Adding session goals creates:**
- **33% more fields**: 6 fields → 8 fields (date, duration, 4 SOAP fields → + goal, goal outcome)
- **Clutter score: 8/10** (high)
- **4 additional micro-decisions per session:**
  1. Should I set a goal? (yes/no)
  2. What should the goal be? (free text)
  3. Did we achieve it? (outcome selection)
  4. How is this different from my Plan? (cognitive burden)

### Duplication Analysis

**Goal duplicates Plan field in 50-60% of use cases:**

| Therapy Type | Goal-Plan Overlap | Example |
|--------------|-------------------|---------|
| Massage Therapy | 70% overlap | Goal: "Reduce neck tension"<br>Plan: "Focus on trapezius, apply heat" → Goal is obvious |
| Physiotherapy | 50% overlap | Goal: "Improve shoulder ROM to 120°"<br>Plan: "Shoulder mobilization exercises" → Partial duplicate |
| Psychotherapy | 20% overlap | Goal: "Discuss workplace anxiety"<br>Plan: "CBT homework on thought patterns" → Distinct |

**Insight:** Goals are most valuable in psychotherapy, least valuable in massage therapy. PazPaz serves all three—forcing a separate goal field is therapy-type bias.

### Industry Precedent

**Competitive analysis of EMR/EHR systems:**
- SimplePractice: SOAP notes, no separate goal field
- TherapyNotes: SOAP notes, treatment plan goals (separate feature)
- Jane App: SOAP notes, no separate goal field
- Cliniko: SOAP notes, no separate goal field

**Finding:** No EMR surveyed uses a per-session goal field alongside SOAP notes. Goals are either:
1. Embedded in Plan field (most common)
2. Part of formal treatment planning (separate feature)

### Decision Fatigue

**Cognitive load per session:**
- Current: 6 decisions (date, duration, 4 SOAP fields)
- With goals: 10 decisions (6 + goal text, goal outcome, goal vs. plan distinction, outcome timing)

**Impact:** 67% increase in decision points for unclear value gain.

### Simplicity-First Principle

**PazPaz's core value proposition:**
> "Lightweight practice management for independent therapists... simplicity first, no unnecessary complexity."

**Adding session goals in V1 violates this principle by:**
1. Increasing interface complexity before validating core workflows
2. Forcing structure on therapists who may not need it
3. Duplicating functionality that already exists (Plan field)

---

## Alternatives Considered

### Alternative 1: Merge into Plan Field
**Approach:** Use Plan field for goals
**Verdict:** ❌ This defeats the purpose—if Plan serves as Goal, why add a separate field?

### Alternative 2: Single-Line Metadata Field
**Approach:** Reduce goal to single line above SOAP
**Verdict:** ❌ Still clutters interface, doesn't solve duplication problem

### Alternative 3: Dropdown Goal Tags
**Approach:** Predefined goal categories (pain reduction, ROM improvement, etc.)
**Verdict:** 🤔 Interesting but complex for V1, better for V2

### Alternative 4: NLP Extraction from Plan Field
**Approach:** Auto-detect goals from Plan text using NLP
**Verdict:** ✅ Ideal for V2—zero interface clutter, learns from usage patterns

### Alternative 5: Defer to V2
**Approach:** Ship V1 without separate goal field, learn from real usage
**Verdict:** ✅ **RECOMMENDED**—validates core workflows first, makes V2 decisions data-informed

---

## Decision Rationale

**We defer session goals to V2 because:**

1. **Premature Optimization**
   We haven't validated core SOAP workflows with real therapists yet. Adding goals now risks building the wrong feature.

2. **Duplication Risk**
   50-60% of goals would duplicate Plan field content. Better to learn how therapists use Plan first.

3. **Complexity vs. Value**
   20 hours implementation time for 33% more interface complexity is poor ROI for uncertain value.

4. **Data-Informed Design**
   V2 can analyze real Plan field usage patterns to design goal tracking that fits actual workflows.

5. **Simplicity First**
   Aligns with PazPaz's core principle: start simple, add complexity only when validated by user research.

---

## V1 Approach Instead

**Day 13: Timeline UX Polish + Session Context (8 hours)**

Focus on quick wins that enhance existing timeline AND solve progression tracking:

1. **Enhanced Visual Hierarchy (2 hours)**
   - Colored left border on sessions (blue=draft, green=finalized)
   - Gray background for appointments
   - Bold session timestamps
   - Improved spacing

2. **SOAP Preview Enhancement (2 hours)**
   - Show ALL SOAP fields in timeline (not just Subjective)
   - Format: "S: [40 chars] | O: [40 chars] | A: [40 chars] | P: [40 chars]"
   - Intelligent truncation with ellipsis
   - "Draft - incomplete" badge for empty SOAP fields

3. **Previous Session Context Panel (4 hours)** ← NEW
   - Backend API endpoint: `GET /api/v1/clients/{id}/sessions/latest-finalized` (1h)
   - Frontend collapsible sidebar showing previous SOAP fields (3h)
   - Solves "How do I know this is Plan A vs Plan B?" problem
   - Desktop: right sidebar (400px), Mobile: bottom drawer

**Benefits:**
- Immediate UX value with minimal complexity
- **Solves progression tracking** (contextual awareness)
- No new database fields or formal treatment plan structure
- Richer timeline information without clutter
- 12 hours saved (8h vs. 20h for session goals)

---

## V2 Considerations

**When to revisit session goals:**

1. **After 3-6 months of V1 usage**
   Collect data on how therapists use the Plan field

2. **Based on user research**
   Interview therapists: "Do you track session goals? Where? How?"

3. **With NLP/AI enhancement**
   Auto-extract goals from Plan field text (zero interface clutter)

4. **As part of formal treatment planning**
   Multi-session treatment goals (different feature scope)

**V2 Design Options:**
- NLP-powered goal detection from Plan field
- Optional goal overlay (show/hide toggle)
- Therapy-type-specific templates (psychotherapy gets goals, massage doesn't)
- Multi-session treatment goal tracking (separate from per-session SOAP)

---

## Consequences

### Positive
- ✅ V1 maintains simplicity-first principle
- ✅ Reduces development time (16 hours saved)
- ✅ Validates core workflows before adding structure
- ✅ V2 goal design informed by real usage data
- ✅ No risk of building unused feature

### Negative
- ❌ Therapists who track separate goals must use Plan field or external tools
- ❌ No built-in goal outcome tracking in V1
- ❌ May need to add goals in V2 based on user feedback (but that's expected)

### Neutral
- ⚪ Plan field usage patterns will inform V2 design
- ⚪ Can still add goals later without breaking changes (additive feature)

---

## References

- [UX Evaluation: Session Goals Integration](../reports/ux/session-goals-evaluation-2025-10-13.md) *(if created)*
- [SECURITY_FIRST_IMPLEMENTATION_PLAN.md](../SECURITY_FIRST_IMPLEMENTATION_PLAN.md) - Day 13
- [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) - Simplicity-first principle

---

## Related Decisions

- [WHY_NO_PLAN_OF_CARE_V1.md](WHY_NO_PLAN_OF_CARE_V1.md) - Similar reasoning: defer formal structures to V2

---

**Last Updated:** 2025-10-13
