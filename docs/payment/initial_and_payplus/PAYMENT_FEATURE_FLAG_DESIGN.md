# Payment Feature Flag Design: Opt-In Architecture

**Status:** Design Document
**Created:** October 30, 2025
**Purpose:** Define how payment functionality is conditionally enabled per workspace

---

## Overview

Payment functionality is **optional** and controlled by workspace settings. When enabled, it:
- Adds payment-related fields to UI (price input, payment status)
- Modifies appointment behavior (auto-send payment requests)
- Shows payment indicators on calendar
- Enables financial reporting

When disabled, PazPaz functions exactly as before (scheduling + documentation only).

---

## User Experience Flow

### **State 1: Payments Disabled (Default)**

**Settings Tab:**
```
┌─────────────────────────────────────────────┐
│ Settings > Payments                         │
├─────────────────────────────────────────────┤
│                                             │
│ 💳 Enable Payment Collection                │
│                                             │
│ [ Enable Payments ]  <-- Toggle button     │
│                                             │
│ Accept online payments from clients         │
│ after appointments complete.                │
│                                             │
└─────────────────────────────────────────────┘
```

**Appointment View (Payments Disabled):**
```
┌─────────────────────────────────────────────┐
│ Appointment Details                         │
├─────────────────────────────────────────────┤
│ Client: John Doe                            │
│ Date: Nov 5, 2025 10:00 AM                  │
│ Service: Massage Therapy                    │
│ Duration: 60 minutes                        │
│ Location: Main Office                       │
│                                             │
│ [ Mark as Complete ]                        │
│                                             │
│ NO PAYMENT FIELDS VISIBLE                   │
└─────────────────────────────────────────────┘
```

**Calendar View (Payments Disabled):**
```
10:00 AM  John Doe - Massage
          ✅ Completed
```

---

### **State 2: Payments Enabled (After Setup)**

**Settings Tab (Expanded):**
```
┌─────────────────────────────────────────────┐
│ Settings > Payments                         │
├─────────────────────────────────────────────┤
│                                             │
│ 💳 Payment Collection                       │
│ [✓] Payments Enabled                        │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Provider Configuration                  │ │
│ ├─────────────────────────────────────────┤ │
│ │ Provider: PayPlus ▾                     │ │
│ │                                         │ │
│ │ API Key: ••••••••••••                  │ │
│ │ Payment Page UID: abc123                │ │
│ │ Webhook Secret: ••••••••••••           │ │
│ │                                         │ │
│ │ [ Test Connection ]                     │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Business Details (for receipts)         │ │
│ ├─────────────────────────────────────────┤ │
│ │ Business Name: Dr. Sarah Cohen Clinic   │ │
│ │ Tax ID: 123456789                       │ │
│ │ [✓] VAT Registered (17%)                │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ Automation Settings                     │ │
│ ├─────────────────────────────────────────┤ │
│ │ [✓] Auto-send payment requests          │ │
│ │ Timing: Immediately ▾                   │ │
│ │   • Immediately after completion        │ │
│ │   • End of day (6 PM)                   │ │
│ │   • End of month                        │ │
│ │   • Manual only                         │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [ Save Changes ]  [ Disable Payments ]      │
└─────────────────────────────────────────────┘
```

**Appointment View (Payments Enabled):**
```
┌─────────────────────────────────────────────┐
│ Appointment Details                         │
├─────────────────────────────────────────────┤
│ Client: John Doe                            │
│ Date: Nov 5, 2025 10:00 AM                  │
│ Service: Massage Therapy                    │
│ Duration: 60 minutes                        │
│ Location: Main Office                       │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 💰 Payment                              │ │ <-- NEW SECTION
│ ├─────────────────────────────────────────┤ │
│ │ Price: ₪ [150.00]  (editable)           │ │
│ │ Status: 🟡 Unpaid                       │ │
│ │                                         │ │
│ │ [ Send Payment Request ]                │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [ Mark as Complete ]                        │
└─────────────────────────────────────────────┘
```

