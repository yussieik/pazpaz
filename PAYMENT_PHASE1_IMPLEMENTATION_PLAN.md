# Payment System Phase 1: Manual Tracking Implementation Plan

**Status:** Implementation Plan
**Version:** 1.0
**Created:** 2025-11-02
**Architecture:** Based on [docs/payment/PAYMENT_SYSTEM_ARCHITECTURE_V2.md](docs/payment/PAYMENT_SYSTEM_ARCHITECTURE_V2.md)

---

## Overview

This plan implements **Phase 1: Manual Payment Tracking** - a simple, robust system for therapists to track bank transfer payments manually.

**Goal:** Enable therapists to:
1. Configure their bank account details
2. Set prices on appointments
3. Manually mark appointments as paid (bank transfer, Bit, PayBox, cash, etc.)
4. Track payment history

**Non-Goals (Phase 2+):**
- Automated payment provider integrations (Bit, PayBox, PayPlus APIs)
- Auto-generated payment links
- Webhook-based payment confirmations

---

## Phase 1 Scope

### What We're Building
- ✅ Manual payment tracking with bank account details
- ✅ Payment fields on appointments (price, status, method, notes, paid_at)
- ✅ Backend API for marking payments as paid
- ✅ Frontend UI for payment configuration and tracking
- ✅ Dual-mode architecture (manual + provider fields reserved for future)

### What We're Removing
- ❌ PayPlus-specific implementation code
- ❌ PaymentTransaction model (already deleted)
- ❌ payment_link payment method (replaced with bit, paybox)
- ❌ PayPlus tests and documentation

### What We're Keeping
- ✅ Payment provider architecture (fields in database, base classes)
- ✅ Appointment payment fields (provider-agnostic)
- ✅ Workspace payment configuration structure

---

## Implementation Steps

### Phase 1A: Database & Models (COMPLETED ✅)

#### Step 1: Database Migration ✅
**Files:** `backend/alembic/versions/6679fc01412c_*.py`
**Status:** ✅ COMPLETED
**Deliverable:** Migration keeps provider fields while adding bank_account_details

**Changes Made:**
- Added `bank_account_details` field to workspaces
- Kept `payment_provider`, `payment_provider_config`, `payment_auto_send`, `payment_send_timing` fields
- Dropped `payment_transactions` table
- Updated `payment_method` constraint (added 'bit', 'paybox', removed 'payment_link')

**Verification:**
```bash
env PYTHONPATH=src uv run alembic upgrade head
env PYTHONPATH=src uv run alembic downgrade -1
env PYTHONPATH=src uv run alembic upgrade head
```

---

#### Step 2: Workspace Model Update ✅
**Files:** `backend/src/pazpaz/models/workspace.py`
**Status:** ✅ COMPLETED
**Deliverable:** Dual-mode architecture with manual + provider fields

**Changes Made:**
- Added payment provider fields with dual-mode comments
- Updated `payments_enabled` property to check manual OR automated
- Added comprehensive docstrings

**Verification:**
```python
# Test dual-mode payments_enabled property
workspace = Workspace(bank_account_details="Account 123")
assert workspace.payments_enabled == True

workspace = Workspace(payment_provider="bit")
assert workspace.payments_enabled == True

workspace = Workspace()
assert workspace.payments_enabled == False
```

---

#### Step 3: PaymentMethod Enum Update ✅
**Files:** `backend/src/pazpaz/models/enums.py`
**Status:** ✅ COMPLETED
**Deliverable:** Added BIT, PAYBOX; removed PAYMENT_LINK

**Changes Made:**
- Added `BIT = "bit"`
- Added `PAYBOX = "paybox"`
- Removed `PAYMENT_LINK = "payment_link"`

---

#### Step 4: PaymentTransaction Model Deletion ✅
**Files:** `backend/src/pazpaz/models/payment_transaction.py` (deleted)
**Status:** ✅ COMPLETED
**Deliverable:** Removed PaymentTransaction model and references

**Changes Made:**
- Deleted entire file
- Removed from `backend/src/pazpaz/models/__init__.py`
- Removed relationship from `appointment.py`

---

### Phase 1B: Backend API Cleanup (PENDING)

#### Step 5: Delete PayPlus Provider Implementation ✅
**Files Deleted:**
- `backend/src/pazpaz/payments/providers/payplus.py` (642 lines removed)

**Status:** ✅ COMPLETED
**Deliverable:** PayPlus provider implementation removed
**Verification:** No payplus imports remain in codebase

---

