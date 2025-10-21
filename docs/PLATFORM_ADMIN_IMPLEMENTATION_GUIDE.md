# Platform Admin Panel Implementation Guide

**Timeline**: 5 days
**Purpose**: Enable platform creator to onboard solo therapists to PazPaz
**Future-Ready**: Prepared for multi-therapist clinic workspaces (Phase 2)

---

## Overview

This guide implements a platform admin panel that allows YOU (PazPaz creator) to:
1. Create workspace + therapist account
2. Send magic link invitation to therapist
3. List and manage all workspaces
4. Monitor adoption and usage

**What We're NOT Building Yet** (Phase 2):
- Therapists inviting their own staff
- Multi-therapist clinic management UI
- Billing/subscription management
- Advanced analytics

---

## Architecture Decisions

### Two-Level Access System

```
Platform Level (YOU)
├─ Platform Admin Panel (/platform-admin)
├─ Create/manage ALL workspaces
├─ Onboard therapists
└─ Monitor platform usage

Workspace Level (THERAPISTS)
├─ Therapist App (/)
├─ Manage their own practice
├─ Cannot see other workspaces
└─ (Future) Invite other therapists to their clinic
```

### Database Structure (Future-Proof)

```
Workspace (Practice/Clinic)
├─ id: UUID
├─ name: "Sarah's Massage Therapy"
├─ created_at, updated_at
└─ Users (1+ therapists)
    ├─ User 1: Sarah (OWNER, is_active=true)
    └─ (Future) User 2: Maya (THERAPIST, is_active=true)

Phase 1: 1 workspace = 1 therapist
Phase 2: 1 workspace = multiple therapists (clinic)
```

**Why this works**: No schema changes needed for Phase 2, just UI changes

---

## Implementation Plan

### Day 1: Database & Platform Admin Auth

#### Step 1.1: Add platform admin flag to User model ✅ COMPLETED
**Agent**: `database-architect`
**File**: `backend/src/pazpaz/models/user.py`

- [x] Add `is_platform_admin` field to User model:
  ```python
  class User(Base):
      # ... existing fields ...

      is_platform_admin: Mapped[bool] = mapped_column(
          Boolean,
          default=False,
          nullable=False,
          comment="True if user can access platform admin panel"
      )
  ```
- [x] Add index for platform admin queries:
  ```python
  Index('idx_users_platform_admin', 'is_platform_admin'),
  ```

**Implementation Notes**:
- ✅ Field added with proper constraints (default=False, nullable=False)
- ✅ Index created for efficient platform admin lookups
- ✅ 11 comprehensive unit tests created (`backend/tests/unit/models/test_user.py`)
- ✅ All tests passing (11/11 new tests + all existing tests)
- ✅ Security: Default to least privilege (False by default)
- ✅ Documentation: See `backend/PLATFORM_ADMIN_STEP_1_1_NOTES.md` for details

**Note**: Platform admins still have `workspace_id` (maintains workspace scoping). Platform admin authorization will be handled separately in API endpoints.

---

#### Step 1.2: Add invitation fields to User model ✅ COMPLETED
**Agent**: `database-architect`
**File**: `backend/src/pazpaz/models/user.py`

- [x] Add invitation tracking fields:
  ```python
  # Invitation tracking
  invitation_token_hash: Mapped[str | None] = mapped_column(
      String(64),
      nullable=True,
      index=True,
      comment="SHA256 hash of invitation token"
  )
  invited_by_platform_admin: Mapped[bool] = mapped_column(
      Boolean,
      default=False,
      nullable=False,
      comment="True if invited by platform admin (not by another user)"
  )
  invited_at: Mapped[datetime | None] = mapped_column(
      DateTime(timezone=True),
      nullable=True,
      comment="When invitation was sent"
  )
  ```

**Implementation Notes**:
- ✅ Three invitation tracking fields added with proper constraints
- ✅ Index created on `invitation_token_hash` for fast token lookups
- ✅ 14 comprehensive unit tests added to `backend/tests/unit/models/test_user.py`
- ✅ All 25 tests passing (11 from Step 1.1 + 14 new tests)
- ✅ Security: SHA256 hash storage (64 chars), never plaintext tokens
- ✅ Performance: O(log n) token lookups with B-tree index
- ✅ Audit trail: `invited_by_platform_admin` flag never cleared for permanent history
- ✅ Documentation: See `backend/STEP_1_2_IMPLEMENTATION_SUMMARY.md` for details

**Token Lifecycle**:
1. Platform admin creates workspace → generates token → stores SHA256 hash
2. `invitation_token_hash` = hash, `invited_by_platform_admin` = True, `invited_at` = now()
3. User accepts invitation → token verified → user created
4. `invitation_token_hash` set to NULL (single-use token consumed)

---

#### Step 1.3: Create Alembic migration ✅ COMPLETED
**Agent**: `database-architect`
**Files**: `backend/alembic/versions/`

