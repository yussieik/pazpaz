# Payment Features Guide

**Status:** Phase 0 Complete (Foundation)
**Created:** October 30, 2025
**Last Updated:** October 30, 2025

---

## Overview

This guide explains how the payment feature flag architecture works in PazPaz and how to use it when implementing payment-related functionality.

**Key Principle:** Payments are **opt-in**. By default, all workspaces have payments **disabled**. Payments are enabled per-workspace when `payment_provider` is set.

---

## Feature Flag Architecture

### Design Philosophy

PazPaz uses an **opt-in feature flag system** where:
1. **Payments disabled by default** - All new workspaces have `payment_provider = NULL`
2. **Zero-downtime deployments** - All payment fields are nullable or have safe defaults
3. **Workspace-scoped** - Each workspace controls its own payment settings
4. **Graceful degradation** - System works normally when payments are disabled

### Database-Driven Feature Flags

The feature flag state is stored directly in the database, not in configuration files or environment variables:

```python
# Feature flag is stored in the workspaces table
payment_provider: VARCHAR(50) NULL  # NULL = disabled, non-NULL = enabled
```

**Why database-driven?**
- Each workspace can independently enable/disable payments
- No code deploys required to enable payments for a therapist
- Configuration persists across deployments
- Easy to audit who has payments enabled

---

## Checking if Payments Are Enabled

### Method 1: Using `Workspace.payments_enabled` Property (Recommended)

The `Workspace` model has a helper property to check if payments are enabled:

```python
from pazpaz.models import Workspace

# In an API endpoint or service function
async def some_endpoint(
    workspace: Workspace = Depends(get_current_workspace),
):
    if workspace.payments_enabled:
        # Payments are enabled - show payment UI, allow payment requests
        pass
    else:
        # Payments are disabled - hide payment features
        pass
```

**How it works:**
```python
# src/pazpaz/models/workspace.py
@property
def payments_enabled(self) -> bool:
    """Check if payments are enabled for this workspace."""
    return self.payment_provider is not None
```

### Method 2: Using `PaymentFeatureChecker` Utility (For Complex Logic)

For more complex checks involving appointments, use the `PaymentFeatureChecker` utility class:

```python
from pazpaz.utils.payment_features import PaymentFeatureChecker

# Check if workspace has payments enabled
is_enabled = PaymentFeatureChecker.is_enabled(workspace)

# Check if payment request can be sent for an appointment
can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

if can_send:
    # Send payment request
    pass
else:
    # Log reason: "Payments not enabled for workspace"
    logger.info("cannot_send_payment", reason=reason)
```

---

## Payment Feature Checker Reference

### `PaymentFeatureChecker.is_enabled(workspace)`

**Purpose:** Check if payments are enabled at the workspace level

**Parameters:**
- `workspace: Workspace` - The workspace to check

**Returns:** `bool` - True if payments enabled, False otherwise

**Example:**
```python
from pazpaz.models import Workspace
from pazpaz.utils.payment_features import PaymentFeatureChecker

workspace = await get_workspace_by_id(workspace_id)

if PaymentFeatureChecker.is_enabled(workspace):
    # Show payment settings UI
    # Allow creating payment requests
    # Display revenue reports
    pass
else:
    # Hide all payment features
    # Return 404 on payment endpoints
    pass
```

---

### `PaymentFeatureChecker.can_send_payment_request(appointment)`

**Purpose:** Check if a payment request can be sent for a specific appointment

**Parameters:**
- `appointment: Appointment` - The appointment to check (must have `workspace` relationship loaded)

**Returns:** `tuple[bool, str]` - `(can_send, reason)`
- `can_send: bool` - True if payment request can be sent
- `reason: str` - Human-readable reason for success or failure

**Validation Rules (all must pass):**
1. Payments enabled for workspace (`workspace.payment_provider` is not NULL)
2. Appointment has a price (`appointment.payment_price` is not NULL)
3. Appointment completed (`appointment.status == "attended"`)
4. Not already paid (`appointment.payment_status != "paid"`)
5. Payment request not already sent (`appointment.payment_status != "pending"`)

**Example:**
```python
from pazpaz.models import Appointment
from pazpaz.utils.payment_features import PaymentFeatureChecker
from sqlalchemy.orm import selectinload

# Load appointment with workspace relationship
result = await db.execute(
    select(Appointment)
    .options(selectinload(Appointment.workspace))
    .where(Appointment.id == appointment_id)
)
appointment = result.scalar_one()

# Check if payment request can be sent
can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

if can_send:
    # Create payment request
    payment_link = await create_payment_request(appointment)
    logger.info("payment_request_sent", appointment_id=appointment.id)
else:
    logger.info(
        "payment_request_not_sent",
        appointment_id=appointment.id,
        reason=reason,
    )
```