#### Step 6: Update Payment Provider Base Classes ✅
**Files Modified:**
- `backend/src/pazpaz/payments/__init__.py` - Added comment about PayPlus removal
- `backend/src/pazpaz/payments/providers/__init__.py` - Removed payplus import, emptied __all__

**Status:** ✅ COMPLETED
**Deliverable:** Provider infrastructure kept for future, PayPlus imports removed
**Verification:** ✅ No PayPlus imports in payments/ directory

---

#### Step 7: Simplify Payment Service ✅
**File:** `backend/src/pazpaz/services/payment_service.py`

**Status:** ✅ COMPLETED
**Deliverable:** Simplified from 686 lines → 350 lines (-49%)
**Changes:**
- Removed: PaymentTransaction, create_payment_request, process_webhook, Redis, VAT calc, email
- Added: mark_as_paid, mark_as_unpaid, update_payment_price, update_payment_details
**Verification:** ✅ `ruff check` passed, `ruff format` - no changes needed

**Example Implementation:**
```python
class PaymentService:
    """Service for manual payment tracking (Phase 1)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def mark_as_paid(
        self,
        appointment: Appointment,
        payment_method: str,
        notes: str | None = None,
    ) -> Appointment:
        """Mark appointment as paid."""
        appointment.payment_status = PaymentStatus.PAID
        appointment.paid_at = datetime.now(UTC)
        appointment.payment_method = payment_method
        if notes:
            appointment.payment_notes = notes

        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def mark_as_unpaid(self, appointment: Appointment) -> Appointment:
        """Mark appointment as unpaid."""
        appointment.payment_status = PaymentStatus.NOT_PAID
        appointment.paid_at = None
        appointment.payment_method = None
        appointment.payment_notes = None

        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def update_payment_price(
        self, appointment: Appointment, price: Decimal
    ) -> Appointment:
        """Update appointment payment price."""
        appointment.payment_price = price
        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment
```

**Verification:**
```bash
env PYTHONPATH=src uv run ruff check backend/src/pazpaz/services/payment_service.py
env PYTHONPATH=src uv run ruff format backend/src/pazpaz/services/payment_service.py
```

**Agent:** fullstack-backend-specialist

---

#### Step 8: Update Payments API Endpoints
**File:** `backend/src/pazpaz/api/payments.py`

**Current State:** PayPlus-specific endpoints
**Target State:** Manual payment tracking endpoints

**Endpoints to Keep/Update:**
- `POST /api/v1/workspaces/{workspace_id}/payments/configure` → Update bank details
- `GET /api/v1/workspaces/{workspace_id}/payments/config` → Get bank details

**Endpoints to Remove:**
- `POST /api/v1/payments/send` (PayPlus payment link generation)
- `POST /api/v1/payments/webhook` (PayPlus webhook)
- Any PayPlus-specific endpoints

**New Endpoints:**
```python
@router.get("/workspaces/{workspace_id}/payments/config")
async def get_payment_config(workspace_id: UUID):
    """Get workspace payment configuration."""
    workspace = await get_workspace(workspace_id)
    return {
        "mode": "manual" if workspace.bank_account_details else "disabled",
        "bank_account_details": workspace.bank_account_details,
        "payments_enabled": workspace.payments_enabled,
    }

@router.put("/workspaces/{workspace_id}/payments/config")
async def update_payment_config(
    workspace_id: UUID,
    config: PaymentConfigUpdate,
):
    """Update workspace payment configuration."""
    workspace = await get_workspace(workspace_id)
    workspace.bank_account_details = config.bank_account_details
    await db.commit()
    return {"message": "Payment configuration updated"}
```

**Verification:**
```bash
env PYTHONPATH=src uv run pytest tests/integration/api/test_payment_config.py -v
```

**Agent:** fullstack-backend-specialist

---

#### Step 9: Update Appointments API
**File:** `backend/src/pazpaz/api/appointments.py`

**Changes:**
1. Ensure appointment creation/update accepts payment fields
2. Add endpoint to mark appointment as paid
3. Remove any PayPlus-specific logic

**New Endpoints:**
```python
@router.patch("/appointments/{appointment_id}/payment")
async def update_appointment_payment(
    appointment_id: UUID,
    payment: AppointmentPaymentUpdate,
):
    """Update appointment payment details."""
    appointment = await get_appointment(appointment_id)

    if payment.payment_status == "paid":
        await payment_service.mark_as_paid(
            appointment,
            payment_method=payment.payment_method,
            notes=payment.payment_notes,
        )
    elif payment.payment_status == "not_paid":
        await payment_service.mark_as_unpaid(appointment)

    if payment.payment_price is not None:
        await payment_service.update_payment_price(
            appointment, payment.payment_price
        )

    return appointment
```