- [x] Generate migration:
  ```bash
  cd backend
  env PYTHONPATH=src uv run alembic revision --autogenerate -m "add_platform_admin_and_invitations"
  ```
- [x] Review migration for:
  - `is_platform_admin` column (default False)
  - `invitation_token_hash` column with index
  - `invited_by_platform_admin` column
  - `invited_at` column
- [x] Test migration:
  ```bash
  env PYTHONPATH=src uv run alembic upgrade head
  env PYTHONPATH=src uv run alembic downgrade -1
  env PYTHONPATH=src uv run alembic upgrade head
  ```

**Implementation Notes**:
- ✅ Migration created: `da1a1442ee90_add_platform_admin_and_invitations.py`
- ✅ All 4 columns added with correct types and constraints
- ✅ Server defaults set correctly (`false` for boolean columns)
- ✅ Two indexes created: `idx_users_platform_admin`, `ix_users_invitation_token_hash`
- ✅ Migration tested: upgrade ✓, downgrade ✓, re-upgrade ✓
- ✅ Database verified: All columns and indexes present
- ✅ Unit tests passing: 25/25 tests (11 platform admin + 14 invitation)
- ✅ Reversible migration with proper downgrade function

**Migration File**: `backend/alembic/versions/da1a1442ee90_add_platform_admin_and_invitations.py`

**Create Platform Admin Account**:
After migration is applied, manually designate a platform admin:
```bash
# Replace 'your-email@example.com' with your email
PGPASSWORD=pazpaz psql -U pazpaz -h localhost -d pazpaz -c \
  "UPDATE users SET is_platform_admin = true WHERE email = 'your-email@example.com';"

# Verify platform admin was created
PGPASSWORD=pazpaz psql -U pazpaz -h localhost -d pazpaz -c \
  "SELECT id, email, full_name, is_platform_admin FROM users WHERE is_platform_admin = true;"
```

**Production Notes**:
- Index creation is fast (<1 second for small-to-medium tables)
- Server defaults ensure existing data is not affected
- No data transformation required (all fields nullable or have defaults)

---

### Day 2: Backend Services

#### Step 2.1: Create invitation token utilities
**Agent**: `fullstack-backend-specialist`
**File**: `backend/src/pazpaz/core/invitation_tokens.py` (NEW)

- [ ] Create token generation functions:
  ```python
  """Invitation token utilities for platform admin."""

  import secrets
  import hashlib
  from datetime import datetime, timedelta, UTC

  # Use 256-bit tokens (32 bytes = 256 bits)
  TOKEN_BYTES = 32
  TOKEN_EXPIRY_DAYS = 7

  def generate_invitation_token() -> tuple[str, str]:
      """Generate invitation token and its hash.

      Returns:
          (token, token_hash) - token is sent in email, hash stored in DB
      """
      token = secrets.token_urlsafe(TOKEN_BYTES)
      token_hash = hashlib.sha256(token.encode()).hexdigest()
      return token, token_hash

  def verify_invitation_token(provided_token: str, stored_hash: str) -> bool:
      """Verify invitation token using timing-safe comparison.

      Prevents timing attacks by using secrets.compare_digest.
      """
      provided_hash = hashlib.sha256(provided_token.encode()).hexdigest()
      return secrets.compare_digest(provided_hash, stored_hash)

  def get_invitation_expiry() -> datetime:
      """Get expiration datetime for invitations (7 days from now)."""
      return datetime.now(UTC) + timedelta(days=TOKEN_EXPIRY_DAYS)

  def is_invitation_expired(invited_at: datetime) -> bool:
      """Check if invitation has expired."""
      expiry = invited_at + timedelta(days=TOKEN_EXPIRY_DAYS)
      return datetime.now(UTC) > expiry
  ```
- [ ] Add unit tests:
  - `test_generate_token_creates_unique_tokens()`
  - `test_verify_token_matches_hash()`
  - `test_verify_token_timing_safe()`
  - `test_invitation_expiry_calculation()`

---

#### Step 2.2: Create platform onboarding service
**Agent**: `fullstack-backend-specialist`
**File**: `backend/src/pazpaz/services/platform_onboarding_service.py` (NEW)