**Possible Return Values:**
- `(True, "Can send payment request")` - All checks passed
- `(False, "Payments not enabled for workspace")` - No payment provider configured
- `(False, "No price set for appointment")` - `payment_price` is NULL
- `(False, "Appointment not completed yet")` - Status is not "attended"
- `(False, "Already paid")` - Already processed payment
- `(False, "Payment request already sent")` - Already in pending state

---

## Auto-Send Payment Requests

### Configuration Hierarchy

Payment requests can be automatically sent after appointment completion. The configuration follows a two-level hierarchy:

1. **Workspace-level default** (`workspace.payment_auto_send`)
2. **Appointment-level override** (`appointment.payment_auto_send`)

### Decision Logic

```python
# Determine if auto-send is enabled for this appointment
def should_auto_send(appointment: Appointment) -> bool:
    """
    Check if payment request should be automatically sent.

    Appointment-level setting overrides workspace-level setting.
    """
    workspace = appointment.workspace

    # Use appointment-level override if set
    if appointment.payment_auto_send is not None:
        return appointment.payment_auto_send

    # Fall back to workspace-level default
    return workspace.payment_auto_send
```

### Send Timing Options

The `payment_send_timing` field controls **when** payment requests are sent:

| Value | Description |
|-------|-------------|
| `immediately` | Send payment request immediately after appointment marked "attended" |
| `end_of_day` | Batch send at end of business day (e.g., 11:59 PM) |
| `end_of_month` | Batch send at end of month (e.g., last day of month) |
| `manual` | Never auto-send; therapist manually sends payment requests |

**Example Implementation:**
```python
from pazpaz.models import Appointment, Workspace
from pazpaz.utils.payment_features import PaymentFeatureChecker

async def handle_appointment_completion(appointment: Appointment):
    """Called when appointment status changes to 'attended'."""

    workspace = appointment.workspace

    # Check if we can send payment request
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    if not can_send:
        logger.info("payment_request_not_applicable", reason=reason)
        return

    # Check if auto-send is enabled
    auto_send_enabled = (
        appointment.payment_auto_send
        if appointment.payment_auto_send is not None
        else workspace.payment_auto_send
    )

    if not auto_send_enabled:
        logger.info("payment_auto_send_disabled")
        return

    # Check send timing
    if workspace.payment_send_timing == "immediately":
        # Send now
        await send_payment_request(appointment)
    elif workspace.payment_send_timing == "end_of_day":
        # Queue for end of day batch
        await queue_payment_for_end_of_day(appointment)
    elif workspace.payment_send_timing == "end_of_month":
        # Queue for end of month batch
        await queue_payment_for_end_of_month(appointment)
    else:  # manual
        # Do nothing - therapist will manually send
        logger.info("payment_send_timing_manual")
```

---

## Frontend Integration Pattern

### Step 1: Check Payment Config on App Load

```typescript
// src/composables/usePayments.ts
import { ref } from 'vue'
import { api } from '@/api/client'

export function usePayments() {
  const paymentsEnabled = ref(false)
  const paymentProvider = ref<string | null>(null)
  const loading = ref(true)

  async function loadPaymentConfig() {
    try {
      const config = await api.payments.getConfig()
      paymentsEnabled.value = config.enabled
      paymentProvider.value = config.provider
    } catch (error) {
      console.error('Failed to load payment config:', error)
      paymentsEnabled.value = false
    } finally {
      loading.value = false
    }
  }

  return {
    paymentsEnabled,
    paymentProvider,
    loading,
    loadPaymentConfig,
  }
}
```

### Step 2: Conditionally Render Payment UI

```vue
<!-- src/components/AppointmentDetail.vue -->
<template>
  <div class="appointment-detail">
    <h1>Appointment Details</h1>

    <!-- Other appointment info -->

    <!-- Only show payment section if payments enabled -->
    <div v-if="paymentsEnabled" class="payment-section">
      <h2>Payment</h2>
      <p>Price: {{ appointment.payment_price }} ILS</p>
      <p>Status: {{ appointment.payment_status }}</p>

      <button
        v-if="appointment.payment_status === 'unpaid'"
        @click="sendPaymentRequest"
      >
        Send Payment Request
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePayments } from '@/composables/usePayments'

const { paymentsEnabled, loadPaymentConfig } = usePayments()

onMounted(async () => {
  await loadPaymentConfig()
})
</script>
```

### Step 3: API Client Usage