**Verification:**
```bash
env PYTHONPATH=src uv run pytest tests/integration/api/test_appointment_payments.py -v
```

**Agent:** fullstack-backend-specialist

---

#### Step 10: Update Workspace API
**File:** `backend/src/pazpaz/api/workspaces.py`

**Changes:**
1. Ensure workspace responses include payment configuration
2. Remove PayPlus-specific fields from responses (keep provider fields for future)

**Example Response:**
```json
{
  "id": "...",
  "name": "...",
  "payment_config": {
    "mode": "manual",
    "bank_account_details": "Bank Leumi, Account: 12-345-67890",
    "payments_enabled": true
  }
}
```

**Verification:**
```bash
env PYTHONPATH=src uv run pytest tests/integration/api/test_workspaces.py -v -k payment
```

**Agent:** fullstack-backend-specialist

---

#### Step 11: Update Pydantic Schemas
**File:** `backend/src/pazpaz/schemas/appointment.py`

**Changes:**
1. Remove `payment_link` from PaymentMethod enum
2. Add `bit`, `paybox` to PaymentMethod enum
3. Ensure schemas match updated models

**Example:**
```python
class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    BIT = "bit"
    PAYBOX = "paybox"
    OTHER = "other"

class AppointmentPaymentUpdate(BaseModel):
    payment_price: Decimal | None = None
    payment_status: PaymentStatus | None = None
    payment_method: PaymentMethod | None = None
    payment_notes: str | None = None
```

**Verification:**
```bash
env PYTHONPATH=src uv run ruff check backend/src/pazpaz/schemas/
```

**Agent:** fullstack-backend-specialist

---

### Phase 1C: Backend Tests Cleanup (PENDING)

#### Step 12: Delete PayPlus-Specific Tests
**Files to Delete:**
- `backend/tests/test_payments/test_payplus_provider.py`
- `backend/tests/test_payments/test_payment_integration.py` (if PayPlus-specific)
- `backend/tests/test_payments/test_payment_endpoints.py` (if PayPlus-specific)
- `backend/tests/test_payments/conftest.py` (if PayPlus fixtures only)
- `backend/tests/migrations/test_payment_migration.py` (if outdated)
- `backend/tests/unit/models/test_payment_models.py` (if PaymentTransaction tests)

**Verification:**
```bash
# Delete entire test_payments directory if all tests are PayPlus-specific
rm -rf backend/tests/test_payments/

# Delete migration tests if outdated
rm backend/tests/migrations/test_payment_migration.py
rm backend/tests/unit/models/test_payment_models.py
```

**Agent:** backend-qa-specialist (review before deletion)

---

#### Step 13: Create Manual Payment Tests
**New Files to Create:**
- `backend/tests/integration/api/test_manual_payments.py`

**Test Coverage:**
```python
# tests/integration/api/test_manual_payments.py

async def test_enable_manual_payments():
    """Test enabling manual payment tracking."""
    # Update workspace with bank details
    # Verify payments_enabled = True

async def test_mark_appointment_as_paid():
    """Test marking appointment as paid."""
    # Create appointment with price
    # Mark as paid via API
    # Verify status, paid_at, method

async def test_mark_appointment_as_unpaid():
    """Test reverting paid appointment to unpaid."""
    # Mark appointment as paid
    # Revert to unpaid
    # Verify status reset

async def test_update_payment_price():
    """Test updating appointment payment price."""
    # Create appointment
    # Update price
    # Verify price updated

async def test_payment_filtering():
    """Test filtering appointments by payment status."""
    # Create paid and unpaid appointments
    # Filter by payment_status
    # Verify results
```

**Verification:**
```bash
env PYTHONPATH=src uv run pytest backend/tests/integration/api/test_manual_payments.py -v
```

**Agent:** backend-qa-specialist

---

#### Step 14: Update Existing Appointment Tests
**Files to Update:**
- `backend/tests/integration/api/test_appointment_payments.py`

**Changes:**
1. Remove PayPlus-specific test cases
2. Update to test manual payment workflow
3. Ensure payment fields are tested in CRUD operations

**Verification:**
```bash
env PYTHONPATH=src uv run pytest backend/tests/integration/api/test_appointment_payments.py -v
```

**Agent:** backend-qa-specialist

---

### Phase 1D: Frontend Implementation (PENDING)

#### Step 15: Update Payment Settings Component
**File:** `frontend/src/components/settings/PaymentSettings.vue`

**Current State:** Likely PayPlus-specific UI
**Target State:** Manual payment configuration only