**After Appointment Completed (Auto-send enabled):**
```
┌─────────────────────────────────────────────┐
│ Appointment Details                         │
├─────────────────────────────────────────────┤
│ Client: John Doe                            │
│ Date: Nov 5, 2025 10:00 AM                  │
│ Service: Massage Therapy                    │
│ ✅ Completed (Nov 5, 10:55 AM)              │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 💰 Payment                              │ │
│ ├─────────────────────────────────────────┤ │
│ │ Price: ₪150.00                          │ │
│ │ Status: 🟡 Pending Payment              │ │
│ │                                         │ │
│ │ ✉️ Payment email sent to client         │ │
│ │ 📋 Payment link: payplus.co.il/xyz      │ │
│ │                                         │ │
│ │ [ Resend Email ]  [ Copy Link ]         │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**After Client Pays:**
```
┌─────────────────────────────────────────────┐
│ Appointment Details                         │
├─────────────────────────────────────────────┤
│ Client: John Doe                            │
│ Date: Nov 5, 2025 10:00 AM                  │
│ Service: Massage Therapy                    │
│ ✅ Completed (Nov 5, 10:55 AM)              │
│                                             │
│ ┌─────────────────────────────────────────┐ │
│ │ 💰 Payment                              │ │
│ ├─────────────────────────────────────────┤ │
│ │ Price: ₪150.00                          │ │
│ │ Status: ✅ Paid (Nov 5, 11:30 AM)       │ │
│ │                                         │ │
│ │ Method: Credit Card (PayPlus)           │ │
│ │ Transaction: #2025-001234               │ │
│ │                                         │ │
│ │ [ View Receipt ]  [ Download PDF ]      │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**Calendar View (Payments Enabled):**
```
10:00 AM  John Doe - Massage
          ✅ Completed  💵 Paid  <-- NEW INDICATOR
```

---

## Database Schema: Conditional Fields

### **Appointments Table: Enhanced with Payment Fields**

```sql
-- ALWAYS present (even when payments disabled)
CREATE TABLE appointments (
    id UUID PRIMARY KEY,
    workspace_id UUID REFERENCES workspaces(id),
    client_id UUID REFERENCES clients(id),
    service_id UUID REFERENCES services(id),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20),  -- 'scheduled', 'completed', 'cancelled'

    -- Payment fields (NULL when payments disabled)
    payment_price NUMERIC(10, 2),  -- NULL = no price set
    payment_status VARCHAR(20) DEFAULT 'unpaid',  -- 'unpaid', 'pending', 'paid', 'failed'
    payment_auto_send BOOLEAN DEFAULT NULL,  -- NULL = use workspace default

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Key Design Decision:**
- Payment fields are **always in the schema** but **nullable**
- When payments disabled: `payment_price = NULL`, `payment_status = 'unpaid'`
- When payments enabled: Therapist sets `payment_price`, status tracks payment

**Benefits:**
- No schema migration when enabling/disabling payments
- Easy to query "all appointments with payment enabled" (`WHERE payment_price IS NOT NULL`)
- Historical data preserved if therapist disables then re-enables

---

## Backend Logic: Feature Flag Checks

### **Payment Service: Workspace-Aware**

```python
# src/pazpaz/services/payment_service.py

class PaymentService:
    """Payment operations with feature flag checks."""

    async def can_send_payment_request(
        self,
        appointment: Appointment
    ) -> tuple[bool, str]:
        """
        Check if payment request can be sent.

        Returns:
            (can_send: bool, reason: str)
        """
        workspace = appointment.workspace

        # Check 1: Payments enabled for workspace
        if not workspace.payment_provider:
            return False, "Payments not enabled for workspace"

        # Check 2: Appointment has price set
        if appointment.payment_price is None:
            return False, "No price set for appointment"

        # Check 3: Appointment completed
        if appointment.status != "completed":
            return False, "Appointment not completed yet"

        # Check 4: Not already paid
        if appointment.payment_status == "paid":
            return False, "Already paid"

        # Check 5: Not already pending (avoid duplicate requests)
        if appointment.payment_status == "pending":
            return False, "Payment request already sent"

        return True, "Can send payment request"

    async def handle_appointment_completion(
        self,
        appointment: Appointment
    ) -> None:
        """
        Called when appointment marked as complete.

        Conditionally sends payment request based on workspace settings.
        """
        workspace = appointment.workspace

        # Feature flag check: Are payments enabled?
        if not workspace.payment_provider:
            # Payments disabled, do nothing
            return

        # Check if auto-send enabled
        if not workspace.payment_auto_send:
            # Manual payment requests only
            return

        # Check if can send payment request
        can_send, reason = await self.can_send_payment_request(appointment)
        if not can_send:
            logger.info(f"Cannot send payment request: {reason}")
            return

        # Send payment request
        await self.create_payment_request(
            appointment=appointment,
            customer_email=appointment.client.email
        )
```

### **API Endpoints: Conditional Responses**

```python
# src/pazpaz/api/v1/appointments.py