```typescript
// Generated from OpenAPI spec
import { ApiClient } from '@/api/generated'

const client = new ApiClient({ baseURL: '/api/v1' })

// Get payment config for current workspace
const config = await client.payments.getConfig()
// Returns: { enabled: boolean, provider: string | null, auto_send: boolean, ... }

if (config.enabled) {
  // Show payment features
}
```

---

## Backend API Pattern

### Checking Payments in Endpoints

All payment-related endpoints should check if payments are enabled:

```python
from fastapi import APIRouter, Depends, HTTPException
from pazpaz.dependencies import get_current_user, get_db
from pazpaz.models import User

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

@router.post("/send-request/{appointment_id}")
async def send_payment_request(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send payment request for appointment."""

    # Load appointment with workspace
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.workspace))
        .where(
            Appointment.id == appointment_id,
            Appointment.workspace_id == current_user.workspace_id,
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Check if payments enabled
    if not appointment.workspace.payments_enabled:
        raise HTTPException(
            status_code=400,
            detail="Payments not enabled for workspace",
        )

    # Check if payment request can be sent
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    if not can_send:
        raise HTTPException(status_code=400, detail=reason)

    # Send payment request (Phase 1 implementation)
    payment_link = await create_payment_link(appointment)

    return {"payment_link": payment_link}
```

---

## Testing Payment Features

### Unit Test Example

```python
# tests/unit/utils/test_payment_features.py
import pytest
from decimal import Decimal
from pazpaz.models import Workspace, Appointment
from pazpaz.utils.payment_features import PaymentFeatureChecker

async def test_is_enabled_returns_false_when_no_provider(db_session):
    """Payments should be disabled when payment_provider is NULL."""
    workspace = Workspace(name="Test Clinic")
    db_session.add(workspace)
    await db_session.commit()

    assert PaymentFeatureChecker.is_enabled(workspace) is False

async def test_is_enabled_returns_true_when_provider_set(db_session):
    """Payments should be enabled when payment_provider is set."""
    workspace = Workspace(name="Test Clinic", payment_provider="payplus")
    db_session.add(workspace)
    await db_session.commit()

    assert PaymentFeatureChecker.is_enabled(workspace) is True

async def test_can_send_payment_request_all_conditions_met(db_session):
    """Payment request can be sent when all conditions are met."""
    workspace = Workspace(name="Test Clinic", payment_provider="payplus")
    # ... create appointment with price, status=attended, payment_status=unpaid

    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    assert can_send is True
    assert reason == "Can send payment request"
```

### Integration Test Example

```python
# tests/integration/api/test_payment_endpoints.py
import pytest
from httpx import AsyncClient

async def test_get_config_returns_disabled_by_default(
    async_client: AsyncClient,
    test_user: User,
):
    """Payment config should show disabled for new workspaces."""
    response = await async_client.get(
        "/api/v1/payments/config",
        cookies={"access_token": test_user.token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["provider"] is None

async def test_get_config_returns_enabled_when_provider_set(
    async_client: AsyncClient,
    test_user: User,
    db_session,
):
    """Payment config should show enabled when provider is set."""
    # Enable payments for workspace
    test_user.workspace.payment_provider = "payplus"
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/payments/config",
        cookies={"access_token": test_user.token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["provider"] == "payplus"
```

---

## Common Use Cases

### Use Case 1: Conditionally Show Payment UI

```python
# Backend: Include payments_enabled in appointment response
from pydantic import BaseModel

class AppointmentResponse(BaseModel):
    id: uuid.UUID
    scheduled_start: datetime
    # ... other fields
    payment_price: Decimal | None
    payment_status: str
    # Computed field
    workspace_payments_enabled: bool

@router.get("/appointments/{id}")
async def get_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    # ... load appointment

    return AppointmentResponse(
        **appointment.dict(),
        workspace_payments_enabled=appointment.workspace.payments_enabled,
    )
```

### Use Case 2: Automatically Send Payment Requests

```python
# In appointment update endpoint
@router.patch("/appointments/{id}")
async def update_appointment(
    appointment_id: uuid.UUID,
    data: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ... load and update appointment

    # Check if status changed to "attended"
    if data.status == AppointmentStatus.ATTENDED:
        # Check if payment request should be sent
        can_send, reason = PaymentFeatureChecker.can_send_payment_request(
            appointment
        )

        if can_send:
            # Check if auto-send enabled
            auto_send = (
                appointment.payment_auto_send
                if appointment.payment_auto_send is not None
                else appointment.workspace.payment_auto_send
            )

            if auto_send and appointment.workspace.payment_send_timing == "immediately":
                # Send payment request (Phase 1)
                await send_payment_request(appointment)
```