**UI Flow:**
1. **Disabled State:** "Enable Payment Tracking" button
2. **Enable Modal:** Choose "Manual Tracking" (automated grayed out "Coming Soon")
3. **Manual Mode:** Textarea for bank account details + Copy button
4. **Disable:** Option to disable payment tracking

**Example Template:**
```vue
<template>
  <div class="payment-settings">
    <!-- Disabled State -->
    <div v-if="!paymentsEnabled" class="empty-state">
      <h2>Payment Tracking</h2>
      <p>Track payments from your clients</p>
      <button @click="showEnableModal = true">Enable Payment Tracking</button>
    </div>

    <!-- Enable Modal -->
    <Modal v-model:show="showEnableModal" title="Enable Payment Tracking">
      <div class="mode-selector">
        <div class="mode-option" @click="enableManualMode">
          <h3>📝 Manual Tracking</h3>
          <p>Share your bank account details with clients</p>
          <ul>
            <li>Clients pay via bank transfer, Bit, or PayBox</li>
            <li>You manually mark appointments as paid</li>
            <li>Simple, no integration needed</li>
          </ul>
          <button>Enable Manual Tracking</button>
        </div>

        <div class="mode-option disabled">
          <h3>🤖 Automated Provider</h3>
          <p>Coming in Phase 2</p>
          <ul>
            <li>Auto-generate payment links</li>
            <li>Instant payment confirmations</li>
            <li>Requires Bit/PayBox integration</li>
          </ul>
          <button disabled>Coming Soon</button>
        </div>
      </div>
    </Modal>

    <!-- Manual Mode Configuration -->
    <div v-if="paymentsEnabled" class="manual-mode">
      <h2>Manual Payment Tracking</h2>
      <p>Share these bank details with your clients</p>

      <textarea
        v-model="bankAccountDetails"
        placeholder="Example:&#10;Bank: Bank Leumi&#10;Account: 12-345-67890&#10;Branch: 789&#10;Account Holder: Dr. Sarah Cohen"
        rows="6"
      />

      <div class="actions">
        <button @click="copyToClipboard" class="secondary">
          Copy to Clipboard
        </button>
        <button @click="saveBankDetails" class="primary">
          Save Changes
        </button>
        <button @click="disablePayments" class="danger">
          Disable Payment Tracking
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkspace } from '@/composables/useWorkspace'
import { usePaymentSettings } from '@/composables/usePaymentSettings'

const { workspace, updateWorkspace } = useWorkspace()
const { enableManualPayments, disablePayments } = usePaymentSettings()

const showEnableModal = ref(false)
const bankAccountDetails = ref(workspace.value.bank_account_details || '')

const paymentsEnabled = computed(() =>
  workspace.value.bank_account_details !== null
)

async function enableManualMode() {
  showEnableModal.value = false
  // Navigate to manual mode config
}

async function saveBankDetails() {
  await updateWorkspace({
    bank_account_details: bankAccountDetails.value
  })
}

async function copyToClipboard() {
  await navigator.clipboard.writeText(bankAccountDetails.value)
  // Show toast notification
}
</script>
```

**Verification:**
- Visual regression tests
- Manual testing of enable/disable flow
- Copy to clipboard functionality

**Agent:** fullstack-frontend-specialist

---

#### Step 16: Update Payment Tracking Card Component
**File:** `frontend/src/components/appointments/PaymentTrackingCard.vue`

**Current State:** May have PayPlus-specific UI
**Target State:** Manual payment status tracking

**UI Elements:**
1. Payment status badge (Not Paid, Paid, Waived)
2. Payment method dropdown (Cash, Card, Bank Transfer, Bit, PayBox, Other)
3. Payment price input
4. Payment notes textarea
5. "Mark as Paid" / "Mark as Unpaid" buttons
6. Paid date display