@router.get("/appointments/{appointment_id}")
async def get_appointment(
    appointment_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db)
):
    """Get appointment details with conditional payment fields."""

    appointment = await db.get(Appointment, appointment_id)
    if not appointment or appointment.workspace_id != workspace.id:
        raise HTTPException(404, "Appointment not found")

    response = {
        "id": appointment.id,
        "client": {...},
        "service": {...},
        "start_time": appointment.start_time,
        "status": appointment.status,
    }

    # Conditionally include payment fields
    if workspace.payment_provider:
        response["payment"] = {
            "price": appointment.payment_price,
            "status": appointment.payment_status,
            "can_send_request": await payment_service.can_send_payment_request(appointment),
            "transactions": await get_payment_transactions(appointment.id)
        }

    return response
```

---

## Frontend: Conditional Rendering

### **Vue Composable: Payment Feature Detection**

```typescript
// src/composables/usePayments.ts

import { computed } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'

export function usePayments() {
  const workspaceStore = useWorkspaceStore()

  const paymentsEnabled = computed(() => {
    return !!workspaceStore.current?.payment_provider
  })

  const canSendPaymentRequest = (appointment: Appointment) => {
    if (!paymentsEnabled.value) return false
    if (!appointment.payment_price) return false
    if (appointment.status !== 'completed') return false
    if (appointment.payment_status === 'paid') return false
    return true
  }

  const getPaymentStatusBadge = (status: string) => {
    const badges = {
      'unpaid': { label: 'Unpaid', class: 'badge-warning', icon: '🟡' },
      'pending': { label: 'Pending', class: 'badge-info', icon: '🔄' },
      'paid': { label: 'Paid', class: 'badge-success', icon: '✅' },
      'failed': { label: 'Failed', class: 'badge-error', icon: '❌' },
    }
    return badges[status] || badges['unpaid']
  }

  return {
    paymentsEnabled,
    canSendPaymentRequest,
    getPaymentStatusBadge
  }
}
```

### **Appointment Detail Component**

```vue
<!-- src/components/appointments/AppointmentDetail.vue -->
<template>
  <div class="appointment-detail">
    <h2>Appointment Details</h2>

    <div class="basic-info">
      <p><strong>Client:</strong> {{ appointment.client.name }}</p>
      <p><strong>Date:</strong> {{ formatDate(appointment.start_time) }}</p>
      <p><strong>Service:</strong> {{ appointment.service.name }}</p>
      <p><strong>Status:</strong> {{ appointment.status }}</p>
    </div>

    <!-- Payment Section: Conditionally rendered -->
    <div v-if="paymentsEnabled" class="payment-section">
      <h3>💰 Payment</h3>

      <!-- Price Input (editable before completion) -->
      <div v-if="appointment.status !== 'completed'" class="price-input">
        <label>Price:</label>
        <input
          v-model="appointment.payment_price"
          type="number"
          step="0.01"
          placeholder="150.00"
          @change="updatePrice"
        />
        <span>{{ workspace.currency || 'ILS' }}</span>
      </div>

      <!-- Payment Status (after completion) -->
      <div v-else class="payment-status">
        <span>Price: {{ formatCurrency(appointment.payment_price) }}</span>
        <span
          :class="['badge', paymentBadge.class]"
        >
          {{ paymentBadge.icon }} {{ paymentBadge.label }}
        </span>
      </div>

      <!-- Payment Actions -->
      <div class="payment-actions">
        <!-- Send Payment Request -->
        <button
          v-if="canSendPaymentRequest(appointment)"
          @click="sendPaymentRequest"
          :disabled="sending"
        >
          {{ sending ? 'Sending...' : 'Send Payment Request' }}
        </button>

        <!-- Payment Link (if pending) -->
        <div v-if="appointment.payment_status === 'pending'" class="payment-link">
          <p>✉️ Payment email sent to client</p>
          <input
            :value="paymentLink"
            readonly
            @click="copyToClipboard"
            class="copy-link"
          />
          <button @click="resendEmail">Resend Email</button>
        </div>

        <!-- Receipt (if paid) -->
        <div v-if="appointment.payment_status === 'paid'" class="receipt-actions">
          <button @click="viewReceipt">View Receipt</button>
          <button @click="downloadReceipt">Download PDF</button>
        </div>
      </div>
    </div>

    <!-- Completion Button -->
    <div class="actions">
      <button
        v-if="appointment.status !== 'completed'"
        @click="markAsComplete"
        :disabled="paymentsEnabled && !appointment.payment_price"
      >
        Mark as Complete
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { usePayments } from '@/composables/usePayments'
import { useWorkspaceStore } from '@/stores/workspace'
import { usePaymentStore } from '@/stores/payment'
import type { Appointment } from '@/types'