- [ ] Create `PlatformOnboardingService`:
  ```python
  """Service for platform admin to onboard therapists."""

  from sqlalchemy.ext.asyncio import AsyncSession
  from pazpaz.models.workspace import Workspace
  from pazpaz.models.user import User, UserRole
  from pazpaz.core.invitation_tokens import (
      generate_invitation_token,
      verify_invitation_token,
      is_invitation_expired,
  )
  from pazpaz.services.email_service import send_email
  import uuid

  class PlatformOnboardingService:
      """Service for onboarding therapists to the platform."""

      async def create_workspace_and_invite_therapist(
          self,
          db: AsyncSession,
          workspace_name: str,
          therapist_email: str,
          therapist_full_name: str,
      ) -> tuple[Workspace, User, str]:
          """Create workspace + therapist, generate invitation token.

          Returns:
              (workspace, user, invitation_token)
          """
          # 1. Create workspace
          workspace = Workspace(
              id=uuid.uuid4(),
              name=workspace_name,
          )
          db.add(workspace)

          # 2. Check if email already exists
          existing_user = await db.execute(
              select(User).where(User.email == therapist_email)
          )
          if existing_user.scalar_one_or_none():
              raise ValueError(f"User with email {therapist_email} already exists")

          # 3. Generate invitation token
          token, token_hash = generate_invitation_token()

          # 4. Create therapist user (inactive, pending invitation)
          user = User(
              id=uuid.uuid4(),
              workspace_id=workspace.id,
              email=therapist_email,
              full_name=therapist_full_name,
              role=UserRole.OWNER,
              is_active=False,  # Activated when they accept invitation
              is_platform_admin=False,
              invitation_token_hash=token_hash,
              invited_by_platform_admin=True,
              invited_at=datetime.now(UTC),
          )
          db.add(user)

          await db.commit()
          await db.refresh(workspace)
          await db.refresh(user)

          return workspace, user, token

      async def send_therapist_invitation_email(
          self,
          user: User,
          workspace: Workspace,
          token: str,
      ) -> None:
          """Send invitation email to therapist."""
          # Generate magic link
          magic_link = f"{settings.frontend_url}/auth/accept-invite?token={token}"

          # Email template
          subject = f"Welcome to PazPaz - Your workspace is ready!"
          body = f"""
          Hi {user.full_name},

          Your PazPaz workspace "{workspace.name}" has been created!

          Click the link below to activate your account and get started:
          {magic_link}

          This invitation link will expire in 7 days.

          Once you log in, you'll be able to:
          • Set up your practice details
          • Add clients and manage appointments
          • Create SOAP session notes
          • Track treatment plans

          If you have any questions, just reply to this email.

          Welcome to PazPaz!
          """

          await send_email(
              to=user.email,
              subject=subject,
              body=body,
          )

      async def accept_therapist_invitation(
          self,
          db: AsyncSession,
          token: str,
      ) -> User:
          """Accept therapist invitation and activate account.

          Raises:
              ValueError: If token invalid, expired, or already accepted
          """
          # 1. Find user by token hash
          token_hash = hashlib.sha256(token.encode()).hexdigest()
          result = await db.execute(
              select(User).where(User.invitation_token_hash == token_hash)
          )
          user = result.scalar_one_or_none()

          if not user:
              raise ValueError("Invalid invitation token")

          # 2. Check if already accepted
          if user.is_active:
              raise ValueError("Invitation already accepted")

          # 3. Check if expired
          if user.invited_at and is_invitation_expired(user.invited_at):
              raise ValueError("Invitation has expired")

          # 4. Activate user and clear token
          user.is_active = True
          user.invitation_token_hash = None  # Single-use token

          await db.commit()
          await db.refresh(user)

          # 5. Create audit event
          await create_audit_event(
              db=db,
              event_type="user.invitation_accepted",
              user_id=user.id,
              workspace_id=user.workspace_id,
              metadata={"invited_by_platform_admin": True},
          )

          return user

      async def resend_therapist_invitation(
          self,
          db: AsyncSession,
          user_id: uuid.UUID,
      ) -> str:
          """Resend invitation to therapist (generate new token).

          Returns:
              New invitation token (to send in email)
          """
          # 1. Get user
          user = await db.get(User, user_id)
          if not user:
              raise ValueError("User not found")

          if user.is_active:
              raise ValueError("User already active")

          # 2. Generate new token
          token, token_hash = generate_invitation_token()

          # 3. Update user
          user.invitation_token_hash = token_hash
          user.invited_at = datetime.now(UTC)

          await db.commit()

          return token

      async def list_all_workspaces(
          self,
          db: AsyncSession,
          page: int = 1,
          page_size: int = 50,
      ) -> tuple[list[Workspace], int]:
          """List all workspaces (for platform admin).

          Returns:
              (workspaces, total_count)
          """
          # Count total
          count_result = await db.execute(select(func.count(Workspace.id)))
          total = count_result.scalar()

          # Get page
          offset = (page - 1) * page_size
          result = await db.execute(
              select(Workspace)
              .order_by(Workspace.created_at.desc())
              .offset(offset)
              .limit(page_size)
          )
          workspaces = result.scalars().all()

          return list(workspaces), total

      async def get_workspace_details(
          self,
          db: AsyncSession,
          workspace_id: uuid.UUID,
      ) -> dict:
          """Get workspace details with users (for platform admin)."""
          workspace = await db.get(Workspace, workspace_id)
          if not workspace:
              raise ValueError("Workspace not found")

          # Get users in workspace
          users_result = await db.execute(
              select(User).where(User.workspace_id == workspace_id)
          )
          users = users_result.scalars().all()

          return {
              "workspace": workspace,
              "users": users,
              "user_count": len(users),
              "active_users": [u for u in users if u.is_active],
              "pending_users": [u for u in users if not u.is_active],
          }
  ```