**Example Template:**
```vue
<template>
  <div class="payment-tracking-card">
    <div class="payment-header">
      <h3>Payment</h3>
      <Badge :status="paymentStatus" />
    </div>

    <div class="payment-fields">
      <!-- Price -->
      <div class="field">
        <label>Price</label>
        <input
          v-model.number="price"
          type="number"
          step="0.01"
          placeholder="0.00"
        />
      </div>

      <!-- Status -->
      <div class="field">
        <label>Status</label>
        <select v-model="status">
          <option value="not_paid">Not Paid</option>
          <option value="paid">Paid</option>
          <option value="waived">Waived</option>
        </select>
      </div>

      <!-- Method (only when paid) -->
      <div v-if="status === 'paid'" class="field">
        <label>Payment Method</label>
        <select v-model="method">
          <option value="cash">Cash</option>
          <option value="card">Card</option>
          <option value="bank_transfer">Bank Transfer</option>
          <option value="bit">Bit</option>
          <option value="paybox">PayBox</option>
          <option value="other">Other</option>
        </select>
      </div>

      <!-- Notes -->
      <div class="field">
        <label>Notes</label>
        <textarea
          v-model="notes"
          placeholder="Payment reference, invoice number, etc."
          rows="2"
        />
      </div>

      <!-- Paid Date (read-only when paid) -->
      <div v-if="status === 'paid' && paidAt" class="field">
        <label>Paid At</label>
        <input :value="formatDate(paidAt)" disabled />
      </div>
    </div>

    <div class="payment-actions">
      <button
        v-if="status !== 'paid'"
        @click="markAsPaid"
        class="primary"
      >
        Mark as Paid
      </button>
      <button
        v-if="status === 'paid'"
        @click="markAsUnpaid"
        class="secondary"
      >
        Mark as Unpaid
      </button>
      <button @click="savePaymentDetails" class="secondary">
        Save Changes
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppointmentPayment } from '@/composables/useAppointmentPayment'

const props = defineProps<{
  appointmentId: string
}>()

const {
  price,
  status,
  method,
  notes,
  paidAt,
  markAsPaid,
  markAsUnpaid,
  savePaymentDetails,
} = useAppointmentPayment(props.appointmentId)
</script>
```

**Verification:**
- Visual regression tests
- Manual testing of mark paid/unpaid flow
- Form validation

**Agent:** fullstack-frontend-specialist

---

#### Step 17: Create Payment Composables
**File:** `frontend/src/composables/usePaymentSettings.ts`

**Implementation:**
```typescript
export function usePaymentSettings() {
  const workspace = useWorkspace()
  const api = useApi()

  const paymentsEnabled = computed(() =>
    workspace.value.bank_account_details !== null
  )

  async function enableManualPayments(bankDetails: string) {
    await api.patch(`/workspaces/${workspace.value.id}/payments/config`, {
      bank_account_details: bankDetails,
    })
    await workspace.refresh()
  }

  async function disablePayments() {
    await api.patch(`/workspaces/${workspace.value.id}/payments/config`, {
      bank_account_details: null,
    })
    await workspace.refresh()
  }

  async function updateBankDetails(bankDetails: string) {
    await api.patch(`/workspaces/${workspace.value.id}/payments/config`, {
      bank_account_details: bankDetails,
    })
    await workspace.refresh()
  }

  return {
    paymentsEnabled,
    enableManualPayments,
    disablePayments,
    updateBankDetails,
  }
}
```

**File:** `frontend/src/composables/useAppointmentPayment.ts`

**Implementation:**
```typescript
export function useAppointmentPayment(appointmentId: string) {
  const appointment = ref<Appointment | null>(null)
  const api = useApi()

  const price = computed({
    get: () => appointment.value?.payment_price,
    set: (val) => {
      if (appointment.value) appointment.value.payment_price = val
    },
  })

  const status = computed({
    get: () => appointment.value?.payment_status,
    set: (val) => {
      if (appointment.value) appointment.value.payment_status = val
    },
  })

  const method = computed({
    get: () => appointment.value?.payment_method,
    set: (val) => {
      if (appointment.value) appointment.value.payment_method = val
    },
  })

  const notes = computed({
    get: () => appointment.value?.payment_notes,
    set: (val) => {
      if (appointment.value) appointment.value.payment_notes = val
    },
  })

  const paidAt = computed(() => appointment.value?.paid_at)

  async function markAsPaid() {
    await api.patch(`/appointments/${appointmentId}/payment`, {
      payment_status: 'paid',
      payment_method: method.value || 'bank_transfer',
    })
    await loadAppointment()
  }

  async function markAsUnpaid() {
    await api.patch(`/appointments/${appointmentId}/payment`, {
      payment_status: 'not_paid',
    })
    await loadAppointment()
  }

  async function savePaymentDetails() {
    await api.patch(`/appointments/${appointmentId}/payment`, {
      payment_price: price.value,
      payment_method: method.value,
      payment_notes: notes.value,
    })
    await loadAppointment()
  }

  async function loadAppointment() {
    appointment.value = await api.get(`/appointments/${appointmentId}`)
  }

  onMounted(() => loadAppointment())

  return {
    price,
    status,
    method,
    notes,
    paidAt,
    markAsPaid,
    markAsUnpaid,
    savePaymentDetails,
  }
}
```

**Verification:**
```bash
npm run type-check
npm run lint
```

**Agent:** fullstack-frontend-specialist

---