const props = defineProps<{
  appointment: Appointment
}>()

const workspaceStore = useWorkspaceStore()
const paymentStore = usePaymentStore()
const { paymentsEnabled, canSendPaymentRequest, getPaymentStatusBadge } = usePayments()

const sending = ref(false)

const workspace = computed(() => workspaceStore.current)
const paymentBadge = computed(() => getPaymentStatusBadge(props.appointment.payment_status))
const paymentLink = computed(() => {
  // Get latest payment transaction link
  return paymentStore.getLatestLink(props.appointment.id)
})

async function updatePrice() {
  // Save updated price to backend
  await api.updateAppointment(props.appointment.id, {
    payment_price: props.appointment.payment_price
  })
}

async function sendPaymentRequest() {
  sending.value = true
  try {
    await paymentStore.createPaymentRequest({
      appointment_id: props.appointment.id,
      customer_email: props.appointment.client.email
    })
    // Update appointment status to 'pending'
    props.appointment.payment_status = 'pending'
  } finally {
    sending.value = false
  }
}

async function markAsComplete() {
  await api.updateAppointment(props.appointment.id, {
    status: 'completed'
  })

  // If payments enabled and auto-send, backend will send payment request
  if (paymentsEnabled.value && workspace.value?.payment_auto_send) {
    // Show toast: "Payment request will be sent automatically"
  }
}

function copyToClipboard() {
  navigator.clipboard.writeText(paymentLink.value)
}

async function resendEmail() {
  await paymentStore.resendPaymentEmail(props.appointment.id)
}

async function viewReceipt() {
  // Open receipt in new tab
  const receipt = await paymentStore.getReceipt(props.appointment.id)
  window.open(receipt.pdf_url, '_blank')
}

async function downloadReceipt() {
  const receipt = await paymentStore.getReceipt(props.appointment.id)
  window.location.href = receipt.pdf_url + '?download=true'
}
</script>

<style scoped>
.payment-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
  background: #f9fafb;
}

.payment-status .badge {
  margin-left: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.badge-success {
  background: #d1fae5;
  color: #065f46;
}

.badge-warning {
  background: #fef3c7;
  color: #92400e;
}

.badge-info {
  background: #dbeafe;
  color: #1e40af;
}

.copy-link {
  width: 100%;
  padding: 8px;
  font-family: monospace;
  cursor: pointer;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 4px;
}
</style>
```

### **Calendar Component: Payment Indicators**

```vue
<!-- src/components/calendar/CalendarEvent.vue -->
<template>
  <div :class="['calendar-event', statusClass]">
    <div class="event-time">{{ formatTime(event.start_time) }}</div>
    <div class="event-title">
      {{ event.client.name }} - {{ event.service.name }}
    </div>
    <div class="event-status">
      <span v-if="event.status === 'completed'">✅ Completed</span>
      <!-- Payment indicator (only if payments enabled) -->
      <span v-if="paymentsEnabled && event.payment_status === 'paid'">
        💵 Paid
      </span>
      <span v-else-if="paymentsEnabled && event.payment_status === 'pending'">
        🔄 Pending
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePayments } from '@/composables/usePayments'

const props = defineProps<{
  event: CalendarEvent
}>()

const { paymentsEnabled } = usePayments()

const statusClass = computed(() => {
  const classes = ['calendar-event']
  if (props.event.status === 'completed') classes.push('completed')
  if (paymentsEnabled.value && props.event.payment_status === 'paid') {
    classes.push('paid')
  }
  return classes.join(' ')
})
</script>

<style scoped>
.calendar-event {
  padding: 8px;
  border-radius: 4px;
  border-left: 4px solid #3b82f6;
}

.calendar-event.completed {
  border-left-color: #10b981;
}

.calendar-event.paid {
  background: #d1fae5;
}
</style>
```

---

## Migration Path: Enabling Payments

### **Step-by-Step Onboarding Flow**

```
User clicks "Enable Payments" in Settings
         ↓
Step 1: Choose Provider
  [ ] PayPlus (Israel)
  [ ] Meshulam (Israel)
  [ ] Stripe (US)
         ↓
Step 2: Enter API Credentials
  API Key: [________]
  Payment Page UID: [________]
  Webhook Secret: [________]
  [ Test Connection ]
         ↓
Step 3: Business Details
  Business Name: [________]
  Tax ID: [________]
  [ ] VAT Registered?
         ↓