- [ ] Add unit tests:
  - `test_create_workspace_and_invite_success()`
  - `test_create_workspace_duplicate_email_fails()`
  - `test_accept_invitation_success()`
  - `test_accept_invitation_expired_fails()`
  - `test_accept_invitation_already_accepted_fails()`
  - `test_resend_invitation_success()`
  - `test_list_workspaces_pagination()`
  - `test_get_workspace_details()`

---

### Day 3: Platform Admin API Endpoints

#### Step 3.1: Create platform admin permission dependency
**Agent**: `fullstack-backend-specialist`
**File**: `backend/src/pazpaz/api/dependencies/platform_admin.py` (NEW)

- [ ] Create platform admin check:
  ```python
  """Platform admin permission dependencies."""

  from fastapi import Depends, HTTPException, status
  from pazpaz.api.dependencies.auth import get_current_user
  from pazpaz.models.user import User

  async def require_platform_admin(
      current_user: User = Depends(get_current_user),
  ) -> User:
      """Require platform admin access.

      Only users with is_platform_admin=True can access.
      """
      if not current_user.is_platform_admin:
          raise HTTPException(
              status_code=status.HTTP_403_FORBIDDEN,
              detail="Platform admin access required"
          )
      return current_user
  ```

---

#### Step 3.2: Create platform admin router
**Agent**: `fullstack-backend-specialist`
**File**: `backend/src/pazpaz/api/v1/platform_admin.py` (NEW)

- [ ] Create Pydantic schemas:
  ```python
  from pydantic import BaseModel, EmailStr, Field
  import uuid
  from datetime import datetime

  class CreateWorkspaceRequest(BaseModel):
      workspace_name: str = Field(..., min_length=1, max_length=255)
      therapist_email: EmailStr
      therapist_full_name: str = Field(..., min_length=1, max_length=255)

  class WorkspaceResponse(BaseModel):
      id: uuid.UUID
      name: str
      created_at: datetime
      user_count: int
      active_users: int
      pending_users: int

      class Config:
          from_attributes = True

  class UserResponse(BaseModel):
      id: uuid.UUID
      email: str
      full_name: str
      role: str
      is_active: bool
      invited_at: datetime | None

      class Config:
          from_attributes = True

  class WorkspaceDetailResponse(BaseModel):
      workspace: WorkspaceResponse
      users: list[UserResponse]

  class WorkspaceListResponse(BaseModel):
      workspaces: list[WorkspaceResponse]
      total: int
      page: int
      page_size: int
  ```

- [ ] Create platform admin endpoints:
  ```python
  from fastapi import APIRouter, Depends, BackgroundTasks, Query
  from sqlalchemy.ext.asyncio import AsyncSession
  from pazpaz.api.dependencies.db import get_db
  from pazpaz.api.dependencies.platform_admin import require_platform_admin
  from pazpaz.services.platform_onboarding_service import PlatformOnboardingService

  router = APIRouter(
      prefix="/platform-admin",
      tags=["platform-admin"],
      dependencies=[Depends(require_platform_admin)],  # All routes require platform admin
  )

  @router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
  async def create_workspace_and_invite_therapist(
      request: CreateWorkspaceRequest,
      background_tasks: BackgroundTasks,
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(require_platform_admin),
  ):
      """Create workspace and invite therapist (Platform admin only)."""
      service = PlatformOnboardingService()

      workspace, user, token = await service.create_workspace_and_invite_therapist(
          db=db,
          workspace_name=request.workspace_name,
          therapist_email=request.therapist_email,
          therapist_full_name=request.therapist_full_name,
      )

      # Send invitation email in background
      background_tasks.add_task(
          service.send_therapist_invitation_email,
          user=user,
          workspace=workspace,
          token=token,
      )

      return WorkspaceResponse(
          id=workspace.id,
          name=workspace.name,
          created_at=workspace.created_at,
          user_count=1,
          active_users=0,
          pending_users=1,
      )

  @router.get("/workspaces", response_model=WorkspaceListResponse)
  async def list_workspaces(
      page: int = Query(1, ge=1),
      page_size: int = Query(50, ge=1, le=100),
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(require_platform_admin),
  ):
      """List all workspaces (Platform admin only)."""
      service = PlatformOnboardingService()
      workspaces, total = await service.list_all_workspaces(db, page, page_size)

      # Get user counts for each workspace
      workspace_responses = []
      for ws in workspaces:
          details = await service.get_workspace_details(db, ws.id)
          workspace_responses.append(
              WorkspaceResponse(
                  id=ws.id,
                  name=ws.name,
                  created_at=ws.created_at,
                  user_count=details["user_count"],
                  active_users=len(details["active_users"]),
                  pending_users=len(details["pending_users"]),
              )
          )

      return WorkspaceListResponse(
          workspaces=workspace_responses,
          total=total,
          page=page,
          page_size=page_size,
      )

  @router.get("/workspaces/{workspace_id}", response_model=WorkspaceDetailResponse)
  async def get_workspace_details(
      workspace_id: uuid.UUID,
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(require_platform_admin),
  ):
      """Get workspace details with users (Platform admin only)."""
      service = PlatformOnboardingService()
      details = await service.get_workspace_details(db, workspace_id)

      return WorkspaceDetailResponse(
          workspace=WorkspaceResponse(
              id=details["workspace"].id,
              name=details["workspace"].name,
              created_at=details["workspace"].created_at,
              user_count=details["user_count"],
              active_users=len(details["active_users"]),
              pending_users=len(details["pending_users"]),
          ),
          users=[
              UserResponse(
                  id=u.id,
                  email=u.email,
                  full_name=u.full_name,
                  role=u.role.value,
                  is_active=u.is_active,
                  invited_at=u.invited_at,
              )
              for u in details["users"]
          ],
      )

  @router.post("/workspaces/{workspace_id}/users/{user_id}/resend", status_code=204)
  async def resend_therapist_invitation(
      workspace_id: uuid.UUID,
      user_id: uuid.UUID,
      background_tasks: BackgroundTasks,
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(require_platform_admin),
  ):
      """Resend invitation to therapist (Platform admin only)."""
      service = PlatformOnboardingService()

      # Get user and workspace
      user = await db.get(User, user_id)
      if not user or user.workspace_id != workspace_id:
          raise HTTPException(status_code=404, detail="User not found")

      workspace = await db.get(Workspace, workspace_id)

      # Resend invitation
      token = await service.resend_therapist_invitation(db, user_id)

      # Send email in background
      background_tasks.add_task(
          service.send_therapist_invitation_email,
          user=user,
          workspace=workspace,
          token=token,
      )
  ```