### Use Case 3: Enable Payments for Workspace

```python
# In workspace settings endpoint
@router.patch("/workspaces/{id}/payment-settings")
async def update_payment_settings(
    workspace_id: uuid.UUID,
    settings: PaymentSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable or update payment settings for workspace."""

    # Verify user owns workspace
    if current_user.workspace_id != workspace_id:
        raise HTTPException(status_code=403)

    workspace = current_user.workspace

    # Enable payments
    workspace.payment_provider = settings.provider  # "payplus", "meshulam", etc.
    workspace.payment_provider_config = encrypt_config(settings.api_keys)
    workspace.payment_auto_send = settings.auto_send
    workspace.payment_send_timing = settings.send_timing

    await db.commit()

    logger.info(
        "payment_settings_updated",
        workspace_id=workspace_id,
        provider=settings.provider,
    )

    return {"enabled": workspace.payments_enabled}
```

---

## Security Considerations

### 1. Never Expose Encrypted Config

**NEVER** return `payment_provider_config` in API responses:

```python
# ❌ INCORRECT - Exposes encrypted API keys
class PaymentConfigResponse(BaseModel):
    enabled: bool
    provider: str | None
    provider_config: dict  # ❌ Security risk!

# ✅ CORRECT - Never expose config
class PaymentConfigResponse(BaseModel):
    enabled: bool
    provider: str | None
    auto_send: bool
    # No provider_config field
```

### 2. Always Verify Workspace Ownership

```python
# ✅ CORRECT - Verify user owns workspace
@router.post("/payments/send-request/{appointment_id}")
async def send_payment_request(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    appointment = await get_appointment(appointment_id)

    # Verify appointment belongs to user's workspace
    if appointment.workspace_id != current_user.workspace_id:
        raise HTTPException(status_code=404)  # Don't reveal existence
```

### 3. Encrypt Payment Provider Config

Use existing PHI encryption infrastructure:

```python
from pazpaz.utils.encryption import encrypt_field, decrypt_field

# Encrypt before storing
encrypted_config = encrypt_field(
    json.dumps({"api_key": "...", "secret": "..."}),
    ENCRYPTION_MASTER_KEY,
)

workspace.payment_provider_config = {"data": encrypted_config}

# Decrypt when needed
decrypted_config = decrypt_field(
    workspace.payment_provider_config["data"],
    ENCRYPTION_MASTER_KEY,
)
api_key = json.loads(decrypted_config)["api_key"]
```

---

## Future Features (Phase 1+)

The feature flag architecture makes it easy to add new payment features:

### Example: Subscription Billing

```python
# Add to workspaces table
ALTER TABLE workspaces ADD COLUMN subscription_billing_enabled BOOLEAN DEFAULT false;

# Add to Workspace model
subscription_billing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

# Check feature flag
if workspace.subscription_billing_enabled:
    # Show subscription plans UI
    pass
```

### Example: Payment Installments

```python
# Add to appointments table
ALTER TABLE appointments ADD COLUMN payment_installments INTEGER;

# Update PaymentFeatureChecker
@staticmethod
def supports_installments(workspace: Workspace) -> bool:
    """Check if workspace supports payment installments."""
    # Check if provider supports installments
    return workspace.payment_provider in ["payplus", "stripe"]
```

---

## Troubleshooting

### Problem: "Payments not enabled for workspace"

**Cause:** `workspace.payment_provider` is NULL

**Solution:** Set payment provider in workspace settings:
```sql
UPDATE workspaces
SET payment_provider = 'payplus'
WHERE id = '<workspace_id>';
```

### Problem: "No price set for appointment"

**Cause:** `appointment.payment_price` is NULL

**Solution:** Set price before marking appointment as attended:
```python
appointment.payment_price = Decimal("150.00")
await db.commit()
```

### Problem: Payment config endpoint returns 401

**Cause:** Missing or invalid JWT token

**Solution:** Ensure user is authenticated:
```typescript
// Include credentials in API calls
const config = await fetch('/api/v1/payments/config', {
  credentials: 'include',  // Send cookies
})
```

---

## References

- [Payment Schema Documentation](database/PAYMENT_SCHEMA.md)
- [Payment Integration Plan](../PAYMENT_INTEGRATION_PLAN.md)
- [Phase 0 Foundation](../PAYMENT_PHASE_0_FOUNDATION.md)
- [PaymentFeatureChecker Source Code](../../backend/src/pazpaz/utils/payment_features.py)
- [Payment API Endpoint](../../backend/src/pazpaz/api/payments.py)