#### Step 18: Update Frontend Types
**Files:** `frontend/src/types/*.ts`

**Changes:**
1. Update Workspace type to include payment fields
2. Update Appointment type for payment tracking
3. Remove PayPlus-specific types

**Example:**
```typescript
// frontend/src/types/workspace.ts
export interface Workspace {
  id: string
  name: string
  bank_account_details: string | null
  payment_provider: string | null  // Reserved for Phase 2
  // ...
}

// frontend/src/types/appointment.ts
export type PaymentStatus = 'not_paid' | 'paid' | 'payment_sent' | 'waived'
export type PaymentMethod = 'cash' | 'card' | 'bank_transfer' | 'bit' | 'paybox' | 'other'

export interface Appointment {
  id: string
  payment_price: number | null
  payment_status: PaymentStatus
  payment_method: PaymentMethod | null
  payment_notes: string | null
  paid_at: string | null
  // ...
}
```

**Verification:**
```bash
npm run type-check
```

**Agent:** fullstack-frontend-specialist

---

### Phase 1E: Documentation & Cleanup (PENDING)

#### Step 19: Archive PayPlus Documentation
**Files to Archive:**
- Move PayPlus docs to `docs/payment/archive/payplus/`

**Commands:**
```bash
mkdir -p docs/payment/archive/payplus
mv docs/payment/*payplus* docs/payment/archive/payplus/ 2>/dev/null || true
```

**Create Archive README:**
```markdown
# PayPlus Integration Archive

This directory contains archived documentation for the PayPlus payment provider integration.

**Status:** Deprecated (removed in Phase 1)
**Reason:** Replaced with manual payment tracking system

PayPlus integration may be re-added in Phase 2+ if there's demand.

See [../PAYMENT_SYSTEM_ARCHITECTURE_V2.md](../PAYMENT_SYSTEM_ARCHITECTURE_V2.md) for current architecture.
```

**Agent:** Manual execution

---

#### Step 20: Update Main Documentation
**Files to Update:**
- `docs/PROJECT_OVERVIEW.md` - Update payment section
- `docs/backend/api/README.md` - Update payment API docs
- `README.md` - Update feature list if needed

**Changes:**
```markdown
## Payment Tracking

PazPaz supports manual payment tracking for appointments:
- Configure bank account details in Settings
- Set prices on appointments
- Manually mark appointments as paid (bank transfer, Bit, PayBox, cash, etc.)
- Track payment history and status

**Supported Payment Methods:**
- Bank Transfer
- Bit (Israeli mobile payment app)
- PayBox (Israeli payment service)
- Cash
- Card
- Other

**Phase 2 (Future):** Automated payment provider integrations (Bit, PayBox APIs)
```

**Agent:** Manual execution

---

### Phase 1F: Testing & Validation (PENDING)

#### Step 21: Run Full Backend Test Suite
**Commands:**
```bash
# Run all tests
env PYTHONPATH=src uv run pytest backend/tests/ -v

# Run payment-specific tests
env PYTHONPATH=src uv run pytest backend/tests/ -v -k payment

# Check test coverage
env PYTHONPATH=src uv run pytest backend/tests/ --cov=pazpaz --cov-report=html
```

**Success Criteria:**
- All tests pass
- No PayPlus references in test output
- Coverage >80% for payment-related code

**Agent:** backend-qa-specialist

---

#### Step 22: Run Frontend Tests
**Commands:**
```bash
# Type checking
npm run type-check

# Linting
npm run lint

# Unit tests (if configured)
npm run test:unit

# E2E tests (if configured)
npm run test:e2e
```

**Success Criteria:**
- No TypeScript errors
- No linting errors
- All tests pass

**Agent:** fullstack-frontend-specialist

---

#### Step 23: Manual QA Testing
**Test Scenarios:**

1. **Enable Manual Payments:**
   - Open Settings → Payments
   - Click "Enable Payment Tracking"
   - Choose "Manual Tracking"
   - Enter bank account details
   - Save
   - Verify details saved

2. **Configure Appointment Price:**
   - Create new appointment
   - Set payment price
   - Verify price saved

3. **Mark Appointment as Paid:**
   - Open appointment details
   - Click "Mark as Paid"
   - Select payment method (Bit)
   - Add notes "Paid via Bit app"
   - Verify status = Paid
   - Verify paid_at timestamp set

4. **Mark Appointment as Unpaid:**
   - Open paid appointment
   - Click "Mark as Unpaid"
   - Verify status = Not Paid
   - Verify paid_at cleared

5. **Filter by Payment Status:**
   - Go to appointments list
   - Filter by "Paid" status
   - Verify only paid appointments shown