- [ ] Register router in `backend/src/pazpaz/api/v1/__init__.py`:
  ```python
  from pazpaz.api.v1 import platform_admin

  app.include_router(platform_admin.router)
  ```

---

#### Step 3.3: Update auth router for invitation acceptance
**Agent**: `fullstack-backend-specialist`
**File**: `backend/src/pazpaz/api/v1/auth.py`

- [ ] Add invitation acceptance endpoint:
  ```python
  from pazpaz.services.platform_onboarding_service import PlatformOnboardingService

  @router.get("/accept-invite")
  async def accept_invitation(
      token: str = Query(..., description="Invitation token from email"),
      db: AsyncSession = Depends(get_db),
  ):
      """Accept invitation and activate account."""
      service = PlatformOnboardingService()

      try:
          user = await service.accept_therapist_invitation(db, token)
      except ValueError as e:
          # Redirect to login with error
          return RedirectResponse(
              url=f"/login?error=invalid_invitation&message={str(e)}"
          )

      # Generate JWT and log user in
      access_token = create_access_token(
          user_id=user.id,
          workspace_id=user.workspace_id,
      )

      # Set cookie and redirect to app
      response = RedirectResponse(url="/")
      response.set_cookie(
          key="access_token",
          value=access_token,
          httponly=True,
          secure=True,  # HTTPS only in production
          samesite="lax",
          max_age=86400 * 30,  # 30 days
      )

      return response
  ```

---

### Day 4: Frontend - Platform Admin Portal

#### Step 4.1: Generate TypeScript client
**Agent**: `fullstack-frontend-specialist`
**Commands**: Terminal

- [ ] Start backend and generate OpenAPI spec:
  ```bash
  cd backend
  env PYTHONPATH=src uv run fastapi dev src/pazpaz/main.py
  curl http://localhost:8000/openapi.json > ../frontend/openapi.json
  ```
- [ ] Generate TypeScript client:
  ```bash
  cd frontend
  npx openapi-typescript-codegen --input ./openapi.json --output ./src/api/generated --client axios
  ```
- [ ] Verify platform admin endpoints generated

---

#### Step 4.2: Create platform admin composable
**Agent**: `fullstack-frontend-specialist`
**File**: `frontend/src/composables/usePlatformAdmin.ts` (NEW)

- [ ] Create composable:
  ```typescript
  import { ref } from 'vue'
  import { platformAdminApi } from '@/api/client'
  import type {
    CreateWorkspaceRequest,
    WorkspaceResponse,
    WorkspaceDetailResponse,
  } from '@/api/generated'

  export function usePlatformAdmin() {
    const workspaces = ref<WorkspaceResponse[]>([])
    const loading = ref(false)
    const error = ref<string | null>(null)
    const total = ref(0)

    async function fetchWorkspaces(page = 1) {
      loading.value = true
      error.value = null
      try {
        const response = await platformAdminApi.listWorkspaces(page, 50)
        workspaces.value = response.data.workspaces
        total.value = response.data.total
      } catch (err) {
        error.value = 'Failed to load workspaces'
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    async function createWorkspace(request: CreateWorkspaceRequest) {
      loading.value = true
      error.value = null
      try {
        await platformAdminApi.createWorkspaceAndInviteTherapist(request)
        await fetchWorkspaces() // Reload list
      } catch (err: any) {
        if (err.response?.data?.detail) {
          error.value = err.response.data.detail
        } else {
          error.value = 'Failed to create workspace'
        }
        throw err
      } finally {
        loading.value = false
      }
    }

    async function resendInvitation(workspaceId: string, userId: string) {
      await platformAdminApi.resendTherapistInvitation(workspaceId, userId)
    }

    return {
      workspaces,
      loading,
      error,
      total,
      fetchWorkspaces,
      createWorkspace,
      resendInvitation,
    }
  }
  ```