Step 4: Automation Settings
  [ ] Auto-send payment requests?
  Timing: [Immediately ▾]
         ↓
Step 5: Set Default Prices (Optional)
  Services:
  - Massage Therapy: ₪150
  - Consultation: ₪100

  (Can override per-appointment)
         ↓
✅ Payments Enabled!
   Payment fields now visible in appointments.
```

### **Backend: Onboarding API**

```python
@router.post("/workspaces/{workspace_id}/enable-payments")
async def enable_payments(
    workspace_id: uuid.UUID,
    config: PaymentConfigRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable payments for workspace.

    Steps:
    1. Validate provider credentials (test API call)
    2. Encrypt and store credentials
    3. Set workspace.payment_provider
    4. Return success
    """

    # Step 1: Validate credentials
    provider = get_payment_provider_class(config.provider)
    test_client = provider(config=config.credentials)

    try:
        await test_client.test_connection()
    except PaymentProviderError as e:
        raise HTTPException(400, f"Invalid credentials: {e}")

    # Step 2: Encrypt credentials
    encrypted_config = encrypt_json(config.credentials)

    # Step 3: Update workspace
    workspace.payment_provider = config.provider
    workspace.payment_provider_config = encrypted_config
    workspace.business_name = config.business_name
    workspace.tax_id = config.tax_id
    workspace.vat_registered = config.vat_registered
    workspace.payment_auto_send = config.auto_send
    workspace.payment_send_timing = config.send_timing

    await db.commit()

    return {"status": "success", "message": "Payments enabled"}
```

---

## Data Consistency: Disabling Payments

### **What Happens When Therapist Disables Payments?**

**Option 1: Soft Disable (Recommended)**
- Set `workspace.payment_provider = NULL`
- Keep all historical payment data intact
- Hide payment UI fields
- Keep `payment_transactions` table (historical record)

**Benefits:**
- Can re-enable payments without data loss
- Historical revenue data preserved
- Audit trail intact

**Option 2: Hard Disable (Not Recommended)**
- Delete payment provider config
- Optionally delete all payment transactions
- Lose historical data

**Recommendation:** Use **Option 1** (soft disable)

```python
@router.post("/workspaces/{workspace_id}/disable-payments")
async def disable_payments(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable payments for workspace (soft disable).

    - Sets payment_provider to NULL
    - Keeps historical payment data
    - Hides payment UI
    """

    # Soft disable
    workspace.payment_provider = None
    workspace.payment_auto_send = False

    # Keep payment_provider_config in case they re-enable
    # (Or set to NULL if you want to force re-configuration)

    await db.commit()

    return {"status": "success", "message": "Payments disabled"}
```

---

## Implementation Checklist

### **Phase 1: Feature Flag Infrastructure**

- [ ] Add `payment_price`, `payment_status` to `appointments` table (nullable)
- [ ] Add payment config fields to `workspaces` table
- [ ] Create `usePayments()` composable (frontend)
- [ ] Update appointment detail component with conditional payment section
- [ ] Update calendar view with payment indicators
- [ ] Build "Enable Payments" onboarding flow in Settings

### **Phase 2: Payment Provider Integration**

- [ ] Implement payment provider abstraction (already designed)
- [ ] PayPlus provider implementation
- [ ] Webhook handling with signature verification
- [ ] Auto-send payment request on appointment completion (if enabled)
- [ ] Email template for payment requests

### **Phase 3: UI Polish**

- [ ] Payment status badges (Unpaid, Pending, Paid)
- [ ] Copy payment link to clipboard
- [ ] Resend payment email button
- [ ] Price input with currency symbol
- [ ] Validation: Prevent completing appointment without price (if payments enabled)

---

## Summary

**Key Design Decisions:**

1. **Optional Feature:** Payments are completely opt-in via workspace settings
2. **Conditional Fields:** Payment fields exist in DB schema but are nullable (no migration needed when enabling/disabling)
3. **UI Injection:** Payment UI sections only render when `workspace.payment_provider` is set
4. **Auto-Send Logic:** When appointment completes, backend checks if auto-send enabled and conditionally sends payment request
5. **Visual Indicators:** Calendar shows payment status (💵 Paid, 🔄 Pending) only when payments enabled
6. **Historical Preservation:** Disabling payments keeps historical data intact (soft disable)

**User Experience:**
- Therapist without payments: PazPaz works exactly as before (simple scheduling + docs)
- Therapist with payments: Appointments gain price field, payment status tracking, auto-email, and calendar indicators

This design keeps the system simple for non-payment users while providing full payment functionality for those who need it.