6. **Copy Bank Details:**
   - Open Settings → Payments
   - Click "Copy to Clipboard"
   - Paste into text editor
   - Verify bank details copied correctly

7. **Disable Payments:**
   - Open Settings → Payments
   - Click "Disable Payment Tracking"
   - Confirm
   - Verify payment fields hidden on appointments

**Agent:** backend-qa-specialist + fullstack-frontend-specialist

---

#### Step 24: Performance Validation
**Metrics to Check:**
- Appointment list query performance (p95 <150ms)
- Payment status filtering performance
- Database indexes working correctly

**Commands:**
```bash
# Check query performance
env PYTHONPATH=src uv run python scripts/benchmark_appointments.py

# Verify indexes exist
psql -U pazpaz -h localhost -d pazpaz -c "\d appointments"
# Should show ix_appointments_workspace_payment_status index
```

**Success Criteria:**
- All appointment queries <150ms p95
- Payment filtering uses index (no full table scan)

**Agent:** backend-qa-specialist

---

#### Step 25: Security Audit
**Checks:**
- Bank account details stored as plain text (not sensitive like API keys)
- Payment notes don't contain PII that should be encrypted
- Workspace isolation enforced (can't access other workspace payments)
- Audit logging captures payment status changes

**Commands:**
```bash
# Check workspace isolation in tests
env PYTHONPATH=src uv run pytest backend/tests/ -v -k isolation

# Verify audit logging
env PYTHONPATH=src uv run pytest backend/tests/ -v -k audit
```

**Agent:** security-auditor

---

### Phase 1G: Deployment & Rollout (PENDING)

#### Step 26: Database Migration in Production
**Pre-Deploy Checklist:**
- [ ] Migration tested on staging database
- [ ] Backup production database
- [ ] Migration runs in <5 seconds (tested locally)
- [ ] Downgrade path tested

**Deployment Commands:**
```bash
# Backup production DB
pg_dump -U pazpaz -h prod-db pazpaz > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration
DATABASE_URL=<prod-url> env PYTHONPATH=src uv run alembic upgrade head

# Verify migration
DATABASE_URL=<prod-url> psql -c "\d workspaces"
DATABASE_URL=<prod-url> psql -c "\d appointments"
```

**Rollback Plan:**
```bash
# If issues found:
DATABASE_URL=<prod-url> env PYTHONPATH=src uv run alembic downgrade -1
```

**Agent:** devops-infrastructure-specialist

---

#### Step 27: Deploy Backend
**Steps:**
1. Merge PR to main branch
2. CI/CD builds Docker image
3. Deploy to staging
4. Smoke tests on staging
5. Deploy to production
6. Monitor logs and metrics

**Monitoring:**
- Check error rates in Sentry
- Monitor API response times
- Check database query performance

**Agent:** devops-infrastructure-specialist

---

#### Step 28: Deploy Frontend
**Steps:**
1. Build production bundle
2. Deploy to staging
3. Visual regression tests
4. Deploy to production
5. Monitor for errors

**Verification:**
- Open production app
- Enable manual payments
- Create appointment with payment
- Mark as paid
- Verify everything works

**Agent:** devops-infrastructure-specialist

---

#### Step 29: Feature Announcement
**Communication:**
1. In-app notification: "New: Manual Payment Tracking!"
2. Email to users: "Track Payments Easily"
3. Documentation update: "How to Use Payment Tracking"
4. Blog post (optional): "Simplifying Payment Management for Therapists"

**Content:**
```markdown
## New Feature: Manual Payment Tracking

Track payments from your clients without requiring third-party integrations!

**How it works:**
1. Go to Settings → Payments
2. Enable "Manual Tracking"
3. Enter your bank account details
4. Set prices on appointments
5. Mark appointments as paid when clients pay

**Supported Methods:**
- Bank Transfer
- Bit
- PayBox
- Cash
- Card

Get started today!
```

**Agent:** Manual execution (user/product team)

---

#### Step 30: Monitor & Iterate
**Metrics to Track:**
- % of workspaces enabling manual payments
- Average time to enable payments
- Number of appointments with payment tracking
- User feedback and support tickets

**Success Criteria (Week 1):**
- [ ] >50% of active workspaces enable manual payments
- [ ] <5 support tickets related to payments
- [ ] No critical bugs reported
- [ ] Average enable time <2 minutes

**Agent:** Product team + backend-qa-specialist

---

## File Checklist

### Files Modified ✅ (Completed)
- [x] `backend/alembic/versions/6679fc01412c_*.py` - Migration
- [x] `backend/src/pazpaz/models/workspace.py` - Workspace model
- [x] `backend/src/pazpaz/models/enums.py` - PaymentMethod enum
- [x] `backend/src/pazpaz/models/__init__.py` - Remove PaymentTransaction

### Files to Delete ❌ (Pending)
- [ ] `backend/src/pazpaz/models/payment_transaction.py` - ALREADY DELETED ✅
- [ ] `backend/src/pazpaz/payments/providers/payplus.py`
- [ ] `backend/tests/test_payments/test_payplus_provider.py`
- [ ] `backend/tests/test_payments/test_payment_integration.py`
- [ ] `backend/tests/test_payments/test_payment_endpoints.py`
- [ ] `backend/tests/test_payments/conftest.py`
- [ ] `backend/tests/migrations/test_payment_migration.py`
- [ ] `backend/tests/unit/models/test_payment_models.py`
- [ ] `backend/tests/integration/api/test_payment_config.py` (if PayPlus-specific)

### Files to Update 🔄 (Pending)
- [ ] `backend/src/pazpaz/services/payment_service.py` - Simplify to manual only
- [ ] `backend/src/pazpaz/api/payments.py` - Remove PayPlus endpoints
- [ ] `backend/src/pazpaz/api/appointments.py` - Add payment update endpoint
- [ ] `backend/src/pazpaz/api/workspaces.py` - Include payment config in response
- [ ] `backend/src/pazpaz/schemas/appointment.py` - Update PaymentMethod enum
- [ ] `backend/src/pazpaz/payments/factory.py` - Remove PayPlus registration
- [ ] `backend/src/pazpaz/payments/__init__.py` - Remove PayPlus exports
- [ ] `backend/tests/integration/api/test_appointment_payments.py` - Update tests
- [ ] `frontend/src/components/settings/PaymentSettings.vue` - Manual mode UI
- [ ] `frontend/src/components/appointments/PaymentTrackingCard.vue` - Payment tracking UI
- [ ] `frontend/src/composables/usePaymentSettings.ts` - Payment settings logic
- [ ] `frontend/src/composables/useAppointmentPayment.ts` - Appointment payment logic
- [ ] `frontend/src/types/workspace.ts` - Workspace type
- [ ] `frontend/src/types/appointment.ts` - Appointment payment types

### Files to Create ➕ (Pending)
- [ ] `backend/tests/integration/api/test_manual_payments.py` - Manual payment tests
- [ ] `docs/payment/archive/payplus/README.md` - Archive notice

### Files to Keep (No Changes) ✓
- `backend/src/pazpaz/payments/base.py` - Provider base class (for future)
- `backend/src/pazpaz/payments/exceptions.py` - Payment exceptions
- `backend/src/pazpaz/models/appointment.py` - Payment fields (already correct)

---

## Risk Assessment

### High Risk
- **Database Migration:** Could fail on large datasets
  - **Mitigation:** Test on staging with production-size data, have rollback plan
- **Data Loss:** Existing payment data could be lost
  - **Mitigation:** Migration keeps all appointment payment fields, only drops transaction table

### Medium Risk
- **API Breaking Changes:** Frontend could break if API changes incompatible
  - **Mitigation:** Deploy backend first, ensure backwards compatibility
- **User Confusion:** Users may not understand manual vs automated
  - **Mitigation:** Clear UI copy, in-app help tooltips

### Low Risk
- **Performance Degradation:** Payment queries could slow down
  - **Mitigation:** Indexes in place, performance tests before deploy

---

## Success Metrics

### Phase 1 Launch (Week 1)
- [ ] 0 critical bugs
- [ ] >50% workspace adoption
- [ ] <2 minute average enable time
- [ ] <5 support tickets

### Phase 1 Maturity (Month 1)
- [ ] >80% workspace adoption
- [ ] >1000 appointments with payment tracking
- [ ] Positive user feedback (NPS >40)
- [ ] <1% error rate on payment endpoints

---

## Next Steps After Phase 1

### Phase 2: Bit Integration (Future)
- Implement BitPaymentProvider
- Add Bit API credentials configuration
- Auto-generate Bit payment links
- Webhook for payment confirmations

### Phase 3: PayBox Integration (Future)
- Implement PayBoxPaymentProvider
- Add PayBox API credentials configuration
- Auto-generate PayBox payment links
- Webhook for payment confirmations

---

**Plan Status:** Ready for Implementation
**Estimated Time:** 2-3 weeks (backend + frontend + testing)
**Assigned Agents:** fullstack-backend-specialist, fullstack-frontend-specialist, backend-qa-specialist, security-auditor, devops-infrastructure-specialist