---

#### Step 4.3: Create Platform Admin Page
**Agent**: `fullstack-frontend-specialist`
**File**: `frontend/src/views/PlatformAdminPage.vue` (NEW)

- [ ] Create platform admin page:
  ```vue
  <template>
    <div class="min-h-screen bg-gray-50">
      <!-- Header -->
      <header class="bg-white border-b border-gray-200 px-6 py-4">
        <div class="flex items-center justify-between max-w-7xl mx-auto">
          <h1 class="text-2xl font-bold text-gray-900">
            PazPaz Platform Admin
          </h1>
          <div class="text-sm text-gray-600">
            {{ workspaces.length }} of {{ total }} workspaces
          </div>
        </div>
      </header>

      <!-- Main Content -->
      <main class="max-w-7xl mx-auto px-6 py-8">
        <!-- Actions -->
        <div class="mb-6 flex justify-between items-center">
          <div class="flex-1 max-w-md">
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Search workspaces..."
              class="w-full px-4 py-2 border border-gray-300 rounded-lg"
            />
          </div>
          <button
            @click="showCreateModal = true"
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 font-medium"
          >
            + Onboard Therapist
          </button>
        </div>

        <!-- Workspace List -->
        <div v-if="loading && !workspaces.length" class="text-center py-12">
          <div class="text-gray-500">Loading workspaces...</div>
        </div>

        <div v-else-if="!workspaces.length" class="text-center py-12">
          <div class="text-gray-500 mb-4">No workspaces yet</div>
          <button
            @click="showCreateModal = true"
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
          >
            Onboard Your First Therapist
          </button>
        </div>

        <div v-else class="space-y-4">
          <WorkspaceCard
            v-for="workspace in filteredWorkspaces"
            :key="workspace.id"
            :workspace="workspace"
            @resend="handleResendInvitation"
            @view="handleViewDetails"
          />
        </div>

        <!-- Pagination -->
        <div v-if="total > 50" class="mt-6 flex justify-center">
          <button
            @click="currentPage--"
            :disabled="currentPage === 1"
            class="px-4 py-2 border rounded-l-lg disabled:opacity-50"
          >
            Previous
          </button>
          <div class="px-4 py-2 border-t border-b">
            Page {{ currentPage }} of {{ Math.ceil(total / 50) }}
          </div>
          <button
            @click="currentPage++"
            :disabled="currentPage >= Math.ceil(total / 50)"
            class="px-4 py-2 border rounded-r-lg disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </main>

      <!-- Create Workspace Modal -->
      <CreateWorkspaceModal
        v-if="showCreateModal"
        @close="showCreateModal = false"
        @create="handleCreateWorkspace"
      />

      <!-- Workspace Details Modal -->
      <WorkspaceDetailsModal
        v-if="selectedWorkspace"
        :workspace-id="selectedWorkspace"
        @close="selectedWorkspace = null"
      />
    </div>
  </template>

  <script setup lang="ts">
  import { ref, onMounted, computed, watch } from 'vue'
  import { usePlatformAdmin } from '@/composables/usePlatformAdmin'
  import WorkspaceCard from '@/components/platform-admin/WorkspaceCard.vue'
  import CreateWorkspaceModal from '@/components/platform-admin/CreateWorkspaceModal.vue'
  import WorkspaceDetailsModal from '@/components/platform-admin/WorkspaceDetailsModal.vue'

  const {
    workspaces,
    loading,
    total,
    fetchWorkspaces,
    createWorkspace,
    resendInvitation,
  } = usePlatformAdmin()

  const searchQuery = ref('')
  const showCreateModal = ref(false)
  const selectedWorkspace = ref<string | null>(null)
  const currentPage = ref(1)

  const filteredWorkspaces = computed(() => {
    if (!searchQuery.value) return workspaces.value
    const query = searchQuery.value.toLowerCase()
    return workspaces.value.filter(ws =>
      ws.name.toLowerCase().includes(query)
    )
  })

  onMounted(() => {
    fetchWorkspaces(currentPage.value)
  })

  watch(currentPage, () => {
    fetchWorkspaces(currentPage.value)
  })

  async function handleCreateWorkspace(data: any) {
    try {
      await createWorkspace(data)
      showCreateModal.value = false
      // Show success toast
    } catch (err) {
      // Error shown in modal
    }
  }

  function handleViewDetails(workspaceId: string) {
    selectedWorkspace.value = workspaceId
  }

  async function handleResendInvitation(workspace: any, user: any) {
    try {
      await resendInvitation(workspace.id, user.id)
      // Show success toast
    } catch (err) {
      // Show error toast
    }
  }
  </script>
  ```

- [ ] Add route:
  ```typescript
  // frontend/src/router/index.ts
  {
    path: '/platform-admin',
    name: 'platform-admin',
    component: () => import('@/views/PlatformAdminPage.vue'),
    meta: {
      requiresAuth: true,
      requiresPlatformAdmin: true  // Check is_platform_admin
    }
  }
  ```

- [ ] Add route guard for platform admin:
  ```typescript
  router.beforeEach((to, from, next) => {
    if (to.meta.requiresPlatformAdmin) {
      const authStore = useAuthStore()
      if (!authStore.currentUser?.is_platform_admin) {
        next('/') // Redirect regular users
        return
      }
    }
    next()
  })
  ```

---

#### Step 4.4: Create WorkspaceCard component
**Agent**: `fullstack-frontend-specialist`
**File**: `frontend/src/components/platform-admin/WorkspaceCard.vue` (NEW)

- [ ] Create workspace card:
  ```vue
  <template>
    <div class="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition">
      <div class="flex items-start justify-between">
        <!-- Workspace Info -->
        <div class="flex-1">
          <h3 class="text-lg font-semibold text-gray-900">{{ workspace.name }}</h3>
          <p class="text-sm text-gray-600 mt-1">
            Created {{ formatDate(workspace.created_at) }}
          </p>

          <!-- Stats -->
          <div class="mt-4 flex space-x-6">
            <div>
              <div class="text-2xl font-bold text-gray-900">
                {{ workspace.user_count }}
              </div>
              <div class="text-xs text-gray-500">Users</div>
            </div>
            <div>
              <div class="text-2xl font-bold text-emerald-600">
                {{ workspace.active_users }}
              </div>
              <div class="text-xs text-gray-500">Active</div>
            </div>
            <div v-if="workspace.pending_users > 0">
              <div class="text-2xl font-bold text-amber-600">
                {{ workspace.pending_users }}
              </div>
              <div class="text-xs text-gray-500">Pending</div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center space-x-2">
          <button
            @click="$emit('view', workspace.id)"
            class="px-3 py-1 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            View Details
          </button>
        </div>
      </div>
    </div>
  </template>

  <script setup lang="ts">
  import type { WorkspaceResponse } from '@/api/generated'

  defineProps<{
    workspace: WorkspaceResponse
  }>()

  defineEmits(['view', 'resend'])

  function formatDate(date: string) {
    return new Date(date).toLocaleDateString()
  }
  </script>
  ```

---

#### Step 4.5: Create CreateWorkspaceModal component
**Agent**: `fullstack-frontend-specialist`
**File**: `frontend/src/components/platform-admin/CreateWorkspaceModal.vue` (NEW)

- [ ] Create onboarding modal:
  ```vue
  <template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div class="bg-white rounded-lg max-w-md w-full p-6">
        <h2 class="text-xl font-semibold text-gray-900 mb-4">
          Onboard New Therapist
        </h2>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- Workspace Name -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Workspace Name *
            </label>
            <input
              v-model="form.workspace_name"
              type="text"
              required
              placeholder="Sarah's Massage Therapy"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
            <p class="text-xs text-gray-500 mt-1">
              The therapist's practice name
            </p>
          </div>

          <!-- Therapist Email -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Therapist Email *
            </label>
            <input
              v-model="form.therapist_email"
              type="email"
              required
              placeholder="sarah@example.com"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>

          <!-- Therapist Full Name -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Full Name *
            </label>
            <input
              v-model="form.therapist_full_name"
              type="text"
              required
              placeholder="Sarah Chen"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </div>

          <!-- What Happens Next -->
          <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p class="text-sm text-blue-800">
              <strong>What happens next:</strong>
            </p>
            <ul class="text-xs text-blue-700 mt-2 space-y-1">
              <li>✓ Workspace created</li>
              <li>✓ Invitation email sent to therapist</li>
              <li>✓ Therapist clicks link to activate account</li>
              <li>✓ They set up their practice and start using PazPaz</li>
            </ul>
          </div>

          <!-- Error Message -->
          <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-3">
            <p class="text-sm text-red-800">{{ error }}</p>
          </div>

          <!-- Actions -->
          <div class="flex space-x-3 pt-4">
            <button
              type="button"
              @click="$emit('close')"
              class="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="loading"
              class="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
            >
              {{ loading ? 'Creating...' : 'Send Invitation' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </template>

  <script setup lang="ts">
  import { ref } from 'vue'

  const emit = defineEmits(['close', 'create'])

  const form = ref({
    workspace_name: '',
    therapist_email: '',
    therapist_full_name: '',
  })

  const loading = ref(false)
  const error = ref<string | null>(null)

  async function handleSubmit() {
    loading.value = true
    error.value = null

    try {
      await emit('create', form.value)
    } catch (err: any) {
      error.value = err.message || 'Failed to create workspace'
    } finally {
      loading.value = false
    }
  }
  </script>
  ```

---

### Day 5: Testing & Documentation

#### Step 5.1: Backend integration tests
**Agent**: `backend-qa-specialist`
**File**: `backend/tests/test_api/test_platform_admin.py` (NEW)

- [ ] Test platform admin endpoints:
  - `test_create_workspace_success()`
  - `test_create_workspace_duplicate_email_fails()`
  - `test_create_workspace_non_admin_fails()`
  - `test_list_workspaces_success()`
  - `test_list_workspaces_pagination()`
  - `test_list_workspaces_non_admin_fails()`
  - `test_get_workspace_details_success()`
  - `test_resend_invitation_success()`
  - `test_accept_invitation_success()`
  - `test_accept_invitation_expired_fails()`
  - `test_accept_invitation_invalid_token_fails()`

- [ ] Test security:
  - Regular users cannot access platform admin endpoints (403)
  - Platform admin can only see all workspaces (no workspace scoping)
  - Invitation tokens are hashed (not plaintext)
  - Tokens are single-use (deleted after acceptance)

---

#### Step 5.2: End-to-end testing
**Agent**: `backend-qa-specialist`
**Tools**: Playwright or manual testing

- [ ] Test complete onboarding flow:
  1. Platform admin logs in
  2. Creates workspace + therapist
  3. Invitation email sent (verify MailHog)
  4. Therapist clicks magic link
  5. Therapist account activated
  6. Therapist logs in successfully
  7. Therapist sees their workspace

- [ ] Test error cases:
  - Duplicate email (error shown)
  - Expired invitation (error shown)
  - Invalid token (error shown)

---

#### Step 5.3: Documentation
**Agent**: `fullstack-backend-specialist`

- [ ] Create platform admin guide:
  **File**: `docs/platform-admin-guide.md`
  - How to onboard therapists
  - How to resend invitations
  - How to view workspace details
  - Troubleshooting common issues

- [ ] Update architecture docs:
  **File**: `docs/architecture/platform-admin-system.md`
  - Platform vs workspace-level access
  - Invitation flow diagram
  - Security model

---

## Future: Phase 2 - Multi-Therapist Clinics

**Not in this implementation**, but architecture is ready:

### When a clinic has multiple therapists:

```
Clinic Workspace: "Downtown Wellness Center"
├─ Dr. Smith (OWNER) - Can invite other therapists
├─ Dr. Jones (THERAPIST) - Shares calendar, clients
└─ Emma (RECEPTIONIST) - Books appointments for all therapists

Shared resources:
- Shared calendar (see all therapists' appointments)
- Shared client database
- Per-therapist session notes (privacy)
```

### What changes in Phase 2:

**Backend**:
- Add THERAPIST role (separate from ASSISTANT)
- Add RECEPTIONIST role
- OWNER can invite THERAPIST to their workspace
- Shared calendar logic
- Permission system (who can see whose notes)

**Frontend**:
- Workspace admin page (for OWNER to invite therapists)
- Calendar view with multi-therapist filter
- "My patients" vs "All patients" toggle

**Database**: No changes needed (workspace already supports multiple users)

---

## Success Metrics

**Week 1**:
- [ ] Platform admin can onboard 5+ therapists
- [ ] 90%+ invitation acceptance rate
- [ ] 0 therapists locked out (expired/invalid tokens)
- [ ] Average time to onboard: <2 minutes

**Week 4**:
- [ ] 20+ active workspaces
- [ ] <5% support tickets related to onboarding
- [ ] 100% of therapists successfully activated

---

## Appendix

### Key Files Created

**Backend**:
- `backend/src/pazpaz/models/user.py` (modified - add is_platform_admin, invitation fields)
- `backend/src/pazpaz/core/invitation_tokens.py` (new)
- `backend/src/pazpaz/services/platform_onboarding_service.py` (new)
- `backend/src/pazpaz/api/dependencies/platform_admin.py` (new)
- `backend/src/pazpaz/api/v1/platform_admin.py` (new)
- `backend/src/pazpaz/api/v1/auth.py` (modified - add accept-invite)
- `backend/alembic/versions/xxx_add_platform_admin.py` (new migration)
- `backend/tests/test_api/test_platform_admin.py` (new)

**Frontend**:
- `frontend/src/views/PlatformAdminPage.vue` (new)
- `frontend/src/components/platform-admin/WorkspaceCard.vue` (new)
- `frontend/src/components/platform-admin/CreateWorkspaceModal.vue` (new)
- `frontend/src/components/platform-admin/WorkspaceDetailsModal.vue` (new)
- `frontend/src/composables/usePlatformAdmin.ts` (new)
- `frontend/src/router/index.ts` (modified - add platform admin route + guard)

**Scripts**:
- `backend/scripts/create_platform_admin.py` (new - create your admin account)

---

**End of Implementation Guide**
